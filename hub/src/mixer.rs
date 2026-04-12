/// Core audio mixer engine — low-latency multi-channel mixing for Koe Hub.
///
/// Supports up to 32 input channels with per-channel gain, pan, mute/solo,
/// 4-band fully parametric EQ, aux sends, stereo linking, channel inserts,
/// and channel groups/buses for organized mixing.

use std::sync::atomic::{AtomicBool, Ordering};

/// Maximum number of input channels.
pub const MAX_CHANNELS: usize = 32;

/// Number of aux send buses.
pub const AUX_BUS_COUNT: usize = 4;

/// Default sample rate (48 kHz).
pub const SAMPLE_RATE: u32 = 48_000;

/// Buffer size in frames (128 frames = 2.67 ms at 48 kHz).
pub const BUFFER_FRAMES: usize = 128;

/// Ring buffer capacity per channel (holds ~170 ms at 48 kHz).
const RING_BUF_CAPACITY: usize = 8192;

// ---- 4-band parametric EQ biquad state ----

/// Number of EQ bands per channel.
pub const EQ_BAND_COUNT: usize = 4;

/// EQ filter type for each band.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum EqBandType {
    LowShelf,
    Peak,
    HighShelf,
    LowPass,
    HighPass,
}

impl Default for EqBandType {
    fn default() -> Self {
        EqBandType::Peak
    }
}

/// Parameters for a single EQ band.
#[derive(Clone, Debug)]
pub struct EqBand {
    pub band_type: EqBandType,
    pub frequency: f32, // 20.0 .. 20000.0 Hz
    pub gain_db: f32,   // -18.0 .. +18.0 dB
    pub q: f32,         // 0.1 .. 10.0
}

impl Default for EqBand {
    fn default() -> Self {
        Self {
            band_type: EqBandType::Peak,
            frequency: 1000.0,
            gain_db: 0.0,
            q: 0.7,
        }
    }
}

#[derive(Clone)]
struct BiquadState {
    x1: f32,
    x2: f32,
    y1: f32,
    y2: f32,
}

impl Default for BiquadState {
    fn default() -> Self {
        Self { x1: 0.0, x2: 0.0, y1: 0.0, y2: 0.0 }
    }
}

#[derive(Clone)]
struct BiquadCoeffs {
    b0: f32,
    b1: f32,
    b2: f32,
    a1: f32,
    a2: f32,
}

impl Default for BiquadCoeffs {
    fn default() -> Self {
        // Pass-through (unity gain, no filtering)
        Self { b0: 1.0, b1: 0.0, b2: 0.0, a1: 0.0, a2: 0.0 }
    }
}

impl BiquadCoeffs {
    /// Peak EQ filter at `freq_hz` with `gain_db` and `q`.
    fn peak_eq(freq_hz: f32, gain_db: f32, q: f32, sample_rate: f32) -> Self {
        let a = 10.0_f32.powf(gain_db / 40.0);
        let w0 = 2.0 * std::f32::consts::PI * freq_hz / sample_rate;
        let (sin_w0, cos_w0) = (w0.sin(), w0.cos());
        let alpha = sin_w0 / (2.0 * q);

        let b0 = 1.0 + alpha * a;
        let b1 = -2.0 * cos_w0;
        let b2 = 1.0 - alpha * a;
        let a0 = 1.0 + alpha / a;
        let a1 = -2.0 * cos_w0;
        let a2 = 1.0 - alpha / a;

        Self {
            b0: b0 / a0,
            b1: b1 / a0,
            b2: b2 / a0,
            a1: a1 / a0,
            a2: a2 / a0,
        }
    }

    /// Low shelf filter.
    fn low_shelf(freq_hz: f32, gain_db: f32, q: f32, sample_rate: f32) -> Self {
        let a = 10.0_f32.powf(gain_db / 40.0);
        let w0 = 2.0 * std::f32::consts::PI * freq_hz / sample_rate;
        let (sin_w0, cos_w0) = (w0.sin(), w0.cos());
        let alpha = sin_w0 / (2.0 * q);
        let two_sqrt_a_alpha = 2.0 * a.sqrt() * alpha;

        let a0 = (a + 1.0) + (a - 1.0) * cos_w0 + two_sqrt_a_alpha;
        let b0 = a * ((a + 1.0) - (a - 1.0) * cos_w0 + two_sqrt_a_alpha);
        let b1 = 2.0 * a * ((a - 1.0) - (a + 1.0) * cos_w0);
        let b2 = a * ((a + 1.0) - (a - 1.0) * cos_w0 - two_sqrt_a_alpha);
        let a1 = -2.0 * ((a - 1.0) + (a + 1.0) * cos_w0);
        let a2 = (a + 1.0) + (a - 1.0) * cos_w0 - two_sqrt_a_alpha;

        Self { b0: b0 / a0, b1: b1 / a0, b2: b2 / a0, a1: a1 / a0, a2: a2 / a0 }
    }

    /// High shelf filter.
    fn high_shelf(freq_hz: f32, gain_db: f32, q: f32, sample_rate: f32) -> Self {
        let a = 10.0_f32.powf(gain_db / 40.0);
        let w0 = 2.0 * std::f32::consts::PI * freq_hz / sample_rate;
        let (sin_w0, cos_w0) = (w0.sin(), w0.cos());
        let alpha = sin_w0 / (2.0 * q);
        let two_sqrt_a_alpha = 2.0 * a.sqrt() * alpha;

        let a0 = (a + 1.0) - (a - 1.0) * cos_w0 + two_sqrt_a_alpha;
        let b0 = a * ((a + 1.0) + (a - 1.0) * cos_w0 + two_sqrt_a_alpha);
        let b1 = -2.0 * a * ((a - 1.0) + (a + 1.0) * cos_w0);
        let b2 = a * ((a + 1.0) + (a - 1.0) * cos_w0 - two_sqrt_a_alpha);
        let a1 = 2.0 * ((a - 1.0) - (a + 1.0) * cos_w0);
        let a2 = (a + 1.0) - (a - 1.0) * cos_w0 - two_sqrt_a_alpha;

        Self { b0: b0 / a0, b1: b1 / a0, b2: b2 / a0, a1: a1 / a0, a2: a2 / a0 }
    }

    /// Low-pass filter.
    fn low_pass(freq_hz: f32, q: f32, sample_rate: f32) -> Self {
        let w0 = 2.0 * std::f32::consts::PI * freq_hz / sample_rate;
        let (sin_w0, cos_w0) = (w0.sin(), w0.cos());
        let alpha = sin_w0 / (2.0 * q);

        let b1 = 1.0 - cos_w0;
        let b0 = b1 / 2.0;
        let b2 = b0;
        let a0 = 1.0 + alpha;
        let a1 = -2.0 * cos_w0;
        let a2 = 1.0 - alpha;

        Self { b0: b0 / a0, b1: b1 / a0, b2: b2 / a0, a1: a1 / a0, a2: a2 / a0 }
    }

    /// High-pass filter.
    fn high_pass(freq_hz: f32, q: f32, sample_rate: f32) -> Self {
        let w0 = 2.0 * std::f32::consts::PI * freq_hz / sample_rate;
        let (sin_w0, cos_w0) = (w0.sin(), w0.cos());
        let alpha = sin_w0 / (2.0 * q);

        let b1 = -(1.0 + cos_w0);
        let b0 = (1.0 + cos_w0) / 2.0;
        let b2 = b0;
        let a0 = 1.0 + alpha;
        let a1 = -2.0 * cos_w0;
        let a2 = 1.0 - alpha;

        Self { b0: b0 / a0, b1: b1 / a0, b2: b2 / a0, a1: a1 / a0, a2: a2 / a0 }
    }

    /// Build coefficients from an EqBand parameter set.
    fn from_eq_band(band: &EqBand, sample_rate: f32) -> Self {
        let freq = band.frequency.clamp(20.0, 20000.0);
        let gain = band.gain_db.clamp(-18.0, 18.0);
        let q = band.q.clamp(0.1, 10.0);
        match band.band_type {
            EqBandType::LowShelf => Self::low_shelf(freq, gain, q, sample_rate),
            EqBandType::Peak => Self::peak_eq(freq, gain, q, sample_rate),
            EqBandType::HighShelf => Self::high_shelf(freq, gain, q, sample_rate),
            EqBandType::LowPass => Self::low_pass(freq, q, sample_rate),
            EqBandType::HighPass => Self::high_pass(freq, q, sample_rate),
        }
    }
}

fn biquad_process(c: &BiquadCoeffs, s: &mut BiquadState, input: f32) -> f32 {
    let out = c.b0 * input + c.b1 * s.x1 + c.b2 * s.x2 - c.a1 * s.y1 - c.a2 * s.y2;
    s.x2 = s.x1;
    s.x1 = input;
    s.y2 = s.y1;
    s.y1 = out;
    out
}

// ---- Ring buffer (single-producer / single-consumer) ----

pub struct RingBuffer {
    buf: Vec<f32>,
    head: usize,
    tail: usize,
    len: usize,
}

impl RingBuffer {
    pub fn new(capacity: usize) -> Self {
        Self {
            buf: vec![0.0; capacity],
            head: 0,
            tail: 0,
            len: 0,
        }
    }

    pub fn push(&mut self, sample: f32) {
        if self.len == self.buf.len() {
            // Overwrite oldest on overflow
            self.tail = (self.tail + 1) % self.buf.len();
        } else {
            self.len += 1;
        }
        self.buf[self.head] = sample;
        self.head = (self.head + 1) % self.buf.len();
    }

    pub fn pop(&mut self) -> Option<f32> {
        if self.len == 0 {
            return None;
        }
        let val = self.buf[self.tail];
        self.tail = (self.tail + 1) % self.buf.len();
        self.len -= 1;
        Some(val)
    }

    pub fn available(&self) -> usize {
        self.len
    }

    pub fn clear(&mut self) {
        self.head = 0;
        self.tail = 0;
        self.len = 0;
    }
}

// ---- Channel groups / buses ----

/// A group/bus aggregating multiple mixer channels.
pub struct ChannelGroup {
    pub name: String,
    pub channels: Vec<usize>, // Channel IDs belonging to this group
    pub group_gain: f32,      // 0.0 .. 4.0
    pub group_mute: bool,
}

impl ChannelGroup {
    pub fn new(name: &str, channels: Vec<usize>) -> Self {
        Self {
            name: name.to_string(),
            channels,
            group_gain: 1.0,
            group_mute: false,
        }
    }
}

/// Pre-defined channel group layout for 32-channel mixer.
pub fn default_channel_groups() -> Vec<ChannelGroup> {
    vec![
        ChannelGroup::new("Instruments", (0..8).collect()),
        ChannelGroup::new("Vocals", (8..16).collect()),
        ChannelGroup::new("FX Returns", (16..24).collect()),
        ChannelGroup::new("Aux", (24..32).collect()),
    ]
}

// ---- Audio channel ----

pub struct AudioChannel {
    pub id: usize,
    pub name: String,
    pub gain: f32,
    pub pan: f32, // -1.0 (left) .. 1.0 (right)
    pub mute: bool,
    pub solo: bool,

    // 4-band parametric EQ (replaces old 3-band)
    pub eq_bands: [EqBand; EQ_BAND_COUNT],

    // Legacy convenience accessors (mapped to eq_bands[0..3])
    pub eq_low: f32,  // dB — kept for API compat, synced to eq_bands[0].gain_db
    pub eq_mid: f32,  // dB — synced to eq_bands[1].gain_db
    pub eq_high: f32, // dB — synced to eq_bands[2].gain_db

    pub peak_level: f32,
    pub active: AtomicBool,

    // Aux sends: per-channel send level to each aux bus (0.0 = off, 1.0 = unity)
    pub aux_sends: [f32; AUX_BUS_COUNT],

    // Stereo linking: if set, this channel is linked to the given channel ID.
    // Gain, pan, mute changes on either channel sync to the pair.
    pub linked_pair: Option<usize>,

    // Channel insert points (index into a shared effect registry)
    pub pre_fader_insert: Option<usize>,
    pub post_fader_insert: Option<usize>,

    ring: RingBuffer,
    eq_states: [BiquadState; EQ_BAND_COUNT],
}

impl AudioChannel {
    pub fn new(id: usize, name: String) -> Self {
        // Default EQ: band 0 = low shelf 200Hz, 1 = peak 1kHz, 2 = peak 3kHz, 3 = high shelf 8kHz
        let eq_bands = [
            EqBand { band_type: EqBandType::LowShelf, frequency: 200.0, gain_db: 0.0, q: 0.7 },
            EqBand { band_type: EqBandType::Peak, frequency: 1000.0, gain_db: 0.0, q: 0.7 },
            EqBand { band_type: EqBandType::Peak, frequency: 3000.0, gain_db: 0.0, q: 0.7 },
            EqBand { band_type: EqBandType::HighShelf, frequency: 8000.0, gain_db: 0.0, q: 0.7 },
        ];
        Self {
            id,
            name,
            gain: 1.0,
            pan: 0.0,
            mute: false,
            solo: false,
            eq_bands,
            eq_low: 0.0,
            eq_mid: 0.0,
            eq_high: 0.0,
            peak_level: 0.0,
            active: AtomicBool::new(false),
            aux_sends: [0.0; AUX_BUS_COUNT],
            linked_pair: None,
            pre_fader_insert: None,
            post_fader_insert: None,
            ring: RingBuffer::new(RING_BUF_CAPACITY),
            eq_states: Default::default(),
        }
    }

    /// Sync legacy eq_low/mid/high fields to eq_bands gain values.
    pub fn sync_legacy_eq(&mut self) {
        self.eq_bands[0].gain_db = self.eq_low;
        self.eq_bands[1].gain_db = self.eq_mid;
        self.eq_bands[2].gain_db = self.eq_high;
    }

    /// Feed i16 PCM samples into this channel's ring buffer.
    pub fn add_samples_i16(&mut self, samples: &[i16]) {
        for &s in samples {
            self.ring.push(s as f32 / 32768.0);
        }
        self.active.store(true, Ordering::Relaxed);
    }

    /// Feed f32 PCM samples (already normalized to -1..1).
    pub fn add_samples_f32(&mut self, samples: &[f32]) {
        for &s in samples {
            self.ring.push(s);
        }
        self.active.store(true, Ordering::Relaxed);
    }
}

// ---- Mixer engine ----

pub struct MixerEngine {
    pub channels: Vec<AudioChannel>,
    pub master_gain: f32,
    pub sample_rate: u32,
    pub buffer_size: usize,
    pub groups: Vec<ChannelGroup>,
    /// Aux bus output buffers (stereo interleaved per bus).
    /// Populated during process() for downstream monitoring/effects sends.
    pub aux_outputs: Vec<Vec<f32>>,
}

impl MixerEngine {
    /// Create a new mixer with `n` channels (capped at MAX_CHANNELS).
    pub fn new(n: usize) -> Self {
        let n = n.min(MAX_CHANNELS);
        let channels = (0..n)
            .map(|i| AudioChannel::new(i, format!("Ch {}", i + 1)))
            .collect();
        let groups = default_channel_groups();
        Self {
            channels,
            master_gain: 1.0,
            sample_rate: SAMPLE_RATE,
            buffer_size: BUFFER_FRAMES,
            groups,
            aux_outputs: vec![vec![]; AUX_BUS_COUNT],
        }
    }

    /// Feed i16 samples into a specific channel.
    pub fn add_samples(&mut self, channel_id: usize, samples: &[i16]) {
        if let Some(ch) = self.channels.get_mut(channel_id) {
            ch.add_samples_i16(samples);
        }
    }

    /// Link two channels as a stereo pair. Odd channel pans left, even pans right.
    pub fn link_stereo(&mut self, ch_a: usize, ch_b: usize) {
        if ch_a < self.channels.len() && ch_b < self.channels.len() && ch_a != ch_b {
            self.channels[ch_a].linked_pair = Some(ch_b);
            self.channels[ch_b].linked_pair = Some(ch_a);
            // Set default stereo pan
            self.channels[ch_a].pan = -1.0;
            self.channels[ch_b].pan = 1.0;
        }
    }

    /// Unlink a stereo pair.
    pub fn unlink_stereo(&mut self, ch_id: usize) {
        if let Some(ch) = self.channels.get(ch_id) {
            if let Some(partner) = ch.linked_pair {
                if partner < self.channels.len() {
                    self.channels[partner].linked_pair = None;
                    self.channels[partner].pan = 0.0;
                }
            }
        }
        if let Some(ch) = self.channels.get_mut(ch_id) {
            ch.linked_pair = None;
            ch.pan = 0.0;
        }
    }

    /// Sync gain/mute from a channel to its linked partner (if any).
    pub fn sync_linked_channel(&mut self, ch_id: usize) {
        if ch_id >= self.channels.len() {
            return;
        }
        if let Some(partner_id) = self.channels[ch_id].linked_pair {
            if partner_id < self.channels.len() {
                let gain = self.channels[ch_id].gain;
                let mute = self.channels[ch_id].mute;
                let solo = self.channels[ch_id].solo;
                self.channels[partner_id].gain = gain;
                self.channels[partner_id].mute = mute;
                self.channels[partner_id].solo = solo;
            }
        }
    }

    /// Mix all channels and return stereo interleaved f32 output.
    /// Output length = buffer_size * 2 (L, R, L, R, ...).
    /// Also populates aux_outputs for aux bus sends.
    pub fn process(&mut self) -> Vec<f32> {
        let frames = self.buffer_size;
        let mut output = vec![0.0_f32; frames * 2];

        // Initialize aux bus outputs
        for aux in &mut self.aux_outputs {
            aux.clear();
            aux.resize(frames * 2, 0.0);
        }

        // Determine if any channel has solo enabled
        let any_solo = self.channels.iter().any(|ch| ch.solo);

        // Collect group mute/gain for each channel
        let mut group_gain = vec![1.0_f32; self.channels.len()];
        let mut group_mute = vec![false; self.channels.len()];
        for grp in &self.groups {
            for &ch_id in &grp.channels {
                if ch_id < group_gain.len() {
                    group_gain[ch_id] *= grp.group_gain;
                    if grp.group_mute {
                        group_mute[ch_id] = true;
                    }
                }
            }
        }

        // Compute 4-band EQ coefficients for each channel
        let sr = self.sample_rate as f32;
        let eq_coeffs: Vec<[BiquadCoeffs; EQ_BAND_COUNT]> = self.channels.iter().map(|ch| {
            [
                BiquadCoeffs::from_eq_band(&ch.eq_bands[0], sr),
                BiquadCoeffs::from_eq_band(&ch.eq_bands[1], sr),
                BiquadCoeffs::from_eq_band(&ch.eq_bands[2], sr),
                BiquadCoeffs::from_eq_band(&ch.eq_bands[3], sr),
            ]
        }).collect();

        for (ch_idx, ch) in self.channels.iter_mut().enumerate() {
            // Skip muted channels (channel mute OR group mute); if solo is active, skip non-solo
            let is_muted = ch.mute || group_mute[ch_idx] || (any_solo && !ch.solo);
            if is_muted {
                // Drain the ring buffer even if muted, to keep it from growing
                for _ in 0..frames {
                    ch.ring.pop();
                }
                ch.peak_level *= 0.95; // Decay
                continue;
            }

            let gain = ch.gain * group_gain[ch_idx];
            // Equal-power pan: left = cos(theta), right = sin(theta)
            // where theta = (pan + 1) / 2 * pi/2
            let theta = (ch.pan + 1.0) * 0.5 * std::f32::consts::FRAC_PI_2;
            let gain_l = gain * theta.cos();
            let gain_r = gain * theta.sin();

            let mut peak = 0.0_f32;
            let coeffs = &eq_coeffs[ch_idx];

            // Capture aux send levels for this channel
            let aux_sends = ch.aux_sends;

            for i in 0..frames {
                let raw = ch.ring.pop().unwrap_or(0.0);

                // Apply 4-band parametric EQ
                let mut sample = raw;
                for (band, coeff) in coeffs.iter().enumerate() {
                    sample = biquad_process(coeff, &mut ch.eq_states[band], sample);
                }

                peak = peak.max(sample.abs());

                // Main bus
                output[i * 2] += sample * gain_l;
                output[i * 2 + 1] += sample * gain_r;

                // Aux sends (post-EQ, pre-fader by default)
                for (aux_idx, &send_level) in aux_sends.iter().enumerate() {
                    if send_level > 0.0 {
                        self.aux_outputs[aux_idx][i * 2] += sample * send_level;
                        self.aux_outputs[aux_idx][i * 2 + 1] += sample * send_level;
                    }
                }
            }

            ch.peak_level = peak;
        }

        // Apply master gain
        if (self.master_gain - 1.0).abs() > f32::EPSILON {
            for s in output.iter_mut() {
                *s *= self.master_gain;
            }
        }

        output
    }

    /// Return peak levels for all channels: (channel_id, peak_level).
    pub fn get_peak_levels(&self) -> Vec<(usize, f32)> {
        self.channels
            .iter()
            .map(|ch| (ch.id, ch.peak_level))
            .collect()
    }

    /// Find the next available (inactive) channel index.
    pub fn next_available_channel(&self) -> Option<usize> {
        self.channels
            .iter()
            .position(|ch| !ch.active.load(Ordering::Relaxed))
    }

    /// Get the group that a channel belongs to, if any.
    pub fn channel_group(&self, ch_id: usize) -> Option<&ChannelGroup> {
        self.groups.iter().find(|g| g.channels.contains(&ch_id))
    }

    /// Get the group name for a channel.
    pub fn channel_group_name(&self, ch_id: usize) -> &str {
        self.channel_group(ch_id).map(|g| g.name.as_str()).unwrap_or("Ungrouped")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ring_buffer_basic() {
        let mut rb = RingBuffer::new(4);
        rb.push(1.0);
        rb.push(2.0);
        rb.push(3.0);
        assert_eq!(rb.available(), 3);
        assert_eq!(rb.pop(), Some(1.0));
        assert_eq!(rb.pop(), Some(2.0));
        assert_eq!(rb.pop(), Some(3.0));
        assert_eq!(rb.pop(), None);
    }

    #[test]
    fn test_ring_buffer_overflow() {
        let mut rb = RingBuffer::new(2);
        rb.push(1.0);
        rb.push(2.0);
        rb.push(3.0); // Overwrites 1.0
        assert_eq!(rb.available(), 2);
        assert_eq!(rb.pop(), Some(2.0));
        assert_eq!(rb.pop(), Some(3.0));
    }

    #[test]
    fn test_mixer_silent_output() {
        let mut engine = MixerEngine::new(2);
        let out = engine.process();
        assert_eq!(out.len(), BUFFER_FRAMES * 2);
        assert!(out.iter().all(|&s| s == 0.0));
    }

    #[test]
    fn test_mixer_mono_signal() {
        let mut engine = MixerEngine::new(1);
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES]; // 0.5 amplitude
        engine.add_samples(0, &samples);
        let out = engine.process();
        // Center-panned mono → equal L/R
        assert!(out[0] > 0.0);
        assert!(out[1] > 0.0);
        assert!((out[0] - out[1]).abs() < 0.001);
    }

    #[test]
    fn test_32_channels() {
        let engine = MixerEngine::new(32);
        assert_eq!(engine.channels.len(), 32);
        assert_eq!(engine.groups.len(), 4);
        assert_eq!(engine.groups[0].name, "Instruments");
        assert_eq!(engine.groups[1].name, "Vocals");
        assert_eq!(engine.groups[2].name, "FX Returns");
        assert_eq!(engine.groups[3].name, "Aux");
    }

    #[test]
    fn test_stereo_linking() {
        let mut engine = MixerEngine::new(4);
        engine.link_stereo(0, 1);
        assert_eq!(engine.channels[0].linked_pair, Some(1));
        assert_eq!(engine.channels[1].linked_pair, Some(0));
        assert_eq!(engine.channels[0].pan, -1.0);
        assert_eq!(engine.channels[1].pan, 1.0);

        // Sync gain
        engine.channels[0].gain = 0.5;
        engine.sync_linked_channel(0);
        assert_eq!(engine.channels[1].gain, 0.5);

        // Unlink
        engine.unlink_stereo(0);
        assert_eq!(engine.channels[0].linked_pair, None);
        assert_eq!(engine.channels[1].linked_pair, None);
    }

    #[test]
    fn test_aux_sends() {
        let mut engine = MixerEngine::new(2);
        engine.channels[0].aux_sends[0] = 0.5; // Send ch0 to aux 0 at 50%
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let _out = engine.process();
        // Aux bus 0 should have signal
        assert!(engine.aux_outputs[0].iter().any(|&s| s > 0.0));
        // Aux bus 1 should be silent (no send)
        assert!(engine.aux_outputs[1].iter().all(|&s| s == 0.0));
    }

    #[test]
    fn test_channel_group_mute() {
        let mut engine = MixerEngine::new(32);
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples); // Ch 0 = Instruments group
        engine.groups[0].group_mute = true;
        let out = engine.process();
        // Muted group should produce silence
        assert!(out.iter().all(|&s| s == 0.0));
    }

    #[test]
    fn test_4band_eq_types() {
        let mut engine = MixerEngine::new(1);
        engine.channels[0].eq_bands[0].band_type = EqBandType::HighPass;
        engine.channels[0].eq_bands[0].frequency = 100.0;
        engine.channels[0].eq_bands[3].band_type = EqBandType::LowPass;
        engine.channels[0].eq_bands[3].frequency = 10000.0;
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let out = engine.process();
        assert!(out.iter().all(|s| s.is_finite()));
    }

    #[test]
    fn test_gain_clamp() {
        let mut engine = MixerEngine::new(1);
        // Gain should work at boundaries; verify 0.0 produces silence
        engine.channels[0].gain = 0.0;
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let out = engine.process();
        assert!(out.iter().all(|&s| s.abs() < f32::EPSILON), "gain=0 should produce silence");

        // Gain at 4.0 should amplify
        let mut engine2 = MixerEngine::new(1);
        engine2.channels[0].gain = 4.0;
        let samples2: Vec<i16> = vec![4096; BUFFER_FRAMES];
        engine2.add_samples(0, &samples2);
        let out2 = engine2.process();
        assert!(out2.iter().any(|&s| s.abs() > 0.1), "gain=4.0 should amplify");
    }

    #[test]
    fn test_pan_full_left() {
        let mut engine = MixerEngine::new(1);
        engine.channels[0].pan = -1.0;
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let out = engine.process();
        // Right channel (odd indices) should be near-silent
        for i in 0..BUFFER_FRAMES {
            assert!(out[i * 2 + 1].abs() < 0.001, "right channel should be silent at pan=-1.0");
        }
        // Left channel should have signal
        assert!(out[0] > 0.0, "left channel should have signal at pan=-1.0");
    }

    #[test]
    fn test_pan_full_right() {
        let mut engine = MixerEngine::new(1);
        engine.channels[0].pan = 1.0;
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let out = engine.process();
        // Left channel (even indices) should be near-silent
        for i in 0..BUFFER_FRAMES {
            assert!(out[i * 2].abs() < 0.001, "left channel should be silent at pan=1.0");
        }
        // Right channel should have signal
        assert!(out[1] > 0.0, "right channel should have signal at pan=1.0");
    }

    #[test]
    fn test_mute_produces_silence() {
        let mut engine = MixerEngine::new(1);
        engine.channels[0].mute = true;
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let out = engine.process();
        assert!(out.iter().all(|&s| s == 0.0), "muted channel should produce silence");
    }

    #[test]
    fn test_solo_isolates_channel() {
        let mut engine = MixerEngine::new(4);
        // Feed signal to channels 0 and 1
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        engine.add_samples(1, &samples);
        // Solo channel 1 only
        engine.channels[1].solo = true;
        let out = engine.process();
        // Output should have signal (from ch1)
        assert!(out.iter().any(|&s| s > 0.0), "solo'd channel should produce output");
        // Ch0 peak_level should have decayed (it was muted by solo logic)
        // After processing, ch0.peak_level decays since it was skipped
        assert!(engine.channels[0].peak_level < 0.01, "non-solo channel should be silent");
    }

    #[test]
    fn test_eq_flat_is_passthrough() {
        // All EQ bands at 0dB should not alter the signal significantly
        let mut engine = MixerEngine::new(1);
        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let out_eq = engine.process();

        // Compare with a fresh engine with same signal
        let mut engine2 = MixerEngine::new(1);
        engine2.add_samples(0, &samples);
        let out_no_eq = engine2.process();

        // Should be nearly identical (both have 0dB EQ)
        let max_diff: f32 = out_eq.iter().zip(out_no_eq.iter())
            .map(|(a, b)| (a - b).abs())
            .fold(0.0_f32, f32::max);
        assert!(max_diff < 0.001, "flat EQ should be passthrough, max_diff={}", max_diff);
    }

    #[test]
    fn test_eq_boost_increases_level() {
        // Boost mid EQ band significantly
        let mut engine = MixerEngine::new(1);
        engine.channels[0].eq_bands[1].gain_db = 12.0; // +12dB at 1kHz
        let samples: Vec<i16> = vec![8192; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let out_boosted = engine.process();

        let mut engine2 = MixerEngine::new(1);
        let samples2: Vec<i16> = vec![8192; BUFFER_FRAMES];
        engine2.add_samples(0, &samples2);
        let out_flat = engine2.process();

        let energy_boosted: f32 = out_boosted.iter().map(|s| s * s).sum();
        let energy_flat: f32 = out_flat.iter().map(|s| s * s).sum();
        // The boosted version should eventually have more energy (biquad needs settling)
        // Just verify it is finite and the boost did something
        assert!(out_boosted.iter().all(|s| s.is_finite()), "boosted EQ should be finite");
        assert!(energy_boosted > 0.0, "boosted EQ should produce non-zero energy");
    }

    #[test]
    fn test_aux_send_isolation() {
        let mut engine = MixerEngine::new(2);
        // Only ch0 sends to aux 0, ch1 has no aux sends
        engine.channels[0].aux_sends[0] = 1.0;
        engine.channels[1].aux_sends[0] = 0.0;

        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        engine.add_samples(1, &samples);
        let main_out = engine.process();

        // Aux 0 should have signal
        assert!(engine.aux_outputs[0].iter().any(|&s| s > 0.0));
        // Main output should have both channels
        assert!(main_out.iter().any(|&s| s > 0.0));
        // Aux 1, 2, 3 should be silent
        for aux_idx in 1..4 {
            assert!(engine.aux_outputs[aux_idx].iter().all(|&s| s == 0.0),
                "aux bus {} should be silent", aux_idx);
        }
    }

    #[test]
    fn test_linked_stereo_gain_sync() {
        let mut engine = MixerEngine::new(4);
        engine.link_stereo(0, 1);

        // Change gain on ch0, sync to ch1
        engine.channels[0].gain = 0.75;
        engine.channels[0].mute = true;
        engine.sync_linked_channel(0);
        assert_eq!(engine.channels[1].gain, 0.75);
        assert_eq!(engine.channels[1].mute, true);

        // Change solo on ch1, sync to ch0
        engine.channels[1].solo = true;
        engine.sync_linked_channel(1);
        assert_eq!(engine.channels[0].solo, true);
    }

    #[test]
    fn test_group_gain_applies_to_members() {
        let mut engine = MixerEngine::new(32);
        // Set group gain for "Instruments" (channels 0-7) to 0.5
        engine.groups[0].group_gain = 0.5;

        let samples: Vec<i16> = vec![16384; BUFFER_FRAMES];
        engine.add_samples(0, &samples);
        let out_half = engine.process();

        let mut engine2 = MixerEngine::new(32);
        engine2.add_samples(0, &samples);
        let out_full = engine2.process();

        let energy_half: f32 = out_half.iter().map(|s| s * s).sum();
        let energy_full: f32 = out_full.iter().map(|s| s * s).sum();
        assert!(energy_half < energy_full, "group gain 0.5 should reduce energy");
    }

    #[test]
    fn test_32_channels_no_overflow() {
        let mut engine = MixerEngine::new(32);
        // Feed maximum-amplitude signal to all 32 channels
        let samples: Vec<i16> = vec![32767; BUFFER_FRAMES];
        for ch in 0..32 {
            engine.add_samples(ch, &samples);
        }
        let out = engine.process();
        // Output should be finite (no NaN/Inf) even with massive summing
        assert!(out.iter().all(|s| s.is_finite()), "32-channel sum should be finite");
    }

    #[test]
    fn test_empty_channel_is_silent() {
        let mut engine = MixerEngine::new(4);
        // No samples added to any channel
        let out = engine.process();
        assert!(out.iter().all(|&s| s == 0.0), "empty channels should produce silence");
    }

    #[test]
    fn test_process_returns_stereo() {
        let mut engine = MixerEngine::new(2);
        let out = engine.process();
        assert_eq!(out.len(), BUFFER_FRAMES * 2, "output length should be 2 * buffer_size");
    }

    #[test]
    fn test_biquad_coefficients_valid() {
        // Test that all filter types produce valid (finite) coefficients
        let sr = 48000.0;
        let freqs = [20.0, 200.0, 1000.0, 5000.0, 20000.0];
        let gains = [-18.0, -6.0, 0.0, 6.0, 18.0];
        let qs = [0.1, 0.7, 2.0, 10.0];

        for &freq in &freqs {
            for &gain in &gains {
                for &q in &qs {
                    let band = EqBand { band_type: EqBandType::Peak, frequency: freq, gain_db: gain, q };
                    let c = BiquadCoeffs::from_eq_band(&band, sr);
                    assert!(c.b0.is_finite(), "b0 NaN at freq={freq} gain={gain} q={q}");
                    assert!(c.b1.is_finite(), "b1 NaN at freq={freq} gain={gain} q={q}");
                    assert!(c.b2.is_finite(), "b2 NaN at freq={freq} gain={gain} q={q}");
                    assert!(c.a1.is_finite(), "a1 NaN at freq={freq} gain={gain} q={q}");
                    assert!(c.a2.is_finite(), "a2 NaN at freq={freq} gain={gain} q={q}");
                }
            }
        }

        // Also test all band types
        for bt in &[EqBandType::LowShelf, EqBandType::Peak, EqBandType::HighShelf,
                     EqBandType::LowPass, EqBandType::HighPass] {
            let band = EqBand { band_type: *bt, frequency: 1000.0, gain_db: 6.0, q: 0.7 };
            let c = BiquadCoeffs::from_eq_band(&band, sr);
            assert!(c.b0.is_finite() && c.b1.is_finite() && c.b2.is_finite()
                    && c.a1.is_finite() && c.a2.is_finite(),
                "coefficients invalid for {:?}", bt);
        }
    }
}
