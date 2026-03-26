use axum::{
    extract::ws::{Message, WebSocket, WebSocketUpgrade},
    extract::{Query, Multipart},
    response::{IntoResponse, Json},
    routing::{get, post},
    Router,
};
use serde::Serialize;
use std::collections::HashMap;
use std::net::{Ipv4Addr, SocketAddrV4};
use std::sync::Arc;
use tokio::net::UdpSocket;
use tokio::sync::{broadcast, RwLock};
use tower_http::cors::CorsLayer;
use tower_http::services::ServeDir;
use tracing::{info, warn};

// --- Soluna protocol constants ---
const MULTICAST_ADDR: Ipv4Addr = Ipv4Addr::new(239, 42, 42, 1);
const MULTICAST_PORT: u16 = 4242;
const MAGIC: [u8; 2] = [0x53, 0x4C]; // "SL"
const HEADER_SIZE: usize = 19;

const FLAG_ADPCM: u8 = 0x01;
#[allow(dead_code)]
const FLAG_HEARTBEAT: u8 = 0x04;
#[allow(dead_code)]
const FLAG_CHIRP: u8 = 0x08;
const FLAG_OTA: u8 = 0x20;
const OTA_CHANNEL_HASH: u32 = 0xFFFFFFFF;
const OTA_CHUNK_SIZE: usize = 1024;

// --- FNV-1a hash ---
fn fnv1a(data: &[u8]) -> u32 {
    let mut h: u32 = 0x811c9dc5;
    for &b in data {
        h ^= b as u32;
        h = h.wrapping_mul(0x01000193);
    }
    h
}

// --- Device tracking ---
#[derive(Clone, Debug, Serialize)]
struct DeviceInfo {
    hash: u32,
    channel_hash: u32,
    channel_name: String,
    last_seen_ms: u64,
    last_seq: u32,
    flags: u8,
    audio_level: f32, // 0.0-1.0 RMS
    peer_count: usize,
    #[serde(skip)]
    peers: Vec<u32>,
}

#[derive(Clone, Debug, Serialize)]
struct DashboardState {
    devices: Vec<DeviceInfo>,
    total_packets: u64,
    uptime_secs: u64,
}

// --- Channel name reverse lookup ---
const KNOWN_CHANNELS: &[&str] = &["soluna", "voice", "music", "ambient"];

fn channel_name_from_hash(hash: u32) -> String {
    for &name in KNOWN_CHANNELS {
        if fnv1a(name.as_bytes()) == hash {
            return name.to_string();
        }
    }
    format!("0x{:08x}", hash)
}

// --- Shared state ---
struct AppState {
    devices: RwLock<HashMap<u32, DeviceInfo>>,
    packet_count: RwLock<u64>,
    start_time: std::time::Instant,
    // Broadcast channel for UDP→WS fan-out
    udp_tx: broadcast::Sender<Vec<u8>>,
    // UDP socket for WS→UDP forwarding
    udp_socket: UdpSocket,
}


#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let static_dir = std::env::var("STATIC_DIR").unwrap_or_else(|_| "static".to_string());
    let bind_addr = std::env::var("BIND_ADDR").unwrap_or_else(|_| "0.0.0.0:8080".to_string());

    // UDP multicast socket
    let udp_socket = setup_udp_socket().await;
    let udp_recv = setup_udp_recv_socket().await;

    let (udp_tx, _) = broadcast::channel::<Vec<u8>>(1024);

    let state = Arc::new(AppState {
        devices: RwLock::new(HashMap::new()),
        packet_count: RwLock::new(0),
        start_time: std::time::Instant::now(),
        udp_tx: udp_tx.clone(),
        udp_socket,
    });

    // Spawn UDP receiver task
    let state_clone = state.clone();
    tokio::spawn(async move {
        udp_receive_loop(udp_recv, state_clone).await;
    });

    // Spawn device cleanup task
    let state_clone = state.clone();
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
            let now = now_ms();
            let mut devices = state_clone.devices.write().await;
            devices.retain(|_, d| now - d.last_seen_ms < 15_000);
        }
    });

    let app = Router::new()
        .route("/ws", get(ws_handler))
        .route("/api/devices", get(api_devices))
        .route("/api/status", get(api_status))
        .route("/api/ota", post(api_ota_upload))
        .nest_service("/", ServeDir::new(&static_dir).append_index_html_on_directories(true))
        .layer(CorsLayer::very_permissive())
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(&bind_addr).await.unwrap();
    info!("Soluna dashboard listening on {}", bind_addr);
    axum::serve(listener, app).await.unwrap();
}

async fn setup_udp_socket() -> UdpSocket {
    let socket = UdpSocket::bind("0.0.0.0:0").await.unwrap();
    info!("UDP send socket bound to {}", socket.local_addr().unwrap());
    socket
}

async fn setup_udp_recv_socket() -> UdpSocket {
    let sock = socket2::Socket::new(
        socket2::Domain::IPV4,
        socket2::Type::DGRAM,
        Some(socket2::Protocol::UDP),
    )
    .expect("Failed to create UDP socket");

    sock.set_reuse_address(true).ok();
    sock.set_nonblocking(true).ok();

    let addr: std::net::SocketAddr = SocketAddrV4::new(Ipv4Addr::UNSPECIFIED, MULTICAST_PORT).into();
    sock.bind(&addr.into()).expect("Failed to bind UDP");

    sock.join_multicast_v4(&MULTICAST_ADDR, &Ipv4Addr::UNSPECIFIED)
        .expect("Failed to join multicast");

    let std_socket: std::net::UdpSocket = sock.into();
    let socket = UdpSocket::from_std(std_socket).expect("Failed to convert to tokio socket");
    info!("UDP multicast receiver on 239.42.42.1:{}", MULTICAST_PORT);
    socket
}

async fn udp_receive_loop(socket: UdpSocket, state: Arc<AppState>) {
    let mut buf = [0u8; 2048];
    loop {
        match socket.recv_from(&mut buf).await {
            Ok((len, _addr)) => {
                if len < HEADER_SIZE {
                    continue;
                }
                let packet = &buf[..len];
                if packet[0] != MAGIC[0] || packet[1] != MAGIC[1] {
                    continue;
                }

                // Parse header
                let device_hash = u32::from_le_bytes([packet[2], packet[3], packet[4], packet[5]]);
                let seq = u32::from_le_bytes([packet[6], packet[7], packet[8], packet[9]]);
                let channel_hash =
                    u32::from_le_bytes([packet[10], packet[11], packet[12], packet[13]]);
                let flags = packet[18];

                // Compute audio level from ADPCM payload (approximate)
                let audio_level = if flags & FLAG_ADPCM != 0 && len > HEADER_SIZE {
                    compute_adpcm_level(&packet[HEADER_SIZE..len])
                } else {
                    0.0
                };

                // Update device tracking
                {
                    let mut devices = state.devices.write().await;
                    let entry = devices.entry(device_hash).or_insert_with(|| DeviceInfo {
                        hash: device_hash,
                        channel_hash,
                        channel_name: channel_name_from_hash(channel_hash),
                        last_seen_ms: now_ms(),
                        last_seq: 0,
                        flags: 0,
                        audio_level: 0.0,
                        peer_count: 0,
                        peers: Vec::new(),
                    });
                    entry.last_seen_ms = now_ms();
                    entry.last_seq = seq;
                    entry.flags = flags;
                    entry.channel_hash = channel_hash;
                    entry.channel_name = channel_name_from_hash(channel_hash);
                    // Smooth audio level
                    entry.audio_level = entry.audio_level * 0.7 + audio_level * 0.3;

                    // Track peers per channel
                    let ch = channel_hash;
                    let peers_on_channel: Vec<u32> = devices
                        .values()
                        .filter(|d| d.channel_hash == ch)
                        .map(|d| d.hash)
                        .collect();
                    let peer_count = peers_on_channel.len();
                    if let Some(dev) = devices.get_mut(&device_hash) {
                        dev.peer_count = peer_count;
                        dev.peers = peers_on_channel;
                    }
                }

                // Increment packet counter
                {
                    let mut count = state.packet_count.write().await;
                    *count += 1;
                }

                // Broadcast to WebSocket clients
                let _ = state.udp_tx.send(buf[..len].to_vec());
            }
            Err(e) => {
                if e.kind() != std::io::ErrorKind::WouldBlock {
                    warn!("UDP recv error: {}", e);
                }
                tokio::time::sleep(tokio::time::Duration::from_millis(1)).await;
            }
        }
    }
}

/// Approximate audio level from ADPCM nibbles (fast heuristic)
fn compute_adpcm_level(adpcm: &[u8]) -> f32 {
    if adpcm.is_empty() {
        return 0.0;
    }
    let mut sum: u64 = 0;
    for &b in adpcm {
        let lo = (b & 0x0F) as u64;
        let hi = (b >> 4) as u64;
        // Larger nibble values = larger audio changes
        sum += lo * lo + hi * hi;
    }
    let rms = ((sum as f64) / (adpcm.len() as f64 * 2.0)).sqrt();
    // Normalize: max nibble value is 15, so max rms ~15
    (rms / 10.0).min(1.0) as f32
}

fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64
}

// --- HTTP handlers ---

async fn api_devices(
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
) -> Json<Vec<DeviceInfo>> {
    let devices = state.devices.read().await;
    Json(devices.values().cloned().collect())
}

async fn api_status(
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
) -> Json<DashboardState> {
    let devices = state.devices.read().await;
    let count = *state.packet_count.read().await;
    Json(DashboardState {
        devices: devices.values().cloned().collect(),
        total_packets: count,
        uptime_secs: state.start_time.elapsed().as_secs(),
    })
}

// --- WebSocket handler ---

async fn ws_handler(
    ws: WebSocketUpgrade,
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
    Query(params): Query<HashMap<String, String>>,
) -> impl IntoResponse {
    let channel = params.get("channel").cloned().unwrap_or_else(|| "soluna".to_string());
    ws.on_upgrade(move |socket| handle_ws(socket, state, channel))
}

async fn handle_ws(mut socket: WebSocket, state: Arc<AppState>, channel: String) {
    let channel_hash = fnv1a(channel.as_bytes());
    let device_hash = rand_device_hash();

    info!(
        "WS client connected: device=0x{:08x} channel={}",
        device_hash, channel
    );

    let mut udp_rx = state.udp_tx.subscribe();
    let dest = SocketAddrV4::new(MULTICAST_ADDR, MULTICAST_PORT);

    // Send initial status
    let status = serde_json::json!({
        "type": "connected",
        "device_hash": device_hash,
        "channel": channel,
        "channel_hash": channel_hash,
    });
    let _ = socket
        .send(Message::Text(status.to_string().into()))
        .await;

    loop {
        tokio::select! {
            // WS → UDP: client sends audio
            msg = socket.recv() => {
                match msg {
                    Some(Ok(Message::Binary(data))) => {
                        if data.len() >= HEADER_SIZE && data[0] == MAGIC[0] && data[1] == MAGIC[1] {
                            // Valid Soluna packet — forward to UDP multicast
                            let _ = state.udp_socket.send_to(&data, dest).await;
                        }
                    }
                    Some(Ok(Message::Text(text))) => {
                        // JSON control messages
                        if let Ok(cmd) = serde_json::from_str::<serde_json::Value>(&*text) {
                            if cmd.get("type").and_then(|t| t.as_str()) == Some("ping") {
                                let pong = serde_json::json!({"type": "pong"});
                                let _ = socket.send(Message::Text(pong.to_string().into())).await;
                            }
                        }
                    }
                    Some(Ok(Message::Close(_))) | None => {
                        info!("WS client disconnected: 0x{:08x}", device_hash);
                        break;
                    }
                    _ => {}
                }
            }
            // UDP → WS: relay multicast packets to this client
            Ok(packet) = udp_rx.recv() => {
                if packet.len() >= HEADER_SIZE {
                    let pkt_ch = u32::from_le_bytes([packet[10], packet[11], packet[12], packet[13]]);
                    let sender = u32::from_le_bytes([packet[2], packet[3], packet[4], packet[5]]);
                    // Filter: same channel, not from self
                    if pkt_ch == channel_hash && sender != device_hash {
                        if socket.send(Message::Binary(packet.into())).await.is_err() {
                            break;
                        }
                    }
                }
            }
        }
    }
}

fn rand_device_hash() -> u32 {
    use std::time::SystemTime;
    let seed = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap()
        .as_nanos() as u64;
    // Simple xorshift
    let mut x = seed;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    x as u32
}

// =====================================================
// OTA ファームウェア配信 (サーバー → 全デバイス)
// =====================================================

/// POST /api/ota — ファームウェアバイナリをアップロード→マルチキャスト配信
async fn api_ota_upload(
    axum::extract::State(state): axum::extract::State<Arc<AppState>>,
    mut multipart: Multipart,
) -> impl IntoResponse {
    // ファイルを受け取る
    let mut firmware: Vec<u8> = Vec::new();
    while let Ok(Some(field)) = multipart.next_field().await {
        let name = field.name().unwrap_or("").to_string();
        if name == "firmware" {
            if let Ok(data) = field.bytes().await {
                firmware = data.to_vec();
            }
        }
    }

    if firmware.is_empty() {
        return Json(serde_json::json!({"error": "No firmware file"}));
    }

    let total_chunks = (firmware.len() + OTA_CHUNK_SIZE - 1) / OTA_CHUNK_SIZE;
    let fw_hash = fnv1a(&firmware);
    let fw_size = firmware.len();
    let sender_hash = 0xDEADBEEFu32; // サーバーID

    info!("OTA: uploading {} bytes ({} chunks, hash={:#x})", fw_size, total_chunks, fw_hash);

    // バックグラウンドでカルーセル配信 (5ループ)
    let udp_tx = state.udp_tx.clone();
    tokio::spawn(async move {
        let sock = UdpSocket::bind("0.0.0.0:0").await.unwrap();
        let dest: std::net::SocketAddr = SocketAddrV4::new(MULTICAST_ADDR, MULTICAST_PORT).into();

        for loop_num in 1..=5 {
            info!("OTA broadcast loop {}/5", loop_num);

            for i in 0..total_chunks {
                let offset = i * OTA_CHUNK_SIZE;
                let end = (offset + OTA_CHUNK_SIZE).min(firmware.len());
                let chunk = &firmware[offset..end];

                // パケット構築
                let mut packet = vec![0u8; 31 + chunk.len()];
                // 19B Solunaヘッダ
                packet[0..2].copy_from_slice(&MAGIC);
                packet[2..6].copy_from_slice(&sender_hash.to_le_bytes());
                packet[6..10].copy_from_slice(&(i as u32).to_le_bytes());
                packet[10..14].copy_from_slice(&OTA_CHANNEL_HASH.to_le_bytes());
                packet[14..18].copy_from_slice(&(total_chunks as u32).to_le_bytes());
                packet[18] = FLAG_OTA;
                // OTA拡張ヘッダ
                packet[19..23].copy_from_slice(&(i as u32).to_le_bytes());
                packet[23..27].copy_from_slice(&(total_chunks as u32).to_le_bytes());
                packet[27..31].copy_from_slice(&fw_hash.to_le_bytes());
                packet[31..].copy_from_slice(chunk);

                // UDP マルチキャスト送信
                let _ = sock.send_to(&packet, dest).await;

                // WebSocket経由でもWANデバイスに配信
                let _ = udp_tx.send(packet);

                // 2ms間隔 (帯域制御)
                tokio::time::sleep(tokio::time::Duration::from_millis(2)).await;
            }

            if loop_num < 5 {
                tokio::time::sleep(tokio::time::Duration::from_secs(2)).await;
            }
        }

        info!("OTA broadcast complete: {} chunks × 5 loops", total_chunks);
    });

    Json(serde_json::json!({
        "status": "broadcasting",
        "size": fw_size,
        "chunks": total_chunks,
        "hash": format!("{:#010x}", fw_hash),
        "loops": 5
    }))
}
