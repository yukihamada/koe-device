/// koe.live — static site + OTA firmware endpoint + WebRTC signaling + Soluna relay
///
/// Routes:
///   GET  /                               → static HTML (docs/)
///   GET  /app                            → docs/app.html (P2P web app)
///   GET  /health                         → {"status":"ok"}
///   GET  /api/devices                    → JSON list of recently seen Soluna devices
///   GET  /api/v1/device/firmware         → 204 (up-to-date) | 200 (binary)
///   POST /api/v1/device/firmware/upload  → upload new firmware (admin token)
///   GET  /ws/signal                      → WebRTC signaling (room-based broadcast)
///   GET  /ws/soluna                      → Soluna protocol relay (WS ↔ UDP multicast bridge)

use axum::{
    Router,
    extract::{DefaultBodyLimit, Query, State, WebSocketUpgrade},
    extract::ws::{Message, WebSocket},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
};
use dashmap::DashMap;
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::net::{Ipv4Addr, SocketAddrV4, UdpSocket};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::broadcast;
use tower_http::services::ServeDir;
use tracing::{info, warn};

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
}

// ---- Signal message types ----
#[derive(Debug, Deserialize)]
struct WsSignalParams {
    room: String,
    peer: String,
    name: String,
}

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

    let state = AppState {
        rooms: Arc::new(DashMap::new()),
        peers: Arc::new(DashMap::new()),
        devices: Arc::new(DashMap::new()),
        soluna_rooms: Arc::new(DashMap::new()),
    };

    // Spawn UDP→WS bridge for Soluna multicast
    spawn_udp_bridge(state.devices.clone(), state.soluna_rooms.clone());

    let app = Router::new()
        .route("/health",                          get(handle_health))
        .route("/app",                             get(handle_app))
        .route("/api/devices",                     get(handle_devices))
        .route("/api/v1/device/firmware",          get(handle_firmware_check))
        .route(
            "/api/v1/device/firmware/upload",
            post(handle_firmware_upload)
                .layer(DefaultBodyLimit::max(8 * 1024 * 1024)),
        )
        .route("/api/translate",  post(handle_translate))
        .route("/api/summarize",  post(handle_summarize))
        .route("/api/features",   get(handle_features))
        .route("/api/v1/ai/vocal-remove",    post(handle_ai_proxy))
        .route("/api/v1/ai/voice-clone",     post(handle_ai_proxy))
        .route("/api/v1/ai/harmonize",       post(handle_ai_proxy))
        .route("/api/v1/ai/translate-voice",  post(handle_ai_proxy))
        .route("/api/v1/ai/score-detail",    post(handle_ai_proxy))
        .route("/api/v1/ai/generate-music",  post(handle_ai_proxy))
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

async fn handle_app() -> impl IntoResponse {
    let static_dir = std::env::var("STATIC_DIR").unwrap_or_else(|_| "/app/docs".to_string());
    let path = format!("{}/app.html", static_dir);
    match std::fs::read_to_string(&path) {
        Ok(html) => (
            StatusCode::OK,
            [("content-type", "text/html; charset=utf-8")],
            html,
        )
            .into_response(),
        Err(_) => (StatusCode::NOT_FOUND, "app.html not found").into_response(),
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
    let peer_name = params.name.clone();

    // Get or create room broadcast channel
    let tx = state
        .rooms
        .entry(room_id.clone())
        .or_insert_with(|| {
            let (tx, _) = broadcast::channel(256);
            tx
        })
        .clone();
    let mut rx = tx.subscribe();

    info!("signal: {} ({}) joined room '{}'", peer_id, peer_name, room_id);

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

    // Announce join to others in room
    let join_msg = json!({
        "type": "joined",
        "from": peer_id,
        "data": { "name": peer_name }
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
                            // Inject sender peer ID if missing
                            let mut v = val;
                            if v.get("from").is_none() {
                                v["from"] = json!(peer_id);
                            }
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
                        }
                        if ws_tx.send(Message::Text(text)).await.is_err() { break; }
                    }
                    Err(broadcast::error::RecvError::Closed) => break,
                    Err(broadcast::error::RecvError::Lagged(_)) => continue,
                }
            }
        }
    }

    // Unregister peer
    state.peers.remove(&peer_key);

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

// ---- Helpers ----

fn unix_now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
