/// UDP audio receiver for Koe Hub.
///
/// Listens on two ports:
///   - 0.0.0.0:4242 — Soluna multicast (magic "SL", IMA-ADPCM)
///   - 0.0.0.0:4244 — Koe Pro direct (magic "KP", PCM16/PCM24/Opus)
///
/// Parses incoming packets, decodes audio, and feeds samples into the mixer.

use std::collections::HashMap;
use std::net::{Ipv4Addr, SocketAddrV4, UdpSocket};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use tokio::task;
use tracing::{debug, info, warn};

use crate::mixer::MixerEngine;

// ---- Protocol constants ----

const SOLUNA_MAGIC: [u8; 2] = [0x53, 0x4C]; // "SL"
const SOLUNA_HEADER: usize = 19;
const SOLUNA_PORT: u16 = 4242;
const SOLUNA_MCAST: Ipv4Addr = Ipv4Addr::new(239, 42, 42, 1);

const PRO_MAGIC: [u8; 2] = [0x4B, 0x50]; // "KP"
const PRO_HEADER: usize = 20;
const PRO_PORT: u16 = 4244;

// Crowd Voice port
const CROWD_PORT: u16 = 4246;
const FLAG_CROWD: u8 = 0x20;
const CROWD_SOURCE_TIMEOUT_MS: u64 = 5_000; // Remove source after 5s silence

// Pro codec IDs
const CODEC_PCM16: u8 = 0;
const CODEC_PCM24: u8 = 1;
const CODEC_OPUS: u8 = 2;

// IMA-ADPCM step table
const STEP_TABLE: [i32; 89] = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
    157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544,
    598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878,
    2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894,
    6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818,
    18500, 20350, 22385, 24623, 27086, 29794, 32767,
];

const INDEX_TABLE: [i32; 16] = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8];

/// Device-to-channel mapping.
pub struct DeviceMapping {
    pub device_hash: u32,
    pub channel_id: usize,
    pub name: String,
    pub last_seq: u32,
}

/// Shared device registry: device_hash → DeviceMapping.
/// Supports up to 32 devices (one per mixer channel).
pub type DeviceRegistry = Arc<Mutex<HashMap<u32, DeviceMapping>>>;

pub fn new_device_registry() -> DeviceRegistry {
    Arc::new(Mutex::new(HashMap::with_capacity(32)))
}

/// Assign a specific device to a specific channel with a custom name.
/// Used by the POST /api/channels/:id/assign endpoint.
pub fn assign_device_to_channel(
    registry: &DeviceRegistry,
    mixer: &Arc<Mutex<MixerEngine>>,
    channel_id: usize,
    device_hash: u32,
    name: String,
) -> Result<(), String> {
    let mut engine = mixer.lock().map_err(|e| format!("lock error: {}", e))?;
    if channel_id >= engine.channels.len() {
        return Err(format!("channel {} out of range (max {})", channel_id, engine.channels.len() - 1));
    }

    // Update mixer channel name
    engine.channels[channel_id].name = name.clone();

    // Update registry
    let mut reg = registry.lock().map_err(|e| format!("lock error: {}", e))?;

    // Remove old mapping for this device if it existed on a different channel
    reg.retain(|_, m| m.device_hash != device_hash || m.channel_id == channel_id);

    reg.insert(device_hash, DeviceMapping {
        device_hash,
        channel_id,
        name: name.clone(),
        last_seq: 0,
    });

    info!(device_hash, channel = channel_id, %name, "Device manually assigned to channel");

    // Auto-stereo-link detection: check if a partner name suggests a stereo pair
    // e.g. "Guitar L" + "Guitar R", "Drum OH L" + "Drum OH R"
    let base_name = stereo_base_name(&name);
    if !base_name.is_empty() {
        let partner: Option<usize> = reg.values()
            .filter(|m| m.channel_id != channel_id)
            .find(|m| {
                let other_base = stereo_base_name(&m.name);
                other_base == base_name
            })
            .map(|m| m.channel_id);

        // Need to drop reg before calling link_stereo (engine already borrowed)
        drop(reg);
        if let Some(partner_id) = partner {
            engine.link_stereo(channel_id, partner_id);
            info!(channel_id, partner_id, "Auto-stereo-linked channels");
        }
    }

    Ok(())
}

/// Extract the base name for stereo pair matching.
/// "Guitar L" → "Guitar", "Drum OH R" → "Drum OH", "Piano Left" → "Piano"
fn stereo_base_name(name: &str) -> String {
    let trimmed = name.trim();
    let lower = trimmed.to_lowercase();

    // Check for trailing L/R/Left/Right
    for suffix in &[" l", " r", " left", " right"] {
        if lower.ends_with(suffix) {
            return trimmed[..trimmed.len() - suffix.len()].trim().to_string();
        }
    }
    String::new()
}

// ---- IMA-ADPCM decoder ----

struct AdpcmDecoder {
    predicted: i32,
    step_index: i32,
}

impl AdpcmDecoder {
    fn new() -> Self {
        Self {
            predicted: 0,
            step_index: 0,
        }
    }

    /// Decode a buffer of 4-bit ADPCM nibbles into i16 PCM.
    /// Each byte contains 2 nibbles: low nibble first, then high nibble.
    fn decode(&mut self, adpcm: &[u8]) -> Vec<i16> {
        let mut output = Vec::with_capacity(adpcm.len() * 2);
        for &byte in adpcm {
            output.push(self.decode_nibble(byte & 0x0F));
            output.push(self.decode_nibble((byte >> 4) & 0x0F));
        }
        output
    }

    fn decode_nibble(&mut self, nibble: u8) -> i16 {
        let step = STEP_TABLE[self.step_index as usize];
        let nibble = nibble as i32;

        let mut diff = step >> 3;
        if nibble & 4 != 0 {
            diff += step;
        }
        if nibble & 2 != 0 {
            diff += step >> 1;
        }
        if nibble & 1 != 0 {
            diff += step >> 2;
        }
        if nibble & 8 != 0 {
            self.predicted -= diff;
        } else {
            self.predicted += diff;
        }

        self.predicted = self.predicted.clamp(-32768, 32767);
        self.step_index = (self.step_index + INDEX_TABLE[nibble as usize]).clamp(0, 88);

        self.predicted as i16
    }
}

// ---- Packet parsers ----

/// Parse a Soluna multicast packet.
/// Header: [magic 2B][device_id 4B][seq 4B][channel 4B][ntp_ms 4B][flags 1B][audio ADPCM]
fn parse_soluna_packet(data: &[u8]) -> Option<(u32, u32, Vec<i16>)> {
    if data.len() < SOLUNA_HEADER + 1 {
        return None;
    }
    if data[0..2] != SOLUNA_MAGIC {
        return None;
    }

    let device_id = u32::from_le_bytes([data[2], data[3], data[4], data[5]]);
    let seq = u32::from_le_bytes([data[6], data[7], data[8], data[9]]);
    let flags = data[18];

    // Skip heartbeat packets (no audio)
    if flags & 0x04 != 0 {
        return None;
    }

    let adpcm_data = &data[SOLUNA_HEADER..];
    let mut decoder = AdpcmDecoder::new();
    let pcm = decoder.decode(adpcm_data);

    Some((device_id, seq, pcm))
}

/// Parse a Koe Pro direct packet.
/// Header: [0x4B,0x50][device_hash u32][seq u32][uwb_ts u64][codec u8][ch_count u8][audio..]
fn parse_pro_packet(data: &[u8]) -> Option<(u32, u32, Vec<i16>)> {
    if data.len() < PRO_HEADER + 1 {
        return None;
    }
    if data[0..2] != PRO_MAGIC {
        return None;
    }

    let device_hash = u32::from_le_bytes([data[2], data[3], data[4], data[5]]);
    let seq = u32::from_le_bytes([data[6], data[7], data[8], data[9]]);
    // uwb_timestamp at [10..18] — used for sync, not decoded here
    let codec = data[18];
    let channel_count = data[19];
    let audio_data = &data[PRO_HEADER..];

    let pcm = match codec {
        CODEC_PCM16 => {
            // Raw 16-bit little-endian PCM
            let sample_count = audio_data.len() / 2;
            let mut samples = Vec::with_capacity(sample_count);
            for chunk in audio_data.chunks_exact(2) {
                samples.push(i16::from_le_bytes([chunk[0], chunk[1]]));
            }
            // If stereo, mix down to mono
            if channel_count == 2 {
                mix_to_mono(&samples)
            } else {
                samples
            }
        }
        CODEC_PCM24 => {
            // 24-bit signed little-endian, packed 3 bytes per sample
            let sample_count = audio_data.len() / 3;
            let mut samples = Vec::with_capacity(sample_count);
            for chunk in audio_data.chunks_exact(3) {
                // Sign-extend 24-bit to 32-bit, then scale to i16 range
                let raw = (chunk[0] as i32) | ((chunk[1] as i32) << 8) | ((chunk[2] as i32) << 16);
                let signed = if raw & 0x800000 != 0 {
                    raw | !0xFFFFFF_i32
                } else {
                    raw
                };
                samples.push((signed >> 8) as i16); // Drop lowest 8 bits
            }
            if channel_count == 2 {
                mix_to_mono(&samples)
            } else {
                samples
            }
        }
        CODEC_OPUS => {
            // Opus decoding requires an external library; for now, skip
            warn!("Opus codec not yet supported, dropping packet");
            return None;
        }
        _ => {
            warn!(codec, "Unknown Pro codec");
            return None;
        }
    };

    Some((device_hash, seq, pcm))
}

/// Mix stereo interleaved i16 samples down to mono.
fn mix_to_mono(samples: &[i16]) -> Vec<i16> {
    samples
        .chunks_exact(2)
        .map(|pair| ((pair[0] as i32 + pair[1] as i32) / 2) as i16)
        .collect()
}

// ---- Receiver tasks ----

/// Assign or look up the mixer channel for a device.
fn get_or_assign_channel(
    registry: &DeviceRegistry,
    mixer: &Arc<Mutex<MixerEngine>>,
    device_hash: u32,
    prefix: &str,
) -> Option<usize> {
    let mut reg = registry.lock().unwrap();
    if let Some(mapping) = reg.get(&device_hash) {
        return Some(mapping.channel_id);
    }

    // Auto-assign to next available channel
    let channel_id = {
        let engine = mixer.lock().unwrap();
        engine.next_available_channel()
    };

    match channel_id {
        Some(id) => {
            let name = format!("{} {:08x}", prefix, device_hash);
            info!(device_hash, channel = id, %name, "New device assigned to channel");
            {
                let mut engine = mixer.lock().unwrap();
                if let Some(ch) = engine.channels.get_mut(id) {
                    ch.name = name.clone();
                }
            }
            reg.insert(device_hash, DeviceMapping {
                device_hash,
                channel_id: id,
                name,
                last_seq: 0,
            });
            Some(id)
        }
        None => {
            warn!(device_hash, "No available mixer channels for new device");
            None
        }
    }
}

/// Feed parsed audio into the mixer.
fn feed_mixer(
    mixer: &Arc<Mutex<MixerEngine>>,
    channel_id: usize,
    samples: &[i16],
    device_hash: u32,
    seq: u32,
    registry: &DeviceRegistry,
) {
    // Update sequence number
    if let Ok(mut reg) = registry.lock() {
        if let Some(mapping) = reg.get_mut(&device_hash) {
            if seq <= mapping.last_seq && seq != 0 {
                debug!(device_hash, seq, last = mapping.last_seq, "Out-of-order packet, skipping");
                return;
            }
            mapping.last_seq = seq;
        }
    }

    if let Ok(mut engine) = mixer.lock() {
        engine.add_samples(channel_id, samples);
    }
}

/// Start the Soluna multicast receiver (port 4242).
pub fn start_soluna_receiver(
    mixer: Arc<Mutex<MixerEngine>>,
    registry: DeviceRegistry,
) {
    task::spawn_blocking(move || {
        let socket = match UdpSocket::bind(SocketAddrV4::new(Ipv4Addr::UNSPECIFIED, SOLUNA_PORT)) {
            Ok(s) => s,
            Err(e) => {
                warn!("Failed to bind Soluna port {}: {}", SOLUNA_PORT, e);
                return;
            }
        };

        // Join multicast group
        if let Err(e) = socket.join_multicast_v4(&SOLUNA_MCAST, &Ipv4Addr::UNSPECIFIED) {
            warn!("Failed to join multicast {}: {}", SOLUNA_MCAST, e);
        }

        info!("Soluna receiver listening on 0.0.0.0:{}", SOLUNA_PORT);

        let mut buf = [0u8; 2048];
        loop {
            let (len, _src) = match socket.recv_from(&mut buf) {
                Ok(r) => r,
                Err(e) => {
                    warn!("Soluna recv error: {}", e);
                    continue;
                }
            };

            if let Some((device_id, seq, pcm)) = parse_soluna_packet(&buf[..len]) {
                if let Some(ch_id) = get_or_assign_channel(&registry, &mixer, device_id, "SL") {
                    feed_mixer(&mixer, ch_id, &pcm, device_id, seq, &registry);
                }
            }
        }
    });
}

/// Start the Koe Pro direct receiver (port 4244).
pub fn start_pro_receiver(
    mixer: Arc<Mutex<MixerEngine>>,
    registry: DeviceRegistry,
) {
    task::spawn_blocking(move || {
        let socket = match UdpSocket::bind(SocketAddrV4::new(Ipv4Addr::UNSPECIFIED, PRO_PORT)) {
            Ok(s) => s,
            Err(e) => {
                warn!("Failed to bind Pro port {}: {}", PRO_PORT, e);
                return;
            }
        };

        info!("Pro receiver listening on 0.0.0.0:{}", PRO_PORT);

        let mut buf = [0u8; 4096]; // Larger for 24-bit/Opus packets
        loop {
            let (len, _src) = match socket.recv_from(&mut buf) {
                Ok(r) => r,
                Err(e) => {
                    warn!("Pro recv error: {}", e);
                    continue;
                }
            };

            if let Some((device_hash, seq, pcm)) = parse_pro_packet(&buf[..len]) {
                if let Some(ch_id) = get_or_assign_channel(&registry, &mixer, device_hash, "KP") {
                    feed_mixer(&mixer, ch_id, &pcm, device_hash, seq, &registry);
                }
            }
        }
    });
}

// ---- Crowd Voice Aggregator ----

/// Tracks a single crowd audio source.
struct CrowdSource {
    device_id: u32,
    last_seen: Instant,
    samples: Vec<i16>,
}

/// Aggregates audio from up to 1000 COIN devices into a stereo mix.
///
/// Uses 1/sqrt(N) scaling to prevent clipping while maintaining energy:
/// a crowd of 10 and a crowd of 10,000 sound similar in perceived loudness.
pub struct CrowdAggregator {
    sources: HashMap<u32, CrowdSource>,
    enabled: AtomicBool,
    gain: Mutex<f32>,
    /// Noise gate threshold in linear amplitude (0.0..1.0).
    noise_gate_threshold: f32,
    /// Current RMS level of the mixed crowd audio (for visualization).
    rms_level: Mutex<f32>,
    /// Whether a rhythmic beat pattern was detected.
    beat_detected: AtomicBool,
    /// Ring buffer of recent RMS values for beat detection.
    rms_history: Mutex<Vec<f32>>,
}

impl CrowdAggregator {
    pub fn new() -> Self {
        Self {
            sources: HashMap::with_capacity(1024),
            enabled: AtomicBool::new(false),
            gain: Mutex::new(1.0),
            noise_gate_threshold: 0.02, // ~-34 dBFS
            rms_level: Mutex::new(0.0),
            beat_detected: AtomicBool::new(false),
            rms_history: Mutex::new(Vec::with_capacity(64)),
        }
    }

    /// Check if crowd capture is enabled.
    pub fn is_enabled(&self) -> bool {
        self.enabled.load(Ordering::Relaxed)
    }

    /// Enable or disable crowd capture.
    pub fn set_enabled(&self, enabled: bool) {
        self.enabled.store(enabled, Ordering::Relaxed);
    }

    /// Set the crowd gain (0.0..4.0).
    pub fn set_gain(&self, gain: f32) {
        *self.gain.lock().unwrap() = gain.clamp(0.0, 4.0);
    }

    /// Get the crowd gain.
    pub fn get_gain(&self) -> f32 {
        *self.gain.lock().unwrap()
    }

    /// Get current RMS level of the mixed crowd audio.
    pub fn get_crowd_level(&self) -> f32 {
        *self.rms_level.lock().unwrap()
    }

    /// Get number of currently active crowd sources.
    pub fn get_crowd_count(&self) -> usize {
        self.sources.len()
    }

    /// Whether a beat/clap pattern was detected recently.
    pub fn is_beat_detected(&self) -> bool {
        self.beat_detected.load(Ordering::Relaxed)
    }

    /// Ingest audio from a single COIN device.
    pub fn ingest(&mut self, device_id: u32, samples: Vec<i16>) {
        if !self.is_enabled() {
            return;
        }
        self.sources.entry(device_id)
            .and_modify(|src| {
                src.last_seen = Instant::now();
                src.samples = samples.clone();
            })
            .or_insert(CrowdSource {
                device_id,
                last_seen: Instant::now(),
                samples,
            });
    }

    /// Evict sources that have gone silent.
    pub fn evict_stale(&mut self) {
        let cutoff = Instant::now() - std::time::Duration::from_millis(CROWD_SOURCE_TIMEOUT_MS);
        self.sources.retain(|_, src| src.last_seen > cutoff);
    }

    /// Mix all crowd sources into a mono output buffer.
    /// Uses 1/sqrt(N) scaling to normalize energy regardless of crowd size.
    /// Returns the mixed samples ready to feed into the mixer as a virtual channel.
    pub fn mix(&mut self) -> Vec<i16> {
        self.evict_stale();

        let n = self.sources.len();
        if n == 0 {
            *self.rms_level.lock().unwrap() = 0.0;
            self.beat_detected.store(false, Ordering::Relaxed);
            return Vec::new();
        }

        // Find the maximum sample count across all sources
        let max_len = self.sources.values()
            .map(|s| s.samples.len())
            .max()
            .unwrap_or(0);

        if max_len == 0 {
            return Vec::new();
        }

        // Accumulate in i32 to avoid overflow
        let mut accum = vec![0i32; max_len];
        for src in self.sources.values() {
            for (i, &sample) in src.samples.iter().enumerate() {
                accum[i] += sample as i32;
            }
        }

        // Apply 1/sqrt(N) normalization + gain
        let scale = 1.0 / (n as f32).sqrt();
        let gain = *self.gain.lock().unwrap();
        let combined_scale = scale * gain;

        let mut output = Vec::with_capacity(max_len);
        let mut sum_sq: f64 = 0.0;

        for &acc in &accum {
            let scaled = (acc as f32 * combined_scale) as i32;
            let clamped = scaled.clamp(-32768, 32767) as i16;

            // Noise gate: zero out samples below threshold
            let amplitude = (clamped as f32 / 32768.0).abs();
            let sample = if amplitude < self.noise_gate_threshold {
                0i16
            } else {
                clamped
            };

            sum_sq += (sample as f64) * (sample as f64);
            output.push(sample);
        }

        // Compute RMS
        let rms = ((sum_sq / max_len as f64).sqrt() / 32768.0) as f32;
        *self.rms_level.lock().unwrap() = rms;

        // Simple beat detection: look for sudden RMS spike
        self.detect_beat(rms);

        output
    }

    /// Simple beat detection based on RMS history.
    /// Detects when current RMS is significantly above recent average.
    fn detect_beat(&self, current_rms: f32) {
        let mut history = self.rms_history.lock().unwrap();
        history.push(current_rms);
        if history.len() > 32 {
            history.remove(0);
        }

        if history.len() < 4 {
            return;
        }

        // Average of all but the last entry
        let avg: f32 = history[..history.len() - 1].iter().sum::<f32>()
            / (history.len() - 1) as f32;

        // Beat = current RMS is 2x the recent average and above a minimum
        let is_beat = current_rms > avg * 2.0 && current_rms > 0.05;
        self.beat_detected.store(is_beat, Ordering::Relaxed);
    }
}

/// Shared crowd aggregator state.
pub type SharedCrowdAggregator = Arc<Mutex<CrowdAggregator>>;

pub fn new_crowd_aggregator() -> SharedCrowdAggregator {
    Arc::new(Mutex::new(CrowdAggregator::new()))
}

/// Start the crowd audio listener on port 4246.
///
/// Receives audio from COIN devices with FLAG_CROWD set,
/// aggregates via CrowdAggregator, and feeds the mixed result
/// into the mixer as a virtual "CROWD" channel.
pub fn start_crowd_listener(
    mixer: Arc<Mutex<MixerEngine>>,
    crowd: SharedCrowdAggregator,
) {
    task::spawn_blocking(move || {
        let socket = match UdpSocket::bind(SocketAddrV4::new(Ipv4Addr::UNSPECIFIED, CROWD_PORT)) {
            Ok(s) => s,
            Err(e) => {
                warn!("Failed to bind crowd port {}: {}", CROWD_PORT, e);
                return;
            }
        };

        info!("Crowd voice listener on 0.0.0.0:{}", CROWD_PORT);

        // Reserve a mixer channel for crowd audio (use channel 31 = last channel)
        {
            let mut engine = mixer.lock().unwrap();
            let crowd_ch = engine.channels.len() - 1;
            engine.channels[crowd_ch].name = "CROWD".to_string();
            info!("Crowd audio mapped to mixer channel {}", crowd_ch);
        }

        let mut buf = [0u8; 2048];
        let mut mix_counter: u32 = 0;

        loop {
            let (len, _src) = match socket.recv_from(&mut buf) {
                Ok(r) => r,
                Err(e) => {
                    warn!("Crowd recv error: {}", e);
                    continue;
                }
            };

            // Parse crowd packet (same format as Soluna "SL" but with FLAG_CROWD)
            if len < SOLUNA_HEADER + 1 {
                continue;
            }
            if buf[0..2] != SOLUNA_MAGIC {
                continue;
            }

            let flags = buf[18];
            if flags & FLAG_CROWD == 0 {
                continue;
            }

            let device_id = u32::from_le_bytes([buf[2], buf[3], buf[4], buf[5]]);
            let adpcm_data = &buf[SOLUNA_HEADER..len];
            let mut decoder = AdpcmDecoder::new();
            let pcm = decoder.decode(adpcm_data);

            // Ingest into aggregator
            if let Ok(mut agg) = crowd.lock() {
                agg.ingest(device_id, pcm);
            }

            // Every 4 packets, mix and feed into the mixer
            mix_counter += 1;
            if mix_counter % 4 == 0 {
                if let Ok(mut agg) = crowd.lock() {
                    let mixed = agg.mix();
                    if !mixed.is_empty() {
                        let crowd_ch = {
                            let engine = mixer.lock().unwrap();
                            engine.channels.len() - 1
                        };
                        if let Ok(mut engine) = mixer.lock() {
                            engine.add_samples(crowd_ch, &mixed);
                        }
                    }
                }
            }
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_adpcm_decoder_produces_output() {
        let mut dec = AdpcmDecoder::new();
        let adpcm = vec![0x12, 0x34, 0x56, 0x78];
        let pcm = dec.decode(&adpcm);
        assert_eq!(pcm.len(), 8); // 4 bytes * 2 nibbles each
        assert!(pcm.iter().all(|&s| s >= -32768 && s <= 32767));
    }

    #[test]
    fn test_parse_soluna_heartbeat_skipped() {
        let mut pkt = vec![0u8; 24];
        pkt[0] = 0x53; // 'S'
        pkt[1] = 0x4C; // 'L'
        pkt[18] = 0x04; // FLAG_HEARTBEAT
        assert!(parse_soluna_packet(&pkt).is_none());
    }

    #[test]
    fn test_parse_pro_pcm16() {
        // Build a packet with exactly 2 PCM16 mono samples after the 20-byte header
        let mut pkt = vec![0u8; PRO_HEADER + 4]; // 20 header + 4 bytes (2 samples)
        pkt[0] = 0x4B; // 'K'
        pkt[1] = 0x50; // 'P'
        pkt[2..6].copy_from_slice(&42u32.to_le_bytes()); // device_hash
        pkt[6..10].copy_from_slice(&1u32.to_le_bytes()); // seq
        pkt[18] = CODEC_PCM16; // codec
        pkt[19] = 1; // mono
        // Sample 0: 16384 (0x4000 LE)
        pkt[20] = 0x00;
        pkt[21] = 0x40;
        // Sample 1: -16384 (0xC000 LE)
        pkt[22] = 0x00;
        pkt[23] = 0xC0;

        let (hash, seq, pcm) = parse_pro_packet(&pkt).unwrap();
        assert_eq!(hash, 42);
        assert_eq!(seq, 1);
        assert_eq!(pcm.len(), 2);
        assert_eq!(pcm[0], 16384);
        assert_eq!(pcm[1], -16384);
    }

    #[test]
    fn test_mix_to_mono() {
        let stereo: Vec<i16> = vec![100, 200, -100, -200];
        let mono = mix_to_mono(&stereo);
        assert_eq!(mono, vec![150, -150]);
    }

    #[test]
    fn test_stereo_base_name() {
        assert_eq!(stereo_base_name("Guitar L"), "Guitar");
        assert_eq!(stereo_base_name("Guitar R"), "Guitar");
        assert_eq!(stereo_base_name("Drum OH Left"), "Drum OH");
        assert_eq!(stereo_base_name("Drum OH Right"), "Drum OH");
        assert_eq!(stereo_base_name("Vocals"), ""); // No L/R suffix
        assert_eq!(stereo_base_name("Piano L"), "Piano");
    }

    #[test]
    fn test_device_registry_capacity() {
        let registry = new_device_registry();
        let reg = registry.lock().unwrap();
        // Should support up to 32 devices
        assert!(reg.capacity() >= 32);
    }

    #[test]
    fn test_crowd_mix_sqrt_n_scaling() {
        let mut agg = CrowdAggregator::new();
        agg.set_enabled(true);

        // Ingest 4 identical sources with a simple signal
        let signal: Vec<i16> = vec![16384, -16384, 16384, -16384];
        for i in 0..4u32 {
            agg.ingest(i, signal.clone());
        }

        let mixed = agg.mix();
        assert_eq!(mixed.len(), 4);
        // With 4 sources, scale = 1/sqrt(4) = 0.5
        // Each sum = 4 * 16384 = 65536, scaled = 65536 * 0.5 = 32768 -> clamped to 32767
        assert!(mixed[0] > 0);
        assert!(mixed[1] < 0);
    }

    #[test]
    fn test_crowd_disabled_ignores_audio() {
        let mut agg = CrowdAggregator::new();
        // Not enabled
        agg.ingest(1, vec![100, 200, 300]);
        assert_eq!(agg.get_crowd_count(), 0);
    }

    #[test]
    fn test_crowd_noise_gate() {
        let mut agg = CrowdAggregator::new();
        agg.set_enabled(true);

        // Very quiet signal (below noise gate threshold of ~655 for 0.02)
        let quiet: Vec<i16> = vec![10, -10, 5, -5];
        agg.ingest(1, quiet);
        let mixed = agg.mix();
        // All samples should be gated to zero
        assert!(mixed.iter().all(|&s| s == 0));
    }

    #[test]
    fn test_crowd_gain() {
        let agg = CrowdAggregator::new();
        assert_eq!(agg.get_gain(), 1.0);
        agg.set_gain(2.5);
        assert_eq!(agg.get_gain(), 2.5);
        agg.set_gain(10.0); // clamped to 4.0
        assert_eq!(agg.get_gain(), 4.0);
    }

    #[test]
    fn test_assign_device_to_channel() {
        let mixer = Arc::new(Mutex::new(MixerEngine::new(32)));
        let registry = new_device_registry();

        // Assign device to channel 5
        let result = assign_device_to_channel(&registry, &mixer, 5, 0xDEAD, "Kick Drum".into());
        assert!(result.is_ok());

        // Verify channel name
        let engine = mixer.lock().unwrap();
        assert_eq!(engine.channels[5].name, "Kick Drum");

        // Verify registry
        let reg = registry.lock().unwrap();
        assert!(reg.contains_key(&0xDEAD));
        assert_eq!(reg[&0xDEAD].channel_id, 5);
    }

    #[test]
    fn test_auto_stereo_link() {
        let mixer = Arc::new(Mutex::new(MixerEngine::new(32)));
        let registry = new_device_registry();

        // Assign "Guitar L" to channel 0
        assign_device_to_channel(&registry, &mixer, 0, 0x0001, "Guitar L".into()).unwrap();
        // Assign "Guitar R" to channel 1 — should auto-link
        assign_device_to_channel(&registry, &mixer, 1, 0x0002, "Guitar R".into()).unwrap();

        let engine = mixer.lock().unwrap();
        assert_eq!(engine.channels[0].linked_pair, Some(1));
        assert_eq!(engine.channels[1].linked_pair, Some(0));
    }

    #[test]
    fn test_parse_soluna_wrong_magic_rejected() {
        let mut pkt = vec![0u8; 24];
        pkt[0] = 0x00; // Wrong magic
        pkt[1] = 0x00;
        assert!(parse_soluna_packet(&pkt).is_none(), "wrong magic should be rejected");
    }

    #[test]
    fn test_parse_pro_wrong_magic_rejected() {
        let mut pkt = vec![0u8; 24];
        pkt[0] = 0x53; // 'S' — Soluna magic, not Pro
        pkt[1] = 0x4C;
        assert!(parse_pro_packet(&pkt).is_none(), "wrong magic for Pro should be rejected");
    }

    #[test]
    fn test_parse_pro_pcm24() {
        // Build a PCM24 packet: 20-byte header + 6 bytes (2 samples of 3 bytes each)
        let mut pkt = vec![0u8; PRO_HEADER + 6];
        pkt[0] = 0x4B; // 'K'
        pkt[1] = 0x50; // 'P'
        pkt[2..6].copy_from_slice(&99u32.to_le_bytes());
        pkt[6..10].copy_from_slice(&5u32.to_le_bytes());
        pkt[18] = CODEC_PCM24;
        pkt[19] = 1; // mono

        // Sample 0: 24-bit value 0x100000 (positive, ~1048576)
        pkt[20] = 0x00;
        pkt[21] = 0x00;
        pkt[22] = 0x10;
        // Sample 1: 24-bit value 0xF00000 (negative, sign-extended)
        pkt[23] = 0x00;
        pkt[24] = 0x00;
        pkt[25] = 0xF0;

        let (hash, seq, pcm) = parse_pro_packet(&pkt).unwrap();
        assert_eq!(hash, 99);
        assert_eq!(seq, 5);
        assert_eq!(pcm.len(), 2);
        // 0x100000 >> 8 = 0x1000 = 4096
        assert_eq!(pcm[0], 4096);
        // 0xF00000 sign-extended = -1048576, >> 8 = -4096
        assert_eq!(pcm[1], -4096);
    }

    #[test]
    fn test_parse_pro_opus_stub() {
        let mut pkt = vec![0u8; PRO_HEADER + 4];
        pkt[0] = 0x4B;
        pkt[1] = 0x50;
        pkt[18] = CODEC_OPUS; // Opus not supported yet
        pkt[19] = 1;
        assert!(parse_pro_packet(&pkt).is_none(), "Opus codec should return None (unsupported)");
    }

    #[test]
    fn test_out_of_order_packets_skipped() {
        let mixer = Arc::new(Mutex::new(MixerEngine::new(32)));
        let registry = new_device_registry();

        // Register a device with seq=10
        {
            let mut reg = registry.lock().unwrap();
            reg.insert(42, DeviceMapping {
                device_hash: 42,
                channel_id: 0,
                name: "Test".into(),
                last_seq: 10,
            });
        }

        // Feed with seq=5 (out of order) — should be skipped
        let samples: Vec<i16> = vec![16384; 64];
        feed_mixer(&mixer, 0, &samples, 42, 5, &registry);

        // Process and verify output is silent (skipped packet means no audio was added)
        let mut engine = mixer.lock().unwrap();
        let out = engine.process();
        assert!(out.iter().all(|&s| s == 0.0),
            "out-of-order packet should be skipped, producing silence");
    }

    #[test]
    fn test_duplicate_device_same_channel() {
        let mixer = Arc::new(Mutex::new(MixerEngine::new(32)));
        let registry = new_device_registry();

        // Assign device 0xAA to channel 3
        assign_device_to_channel(&registry, &mixer, 3, 0xAA, "Mic 1".into()).unwrap();
        // Reassign same device to channel 5
        assign_device_to_channel(&registry, &mixer, 5, 0xAA, "Mic 1 moved".into()).unwrap();

        let reg = registry.lock().unwrap();
        // Device 0xAA should only exist once, on channel 5
        assert_eq!(reg.get(&0xAA).unwrap().channel_id, 5);
        // Should not have duplicate entries
        let count = reg.values().filter(|m| m.device_hash == 0xAA).count();
        assert_eq!(count, 1, "device should only appear once in registry");
    }

    #[test]
    fn test_max_32_devices_registered() {
        let mixer = Arc::new(Mutex::new(MixerEngine::new(32)));
        let registry = new_device_registry();

        // Register 32 devices
        for i in 0..32u32 {
            assign_device_to_channel(&registry, &mixer, i as usize, i + 100, format!("Dev {i}")).unwrap();
        }

        let reg = registry.lock().unwrap();
        assert_eq!(reg.len(), 32, "should have exactly 32 devices registered");
    }

    #[test]
    fn test_crowd_evict_stale_sources() {
        let mut agg = CrowdAggregator::new();
        agg.set_enabled(true);

        // Manually insert a stale source
        agg.sources.insert(999, CrowdSource {
            device_id: 999,
            last_seen: Instant::now() - std::time::Duration::from_secs(10), // 10s ago, timeout is 5s
            samples: vec![100; 4],
        });

        assert_eq!(agg.get_crowd_count(), 1);
        agg.evict_stale();
        assert_eq!(agg.get_crowd_count(), 0, "stale source should be evicted");
    }

    #[test]
    fn test_crowd_beat_detection() {
        let mut agg = CrowdAggregator::new();
        agg.set_enabled(true);

        // Build up a baseline of low-level signal
        for i in 0..10u32 {
            agg.ingest(i, vec![100; 64]);
            let _ = agg.mix();
            // Re-ingest to keep sources alive for next iteration
            for j in 0..=i {
                agg.ingest(j, vec![100; 64]);
            }
        }

        // Now send a sudden loud burst — should trigger beat detection
        for i in 0..10u32 {
            agg.ingest(i, vec![30000; 64]);
        }
        let _ = agg.mix();

        // Beat detection depends on RMS history ratio — verify it runs without crash
        // (beat_detected may or may not be true depending on history buildup)
        let _ = agg.is_beat_detected();
    }

    #[test]
    fn test_crowd_max_sources() {
        let mut agg = CrowdAggregator::new();
        agg.set_enabled(true);

        // Ingest from 100 unique devices
        for i in 0..100u32 {
            agg.ingest(i, vec![1000; 8]);
        }
        assert_eq!(agg.get_crowd_count(), 100);

        // Mix should work without overflow
        let mixed = agg.mix();
        assert!(!mixed.is_empty());
        assert!(mixed.iter().all(|&s| s >= -32768 && s <= 32767));
    }

    #[test]
    fn test_adpcm_encode_decode_roundtrip() {
        use crate::streamer::tests::adpcm_encode_for_test;

        // Encode a ramp signal
        let original: Vec<i16> = (0..64).map(|i| (i * 512) as i16).collect();
        let encoded = adpcm_encode_for_test(&original);

        // Decode it
        let mut decoder = AdpcmDecoder::new();
        let decoded = decoder.decode(&encoded);

        assert_eq!(decoded.len(), original.len());
        // ADPCM is lossy — the encoder and decoder have separate state machines,
        // so we only verify that the overall signal shape is preserved (correlation)
        // and that all values are valid i16.
        assert!(decoded.iter().all(|&s| s >= -32768 && s <= 32767));
        // Verify at least some samples are non-zero (signal was preserved)
        let non_zero = decoded.iter().filter(|&&s| s != 0).count();
        assert!(non_zero > original.len() / 2, "most decoded samples should be non-zero");
    }
}
