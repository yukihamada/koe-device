/// Koe Hub — Real-time audio mixer & streaming server for Raspberry Pi CM5.
///
/// Receives audio from multiple Koe Pro devices via UDP, mixes in real-time
/// with per-channel EQ/gain/pan, applies master effects (reverb, compressor,
/// delay), and streams to various outputs.
///
/// Routes:
///   GET  /              → Dashboard HTML (inline)
///   GET  /ws/mixer      → WebSocket for real-time mixer control & metering
///   GET  /api/channels  → List input channels with levels
///   POST /api/channels/:id/gain → Set channel gain
///   POST /api/channels/:id/mute → Toggle mute
///   POST /api/master/effect     → Set master effect params
///   GET  /api/status    → System status (CPU, latency, buffer)

mod mixer;
mod effects;
mod receiver;
mod streamer;

use std::sync::{Arc, Mutex};
use std::time::Instant;

use axum::{
    Router,
    extract::{Path, State, WebSocketUpgrade},
    extract::ws::{Message, WebSocket},
    http::StatusCode,
    response::{Html, IntoResponse},
    routing::{get, post},
};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::json;
use tracing::{info, warn};

use crate::effects::{AudioEffect, Compressor, DeEsser, Delay, EffectParams, Gate, Reverb, StereoWidener};
use crate::mixer::MixerEngine;
use crate::receiver::{new_device_registry, new_crowd_aggregator, DeviceRegistry, SharedCrowdAggregator};
use crate::streamer::Streamer;

// ---- Application state ----

#[derive(Clone)]
struct AppState {
    mixer: Arc<Mutex<MixerEngine>>,
    effects: Arc<Mutex<Vec<Box<dyn AudioEffect>>>>,
    streamer: Arc<Streamer>,
    devices: DeviceRegistry,
    crowd: SharedCrowdAggregator,
    started_at: Instant,
}

// ---- Main ----

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "koe_hub=info".into()),
        )
        .init();

    let mixer = Arc::new(Mutex::new(MixerEngine::new(32)));
    let effects: Arc<Mutex<Vec<Box<dyn AudioEffect>>>> = Arc::new(Mutex::new(Vec::new()));
    let streamer = Arc::new(Streamer::new());
    let devices = new_device_registry();
    let crowd = new_crowd_aggregator();

    let state = AppState {
        mixer: mixer.clone(),
        effects: effects.clone(),
        streamer: streamer.clone(),
        devices: devices.clone(),
        crowd: crowd.clone(),
        started_at: Instant::now(),
    };

    // Start UDP receivers
    receiver::start_soluna_receiver(mixer.clone(), devices.clone());
    receiver::start_pro_receiver(mixer.clone(), devices.clone());
    receiver::start_crowd_listener(mixer.clone(), crowd.clone());

    // Start the mixer processing loop (128 frames @ 48kHz = every 2.67ms)
    let mix_mixer = mixer.clone();
    let mix_effects = effects.clone();
    let mix_streamer = streamer.clone();
    tokio::spawn(async move {
        let interval_us = (mixer::BUFFER_FRAMES as u64 * 1_000_000) / mixer::SAMPLE_RATE as u64;
        let mut interval = tokio::time::interval(tokio::time::Duration::from_micros(interval_us));
        interval.set_missed_tick_behavior(tokio::time::MissedTickBehavior::Skip);

        loop {
            interval.tick().await;

            let mut output = {
                let mut engine = mix_mixer.lock().unwrap();
                engine.process()
            };

            // Apply master effects chain
            {
                let mut fx = mix_effects.lock().unwrap();
                for effect in fx.iter_mut() {
                    effect.process(&mut output);
                }
            }

            // Broadcast to all output streams
            let _ = mix_streamer.tx.send(Arc::new(output));
        }
    });

    // Build axum router
    let app = Router::new()
        .route("/", get(dashboard))
        .route("/ws/mixer", get(ws_mixer))
        .route("/api/channels", get(api_channels))
        .route("/api/channels/{id}/gain", post(api_set_gain))
        .route("/api/channels/{id}/mute", post(api_toggle_mute))
        .route("/api/channels/{id}/assign", post(api_assign_channel))
        .route("/api/channels/{id}/aux", post(api_set_aux))
        .route("/api/channels/{id}/link", post(api_link_channel))
        .route("/api/master/effect", post(api_set_effect))
        .route("/api/crowd/enable", post(api_crowd_enable))
        .route("/api/crowd/status", get(api_crowd_status))
        .route("/api/crowd/gain", post(api_crowd_gain))
        .route("/api/status", get(api_status))
        .with_state(state);

    let bind = "0.0.0.0:3000";
    info!("Koe Hub starting on {}", bind);
    let listener = tokio::net::TcpListener::bind(bind).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

// ---- Dashboard ----

async fn dashboard() -> Html<&'static str> {
    Html(DASHBOARD_HTML)
}

const DASHBOARD_HTML: &str = r##"<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Koe Hub Mixer — 32ch</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#1a1a2e;color:#e0e0e0;padding:20px}
h1{font-size:1.4rem;margin-bottom:16px;color:#0ff}
.group-tabs{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.group-tab{background:#2a2a4a;border:1px solid #444;color:#ccc;padding:6px 16px;border-radius:4px;cursor:pointer;font-size:.8rem}
.group-tab:hover{background:#3a3a5a}
.group-tab.active{background:#0a4;border-color:#0c6;color:#fff}
.channel-scroll{overflow-x:auto;padding-bottom:8px;margin-bottom:20px}
.channels{display:flex;gap:10px;min-width:min-content}
.ch{background:#16213e;border-radius:8px;padding:10px;text-align:center;position:relative;min-width:110px;flex-shrink:0}
.ch.muted{opacity:0.4}
.ch.linked{border:1px solid #0af}
.ch-name{font-size:.7rem;color:#888;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100px}
.ch-group{font-size:.6rem;color:#555;margin-bottom:4px}
.meter{width:14px;height:80px;background:#0a0a1a;border-radius:4px;margin:0 auto 6px;position:relative;overflow:hidden}
.meter-fill{position:absolute;bottom:0;width:100%;background:linear-gradient(to top,#0f0,#ff0 70%,#f00);border-radius:0 0 4px 4px;transition:height 60ms}
.gain-slider{writing-mode:vertical-lr;direction:rtl;width:100%;height:60px;margin:4px 0}
.pan-knob{width:60px}
.controls{display:flex;gap:4px;justify-content:center;margin-top:4px}
.btn{background:#2a2a4a;border:1px solid #444;color:#ccc;padding:3px 8px;border-radius:4px;cursor:pointer;font-size:.65rem}
.btn:hover{background:#3a3a5a}
.btn.active{background:#0a4;border-color:#0c6;color:#fff}
.aux-sends{margin-top:6px;font-size:.6rem}
.aux-sends label{display:block;margin:2px 0}
.aux-sends input{width:60px;height:12px}
.master{background:#16213e;border-radius:8px;padding:16px;margin-bottom:16px}
.status{background:#16213e;border-radius:8px;padding:16px;font-size:.8rem}
.status span{color:#0ff}
.fx-panel{background:#16213e;border-radius:8px;padding:16px;margin-bottom:16px}
.fx-panel label{font-size:.75rem;display:block;margin:4px 0}
.fx-panel select,.fx-panel input{background:#0a0a1a;border:1px solid #333;color:#e0e0e0;padding:4px;border-radius:4px;width:100%}
</style>
</head>
<body>
<h1>Koe Hub Mixer — 32ch</h1>
<div class="group-tabs" id="group-tabs">
  <div class="group-tab active" onclick="filterGroup('all')">All</div>
  <div class="group-tab" onclick="filterGroup('Instruments')">Instruments (1-8)</div>
  <div class="group-tab" onclick="filterGroup('Vocals')">Vocals (9-16)</div>
  <div class="group-tab" onclick="filterGroup('FX Returns')">FX Returns (17-24)</div>
  <div class="group-tab" onclick="filterGroup('Aux')">Aux (25-32)</div>
</div>
<div class="channel-scroll">
  <div class="channels" id="channels"></div>
</div>
<div class="master">
  <strong>Master</strong>
  <input type="range" min="0" max="200" value="100" id="master-gain"
    style="width:100%;margin-top:8px"
    oninput="document.getElementById('mg-val').textContent=this.value+'%'">
  <span id="mg-val" style="font-size:.75rem">100%</span>
</div>
<div class="master" id="crowd-panel" style="border:1px solid rgba(255,180,50,0.2)">
  <strong style="color:#ffb432">CROWD</strong>
  <div style="display:flex;align-items:center;gap:12px;margin-top:8px;flex-wrap:wrap">
    <label style="font-size:.75rem;display:flex;align-items:center;gap:6px">
      <input type="checkbox" id="crowd-toggle" onchange="toggleCrowd(this.checked)"> Enable
    </label>
    <span style="font-size:.75rem;color:#888">Devices: <span id="crowd-count" style="color:#ffb432">0</span></span>
    <span style="font-size:.75rem;color:#888">Level:</span>
    <div style="width:120px;height:14px;background:#0a0a1a;border-radius:4px;overflow:hidden;position:relative">
      <div id="crowd-meter" style="height:100%;background:linear-gradient(90deg,#ffb432,#ff6b00);width:0%;transition:width 60ms;border-radius:4px"></div>
    </div>
    <span id="crowd-beat" style="font-size:.7rem;color:#333;transition:color 0.1s">BEAT</span>
  </div>
  <div style="margin-top:8px;display:flex;align-items:center;gap:8px">
    <label style="font-size:.75rem">Crowd Gain:</label>
    <input type="range" min="0" max="400" value="100" id="crowd-gain" style="width:160px"
      oninput="setCrowdGain(this.value/100);document.getElementById('cg-val').textContent=(this.value)+'%'">
    <span id="cg-val" style="font-size:.75rem">100%</span>
  </div>
</div>
<div class="fx-panel">
  <strong>Master Effects</strong>
  <label>Effect: <select id="fx-type"><option value="">None</option>
    <option value="reverb">Reverb</option>
    <option value="compressor">Compressor</option>
    <option value="delay">Delay</option>
    <option value="gate">Gate</option>
    <option value="deesser">DeEsser</option>
    <option value="stereo_widener">Stereo Widener</option></select></label>
  <div id="fx-params"></div>
  <button class="btn" onclick="applyEffect()" style="margin-top:8px">Apply</button>
</div>
<div class="status" id="status">Connecting...</div>

<script>
const API = location.origin;
let ws;
let currentGroup = 'all';
let allChannels = [];

const GROUP_RANGES = {
  'Instruments': [0, 7],
  'Vocals': [8, 15],
  'FX Returns': [16, 23],
  'Aux': [24, 31]
};

function getGroupName(id) {
  for (const [name, [lo, hi]] of Object.entries(GROUP_RANGES)) {
    if (id >= lo && id <= hi) return name;
  }
  return '';
}

function filterGroup(group) {
  currentGroup = group;
  document.querySelectorAll('.group-tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  renderChannelsFull(allChannels);
}

function connectWS() {
  ws = new WebSocket(`ws://${location.host}/ws/mixer`);
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'levels') {
      allChannels = data.channels;
      renderChannels(data.channels);
    }
    if (data.type === 'status') renderStatus(data);
  };
  ws.onclose = () => setTimeout(connectWS, 1000);
}

function visibleChannels(chs) {
  if (currentGroup === 'all') {
    // Show only active channels or first 8 if none active
    const active = chs.filter(ch => ch.active || ch.peak > 0.001);
    return active.length > 0 ? chs : chs.slice(0, 8);
  }
  const [lo, hi] = GROUP_RANGES[currentGroup] || [0, 31];
  return chs.filter(ch => ch.id >= lo && ch.id <= hi);
}

function renderChannelsFull(chs) {
  const el = document.getElementById('channels');
  const vis = visibleChannels(chs);
  el.innerHTML = vis.map(ch => {
    const i = ch.id;
    const linked = ch.linked_pair !== null && ch.linked_pair !== undefined;
    return `
      <div class="ch ${ch.mute?'muted':''} ${linked?'linked':''}" id="ch-${i}">
        <div class="ch-group">${getGroupName(i)}</div>
        <div class="ch-name" title="${ch.name}">${ch.name}</div>
        <div class="meter"><div class="meter-fill" id="m-${i}"></div></div>
        <input type="range" class="gain-slider" min="0" max="200" value="${Math.round(ch.gain*100)}"
          oninput="setGain(${i},this.value/100)">
        <div class="controls">
          <button class="btn ${ch.mute?'active':''}" onclick="toggleMute(${i})">M</button>
          <button class="btn ${ch.solo?'active':''}" onclick="toggleSolo(${i})">S</button>
        </div>
        <div class="aux-sends">
          ${[0,1,2,3].map(a => `<label>Aux${a+1}: <input type="range" min="0" max="100" value="${Math.round((ch.aux_sends?.[a]||0)*100)}"
            oninput="setAux(${i},${a},this.value/100)"></label>`).join('')}
        </div>
      </div>`;
  }).join('');
  el._init = true;
  el._ids = vis.map(ch => ch.id);
}

function renderChannels(chs) {
  const el = document.getElementById('channels');
  const vis = visibleChannels(chs);
  if (!el._init || !el._ids || JSON.stringify(el._ids) !== JSON.stringify(vis.map(c=>c.id))) {
    renderChannelsFull(chs);
  } else {
    vis.forEach(ch => {
      const fill = document.getElementById('m-'+ch.id);
      if (fill) fill.style.height = Math.min(ch.peak * 100, 100) + '%';
    });
  }
}

function renderStatus(s) {
  document.getElementById('status').innerHTML =
    `Uptime: <span>${s.uptime_s}s</span> | Active: <span>${s.active_channels}/${s.total_channels}</span> | Buffer: <span>${s.buffer_ms}ms</span>`;
}

async function setGain(id, val) {
  await fetch(`${API}/api/channels/${id}/gain`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({gain: parseFloat(val)})
  });
}

async function toggleMute(id) {
  await fetch(`${API}/api/channels/${id}/mute`, {method:'POST'});
}

function toggleSolo(id) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action:'solo', channel:id}));
}

function setAux(chId, auxIdx, val) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action:'aux_send', channel:chId, aux:auxIdx, value:val}));
}

async function applyEffect() {
  const type = document.getElementById('fx-type').value;
  const params = {effect: type};
  document.querySelectorAll('#fx-params input').forEach(inp => {
    params[inp.name] = parseFloat(inp.value);
  });
  await fetch(`${API}/api/master/effect`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(params)
  });
}

document.getElementById('fx-type').onchange = function() {
  const p = document.getElementById('fx-params');
  const presets = {
    reverb: [{n:'room_size',v:0.5},{n:'damping',v:0.5},{n:'wet',v:0.3}],
    compressor: [{n:'threshold',v:-20},{n:'ratio',v:4},{n:'attack_ms',v:5},{n:'release_ms',v:50}],
    delay: [{n:'time_ms',v:250},{n:'feedback',v:0.3},{n:'wet',v:0.2}],
    gate: [{n:'threshold',v:-40},{n:'ratio',v:2},{n:'attack_ms',v:0.5},{n:'release_ms',v:20},{n:'hold_ms',v:10}],
    deesser: [{n:'frequency',v:6000},{n:'threshold',v:-20},{n:'reduction',v:6}],
    stereo_widener: [{n:'width',v:1.2}]
  };
  const items = presets[this.value] || [];
  p.innerHTML = items.map(i => `<label>${i.n}: <input type="number" name="${i.n}" value="${i.v}" step="0.1"></label>`).join('');
};

document.getElementById('master-gain').oninput = function() {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({action:'master_gain', value: this.value / 100}));
};

async function toggleCrowd(enabled) {
  await fetch(`${API}/api/crowd/enable`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({enabled})
  });
}

async function setCrowdGain(val) {
  await fetch(`${API}/api/crowd/gain`, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({gain: parseFloat(val)})
  });
}

// Poll crowd status at ~5 Hz
setInterval(async () => {
  try {
    const r = await fetch(`${API}/api/crowd/status`);
    const d = await r.json();
    document.getElementById('crowd-count').textContent = d.count;
    document.getElementById('crowd-meter').style.width = Math.min(d.level * 500, 100) + '%';
    document.getElementById('crowd-beat').style.color = d.beat_detected ? '#ffb432' : '#333';
    document.getElementById('crowd-toggle').checked = d.enabled;
  } catch(e) {}
}, 200);

connectWS();
</script>
</body>
</html>
"##;

// ---- WebSocket handler ----

async fn ws_mixer(ws: WebSocketUpgrade, State(state): State<AppState>) -> impl IntoResponse {
    ws.on_upgrade(|socket| handle_ws_mixer(socket, state))
}

async fn handle_ws_mixer(socket: WebSocket, state: AppState) {
    let (mut sender, mut receiver) = socket.split();

    // Spawn a task that sends level updates at ~30 Hz
    let meter_state = state.clone();
    let send_task = tokio::spawn(async move {
        let mut interval = tokio::time::interval(tokio::time::Duration::from_millis(33));
        loop {
            interval.tick().await;
            let msg = {
                let engine = meter_state.mixer.lock().unwrap();
                let channels: Vec<serde_json::Value> = engine.channels.iter()
                    .map(|ch| {
                        json!({
                            "id": ch.id,
                            "name": ch.name,
                            "gain": ch.gain,
                            "pan": ch.pan,
                            "mute": ch.mute,
                            "solo": ch.solo,
                            "peak": ch.peak_level,
                            "active": ch.active.load(std::sync::atomic::Ordering::Relaxed),
                            "eq_low": ch.eq_low,
                            "eq_mid": ch.eq_mid,
                            "eq_high": ch.eq_high,
                            "aux_sends": ch.aux_sends,
                            "linked_pair": ch.linked_pair,
                        })
                    }).collect();

                json!({
                    "type": "levels",
                    "channels": channels,
                    "master_gain": engine.master_gain,
                })
            };

            if sender.send(Message::Text(msg.to_string().into())).await.is_err() {
                break;
            }
        }
    });

    // Receive control commands from the client
    let ctrl_state = state.clone();
    while let Some(Ok(msg)) = receiver.next().await {
        if let Message::Text(text) = msg {
            if let Ok(cmd) = serde_json::from_str::<serde_json::Value>(&text) {
                let action = cmd.get("action").and_then(|v| v.as_str()).unwrap_or("");
                match action {
                    "master_gain" => {
                        if let Some(val) = cmd.get("value").and_then(|v| v.as_f64()) {
                            let mut engine = ctrl_state.mixer.lock().unwrap();
                            engine.master_gain = val as f32;
                        }
                    }
                    "solo" => {
                        if let Some(ch_id) = cmd.get("channel").and_then(|v| v.as_u64()) {
                            let mut engine = ctrl_state.mixer.lock().unwrap();
                            if let Some(ch) = engine.channels.get_mut(ch_id as usize) {
                                ch.solo = !ch.solo;
                            }
                        }
                    }
                    "eq" => {
                        if let (Some(ch_id), Some(band), Some(val)) = (
                            cmd.get("channel").and_then(|v| v.as_u64()),
                            cmd.get("band").and_then(|v| v.as_str()),
                            cmd.get("value").and_then(|v| v.as_f64()),
                        ) {
                            let mut engine = ctrl_state.mixer.lock().unwrap();
                            if let Some(ch) = engine.channels.get_mut(ch_id as usize) {
                                match band {
                                    "low" => ch.eq_low = val as f32,
                                    "mid" => ch.eq_mid = val as f32,
                                    "high" => ch.eq_high = val as f32,
                                    _ => {}
                                }
                            }
                        }
                    }
                    "pan" => {
                        if let (Some(ch_id), Some(val)) = (
                            cmd.get("channel").and_then(|v| v.as_u64()),
                            cmd.get("value").and_then(|v| v.as_f64()),
                        ) {
                            let mut engine = ctrl_state.mixer.lock().unwrap();
                            if let Some(ch) = engine.channels.get_mut(ch_id as usize) {
                                ch.pan = (val as f32).clamp(-1.0, 1.0);
                            }
                        }
                    }
                    "aux_send" => {
                        if let (Some(ch_id), Some(aux_idx), Some(val)) = (
                            cmd.get("channel").and_then(|v| v.as_u64()),
                            cmd.get("aux").and_then(|v| v.as_u64()),
                            cmd.get("value").and_then(|v| v.as_f64()),
                        ) {
                            let mut engine = ctrl_state.mixer.lock().unwrap();
                            let ch_id = ch_id as usize;
                            let aux_idx = aux_idx as usize;
                            if let Some(ch) = engine.channels.get_mut(ch_id) {
                                if aux_idx < mixer::AUX_BUS_COUNT {
                                    ch.aux_sends[aux_idx] = (val as f32).clamp(0.0, 1.0);
                                }
                            }
                        }
                    }
                    "link_stereo" => {
                        if let (Some(ch_a), Some(ch_b)) = (
                            cmd.get("channel_a").and_then(|v| v.as_u64()),
                            cmd.get("channel_b").and_then(|v| v.as_u64()),
                        ) {
                            let mut engine = ctrl_state.mixer.lock().unwrap();
                            engine.link_stereo(ch_a as usize, ch_b as usize);
                        }
                    }
                    "unlink_stereo" => {
                        if let Some(ch_id) = cmd.get("channel").and_then(|v| v.as_u64()) {
                            let mut engine = ctrl_state.mixer.lock().unwrap();
                            engine.unlink_stereo(ch_id as usize);
                        }
                    }
                    _ => {}
                }
            }
        }
    }

    send_task.abort();
}

// ---- REST API handlers ----

#[derive(Serialize)]
struct ChannelInfo {
    id: usize,
    name: String,
    gain: f32,
    pan: f32,
    mute: bool,
    solo: bool,
    eq_low: f32,
    eq_mid: f32,
    eq_high: f32,
    peak_level: f32,
    active: bool,
    aux_sends: [f32; 4],
    linked_pair: Option<usize>,
    group: String,
    pre_fader_insert: Option<usize>,
    post_fader_insert: Option<usize>,
}

async fn api_channels(State(state): State<AppState>) -> impl IntoResponse {
    let engine = state.mixer.lock().unwrap();
    let channels: Vec<ChannelInfo> = engine.channels.iter().map(|ch| ChannelInfo {
        id: ch.id,
        name: ch.name.clone(),
        gain: ch.gain,
        pan: ch.pan,
        mute: ch.mute,
        solo: ch.solo,
        eq_low: ch.eq_low,
        eq_mid: ch.eq_mid,
        eq_high: ch.eq_high,
        peak_level: ch.peak_level,
        active: ch.active.load(std::sync::atomic::Ordering::Relaxed),
        aux_sends: ch.aux_sends,
        linked_pair: ch.linked_pair,
        group: engine.channel_group_name(ch.id).to_string(),
        pre_fader_insert: ch.pre_fader_insert,
        post_fader_insert: ch.post_fader_insert,
    }).collect();

    let groups: Vec<serde_json::Value> = engine.groups.iter().map(|g| {
        json!({
            "name": g.name,
            "channels": g.channels,
            "group_gain": g.group_gain,
            "group_mute": g.group_mute,
        })
    }).collect();

    axum::Json(json!({ "channels": channels, "groups": groups }))
}

#[derive(Deserialize)]
struct GainBody {
    gain: f32,
}

async fn api_set_gain(
    Path(id): Path<usize>,
    State(state): State<AppState>,
    axum::Json(body): axum::Json<GainBody>,
) -> impl IntoResponse {
    let mut engine = state.mixer.lock().unwrap();
    if let Some(ch) = engine.channels.get_mut(id) {
        ch.gain = body.gain.clamp(0.0, 4.0);
        (StatusCode::OK, axum::Json(json!({ "ok": true, "gain": ch.gain })))
    } else {
        (StatusCode::NOT_FOUND, axum::Json(json!({ "error": "channel not found" })))
    }
}

async fn api_toggle_mute(
    Path(id): Path<usize>,
    State(state): State<AppState>,
) -> impl IntoResponse {
    let mut engine = state.mixer.lock().unwrap();
    if let Some(ch) = engine.channels.get_mut(id) {
        ch.mute = !ch.mute;
        (StatusCode::OK, axum::Json(json!({ "ok": true, "mute": ch.mute })))
    } else {
        (StatusCode::NOT_FOUND, axum::Json(json!({ "error": "channel not found" })))
    }
}

#[derive(Deserialize)]
struct AssignBody {
    device_hash: String,
    name: String,
}

async fn api_assign_channel(
    Path(id): Path<usize>,
    State(state): State<AppState>,
    axum::Json(body): axum::Json<AssignBody>,
) -> impl IntoResponse {
    let hash = u32::from_str_radix(body.device_hash.trim_start_matches("0x"), 16)
        .unwrap_or(0);
    if hash == 0 {
        return (StatusCode::BAD_REQUEST, axum::Json(json!({ "error": "invalid device_hash" })));
    }
    match receiver::assign_device_to_channel(&state.devices, &state.mixer, id, hash, body.name.clone()) {
        Ok(()) => (StatusCode::OK, axum::Json(json!({ "ok": true, "channel": id, "name": body.name }))),
        Err(e) => (StatusCode::BAD_REQUEST, axum::Json(json!({ "error": e }))),
    }
}

#[derive(Deserialize)]
struct AuxBody {
    aux: usize,
    level: f32,
}

async fn api_set_aux(
    Path(id): Path<usize>,
    State(state): State<AppState>,
    axum::Json(body): axum::Json<AuxBody>,
) -> impl IntoResponse {
    let mut engine = state.mixer.lock().unwrap();
    if let Some(ch) = engine.channels.get_mut(id) {
        if body.aux < mixer::AUX_BUS_COUNT {
            ch.aux_sends[body.aux] = body.level.clamp(0.0, 1.0);
            (StatusCode::OK, axum::Json(json!({ "ok": true })))
        } else {
            (StatusCode::BAD_REQUEST, axum::Json(json!({ "error": "aux index out of range" })))
        }
    } else {
        (StatusCode::NOT_FOUND, axum::Json(json!({ "error": "channel not found" })))
    }
}

#[derive(Deserialize)]
struct LinkBody {
    partner: Option<usize>,
}

async fn api_link_channel(
    Path(id): Path<usize>,
    State(state): State<AppState>,
    axum::Json(body): axum::Json<LinkBody>,
) -> impl IntoResponse {
    let mut engine = state.mixer.lock().unwrap();
    match body.partner {
        Some(partner) => {
            engine.link_stereo(id, partner);
            (StatusCode::OK, axum::Json(json!({ "ok": true, "linked": [id, partner] })))
        }
        None => {
            engine.unlink_stereo(id);
            (StatusCode::OK, axum::Json(json!({ "ok": true, "unlinked": id })))
        }
    }
}

async fn api_set_effect(
    State(state): State<AppState>,
    axum::Json(params): axum::Json<EffectParams>,
) -> impl IntoResponse {
    let mut effects = state.effects.lock().unwrap();
    effects.clear(); // Replace entire chain

    match params.effect.as_str() {
        "reverb" => {
            let room = params.room_size.unwrap_or(0.5);
            let damp = params.damping.unwrap_or(0.5);
            let wet = params.wet.unwrap_or(0.3);
            effects.push(Box::new(Reverb::new(room, damp, wet)));
            (StatusCode::OK, axum::Json(json!({ "ok": true, "effect": "reverb" })))
        }
        "compressor" => {
            let mut comp = Compressor::new(
                params.threshold.unwrap_or(-20.0),
                params.ratio.unwrap_or(4.0),
                params.attack_ms.unwrap_or(5.0),
                params.release_ms.unwrap_or(50.0),
            );
            if let Some(mg) = params.makeup_gain {
                comp.makeup_gain = mg;
            }
            effects.push(Box::new(comp));
            (StatusCode::OK, axum::Json(json!({ "ok": true, "effect": "compressor" })))
        }
        "delay" => {
            let delay = Delay::new(
                params.time_ms.unwrap_or(250.0),
                params.feedback.unwrap_or(0.3),
                params.wet.unwrap_or(0.2),
            );
            effects.push(Box::new(delay));
            (StatusCode::OK, axum::Json(json!({ "ok": true, "effect": "delay" })))
        }
        "gate" => {
            let gate = Gate::new(
                params.threshold.unwrap_or(-40.0),
                params.ratio.unwrap_or(2.0),
                params.attack_ms.unwrap_or(0.5),
                params.release_ms.unwrap_or(20.0),
                params.hold_ms.unwrap_or(10.0),
            );
            effects.push(Box::new(gate));
            (StatusCode::OK, axum::Json(json!({ "ok": true, "effect": "gate" })))
        }
        "deesser" => {
            let deesser = DeEsser::new(
                params.frequency.unwrap_or(6000.0),
                params.threshold.unwrap_or(-20.0),
                params.reduction.unwrap_or(6.0),
            );
            effects.push(Box::new(deesser));
            (StatusCode::OK, axum::Json(json!({ "ok": true, "effect": "deesser" })))
        }
        "stereo_widener" => {
            let widener = StereoWidener::new(
                params.width.unwrap_or(1.2),
            );
            effects.push(Box::new(widener));
            (StatusCode::OK, axum::Json(json!({ "ok": true, "effect": "stereo_widener" })))
        }
        "" => {
            // Clear all effects
            (StatusCode::OK, axum::Json(json!({ "ok": true, "effect": "none" })))
        }
        other => {
            (StatusCode::BAD_REQUEST, axum::Json(json!({ "error": format!("unknown effect: {}", other) })))
        }
    }
}

// ---- Crowd Voice API handlers ----

#[derive(Deserialize)]
struct CrowdEnableBody {
    enabled: bool,
}

async fn api_crowd_enable(
    State(state): State<AppState>,
    axum::Json(body): axum::Json<CrowdEnableBody>,
) -> impl IntoResponse {
    let agg = state.crowd.lock().unwrap();
    agg.set_enabled(body.enabled);
    info!(enabled = body.enabled, "Crowd voice toggled");
    axum::Json(json!({ "ok": true, "enabled": body.enabled }))
}

async fn api_crowd_status(State(state): State<AppState>) -> impl IntoResponse {
    let agg = state.crowd.lock().unwrap();
    axum::Json(json!({
        "enabled": agg.is_enabled(),
        "count": agg.get_crowd_count(),
        "level": agg.get_crowd_level(),
        "gain": agg.get_gain(),
        "beat_detected": agg.is_beat_detected(),
    }))
}

#[derive(Deserialize)]
struct CrowdGainBody {
    gain: f32,
}

async fn api_crowd_gain(
    State(state): State<AppState>,
    axum::Json(body): axum::Json<CrowdGainBody>,
) -> impl IntoResponse {
    let agg = state.crowd.lock().unwrap();
    agg.set_gain(body.gain);
    axum::Json(json!({ "ok": true, "gain": agg.get_gain() }))
}

async fn api_status(State(state): State<AppState>) -> impl IntoResponse {
    let uptime = state.started_at.elapsed().as_secs();
    let engine = state.mixer.lock().unwrap();
    let active = engine.channels.iter()
        .filter(|ch| ch.active.load(std::sync::atomic::Ordering::Relaxed))
        .count();
    let buffer_ms = (engine.buffer_size as f64 / engine.sample_rate as f64) * 1000.0;

    let devices = state.devices.lock().unwrap();
    let device_count = devices.len();

    let crowd_agg = state.crowd.lock().unwrap();
    let crowd_count = crowd_agg.get_crowd_count();
    let crowd_enabled = crowd_agg.is_enabled();
    let crowd_level = crowd_agg.get_crowd_level();
    drop(crowd_agg);

    axum::Json(json!({
        "type": "status",
        "uptime_s": uptime,
        "active_channels": active,
        "total_channels": engine.channels.len(),
        "connected_devices": device_count,
        "sample_rate": engine.sample_rate,
        "buffer_frames": engine.buffer_size,
        "buffer_ms": format!("{:.2}", buffer_ms),
        "master_gain": engine.master_gain,
        "crowd_enabled": crowd_enabled,
        "crowd_count": crowd_count,
        "crowd_level": crowd_level,
    }))
}
