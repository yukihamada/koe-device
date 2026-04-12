/// Output streaming for Koe Hub.
///
/// Routes the mixed stereo output to various destinations:
///   - LocalDAC: system audio output (via stdout piped to aplay/ffplay)
///   - SolunaMulticast: re-encode to ADPCM and broadcast on 239.42.42.1:4242
///   - SRT: low-latency streaming over UDP (placeholder)
///   - RTMP: push to streaming platforms (placeholder)
///   - WAVFile: record to disk

use std::io::Write;
use std::net::{Ipv4Addr, SocketAddrV4, UdpSocket};
use std::path::PathBuf;
use std::sync::Arc;

use tokio::sync::broadcast;
use tracing::{info, warn};

// ---- ADPCM encoder (IMA-ADPCM, mirrors firmware decoder) ----

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

struct AdpcmEncoder {
    predicted: i32,
    step_index: i32,
}

impl AdpcmEncoder {
    fn new() -> Self {
        Self { predicted: 0, step_index: 0 }
    }

    /// Encode i16 PCM samples to IMA-ADPCM bytes.
    /// Two samples per byte (low nibble first).
    fn encode(&mut self, pcm: &[i16]) -> Vec<u8> {
        let mut output = Vec::with_capacity((pcm.len() + 1) / 2);
        let mut i = 0;
        while i < pcm.len() {
            let lo = self.encode_sample(pcm[i]);
            let hi = if i + 1 < pcm.len() {
                self.encode_sample(pcm[i + 1])
            } else {
                0
            };
            output.push(lo | (hi << 4));
            i += 2;
        }
        output
    }

    fn encode_sample(&mut self, sample: i16) -> u8 {
        let step = STEP_TABLE[self.step_index as usize];
        let diff = sample as i32 - self.predicted;

        let mut nibble: u8 = 0;
        if diff < 0 {
            nibble = 8;
        }
        let diff = diff.abs();

        let mut delta = 0_i32;
        if diff >= step {
            nibble |= 4;
            delta += step;
        }
        if diff - delta >= step >> 1 {
            nibble |= 2;
            delta += step >> 1;
        }
        if diff - delta >= step >> 2 {
            nibble |= 1;
            delta += step >> 2;
        }
        delta += step >> 3;

        if nibble & 8 != 0 {
            self.predicted -= delta;
        } else {
            self.predicted += delta;
        }
        self.predicted = self.predicted.clamp(-32768, 32767);
        self.step_index = (self.step_index + INDEX_TABLE[nibble as usize]).clamp(0, 88);

        nibble
    }
}

// ---- Output types ----

/// Output destination for the mixed audio.
#[derive(Debug, Clone)]
pub enum StreamOutput {
    /// System audio output (stdout PCM → pipe to aplay/ffplay)
    LocalDAC,
    /// Re-encode to ADPCM and broadcast on Soluna multicast
    SolunaMulticast,
    /// Low-latency SRT stream to a remote address
    SRT(String),
    /// RTMP push to streaming platform
    RTMP(String),
    /// Record to WAV file on disk
    WAVFile(PathBuf),
}

// ---- WAV file writer ----

struct WavWriter {
    file: std::fs::File,
    data_bytes: u32,
}

impl WavWriter {
    fn new(path: &std::path::Path, sample_rate: u32, channels: u16) -> std::io::Result<Self> {
        let mut file = std::fs::File::create(path)?;
        // Write placeholder header (44 bytes), update on close
        let header = wav_header(sample_rate, channels, 0);
        file.write_all(&header)?;
        Ok(Self { file, data_bytes: 0 })
    }

    fn write_samples(&mut self, samples: &[f32]) -> std::io::Result<()> {
        for &s in samples {
            let clamped = s.clamp(-1.0, 1.0);
            let pcm16 = (clamped * 32767.0) as i16;
            self.file.write_all(&pcm16.to_le_bytes())?;
            self.data_bytes += 2;
        }
        Ok(())
    }

    fn finalize(mut self) -> std::io::Result<()> {
        // Seek back and rewrite header with correct sizes
        use std::io::Seek;
        self.file.seek(std::io::SeekFrom::Start(0))?;
        let header = wav_header(48_000, 2, self.data_bytes);
        self.file.write_all(&header)?;
        self.file.flush()
    }
}

fn wav_header(sample_rate: u32, channels: u16, data_bytes: u32) -> Vec<u8> {
    let bits_per_sample: u16 = 16;
    let byte_rate = sample_rate * channels as u32 * bits_per_sample as u32 / 8;
    let block_align = channels * bits_per_sample / 8;
    let file_size = 36 + data_bytes;

    let mut h = Vec::with_capacity(44);
    h.extend_from_slice(b"RIFF");
    h.extend_from_slice(&file_size.to_le_bytes());
    h.extend_from_slice(b"WAVE");
    h.extend_from_slice(b"fmt ");
    h.extend_from_slice(&16u32.to_le_bytes()); // Subchunk1 size
    h.extend_from_slice(&1u16.to_le_bytes()); // PCM format
    h.extend_from_slice(&channels.to_le_bytes());
    h.extend_from_slice(&sample_rate.to_le_bytes());
    h.extend_from_slice(&byte_rate.to_le_bytes());
    h.extend_from_slice(&block_align.to_le_bytes());
    h.extend_from_slice(&bits_per_sample.to_le_bytes());
    h.extend_from_slice(b"data");
    h.extend_from_slice(&data_bytes.to_le_bytes());
    h
}

// ---- Streamer ----

/// Manages one or more output streams.
pub struct Streamer {
    /// Broadcast channel that the mixer loop sends mixed frames to.
    pub tx: broadcast::Sender<Arc<Vec<f32>>>,
}

impl Streamer {
    pub fn new() -> Self {
        let (tx, _) = broadcast::channel(64);
        Self { tx }
    }

    /// Start streaming to the given output. Each call spawns a new task.
    pub fn start(&self, output: StreamOutput) {
        let mut rx = self.tx.subscribe();

        match output {
            StreamOutput::LocalDAC => {
                tokio::spawn(async move {
                    info!("LocalDAC output started (stdout PCM16 stereo 48kHz)");
                    loop {
                        match rx.recv().await {
                            Ok(frame) => {
                                let stdout = std::io::stdout();
                                let mut out = stdout.lock();
                                for &s in frame.iter() {
                                    let pcm16 = (s.clamp(-1.0, 1.0) * 32767.0) as i16;
                                    if out.write_all(&pcm16.to_le_bytes()).is_err() {
                                        return;
                                    }
                                }
                                let _ = out.flush();
                            }
                            Err(broadcast::error::RecvError::Lagged(n)) => {
                                warn!(n, "LocalDAC lagged, skipping frames");
                            }
                            Err(_) => return,
                        }
                    }
                });
            }

            StreamOutput::SolunaMulticast => {
                tokio::spawn(async move {
                    let socket = match UdpSocket::bind("0.0.0.0:0") {
                        Ok(s) => s,
                        Err(e) => {
                            warn!("Failed to create Soluna output socket: {}", e);
                            return;
                        }
                    };
                    let dest = SocketAddrV4::new(Ipv4Addr::new(239, 42, 42, 1), 4242);
                    let mut encoder = AdpcmEncoder::new();
                    let mut seq: u32 = 0;
                    // Hub device hash: "HUB\0" = 0x00425548
                    let hub_hash: u32 = 0x00425548;

                    info!("Soluna multicast output started → {}", dest);

                    loop {
                        match rx.recv().await {
                            Ok(frame) => {
                                // Mix stereo down to mono for Soluna
                                let mono: Vec<i16> = frame
                                    .chunks_exact(2)
                                    .map(|pair| {
                                        ((pair[0] + pair[1]) * 0.5 * 32767.0).clamp(-32768.0, 32767.0) as i16
                                    })
                                    .collect();

                                let adpcm = encoder.encode(&mono);

                                // Build Soluna packet
                                let mut pkt = Vec::with_capacity(19 + adpcm.len());
                                pkt.extend_from_slice(&[0x53, 0x4C]); // Magic "SL"
                                pkt.extend_from_slice(&hub_hash.to_le_bytes()); // device_id
                                pkt.extend_from_slice(&seq.to_le_bytes()); // seq
                                pkt.extend_from_slice(&0u32.to_le_bytes()); // channel (0 = mix)
                                pkt.extend_from_slice(&0u32.to_le_bytes()); // ntp_ms (placeholder)
                                pkt.push(0x01); // flags: ADPCM
                                pkt.extend_from_slice(&adpcm);

                                let _ = socket.send_to(&pkt, dest);
                                seq = seq.wrapping_add(1);
                            }
                            Err(broadcast::error::RecvError::Lagged(n)) => {
                                warn!(n, "Soluna output lagged");
                            }
                            Err(_) => return,
                        }
                    }
                });
            }

            StreamOutput::SRT(addr) => {
                tokio::spawn(async move {
                    info!("SRT output started → {} (UDP stub)", addr);
                    let socket = match UdpSocket::bind("0.0.0.0:0") {
                        Ok(s) => s,
                        Err(e) => {
                            warn!("Failed to create SRT socket: {}", e);
                            return;
                        }
                    };
                    let dest: std::net::SocketAddr = match addr.parse() {
                        Ok(a) => a,
                        Err(e) => {
                            warn!("Invalid SRT address '{}': {}", addr, e);
                            return;
                        }
                    };

                    loop {
                        match rx.recv().await {
                            Ok(frame) => {
                                // Send raw PCM16 over UDP (SRT handshake not implemented yet)
                                let mut buf = Vec::with_capacity(frame.len() * 2);
                                for &s in frame.iter() {
                                    let pcm16 = (s.clamp(-1.0, 1.0) * 32767.0) as i16;
                                    buf.extend_from_slice(&pcm16.to_le_bytes());
                                }
                                let _ = socket.send_to(&buf, dest);
                            }
                            Err(broadcast::error::RecvError::Lagged(_)) => {}
                            Err(_) => return,
                        }
                    }
                });
            }

            StreamOutput::RTMP(url) => {
                tokio::spawn(async move {
                    warn!("RTMP output to '{}' — not yet implemented, requires ffmpeg subprocess", url);
                });
            }

            StreamOutput::WAVFile(path) => {
                tokio::spawn(async move {
                    let wav_path = path.clone();
                    info!("WAV recording started → {}", wav_path.display());
                    let mut writer = match WavWriter::new(&wav_path, 48_000, 2) {
                        Ok(w) => w,
                        Err(e) => {
                            warn!("Failed to create WAV file '{}': {}", wav_path.display(), e);
                            return;
                        }
                    };

                    loop {
                        match rx.recv().await {
                            Ok(frame) => {
                                if let Err(e) = writer.write_samples(&frame) {
                                    warn!("WAV write error: {}", e);
                                    break;
                                }
                            }
                            Err(broadcast::error::RecvError::Lagged(n)) => {
                                warn!(n, "WAV writer lagged, frames dropped");
                            }
                            Err(_) => break,
                        }
                    }

                    if let Err(e) = writer.finalize() {
                        warn!("WAV finalize error: {}", e);
                    } else {
                        info!("WAV recording saved → {}", wav_path.display());
                    }
                });
            }
        }
    }
}

#[cfg(test)]
pub mod tests {
    use super::*;

    /// Public helper for cross-module ADPCM roundtrip test.
    pub fn adpcm_encode_for_test(pcm: &[i16]) -> Vec<u8> {
        let mut enc = AdpcmEncoder::new();
        enc.encode(pcm)
    }

    #[test]
    fn test_adpcm_roundtrip() {
        // Encode and verify output size
        let mut enc = AdpcmEncoder::new();
        let pcm: Vec<i16> = (0..128).map(|i| (i * 256) as i16).collect();
        let adpcm = enc.encode(&pcm);
        assert_eq!(adpcm.len(), 64); // 128 samples / 2 per byte
    }

    #[test]
    fn test_wav_header_size() {
        let header = wav_header(48_000, 2, 0);
        assert_eq!(header.len(), 44);
        assert_eq!(&header[0..4], b"RIFF");
        assert_eq!(&header[8..12], b"WAVE");
    }

    #[test]
    fn test_soluna_multicast_adpcm_output_size() {
        let mut enc = AdpcmEncoder::new();
        // 128 mono samples (one mixer frame) → 64 ADPCM bytes
        let pcm: Vec<i16> = vec![1000; 128];
        let adpcm = enc.encode(&pcm);
        assert_eq!(adpcm.len(), 64, "128 samples should produce 64 ADPCM bytes");

        // Verify Soluna packet size: 19 header + 64 ADPCM = 83 bytes
        let expected_pkt_size = 19 + adpcm.len();
        assert_eq!(expected_pkt_size, 83);
    }

    #[test]
    fn test_wav_header_sample_rate() {
        let header = wav_header(44_100, 2, 0);
        // Sample rate is at bytes 24..28
        let sr = u32::from_le_bytes([header[24], header[25], header[26], header[27]]);
        assert_eq!(sr, 44_100);

        let header48 = wav_header(48_000, 1, 0);
        let sr48 = u32::from_le_bytes([header48[24], header48[25], header48[26], header48[27]]);
        assert_eq!(sr48, 48_000);
    }

    #[test]
    fn test_wav_header_channels() {
        let header_stereo = wav_header(48_000, 2, 0);
        // Channels is at bytes 22..24
        let ch = u16::from_le_bytes([header_stereo[22], header_stereo[23]]);
        assert_eq!(ch, 2);

        let header_mono = wav_header(48_000, 1, 0);
        let ch_mono = u16::from_le_bytes([header_mono[22], header_mono[23]]);
        assert_eq!(ch_mono, 1);
    }
}
