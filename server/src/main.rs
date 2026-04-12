/// koe.live — static site + OTA firmware endpoint + WebRTC signaling + Soluna relay + Orders
///
/// Routes:
///   GET  /                               → static HTML (docs/)
///   GET  /app                            → docs/app.html (P2P web app)
///   GET  /health                         → {"status":"ok"}
///   GET  /api/devices                    → JSON list of recently seen Soluna devices
///   GET  /api/v1/device/firmware         → 204 (up-to-date) | 200 (binary)
///   POST /api/v1/device/firmware/upload  → upload new firmware (admin token)
///   POST /api/v1/checkout                → Create Stripe Checkout Session
///   POST /api/v1/stripe/webhook          → Stripe webhook (checkout.session.completed)
///   GET  /order/success                  → Order success page
///   GET  /admin/orders                   → Admin order list (Bearer token)
///   PUT  /admin/orders/:id               → Update order status (Bearer token)
///   GET  /admin/orders/export            → CSV export (Bearer token)
///   GET  /ws/signal                      → WebRTC signaling (room-based broadcast)
///   GET  /ws/soluna                      → Soluna protocol relay (WS ↔ UDP multicast bridge)

use axum::{
    Router,
    extract::{DefaultBodyLimit, Path, Query, State, WebSocketUpgrade},
    extract::ws::{Message, WebSocket},
    http::{StatusCode, HeaderMap},
    response::IntoResponse,
    routing::{get, post, put},
};
use dashmap::DashMap;
use futures_util::{SinkExt, StreamExt};
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::net::{Ipv4Addr, SocketAddrV4, UdpSocket};
use std::sync::{Arc, Mutex};
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::broadcast;
use tower_http::services::ServeDir;
use tracing::{info, warn};
use wtransport::{Endpoint, ServerConfig, Identity};
use ring::digest;

const DATA_DIR: &str = "/data";

// Soluna multicast group
const MCAST_ADDR: Ipv4Addr = Ipv4Addr::new(239, 42, 42, 1);
const MCAST_PORT: u16 = 4242;

// ---- Shared state ----

/// One broadcast channel per room for signaling messages.
type RoomMap = Arc<DashMap<String, broadcast::Sender<String>>>;

/// Peer info tracked per room.
#[derive(Clone, Serialize)]
struct PeerInfo {
    id:   String,
    name: String,
}

/// peer_id → PeerInfo, grouped by room_id.
/// Key: "{room_id}::{peer_id}"
type PeerRegistry = Arc<DashMap<String, PeerInfo>>;

/// Track recently seen Soluna devices (device_hash_hex → DeviceInfo).
#[derive(Clone, Serialize)]
struct DeviceInfo {
    hash: String,
    channel_name: String,
    audio_level: f32,
    last_seen: u64,
}

type DeviceRegistry = Arc<DashMap<String, DeviceInfo>>;

#[derive(Clone)]
struct AppState {
    rooms: RoomMap,
    peers: PeerRegistry,
    devices: DeviceRegistry,
    /// Broadcast channel for Soluna WS relay (per-channel).
    soluna_rooms: Arc<DashMap<String, broadcast::Sender<Vec<u8>>>>,
    /// SQLite database for leaderboard + room persistence
    db: Arc<Mutex<Connection>>,
    /// WebTransport certificate hash (base64, for client serverCertificateHashes)
    wt_cert_hash: Arc<String>,
}

// ---- Signal message types ----
#[derive(Debug, Deserialize)]
struct WsSignalParams {
    room: String,
    peer: String,
    name: String,
    #[serde(default)]
    mode: String, // "" (default/speaker) or "listener"
}

/// Global connection counter
static TOTAL_CONNECTIONS: std::sync::atomic::AtomicUsize = std::sync::atomic::AtomicUsize::new(0);

#[derive(Debug, Deserialize)]
struct WsSolunaParams {
    channel: String,
}

// ---- Main ----

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("koe_server=info".parse().unwrap()),
        )
        .init();

    let static_dir = std::env::var("STATIC_DIR").unwrap_or_else(|_| "/app/docs".to_string());
    let port = std::env::var("PORT").unwrap_or_else(|_| "8080".to_string());

    // Init SQLite DB
    let db_path = format!("{}/koe.db", DATA_DIR);
    std::fs::create_dir_all(DATA_DIR).ok();
    let db = Connection::open(&db_path).expect("Failed to open SQLite DB");
    db.execute_batch("
        CREATE TABLE IF NOT EXISTS leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            name TEXT NOT NULL,
            score INTEGER NOT NULL,
            track TEXT NOT NULL,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS rooms (
            name TEXT PRIMARY KEY,
            playlist TEXT DEFAULT '[]',
            last_active INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        );
        CREATE INDEX IF NOT EXISTS idx_lb_room ON leaderboard(room, score DESC);
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stripe_session_id TEXT UNIQUE,
            stripe_payment_intent TEXT,
            customer_email TEXT NOT NULL,
            customer_name TEXT,
            shipping_name TEXT,
            shipping_address TEXT,
            shipping_city TEXT,
            shipping_state TEXT,
            shipping_zip TEXT,
            shipping_country TEXT DEFAULT 'JP',
            phone TEXT,
            product TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            amount_jpy INTEGER,
            status TEXT DEFAULT 'paid',
            tracking_number TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
        CREATE INDEX IF NOT EXISTS idx_orders_email ON orders(customer_email);
        CREATE TABLE IF NOT EXISTS koe_sessions (
            id TEXT PRIMARY KEY,
            room TEXT NOT NULL DEFAULT 'living_room',
            label TEXT,
            start_time INTEGER NOT NULL DEFAULT (strftime('%s','now')),
            end_time INTEGER,
            duration_secs INTEGER,
            tracks INTEGER DEFAULT 6,
            instruments TEXT DEFAULT '[]',
            is_silence INTEGER DEFAULT 0,
            source TEXT DEFAULT 'auto',
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS stone_devices (
            id TEXT PRIMARY KEY,
            sku TEXT NOT NULL DEFAULT 'stone',
            serial TEXT NOT NULL,
            room TEXT DEFAULT 'living_room',
            last_touched INTEGER,
            session_count INTEGER DEFAULT 0,
            tap_count INTEGER DEFAULT 0,
            created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        );
        CREATE TABLE IF NOT EXISTS stone_taps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stone_id TEXT NOT NULL,
            song_title TEXT,
            song_artist TEXT,
            tapped_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
        );
        INSERT OR IGNORE INTO stone_devices(id,sku,serial,room) VALUES
            ('ST-001','stone','KOE-001','living_room'),
            ('ST-002','stone','KOE-002','bookshelf'),
            ('ST-003','stone','KOE-003','side_table'),
            ('ST-004','stone','KOE-004','kitchen'),
            ('ST-005','stone','KOE-005','beachfront_bedroom'),
            ('ST-006','stone','KOE-006','guest_room'),
            ('MN-001','mini','KOE-M01','window'),
            ('MN-002','mini','KOE-M02','music_room'),
            ('MN-003','mini','KOE-M03','beach_deck'),
            ('MN-004','mini','KOE-M04','pool_deck'),
            ('PK-001','pick','KOE-P01','music_room'),
            ('PK-002','pick','KOE-P02','music_room'),
            ('PD-001','pendant','KOE-D01','beachfront_bedroom'),
            ('PD-002','pendant','KOE-D02','entry');
        INSERT OR IGNORE INTO koe_sessions(id,room,label,start_time,end_time,duration_secs,tracks,instruments,source)
        VALUES('seed_june28','living_room','Before you arrived',1751090460,1751091780,1320,2,'[\"acoustic_guitar\"]','seed');
    ").expect("Failed to init DB");
    info!("SQLite DB initialized at {}", db_path);

    // Generate self-signed cert for WebTransport
    let identity = Identity::self_signed(["koe.live", "localhost"]).expect("Failed to create WT identity");
    let cert_der = identity.certificate_chain()
        .as_slice().first()
        .expect("no cert").der().to_vec();
    let cert_hash_raw = digest::digest(&digest::SHA256, &cert_der);
    let cert_hash_b64 = base64::Engine::encode(
        &base64::engine::general_purpose::STANDARD, cert_hash_raw.as_ref());
    info!("WebTransport cert hash: {}", cert_hash_b64);

    let state = AppState {
        rooms: Arc::new(DashMap::new()),
        peers: Arc::new(DashMap::new()),
        devices: Arc::new(DashMap::new()),
        soluna_rooms: Arc::new(DashMap::new()),
        db: Arc::new(Mutex::new(db)),
        wt_cert_hash: Arc::new(cert_hash_b64),
    };

    // Spawn WebTransport QUIC server on port 4443
    spawn_webtransport(identity, state.soluna_rooms.clone());

    // Spawn UDP→WS bridge for Soluna multicast
    spawn_udp_bridge(state.devices.clone(), state.soluna_rooms.clone());

    // Spawn cleanup task — remove stale rooms, devices, soluna channels every 60s
    {
        let st = state.clone();
        tokio::spawn(async move {
            loop {
                tokio::time::sleep(tokio::time::Duration::from_secs(60)).await;
                let now = unix_now();
                // Remove devices not seen in 120s
                st.devices.retain(|_, d| now - d.last_seen < 120);
                // Remove empty rooms (no subscribers)
                st.rooms.retain(|_, tx| tx.receiver_count() > 0);
                // Remove empty soluna channels
                st.soluna_rooms.retain(|_, tx| tx.receiver_count() > 0);
            }
        });
    }

    let app = Router::new()
        .route("/health",                          get(handle_health))
        .route("/app",                             get(handle_app))
        .route("/pro",                             get(handle_page_pro))
        .route("/busker",                          get(handle_page_busker))
        .route("/classroom",                       get(handle_page_classroom))
        .route("/moji",                            get(handle_page_moji))
        .route("/soluna-os",                       get(handle_page_soluna_os))
        .route("/stadium",                         get(handle_page_stadium))
        .route("/order",                           get(handle_page_order))
        .route("/gallery",                         get(handle_page_gallery))
        .route("/business",                        get(handle_page_business))
        .route("/orchestra",                       get(handle_page_orchestra))
        .route("/design",                          get(handle_page_design))
        .route("/compare",                         get(handle_page_compare))
        .route("/crowd",                           get(handle_page_crowd))
        .route("/story",                           get(handle_page_story))
        .route("/3d",                              get(handle_page_3d))
        .route("/start",                           get(handle_page_start))
        .route("/family",                          get(handle_page_family))
        .route("/sessions",                        get(handle_page_sessions))
        .route("/sessions/hawaii-2026-07",         get(handle_page_sessions_hawaii))
        .route("/room",                            get(handle_page_room))
        .route("/archive",                         get(handle_page_archive))
        .route("/key",                             get(handle_page_key))
        .route("/api/devices",                     get(handle_devices))
        .route("/api/v1/device/firmware",          get(handle_firmware_check))
        .route(
            "/api/v1/device/firmware/upload",
            post(handle_firmware_upload)
                .layer(DefaultBodyLimit::max(8 * 1024 * 1024)),
        )
        .route("/api/v1/checkout",                post(handle_checkout))
        .route("/api/v1/stripe/webhook",          post(handle_stripe_webhook))
        .route("/order/success",                   get(handle_order_success))
        .route("/admin/orders",                    get(handle_admin_orders))
        .route("/admin/orders/export",             get(handle_admin_orders_export))
        .route("/admin/orders/:id",                put(handle_admin_order_update))
        .route("/admin",                           get(handle_admin_page))
        .route("/api/translate",  post(handle_translate))
        .route("/api/summarize",  post(handle_summarize))
        .route("/api/transcribe", post(handle_transcribe).layer(DefaultBodyLimit::max(25 * 1024 * 1024)))
        .route("/api/features",   get(handle_features))
        .route("/api/v1/ai/vocal-remove",    post(handle_ai_proxy))
        .route("/api/v1/ai/voice-clone",     post(handle_ai_proxy))
        .route("/api/v1/ai/harmonize",       post(handle_ai_proxy))
        .route("/api/v1/ai/translate-voice",  post(handle_ai_proxy))
        .route("/api/v1/ai/score-detail",    post(handle_ai_proxy))
        .route("/api/v1/ai/generate-music",  post(handle_ai_proxy))
        .route("/api/stats",              get(handle_stats))
        .route("/api/wt-hash",            get(handle_wt_hash))
        .route("/api/leaderboard/:room", get(handle_leaderboard_get).post(handle_leaderboard_post))
        .route("/api/rooms",            get(handle_rooms_list))
        .route("/api/rooms/:room/playlist", get(handle_playlist_get).post(handle_playlist_save))
        .route("/stone/:id",                       get(handle_stone_page))
        .route("/api/v1/stone/:id",                get(handle_stone_api))
        .route("/api/v1/stone/:id/tap",            post(handle_stone_tap))
        .route("/api/v1/sessions",                 get(handle_sessions_list).post(handle_session_create))
        .route("/api/v1/sessions/timeline",        get(handle_sessions_timeline))
        .route("/ws/signal",  get(handle_ws_signal))
        .route("/ws/soluna",  get(handle_ws_soluna))
        .fallback_service(ServeDir::new(&static_dir).append_index_html_on_directories(true))
        .with_state(state);

    let addr = format!("0.0.0.0:{}", port);
    info!("koe-server listening on {}", addr);
    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

// ---- Health ----

async fn handle_health() -> impl IntoResponse {
    (StatusCode::OK, r#"{"status":"ok"}"#)
}

// ---- App HTML ----

async fn handle_app() -> impl IntoResponse { serve_html("app.html").await }
async fn handle_page_pro() -> impl IntoResponse { serve_html("pro.html").await }
async fn handle_page_busker() -> impl IntoResponse { serve_html("busker.html").await }
async fn handle_page_classroom() -> impl IntoResponse { serve_html("classroom.html").await }
async fn handle_page_moji() -> impl IntoResponse { serve_html("moji.html").await }
async fn handle_page_soluna_os() -> impl IntoResponse { serve_html("soluna-os.html").await }
async fn handle_page_stadium() -> impl IntoResponse { serve_html("stadium.html").await }
async fn handle_page_order() -> impl IntoResponse { serve_html("order.html").await }
async fn handle_page_gallery() -> impl IntoResponse { serve_html("gallery.html").await }
async fn handle_page_business() -> impl IntoResponse { serve_html("business.html").await }
async fn handle_page_orchestra() -> impl IntoResponse { serve_html("orchestra.html").await }
async fn handle_page_design() -> impl IntoResponse { serve_html("design.html").await }
async fn handle_page_compare() -> impl IntoResponse { serve_html("compare.html").await }
async fn handle_page_crowd() -> impl IntoResponse { serve_html("crowd.html").await }
async fn handle_page_story() -> impl IntoResponse { serve_html("story.html").await }
async fn handle_page_3d() -> impl IntoResponse { serve_html("3d.html").await }
async fn handle_page_start() -> impl IntoResponse { serve_html("start.html").await }
async fn handle_page_family() -> impl IntoResponse { serve_html("family.html").await }
async fn handle_page_sessions() -> impl IntoResponse { serve_html("sessions.html").await }
async fn handle_page_sessions_hawaii() -> impl IntoResponse { serve_html("sessions-hawaii.html").await }
async fn handle_page_room() -> impl IntoResponse { serve_html("room.html").await }
async fn handle_page_archive() -> impl IntoResponse { serve_html("archive.html").await }
async fn handle_page_key() -> impl IntoResponse { serve_html("key.html").await }

async fn serve_html(filename: &str) -> axum::response::Response {
    let static_dir = std::env::var("STATIC_DIR").unwrap_or_else(|_| "/app/docs".to_string());
    let path = format!("{}/{}", static_dir, filename);
    match std::fs::read_to_string(&path) {
        Ok(html) => (
            StatusCode::OK,
            [("content-type", "text/html; charset=utf-8")],
            html,
        )
            .into_response(),
        Err(_) => (StatusCode::NOT_FOUND, format!("{} not found", filename)).into_response(),
    }
}

// ---- Devices API ----

async fn handle_devices(State(state): State<AppState>) -> impl IntoResponse {
    let now = unix_now();
    let list: Vec<Value> = state
        .devices
        .iter()
        .filter(|e| now - e.value().last_seen < 60)
        .map(|e| {
            let d = e.value();
            json!({
                "id":           d.hash.clone(),
                "hash":         d.hash.clone(),
                "channel_name": d.channel_name.clone(),
                "audio_level":  d.audio_level,
                "last_seen":    d.last_seen,
            })
        })
        .collect();

    (
        StatusCode::OK,
        [("content-type", "application/json")],
        serde_json::to_string(&list).unwrap_or_else(|_| "[]".into()),
    )
}

// ---- WebSocket: Signaling ----

async fn handle_ws_signal(
    ws: WebSocketUpgrade,
    Query(params): Query<WsSignalParams>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| {
        handle_signal_socket(socket, params, state)
    })
}

async fn handle_signal_socket(
    socket: WebSocket,
    params: WsSignalParams,
    state: AppState,
) {
    let room_id = params.room.clone();
    let peer_id = params.peer.clone();
    let is_listener = params.mode == "listener";
    let peer_name = if is_listener {
        format!("{}[L]", params.name)
    } else {
        params.name.clone()
    };

    // Track total connections
    TOTAL_CONNECTIONS.fetch_add(1, std::sync::atomic::Ordering::Relaxed);

    // Get or create room broadcast channel (larger buffer for scale)
    let tx = state
        .rooms
        .entry(room_id.clone())
        .or_insert_with(|| {
            let (tx, _) = broadcast::channel(1024);
            tx
        })
        .clone();
    let mut rx = tx.subscribe();

    info!("signal: {} ({}) joined room '{}' [{}]", peer_id, peer_name, room_id,
        if is_listener { "listener" } else { "speaker" });

    let (mut ws_tx, mut ws_rx) = socket.split();

    // Register this peer
    let peer_key = format!("{}::{}", room_id, peer_id);
    state.peers.insert(peer_key.clone(), PeerInfo { id: peer_id.clone(), name: peer_name.clone() });

    // Send existing peers list to newcomer
    let existing: Vec<Value> = state.peers
        .iter()
        .filter(|e| e.key().starts_with(&format!("{}::", room_id)) && e.value().id != peer_id)
        .map(|e| json!({ "id": e.value().id, "name": e.value().name }))
        .collect();

    let peers_msg = json!({
        "type": "peers",
        "from": "server",
        "data": { "peers": existing }
    });
    let _ = ws_tx.send(Message::Text(peers_msg.to_string())).await;

    // Count peers in this room
    let room_total = state.peers.iter()
        .filter(|e| e.key().starts_with(&format!("{}::", room_id)))
        .count();

    // Announce join to others in room (with room count)
    let join_msg = json!({
        "type": "joined",
        "from": peer_id,
        "data": { "name": peer_name, "room_count": room_total, "is_listener": is_listener }
    });
    let _ = tx.send(join_msg.to_string());

    // Forward incoming WS messages to broadcast channel,
    // and forward broadcast channel messages to this WS.
    loop {
        tokio::select! {
            // WS → broadcast
            msg = ws_rx.next() => {
                match msg {
                    Some(Ok(Message::Text(text))) => {
                        // Parse to validate, then rebroadcast
                        if let Ok(val) = serde_json::from_str::<Value>(&text) {
                            // SECURITY: always overwrite "from" to prevent spoofing
                            let mut v = val;
                            v["from"] = json!(peer_id);
                            let _ = tx.send(v.to_string());
                        }
                    }
                    Some(Ok(Message::Ping(p))) => {
                        let _ = ws_tx.send(Message::Pong(p)).await;
                    }
                    None | Some(Ok(Message::Close(_))) | Some(Err(_)) => break,
                    _ => {}
                }
            }
            // broadcast → WS (skip own messages)
            bcast = rx.recv() => {
                match bcast {
                    Ok(text) => {
                        // Skip messages from self
                        if let Ok(val) = serde_json::from_str::<Value>(&text) {
                            if val.get("from").and_then(|f| f.as_str()) == Some(&peer_id) {
                                continue;
                            }
                            // Listeners skip heavy WebRTC signaling (offer/answer/ice)
                            if is_listener {
                                let msg_type = val.get("type").and_then(|t| t.as_str()).unwrap_or("");
                                if matches!(msg_type, "offer" | "answer" | "ice") {
                                    continue;
                                }
                            }
                        }
                        if ws_tx.send(Message::Text(text)).await.is_err() { break; }
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                    Err(broadcast::error::RecvError::Lagged(_)) => continue,
                }
            }
        }
    }

    // Unregister peer + decrement counter
    state.peers.remove(&peer_key);
    TOTAL_CONNECTIONS.fetch_sub(1, std::sync::atomic::Ordering::Relaxed);

    // Announce leave
    let leave_msg = json!({
        "type": "left",
        "from": peer_id,
        "data": { "name": peer_name }
    });
    let _ = tx.send(leave_msg.to_string());
    info!("signal: {} left room '{}'", peer_id, room_id);
}

// ---- WebSocket: Soluna Relay ----

async fn handle_ws_soluna(
    ws: WebSocketUpgrade,
    Query(params): Query<WsSolunaParams>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_soluna_socket(socket, params, state))
}

async fn handle_soluna_socket(
    socket: WebSocket,
    params: WsSolunaParams,
    state: AppState,
) {
    let channel = params.channel.clone();

    let tx = state
        .soluna_rooms
        .entry(channel.clone())
        .or_insert_with(|| {
            let (tx, _) = broadcast::channel(512);
            tx
        })
        .clone();
    let mut rx = tx.subscribe();

    info!("soluna-ws: client joined channel '{}'", channel);

    let (mut ws_tx, mut ws_rx) = socket.split();

    loop {
        tokio::select! {
            // WS → broadcast (web client sends audio/control)
            msg = ws_rx.next() => {
                match msg {
                    Some(Ok(Message::Binary(data))) => {
                        let _ = tx.send(data.to_vec());
                    }
                    Some(Ok(Message::Ping(p))) => {
                        let _ = ws_tx.send(Message::Pong(p)).await;
                    }
                    None | Some(Ok(Message::Close(_))) | Some(Err(_)) => break,
                    _ => {}
                }
            }
            // broadcast (UDP/other WS) → this WS
            bcast = rx.recv() => {
                match bcast {
                    Ok(data) => {
                        if ws_tx.send(Message::Binary(data)).await.is_err() { break; }
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                    Err(broadcast::error::RecvError::Lagged(_)) => continue,
                }
            }
        }
    }

    info!("soluna-ws: client left channel '{}'", channel);
}

// ---- UDP → WS bridge (Soluna multicast listener) ----

fn spawn_udp_bridge(
    devices: DeviceRegistry,
    soluna_rooms: Arc<DashMap<String, broadcast::Sender<Vec<u8>>>>,
) {
    tokio::spawn(async move {
        // Try to bind to multicast. On Fly.io this may fail gracefully.
        let socket = match UdpSocket::bind(SocketAddrV4::new(Ipv4Addr::UNSPECIFIED, MCAST_PORT)) {
            Ok(s) => s,
            Err(e) => {
                warn!("UDP bridge: cannot bind {}:{} — {}", MCAST_ADDR, MCAST_PORT, e);
                return;
            }
        };

        if let Err(e) = socket.join_multicast_v4(&MCAST_ADDR, &Ipv4Addr::UNSPECIFIED) {
            warn!("UDP bridge: multicast join failed — {}", e);
            // Continue anyway; unicast packets may still arrive
        }

        socket.set_nonblocking(true).ok();
        let socket = std::sync::Arc::new(socket);
        info!("UDP bridge: listening on {}:{}", MCAST_ADDR, MCAST_PORT);

        let mut buf = [0u8; 2048];
        loop {
            match socket.recv_from(&mut buf) {
                Ok((len, _src)) => {
                    let packet = buf[..len].to_vec();

                    // Parse Soluna heartbeat to update device registry
                    // Soluna packet: magic[2] + device_hash[4] + seq[4] + channel_hash[4] + timestamp[4] + flags[1] + ...
                    if len >= 19 {
                        let magic = ((packet[0] as u16) << 8) | packet[1] as u16;
                        if magic == 0x534C {
                            let device_hash = u32::from_le_bytes([packet[2], packet[3], packet[4], packet[5]]);
                            let flags = packet[18];
                            let flag_heartbeat = 0x04u8;

                            if flags & flag_heartbeat != 0 {
                                let hash_hex = format!("{:08x}", device_hash);
                                let now = unix_now();
                                devices.insert(hash_hex.clone(), DeviceInfo {
                                    hash: hash_hex,
                                    channel_name: "soluna".into(),
                                    audio_level: 0.0,
                                    last_seen: now,
                                });
                            }

                            // Relay to all Soluna WS channels
                            soluna_rooms.iter().for_each(|e| {
                                let _ = e.value().send(packet.clone());
                            });
                        }
                    }
                }
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    // No data yet — yield to tokio scheduler
                    tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
                }
                Err(e) => {
                    warn!("UDP bridge recv error: {}", e);
                    tokio::time::sleep(tokio::time::Duration::from_millis(100)).await;
                }
            }
        }
    });
}

// ---- Firmware OTA ----

/// GET /api/v1/device/firmware?device_id=xxx&version=0.7.0
/// 204 = up-to-date  /  200 + binary = update available
async fn handle_firmware_check(
    Query(params): Query<HashMap<String, String>>,
) -> impl IntoResponse {
    let version_path = format!("{}/koe-firmware/version.txt", DATA_DIR);
    let bin_path     = format!("{}/koe-firmware/latest.bin",   DATA_DIR);

    let latest = match std::fs::read_to_string(&version_path) {
        Ok(v) => v.trim().to_string(),
        Err(_) => return StatusCode::NOT_FOUND.into_response(),
    };

    let current = params.get("version").map(|s| s.as_str()).unwrap_or("");
    if current == latest.as_str() {
        return StatusCode::NO_CONTENT.into_response();
    }

    let firmware = match std::fs::read(&bin_path) {
        Ok(d) => d,
        Err(_) => return StatusCode::NOT_FOUND.into_response(),
    };

    let device_id = params.get("device_id").map(|s| s.as_str()).unwrap_or("unknown");
    info!("OTA: serving v{} to {} (was v{})", latest, device_id, current);

    (
        StatusCode::OK,
        [
            ("content-type",       "application/octet-stream"),
            ("x-firmware-version", latest.as_str()),
        ],
        firmware,
    )
        .into_response()
}

/// POST /api/v1/device/firmware/upload?version=0.7.0&token=ADMIN_TOKEN
/// Body: raw .bin
async fn handle_firmware_upload(
    Query(params): Query<HashMap<String, String>>,
    body: axum::body::Bytes,
) -> impl IntoResponse {
    let token = params.get("token").map(|s| s.as_str()).unwrap_or("");
    let admin_token = std::env::var("KOE_ADMIN_TOKEN").unwrap_or_default();
    if admin_token.is_empty() || token != admin_token.as_str() {
        return (StatusCode::UNAUTHORIZED, "Invalid token").into_response();
    }

    let version = match params.get("version") {
        Some(v) if !v.is_empty() => v.clone(),
        _ => return (StatusCode::BAD_REQUEST, "version required").into_response(),
    };
    if body.is_empty() {
        return (StatusCode::BAD_REQUEST, "Empty binary").into_response();
    }

    let dir = format!("{}/koe-firmware", DATA_DIR);
    if let Err(e) = std::fs::create_dir_all(&dir) {
        return (StatusCode::INTERNAL_SERVER_ERROR, format!("mkdir: {}", e)).into_response();
    }
    if let Err(e) = std::fs::write(format!("{}/latest.bin",  dir), &body) {
        return (StatusCode::INTERNAL_SERVER_ERROR, format!("write bin: {}", e)).into_response();
    }
    if let Err(e) = std::fs::write(format!("{}/version.txt", dir), &version) {
        return (StatusCode::INTERNAL_SERVER_ERROR, format!("write ver: {}", e)).into_response();
    }

    info!("OTA: uploaded v{} ({} bytes)", version, body.len());
    (StatusCode::OK, format!("v{} ({} bytes) uploaded", version, body.len())).into_response()
}

// ---- AI API Proxy (Groq) ----

#[derive(Deserialize)]
struct TranslateReq { text: String, target: String }

async fn handle_translate(
    axum::Json(req): axum::Json<TranslateReq>,
) -> impl IntoResponse {
    let groq_key = std::env::var("GROQ_API_KEY").unwrap_or_default();
    if groq_key.is_empty() {
        return (StatusCode::SERVICE_UNAVAILABLE, axum::Json(json!({"error":"GROQ_API_KEY not set"}))).into_response();
    }
    let lang_name = match req.target.as_str() {
        "en" => "English", "zh" => "Chinese", "ko" => "Korean",
        "es" => "Spanish", "ja" => "Japanese", _ => "English",
    };
    let prompt = format!(
        "Translate the following to {}. Output ONLY the translation, no explanation:\n{}",
        lang_name, req.text
    );
    match call_groq(&groq_key, &prompt, 256).await {
        Ok(t) => (StatusCode::OK, axum::Json(json!({"translation": t}))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error": e}))).into_response(),
    }
}

#[derive(Deserialize)]
struct SummarizeReq { transcript: String }

async fn handle_summarize(
    axum::Json(req): axum::Json<SummarizeReq>,
) -> impl IntoResponse {
    let groq_key = std::env::var("GROQ_API_KEY").unwrap_or_default();
    if groq_key.is_empty() {
        return (StatusCode::SERVICE_UNAVAILABLE, axum::Json(json!({"error":"GROQ_API_KEY not set"}))).into_response();
    }
    let truncated = &req.transcript[..req.transcript.len().min(8000)];
    let prompt = format!(
        "以下の会話トランスクリプトから日本語で議事録を作成してください。\
         フォーマット: 参加者、主要な議題、決定事項、アクションアイテムを箇条書きで。\n\n{}",
        truncated
    );
    match call_groq(&groq_key, &prompt, 1024).await {
        Ok(s) => (StatusCode::OK, axum::Json(json!({"summary": s}))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error": e}))).into_response(),
    }
}

// ---- Whisper Transcription (Groq whisper-large-v3-turbo) ----

async fn handle_transcribe(
    body: axum::body::Bytes,
) -> impl IntoResponse {
    let groq_key = std::env::var("GROQ_API_KEY").unwrap_or_default();
    if groq_key.is_empty() {
        return (StatusCode::SERVICE_UNAVAILABLE, axum::Json(json!({"error":"GROQ_API_KEY not set"}))).into_response();
    }
    if body.is_empty() {
        return (StatusCode::BAD_REQUEST, axum::Json(json!({"error":"empty body"}))).into_response();
    }

    info!("transcribe: received {} bytes of audio", body.len());

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .unwrap();

    // Groq Whisper API — multipart form with audio file
    let part = reqwest::multipart::Part::bytes(body.to_vec())
        .file_name("audio.mp3")
        .mime_str("audio/mpeg")
        .unwrap();

    let form = reqwest::multipart::Form::new()
        .text("model", "whisper-large-v3-turbo")
        .text("response_format", "verbose_json")
        .text("timestamp_granularities[]", "segment")
        .text("language", "ja")
        .part("file", part);

    match client
        .post("https://api.groq.com/openai/v1/audio/transcriptions")
        .header("Authorization", format!("Bearer {}", groq_key))
        .multipart(form)
        .send()
        .await
    {
        Ok(resp) => {
            let status = StatusCode::from_u16(resp.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
            match resp.json::<Value>().await {
                Ok(j) => {
                    // Extract segments with timestamps
                    let segments = j.get("segments").cloned().unwrap_or(json!([]));
                    let text = j.get("text").and_then(|t| t.as_str()).unwrap_or("").to_string();
                    info!("transcribe: got {} segments, {} chars",
                        segments.as_array().map(|a| a.len()).unwrap_or(0), text.len());
                    (status, axum::Json(json!({
                        "text": text,
                        "segments": segments,
                    }))).into_response()
                }
                Err(e) => (StatusCode::BAD_GATEWAY, axum::Json(json!({"error": e.to_string()}))).into_response(),
            }
        }
        Err(e) => (StatusCode::BAD_GATEWAY, axum::Json(json!({"error": e.to_string()}))).into_response(),
    }
}

// ---- Feature flags (env var toggles) ----

async fn handle_features() -> impl IntoResponse {
    let gpu_url = std::env::var("GPU_ENDPOINT").unwrap_or_default();
    let has_gpu = !gpu_url.is_empty();
    let has_groq = !std::env::var("GROQ_API_KEY").unwrap_or_default().is_empty();

    let features = json!({
        "translate":      has_groq,
        "summarize":      has_groq,
        "vocal_remove":   has_gpu,
        "voice_clone":    has_gpu,
        "harmonize":      has_gpu,
        "translate_voice": has_gpu,
        "score_detail":   has_gpu,
        "generate_music": has_gpu,
        "gpu_endpoint":   if has_gpu { "online" } else { "offline" },
    });
    (StatusCode::OK, axum::Json(features))
}

// ---- AI proxy (forwards to GPU_ENDPOINT) ----

async fn handle_ai_proxy(
    req: axum::http::Request<axum::body::Body>,
) -> impl IntoResponse {
    let gpu_url = match std::env::var("GPU_ENDPOINT") {
        Ok(u) if !u.is_empty() => u,
        _ => {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                axum::Json(json!({
                    "error": "GPU service offline",
                    "hint": "Set GPU_ENDPOINT env var to enable AI features"
                })),
            ).into_response();
        }
    };

    let path = req.uri().path().to_string();
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(120))
        .build()
        .unwrap();

    // Forward body to GPU endpoint
    let body_bytes = match axum::body::to_bytes(req.into_body(), 50 * 1024 * 1024).await {
        Ok(b) => b,
        Err(e) => {
            return (StatusCode::BAD_REQUEST, axum::Json(json!({"error": e.to_string()}))).into_response();
        }
    };

    let target = format!("{}{}", gpu_url.trim_end_matches('/'), path);
    match client
        .post(&target)
        .header("Content-Type", "application/octet-stream")
        .body(body_bytes.to_vec())
        .send()
        .await
    {
        Ok(resp) => {
            let status = StatusCode::from_u16(resp.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
            let content_type = resp
                .headers()
                .get("content-type")
                .and_then(|v| v.to_str().ok())
                .unwrap_or("application/octet-stream")
                .to_string();
            match resp.bytes().await {
                Ok(bytes) => (status, [("content-type", content_type)], bytes.to_vec()).into_response(),
                Err(e) => (StatusCode::BAD_GATEWAY, axum::Json(json!({"error": e.to_string()}))).into_response(),
            }
        }
        Err(e) => {
            (StatusCode::BAD_GATEWAY, axum::Json(json!({"error": e.to_string()}))).into_response()
        }
    }
}

// ---- WebTransport cert hash ----

async fn handle_wt_hash(State(state): State<AppState>) -> impl IntoResponse {
    (StatusCode::OK, axum::Json(json!({
        "hash": state.wt_cert_hash.as_str(),
        "port": 4443,
    })))
}

// ---- WebTransport QUIC server for Crowd Mode audio ----

fn spawn_webtransport(
    identity: Identity,
    soluna_rooms: Arc<DashMap<String, broadcast::Sender<Vec<u8>>>>,
) {
    tokio::spawn(async move {
        let config = ServerConfig::builder()
            .with_bind_default(4443)
            .with_identity(identity)
            .build();

        let server = Endpoint::server(config).expect("WT server bind failed");

        info!("WebTransport: listening on UDP :4443");

        loop {
            let incoming_session = server.accept().await;

            let rooms = soluna_rooms.clone();
            tokio::spawn(async move {
                // Await QUIC handshake → SessionRequest
                let session_request = match incoming_session.await {
                    Ok(r) => r,
                    Err(e) => { warn!("WT session error: {}", e); return; }
                };

                // Extract channel from path: /crowd/{channel}
                let path = session_request.path().to_string();
                let channel = path.split('/').last().unwrap_or("soluna").to_string();

                // Accept the WebTransport session
                let connection = match session_request.accept().await {
                    Ok(c) => c,
                    Err(e) => { warn!("WT connection error: {}", e); return; }
                };

                info!("WebTransport: client connected to channel '{}'", channel);

                // Get or create broadcast channel for this room
                let tx = rooms
                    .entry(channel.clone())
                    .or_insert_with(|| {
                        let (tx, _) = broadcast::channel(512);
                        tx
                    })
                    .clone();
                let mut rx = tx.subscribe();

                // Bidirectional datagram relay (unreliable, low-latency)
                loop {
                    tokio::select! {
                        // Receive datagram from this client → broadcast to room
                        dgram = connection.receive_datagram() => {
                            match dgram {
                                Ok(data) => {
                                    let bytes: Vec<u8> = data.payload().to_vec();
                                    let _ = tx.send(bytes);
                                }
                                Err(_) => break,
                            }
                        }
                        // Room broadcast → send datagram to this client
                        bcast = rx.recv() => {
                            match bcast {
                                Ok(data) => {
                                    if connection.send_datagram(data).is_err() { break; }
                                }
                                Err(broadcast::error::RecvError::Closed) => break,
                                Err(broadcast::error::RecvError::Lagged(_)) => continue,
                            }
                        }
                    }
                }

                info!("WebTransport: client disconnected from '{}'", channel);
            });
        }
    });
}

// ---- Stats API ----

async fn handle_stats(State(state): State<AppState>) -> impl IntoResponse {
    let total_ws = TOTAL_CONNECTIONS.load(std::sync::atomic::Ordering::Relaxed);
    let rooms: Vec<Value> = state.rooms.iter().map(|e| {
        let room_name = e.key().clone();
        let peer_count = state.peers.iter()
            .filter(|p| p.key().starts_with(&format!("{}::", room_name)))
            .count();
        let listeners = state.peers.iter()
            .filter(|p| p.key().starts_with(&format!("{}::", room_name)) && p.value().name.ends_with("[L]"))
            .count();
        json!({
            "room": room_name,
            "total": peer_count,
            "speakers": peer_count - listeners,
            "listeners": listeners,
        })
    }).collect();
    let total_peers: usize = rooms.iter()
        .map(|r| r["total"].as_u64().unwrap_or(0) as usize)
        .sum();
    (StatusCode::OK, axum::Json(json!({
        "total_connections": total_ws,
        "total_peers": total_peers,
        "rooms": rooms,
        "server": {
            "uptime_s": unix_now(),
            "version": env!("CARGO_PKG_VERSION"),
        }
    })))
}

// ---- Leaderboard API ----

#[derive(Deserialize)]
struct LeaderboardEntry {
    name: String,
    score: u32,
    track: String,
}

async fn handle_leaderboard_get(
    Path(room): Path<String>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    let room = &room[..room.len().min(100)]; // limit room name length
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    let mut stmt = match db.prepare(
        "SELECT name, score, track, created_at FROM leaderboard WHERE room = ?1 ORDER BY score DESC LIMIT 50"
    ) {
        Ok(s) => s,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error": e.to_string()}))).into_response(),
    };
    let rows: Vec<Value> = match stmt.query_map([room], |row| {
        Ok(json!({
            "name": row.get::<_, String>(0)?,
            "score": row.get::<_, i64>(1)?,
            "track": row.get::<_, String>(2)?,
            "created_at": row.get::<_, i64>(3)?,
        }))
    }) {
        Ok(rows) => rows.filter_map(|r| r.ok()).collect(),
        Err(_) => Vec::new(),
    };
    (StatusCode::OK, axum::Json(json!({ "leaderboard": rows }))).into_response()
}

async fn handle_leaderboard_post(
    Path(room): Path<String>,
    State(state): State<AppState>,
    axum::Json(entry): axum::Json<LeaderboardEntry>,
) -> impl IntoResponse {
    // Input validation
    if entry.name.len() > 50 || entry.track.len() > 200 || room.len() > 100 {
        return (StatusCode::BAD_REQUEST, axum::Json(json!({"error":"input too long"}))).into_response();
    }
    if entry.score > 100 {
        return (StatusCode::BAD_REQUEST, axum::Json(json!({"error":"invalid score"}))).into_response();
    }
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    match db.execute(
        "INSERT INTO leaderboard (room, name, score, track) VALUES (?1, ?2, ?3, ?4)",
        rusqlite::params![room, entry.name, entry.score, entry.track],
    ) {
        Ok(_) => (StatusCode::CREATED, axum::Json(json!({"ok": true}))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error": e.to_string()}))).into_response(),
    }
}

// ---- Room / Playlist API ----

async fn handle_rooms_list(
    State(state): State<AppState>,
) -> impl IntoResponse {
    // Active WS rooms + DB rooms
    let mut room_set: Vec<String> = state.rooms.iter().map(|e| e.key().clone()).collect();
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    let mut stmt = match db.prepare("SELECT name FROM rooms ORDER BY last_active DESC LIMIT 50") {
        Ok(s) => s,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"rooms": []}))).into_response(),
    };
    let db_rooms: Vec<String> = match stmt.query_map([], |row| row.get(0)) {
        Ok(rows) => rows.filter_map(|r| r.ok()).collect(),
        Err(_) => Vec::new(),
    };
    for r in db_rooms { if !room_set.contains(&r) { room_set.push(r); } }

    let rooms: Vec<Value> = room_set.iter().map(|name| {
        let peer_count = state.peers.iter().filter(|e| e.key().starts_with(&format!("{}::", name))).count();
        json!({ "name": name, "peers": peer_count })
    }).collect();
    (StatusCode::OK, axum::Json(json!({ "rooms": rooms }))).into_response()
}

async fn handle_playlist_get(
    Path(room): Path<String>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::OK, [("content-type", "application/json")], "[]".to_string()).into_response(),
    };
    let playlist: String = db.query_row(
        "SELECT playlist FROM rooms WHERE name = ?1", [&room],
        |row| row.get(0),
    ).unwrap_or_else(|_| "[]".to_string());
    (StatusCode::OK, [("content-type", "application/json")], playlist).into_response()
}

#[derive(Deserialize)]
struct PlaylistSave {
    playlist: Value,
}

async fn handle_playlist_save(
    Path(room): Path<String>,
    State(state): State<AppState>,
    axum::Json(body): axum::Json<PlaylistSave>,
) -> impl IntoResponse {
    if room.len() > 100 {
        return (StatusCode::BAD_REQUEST, axum::Json(json!({"error":"room name too long"}))).into_response();
    }
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    let playlist_str = serde_json::to_string(&body.playlist).unwrap_or_else(|_| "[]".to_string());
    let now = unix_now() as i64;
    match db.execute(
        "INSERT INTO rooms (name, playlist, last_active) VALUES (?1, ?2, ?3)
         ON CONFLICT(name) DO UPDATE SET playlist = ?2, last_active = ?3",
        rusqlite::params![room, playlist_str, now],
    ) {
        Ok(_) => (StatusCode::OK, axum::Json(json!({"ok": true}))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error": e.to_string()}))).into_response(),
    }
}

// ---- Order / Checkout System ----

#[derive(Deserialize)]
struct CheckoutRequest {
    product: String,
    #[serde(default = "default_qty")]
    quantity: u32,
}
fn default_qty() -> u32 { 1 }

async fn handle_checkout(
    axum::Json(body): axum::Json<CheckoutRequest>,
) -> impl IntoResponse {
    let stripe_key = std::env::var("STRIPE_SECRET_KEY").unwrap_or_default();
    if stripe_key.is_empty() {
        return (StatusCode::SERVICE_UNAVAILABLE, axum::Json(json!({"error":"STRIPE_SECRET_KEY not set"}))).into_response();
    }

    let (price_jpy, name) = match body.product.as_str() {
        "seed" => (12800, "Koe Seed"),
        "seed_earlybird" => (8800, "Koe Seed (早割)"),
        "seed_pro" => (19500, "Koe Seed Pro"),
        "dk_edition" => (29800, "Koe Seed Developer Edition"),
        "deposit" => (1000, "Koe Seed デポジット"),
        _ => return (StatusCode::BAD_REQUEST, axum::Json(json!({"error":"Invalid product"}))).into_response(),
    };

    let qty = body.quantity.max(1).min(100);

    let client = reqwest::Client::new();
    let resp = client.post("https://api.stripe.com/v1/checkout/sessions")
        .header("Authorization", format!("Bearer {}", stripe_key))
        .form(&[
            ("mode", "payment"),
            ("line_items[0][price_data][currency]", "jpy"),
            ("line_items[0][price_data][unit_amount]", &price_jpy.to_string()),
            ("line_items[0][price_data][product_data][name]", name),
            ("line_items[0][quantity]", &qty.to_string()),
            ("shipping_address_collection[allowed_countries][0]", "JP"),
            ("shipping_address_collection[allowed_countries][1]", "US"),
            ("shipping_address_collection[allowed_countries][2]", "GB"),
            ("shipping_address_collection[allowed_countries][3]", "DE"),
            ("shipping_address_collection[allowed_countries][4]", "FR"),
            ("success_url", "https://koe.live/order/success?session_id={CHECKOUT_SESSION_ID}"),
            ("cancel_url", "https://koe.live/order"),
            ("metadata[product]", &body.product),
            ("metadata[quantity]", &qty.to_string()),
        ])
        .send()
        .await;

    match resp {
        Ok(r) => {
            let status = r.status();
            match r.json::<Value>().await {
                Ok(j) => {
                    if status.is_success() {
                        if let Some(url) = j.get("url").and_then(|u| u.as_str()) {
                            (StatusCode::OK, axum::Json(json!({"checkout_url": url}))).into_response()
                        } else {
                            (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"no checkout url in response"}))).into_response()
                        }
                    } else {
                        let err_msg = j.get("error").and_then(|e| e.get("message")).and_then(|m| m.as_str()).unwrap_or("Stripe error");
                        warn!("Stripe checkout error: {}", err_msg);
                        (StatusCode::BAD_GATEWAY, axum::Json(json!({"error": err_msg}))).into_response()
                    }
                }
                Err(e) => (StatusCode::BAD_GATEWAY, axum::Json(json!({"error": e.to_string()}))).into_response(),
            }
        }
        Err(e) => (StatusCode::BAD_GATEWAY, axum::Json(json!({"error": e.to_string()}))).into_response(),
    }
}

/// POST /api/v1/stripe/webhook — Stripe webhook handler
async fn handle_stripe_webhook(
    headers: HeaderMap,
    State(state): State<AppState>,
    body: axum::body::Bytes,
) -> impl IntoResponse {
    let webhook_secret = std::env::var("STRIPE_WEBHOOK_SECRET").unwrap_or_default();
    let sig_header = headers.get("stripe-signature")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("")
        .to_string();

    // Verify webhook signature if secret is configured
    if !webhook_secret.is_empty() {
        if !verify_stripe_signature(&body, &sig_header, &webhook_secret) {
            warn!("Stripe webhook: invalid signature");
            return (StatusCode::BAD_REQUEST, "Invalid signature").into_response();
        }
    }

    let event: Value = match serde_json::from_slice(&body) {
        Ok(v) => v,
        Err(e) => return (StatusCode::BAD_REQUEST, format!("Invalid JSON: {}", e)).into_response(),
    };

    let event_type = event.get("type").and_then(|t| t.as_str()).unwrap_or("");
    info!("Stripe webhook: {}", event_type);

    if event_type == "checkout.session.completed" {
        let session = &event["data"]["object"];
        let session_id = session["id"].as_str().unwrap_or("");
        let payment_intent = session["payment_intent"].as_str().unwrap_or("");
        let email = session["customer_details"]["email"].as_str().unwrap_or("");
        let name = session["customer_details"]["name"].as_str().unwrap_or("");
        let amount = session["amount_total"].as_i64().unwrap_or(0);
        let product = session["metadata"]["product"].as_str().unwrap_or("seed");
        let quantity: i64 = session["metadata"]["quantity"].as_str()
            .and_then(|q| q.parse().ok())
            .unwrap_or(1);

        // Shipping address — try collected_information first, then shipping_details, then customer_details
        let shipping = if !session["collected_information"]["shipping_details"]["address"]["line1"].is_null() {
            &session["collected_information"]["shipping_details"]["address"]
        } else if !session["shipping_details"]["address"]["line1"].is_null() {
            &session["shipping_details"]["address"]
        } else {
            &session["customer_details"]["address"]
        };
        let ship_name = session["collected_information"]["shipping_details"]["name"].as_str()
            .or_else(|| session["shipping_details"]["name"].as_str())
            .or_else(|| session["customer_details"]["name"].as_str())
            .unwrap_or(name);
        let ship_line1 = shipping["line1"].as_str().unwrap_or("");
        let ship_line2 = shipping["line2"].as_str().unwrap_or("");
        let ship_address = if ship_line2.is_empty() {
            ship_line1.to_string()
        } else {
            format!("{} {}", ship_line1, ship_line2)
        };
        let ship_city = shipping["city"].as_str().unwrap_or("");
        let ship_state = shipping["state"].as_str().unwrap_or("");
        let ship_zip = shipping["postal_code"].as_str().unwrap_or("");
        let ship_country = shipping["country"].as_str().unwrap_or("JP");
        let phone = session["customer_details"]["phone"].as_str().unwrap_or("");

        // DB insert — all owned strings to avoid borrow issues
        let session_id_owned = session_id.to_string();
        let payment_intent_owned = payment_intent.to_string();
        let email_owned = email.to_string();
        let name_owned = name.to_string();
        let ship_name_owned = ship_name.to_string();
        let ship_address_owned = ship_address.clone();
        let ship_city_owned = ship_city.to_string();
        let ship_state_owned = ship_state.to_string();
        let ship_zip_owned = ship_zip.to_string();
        let ship_country_owned = ship_country.to_string();
        let phone_owned = phone.to_string();
        let product_owned = product.to_string();

        {
            if let Ok(db) = state.db.lock() {
                match db.execute(
                    "INSERT OR IGNORE INTO orders (stripe_session_id, stripe_payment_intent, customer_email, customer_name, shipping_name, shipping_address, shipping_city, shipping_state, shipping_zip, shipping_country, phone, product, quantity, amount_jpy)
                     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14)",
                    rusqlite::params![session_id_owned, payment_intent_owned, email_owned, name_owned, ship_name_owned, ship_address_owned, ship_city_owned, ship_state_owned, ship_zip_owned, ship_country_owned, phone_owned, product_owned, quantity, amount],
                ) {
                    Ok(_) => info!("Order saved: {} - {} x{} ¥{}", email_owned, product_owned, quantity, amount),
                    Err(e) => warn!("Order save error: {}", e),
                }
            } else {
                warn!("Order save: db lock error");
            }
        }

        // Send confirmation email
        if !email_owned.is_empty() {
            let display_name = if name_owned.is_empty() { &email_owned } else { &name_owned };
            let product_name = match product_owned.as_str() {
                "seed" => "Koe Seed",
                "seed_earlybird" => "Koe Seed (早割)",
                "seed_pro" => "Koe Seed Pro",
                "dk_edition" => "Koe Seed Developer Edition",
                "deposit" => "Koe Seed デポジット",
                _ => &product_owned,
            };
            let full_address = format!("〒{} {} {} {}\n{}", ship_zip_owned, ship_country_owned, ship_state_owned, ship_city_owned, ship_address_owned);
            let html = format!(
                r#"<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:2rem;background:#0a0a0a;color:#e8e8e8;">
<h2 style="color:#8B5CF6;">ご注文ありがとうございます</h2>
<p>{} 様</p>
<p>Koe Seedのご注文を承りました。</p>
<table style="width:100%;border-collapse:collapse;margin:1.5rem 0;">
<tr><td style="padding:0.5rem 0;color:#888;">商品</td><td style="padding:0.5rem 0;">{}</td></tr>
<tr><td style="padding:0.5rem 0;color:#888;">数量</td><td style="padding:0.5rem 0;">{}</td></tr>
<tr><td style="padding:0.5rem 0;color:#888;">金額</td><td style="padding:0.5rem 0;">¥{}</td></tr>
</table>
<p style="color:#888;">お届け先:</p>
<p style="white-space:pre-line;">{}</p>
<p style="margin-top:2rem;">現在製造中です。発送時に追跡番号をお知らせします。<br>予定発送日: 2026年8月</p>
<p style="margin-top:2rem;color:#888;">ご質問は <a href="mailto:hello@koe.live" style="color:#8B5CF6;">hello@koe.live</a> までお気軽にどうぞ。</p>
<p style="margin-top:2rem;color:#666;">— Koe チーム</p>
</div>"#,
                display_name, product_name, quantity, amount, full_address
            );
            send_email(&email_owned, "ご注文ありがとうございます — Koe Seed", &html).await;
        }
    }

    (StatusCode::OK, "ok").into_response()
}

fn verify_stripe_signature(payload: &[u8], sig_header: &str, secret: &str) -> bool {
    // Parse sig header: t=timestamp,v1=signature
    let mut timestamp = "";
    let mut signature = "";
    for part in sig_header.split(',') {
        let kv: Vec<&str> = part.splitn(2, '=').collect();
        if kv.len() == 2 {
            match kv[0] {
                "t" => timestamp = kv[1],
                "v1" => signature = kv[1],
                _ => {}
            }
        }
    }
    if timestamp.is_empty() || signature.is_empty() {
        return false;
    }

    // Compute expected: HMAC-SHA256(secret, "timestamp.payload")
    let signed_payload = format!("{}.{}", timestamp, std::str::from_utf8(payload).unwrap_or(""));
    let key = ring::hmac::Key::new(ring::hmac::HMAC_SHA256, secret.as_bytes());
    let tag = ring::hmac::sign(&key, signed_payload.as_bytes());
    let computed = hex_encode(tag.as_ref());
    computed == signature
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

async fn send_email(to: &str, subject: &str, html: &str) {
    let resend_key = std::env::var("RESEND_API_KEY").unwrap_or_default();
    if resend_key.is_empty() {
        warn!("RESEND_API_KEY not set, skipping email to {}", to);
        return;
    }
    let client = reqwest::Client::new();
    match client.post("https://api.resend.com/emails")
        .header("Authorization", format!("Bearer {}", resend_key))
        .json(&json!({
            "from": "Koe <hello@koe.live>",
            "to": [to],
            "subject": subject,
            "html": html
        }))
        .send()
        .await
    {
        Ok(resp) => info!("Email sent to {}: {}", to, resp.status()),
        Err(e) => warn!("Email send error: {}", e),
    }
}

/// GET /order/success — order success page
async fn handle_order_success() -> impl IntoResponse {
    serve_html("order-success.html").await
}

/// GET /admin — admin dashboard page
async fn handle_admin_page() -> impl IntoResponse {
    serve_html("admin.html").await
}

/// Helper: verify admin auth from Authorization header or ?token= query param
fn verify_admin_auth(headers: &HeaderMap, query: &HashMap<String, String>) -> bool {
    let auth_token = std::env::var("AUTH_TOKEN").unwrap_or_default();
    if auth_token.is_empty() {
        return false;
    }
    // Check Authorization: Bearer <token>
    if let Some(auth) = headers.get("authorization").and_then(|v| v.to_str().ok()) {
        if auth.strip_prefix("Bearer ").unwrap_or("") == auth_token {
            return true;
        }
    }
    // Check ?token= query param
    if let Some(token) = query.get("token") {
        if token == &auth_token {
            return true;
        }
    }
    false
}

/// GET /admin/orders — list all orders (JSON)
async fn handle_admin_orders(
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    if !verify_admin_auth(&headers, &params) {
        return (StatusCode::UNAUTHORIZED, axum::Json(json!({"error":"Unauthorized"}))).into_response();
    }

    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };

    let mut stmt = match db.prepare(
        "SELECT id, stripe_session_id, stripe_payment_intent, customer_email, customer_name, shipping_name, shipping_address, shipping_city, shipping_state, shipping_zip, shipping_country, phone, product, quantity, amount_jpy, status, tracking_number, notes, created_at, updated_at FROM orders ORDER BY id DESC"
    ) {
        Ok(s) => s,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error": e.to_string()}))).into_response(),
    };

    let rows: Vec<Value> = match stmt.query_map([], |row| {
        Ok(json!({
            "id": row.get::<_, i64>(0)?,
            "stripe_session_id": row.get::<_, Option<String>>(1)?,
            "stripe_payment_intent": row.get::<_, Option<String>>(2)?,
            "customer_email": row.get::<_, String>(3)?,
            "customer_name": row.get::<_, Option<String>>(4)?,
            "shipping_name": row.get::<_, Option<String>>(5)?,
            "shipping_address": row.get::<_, Option<String>>(6)?,
            "shipping_city": row.get::<_, Option<String>>(7)?,
            "shipping_state": row.get::<_, Option<String>>(8)?,
            "shipping_zip": row.get::<_, Option<String>>(9)?,
            "shipping_country": row.get::<_, Option<String>>(10)?,
            "phone": row.get::<_, Option<String>>(11)?,
            "product": row.get::<_, String>(12)?,
            "quantity": row.get::<_, i64>(13)?,
            "amount_jpy": row.get::<_, Option<i64>>(14)?,
            "status": row.get::<_, String>(15)?,
            "tracking_number": row.get::<_, Option<String>>(16)?,
            "notes": row.get::<_, Option<String>>(17)?,
            "created_at": row.get::<_, Option<String>>(18)?,
            "updated_at": row.get::<_, Option<String>>(19)?,
        }))
    }) {
        Ok(rows) => rows.filter_map(|r| r.ok()).collect(),
        Err(_) => Vec::new(),
    };

    (StatusCode::OK, axum::Json(json!({"orders": rows, "total": rows.len()}))).into_response()
}

/// PUT /admin/orders/:id — update order status/tracking
#[derive(Deserialize)]
struct OrderUpdate {
    #[serde(default)]
    status: Option<String>,
    #[serde(default)]
    tracking_number: Option<String>,
    #[serde(default)]
    notes: Option<String>,
    #[serde(default)]
    shipping_name: Option<String>,
    #[serde(default)]
    shipping_address: Option<String>,
    #[serde(default)]
    shipping_city: Option<String>,
    #[serde(default)]
    shipping_state: Option<String>,
    #[serde(default)]
    shipping_zip: Option<String>,
    #[serde(default)]
    shipping_country: Option<String>,
}

async fn handle_admin_order_update(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(order_id): Path<i64>,
    axum::Json(body): axum::Json<OrderUpdate>,
) -> impl IntoResponse {
    let empty_params = HashMap::new();
    if !verify_admin_auth(&headers, &empty_params) {
        return (StatusCode::UNAUTHORIZED, axum::Json(json!({"error":"Unauthorized"}))).into_response();
    }

    let valid_statuses = ["paid", "confirmed", "manufacturing", "shipped", "delivered"];
    if let Some(ref s) = body.status {
        if !valid_statuses.contains(&s.as_str()) {
            return (StatusCode::BAD_REQUEST, axum::Json(json!({"error": format!("Invalid status. Must be one of: {:?}", valid_statuses)}))).into_response();
        }
    }

    // All DB work in a sync block — no MutexGuard across await
    let db_result: Result<(String, String, Option<String>), String> = (|| -> Result<(String, String, Option<String>), String> {
        let db = state.db.lock().map_err(|_| "db lock".to_string())?;

        // Get current order data for email notification
        let order_data: Option<(String, String, Option<String>, Option<String>)> = db.query_row(
            "SELECT customer_email, status, customer_name, tracking_number FROM orders WHERE id = ?1",
            [order_id],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?, row.get(3)?)),
        ).ok();

        let (email, old_status, customer_name, _old_tracking) = order_data.ok_or_else(|| "Order not found".to_string())?;

        // Build dynamic UPDATE
        let mut updates = vec!["updated_at = datetime('now')".to_string()];
        let mut param_values: Vec<String> = Vec::new();

        if let Some(ref s) = body.status {
            param_values.push(s.clone());
            updates.push(format!("status = ?{}", param_values.len() + 1));
        }
        if let Some(ref t) = body.tracking_number {
            param_values.push(t.clone());
            updates.push(format!("tracking_number = ?{}", param_values.len() + 1));
        }
        if let Some(ref n) = body.notes {
            param_values.push(n.clone());
            updates.push(format!("notes = ?{}", param_values.len() + 1));
        }
        if let Some(ref v) = body.shipping_name {
            param_values.push(v.clone());
            updates.push(format!("shipping_name = ?{}", param_values.len() + 1));
        }
        if let Some(ref v) = body.shipping_address {
            param_values.push(v.clone());
            updates.push(format!("shipping_address = ?{}", param_values.len() + 1));
        }
        if let Some(ref v) = body.shipping_city {
            param_values.push(v.clone());
            updates.push(format!("shipping_city = ?{}", param_values.len() + 1));
        }
        if let Some(ref v) = body.shipping_state {
            param_values.push(v.clone());
            updates.push(format!("shipping_state = ?{}", param_values.len() + 1));
        }
        if let Some(ref v) = body.shipping_zip {
            param_values.push(v.clone());
            updates.push(format!("shipping_zip = ?{}", param_values.len() + 1));
        }
        if let Some(ref v) = body.shipping_country {
            param_values.push(v.clone());
            updates.push(format!("shipping_country = ?{}", param_values.len() + 1));
        }

        let sql = format!("UPDATE orders SET {} WHERE id = ?1", updates.join(", "));

        // Build params: [order_id, ...param_values]
        let mut all_params: Vec<Box<dyn rusqlite::types::ToSql>> = Vec::new();
        all_params.push(Box::new(order_id));
        for v in &param_values {
            all_params.push(Box::new(v.clone()));
        }
        let params_ref: Vec<&dyn rusqlite::types::ToSql> = all_params.iter().map(|p| p.as_ref()).collect();
        let result = db.execute(&sql, params_ref.as_slice());

        result.map_err(|e| e.to_string())?;
        info!("Order {} updated: status={:?} tracking={:?}", order_id, body.status, body.tracking_number);

        Ok((email, old_status, customer_name))
    })();

    let (email, old_status, customer_name) = match db_result {
        Ok(v) => v,
        Err(e) => {
            let status = if e == "Order not found" { StatusCode::NOT_FOUND } else { StatusCode::INTERNAL_SERVER_ERROR };
            return (status, axum::Json(json!({"error": e}))).into_response();
        }
    };

    // Send shipping notification email if status changed to "shipped"
    if let Some(ref new_status) = body.status {
        if new_status == "shipped" && old_status != "shipped" && !email.is_empty() {
            let display_name = customer_name.as_deref().unwrap_or(&email);
            let tracking = body.tracking_number.as_deref().unwrap_or("未設定");
            let html = format!(
                r#"<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:2rem;background:#0a0a0a;color:#e8e8e8;">
<h2 style="color:#8B5CF6;">発送しました</h2>
<p>{} 様</p>
<p>ご注文の Koe Seed を発送しました！</p>
<table style="width:100%;border-collapse:collapse;margin:1.5rem 0;">
<tr><td style="padding:0.5rem 0;color:#888;">追跡番号</td><td style="padding:0.5rem 0;font-family:monospace;">{}</td></tr>
<tr><td style="padding:0.5rem 0;color:#888;">配送業者</td><td style="padding:0.5rem 0;">DHL Express</td></tr>
<tr><td style="padding:0.5rem 0;color:#888;">追跡URL</td><td style="padding:0.5rem 0;"><a href="https://www.dhl.com/jp/tracking?id={}" style="color:#8B5CF6;">追跡する</a></td></tr>
</table>
<p>到着予定: 3-5営業日</p>
<p style="margin-top:2rem;color:#666;">— Koe チーム</p>
</div>"#,
                display_name, tracking, tracking
            );
            send_email(&email, "発送しました — Koe Seed", &html).await;
        }
    }

    (StatusCode::OK, axum::Json(json!({"ok": true}))).into_response()
}

/// GET /admin/orders/export — CSV export of all orders
async fn handle_admin_orders_export(
    headers: HeaderMap,
    Query(params): Query<HashMap<String, String>>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    if !verify_admin_auth(&headers, &params) {
        return (StatusCode::UNAUTHORIZED, "Unauthorized").into_response();
    }

    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, "DB lock error").into_response(),
    };

    let mut stmt = match db.prepare(
        "SELECT id, customer_email, customer_name, shipping_name, shipping_address, shipping_city, shipping_state, shipping_zip, shipping_country, phone, product, quantity, amount_jpy, status, tracking_number, created_at FROM orders ORDER BY id DESC"
    ) {
        Ok(s) => s,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, format!("Query error: {}", e)).into_response(),
    };

    let mut csv = String::from("ID,Email,Name,ShippingName,Address,City,State,Zip,Country,Phone,Product,Qty,Amount,Status,Tracking,CreatedAt\n");

    let rows = stmt.query_map([], |row| {
        let id: i64 = row.get(0)?;
        let email: String = row.get(1)?;
        let name: String = row.get::<_, Option<String>>(2)?.unwrap_or_default();
        let ship_name: String = row.get::<_, Option<String>>(3)?.unwrap_or_default();
        let addr: String = row.get::<_, Option<String>>(4)?.unwrap_or_default();
        let city: String = row.get::<_, Option<String>>(5)?.unwrap_or_default();
        let state: String = row.get::<_, Option<String>>(6)?.unwrap_or_default();
        let zip: String = row.get::<_, Option<String>>(7)?.unwrap_or_default();
        let country: String = row.get::<_, Option<String>>(8)?.unwrap_or_default();
        let phone: String = row.get::<_, Option<String>>(9)?.unwrap_or_default();
        let product: String = row.get(10)?;
        let qty: i64 = row.get(11)?;
        let amount: i64 = row.get::<_, Option<i64>>(12)?.unwrap_or(0);
        let status: String = row.get(13)?;
        let tracking: String = row.get::<_, Option<String>>(14)?.unwrap_or_default();
        let created: String = row.get::<_, Option<String>>(15)?.unwrap_or_default();
        Ok(format!("{},\"{}\",\"{}\",\"{}\",\"{}\",\"{}\",\"{}\",\"{}\",{},\"{}\",{},{},{},{},\"{}\",{}",
            id, email, name, ship_name, addr, city, state, zip, country, phone, product, qty, amount, status, tracking, created))
    });

    if let Ok(rows) = rows {
        for row in rows.flatten() {
            csv.push_str(&row);
            csv.push('\n');
        }
    }

    (
        StatusCode::OK,
        [
            ("content-type", "text/csv; charset=utf-8"),
            ("content-disposition", "attachment; filename=\"koe-orders.csv\""),
        ],
        csv,
    ).into_response()
}

async fn call_groq(api_key: &str, prompt: &str, max_tokens: u32) -> Result<String, String> {
    let client = reqwest::Client::new();
    let body = json!({
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role":"user","content":prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.3
    });
    let resp = client
        .post("https://api.groq.com/openai/v1/chat/completions")
        .header("Authorization", format!("Bearer {}", api_key))
        .header("Content-Type", "application/json")
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    let j: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
    j["choices"][0]["message"]["content"]
        .as_str()
        .map(|s| s.trim().to_string())
        .ok_or_else(|| format!("unexpected groq response: {}", j))
}

// ---- Stone / Sessions handlers ----

/// GET /stone/:id — serve stone.html (client reads stone ID from URL)
async fn handle_stone_page(
    Path(_stone_id): Path<String>,
    _state: State<AppState>,
) -> impl IntoResponse {
    serve_html("stone.html").await
}

/// GET /api/v1/stone/:id — JSON info for a stone device
async fn handle_stone_api(
    Path(stone_id): Path<String>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    let result = db.query_row(
        "SELECT id, sku, serial, room, last_touched, session_count, tap_count FROM stone_devices WHERE id = ?1",
        rusqlite::params![stone_id],
        |row| Ok(json!({
            "id": row.get::<_,String>(0)?,
            "sku": row.get::<_,String>(1)?,
            "serial": row.get::<_,String>(2)?,
            "room": row.get::<_,String>(3)?,
            "last_touched": row.get::<_,Option<i64>>(4)?,
            "session_count": row.get::<_,i64>(5)?,
            "tap_count": row.get::<_,i64>(6)?,
        }))
    );
    match result {
        Ok(v) => (StatusCode::OK, axum::Json(v)).into_response(),
        Err(_) => (StatusCode::NOT_FOUND, axum::Json(json!({"error":"not found"}))).into_response(),
    }
}

/// POST /api/v1/stone/:id/tap — record a tap/vote on a stone device
async fn handle_stone_tap(
    Path(stone_id): Path<String>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    db.execute(
        "INSERT INTO stone_taps(stone_id, tapped_at) VALUES(?1, strftime('%s','now'))",
        rusqlite::params![stone_id],
    ).ok();
    db.execute(
        "UPDATE stone_devices SET tap_count = tap_count + 1, last_touched = strftime('%s','now') WHERE id = ?1",
        rusqlite::params![stone_id],
    ).ok();
    (StatusCode::OK, axum::Json(json!({"ok":true}))).into_response()
}

/// GET /api/v1/sessions — list sessions (most recent 100)
async fn handle_sessions_list(
    State(state): State<AppState>,
) -> impl IntoResponse {
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    let mut stmt = match db.prepare(
        "SELECT id, room, label, start_time, end_time, duration_secs, tracks, instruments, is_silence, source FROM koe_sessions ORDER BY start_time DESC LIMIT 100"
    ) {
        Ok(s) => s,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":e.to_string()}))).into_response(),
    };
    let sessions: Vec<Value> = match stmt.query_map([], |row| {
        Ok(json!({
            "id": row.get::<_,String>(0)?,
            "room": row.get::<_,String>(1)?,
            "label": row.get::<_,Option<String>>(2)?,
            "start_time": row.get::<_,i64>(3)?,
            "end_time": row.get::<_,Option<i64>>(4)?,
            "duration_secs": row.get::<_,Option<i64>>(5)?,
            "tracks": row.get::<_,i64>(6)?,
            "instruments": row.get::<_,String>(7)?,
            "is_silence": row.get::<_,i64>(8)?,
            "source": row.get::<_,String>(9)?,
        }))
    }) {
        Ok(rows) => rows.filter_map(|r| r.ok()).collect(),
        Err(_) => vec![],
    };
    let count = sessions.len();
    (StatusCode::OK, axum::Json(json!({"sessions": sessions, "count": count}))).into_response()
}

/// POST /api/v1/sessions — create or replace a session (admin)
async fn handle_session_create(
    State(state): State<AppState>,
    headers: HeaderMap,
    axum::Json(body): axum::Json<Value>,
) -> impl IntoResponse {
    let token = std::env::var("KOE_ADMIN_TOKEN").unwrap_or_default();
    let auth = headers.get("authorization")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");
    if !token.is_empty() && auth != format!("Bearer {}", token) {
        return (StatusCode::UNAUTHORIZED, axum::Json(json!({"error":"unauthorized"}))).into_response();
    }
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    let id = body["id"].as_str().unwrap_or("").to_string();
    let room = body["room"].as_str().unwrap_or("living_room").to_string();
    let label = body["label"].as_str().map(|s| s.to_string());
    let start_time = body["start_time"].as_i64().unwrap_or(0);
    let end_time = body["end_time"].as_i64();
    let duration_secs = body["duration_secs"].as_i64();
    let tracks = body["tracks"].as_i64().unwrap_or(6);
    let instruments = body["instruments"].to_string();
    let source = body["source"].as_str().unwrap_or("auto").to_string();
    let r = db.execute(
        "INSERT OR REPLACE INTO koe_sessions(id,room,label,start_time,end_time,duration_secs,tracks,instruments,source) VALUES(?1,?2,?3,?4,?5,?6,?7,?8,?9)",
        rusqlite::params![id, room, label, start_time, end_time, duration_secs, tracks, instruments, source],
    );
    match r {
        Ok(_) => (StatusCode::CREATED, axum::Json(json!({"ok":true,"id":id}))).into_response(),
        Err(e) => (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":e.to_string()}))).into_response(),
    }
}

/// GET /api/v1/sessions/timeline — sessions grouped by day (for EKG visualization)
async fn handle_sessions_timeline(
    State(state): State<AppState>,
) -> impl IntoResponse {
    let db = match state.db.lock() {
        Ok(db) => db,
        Err(_) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":"db lock"}))).into_response(),
    };
    let mut stmt = match db.prepare(
        "SELECT (start_time / 86400) as day, COUNT(*) as count, SUM(duration_secs) as total_secs FROM koe_sessions WHERE is_silence = 0 GROUP BY day ORDER BY day"
    ) {
        Ok(s) => s,
        Err(e) => return (StatusCode::INTERNAL_SERVER_ERROR, axum::Json(json!({"error":e.to_string()}))).into_response(),
    };
    let days: Vec<Value> = match stmt.query_map([], |row| {
        Ok(json!({
            "day": row.get::<_,i64>(0)?,
            "count": row.get::<_,i64>(1)?,
            "total_secs": row.get::<_,Option<i64>>(2)?,
        }))
    }) {
        Ok(rows) => rows.filter_map(|r| r.ok()).collect(),
        Err(_) => vec![],
    };
    (StatusCode::OK, axum::Json(json!({"days": days}))).into_response()
}

// ---- Helpers ----

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
