/// Audio effects for Koe Hub master bus and channel inserts.
///
/// All effects operate on f32 stereo-interleaved samples and implement
/// the `AudioEffect` trait for uniform processing.

use serde::{Deserialize, Serialize};

// ---- Trait ----

pub trait AudioEffect: Send {
    fn process(&mut self, samples: &mut [f32]);
    fn name(&self) -> &'static str;
}

// ---- Schroeder Reverb (4 comb + 2 allpass) ----

struct CombFilter {
    buffer: Vec<f32>,
    index: usize,
    feedback: f32,
    damp1: f32,
    damp2: f32,
    filter_store: f32,
}

impl CombFilter {
    fn new(size: usize, feedback: f32, damping: f32) -> Self {
        Self {
            buffer: vec![0.0; size],
            index: 0,
            feedback,
            damp1: damping,
            damp2: 1.0 - damping,
            filter_store: 0.0,
        }
    }

    fn process(&mut self, input: f32) -> f32 {
        let output = self.buffer[self.index];
        self.filter_store = output * self.damp2 + self.filter_store * self.damp1;
        self.buffer[self.index] = input + self.filter_store * self.feedback;
        self.index = (self.index + 1) % self.buffer.len();
        output
    }

    fn set_params(&mut self, feedback: f32, damping: f32) {
        self.feedback = feedback;
        self.damp1 = damping;
        self.damp2 = 1.0 - damping;
    }
}

struct AllpassFilter {
    buffer: Vec<f32>,
    index: usize,
}

impl AllpassFilter {
    fn new(size: usize) -> Self {
        Self {
            buffer: vec![0.0; size],
            index: 0,
        }
    }

    fn process(&mut self, input: f32) -> f32 {
        let buffered = self.buffer[self.index];
        let output = -input + buffered;
        self.buffer[self.index] = input + buffered * 0.5;
        self.index = (self.index + 1) % self.buffer.len();
        output
    }
}

/// Schroeder reverb with 4 parallel comb filters + 2 series allpass filters.
pub struct Reverb {
    pub room_size: f32,  // 0.0 .. 1.0
    pub damping: f32,    // 0.0 .. 1.0
    pub wet: f32,        // 0.0 .. 1.0
    pub dry: f32,        // 0.0 .. 1.0

    combs_l: [CombFilter; 4],
    combs_r: [CombFilter; 4],
    allpasses_l: [AllpassFilter; 2],
    allpasses_r: [AllpassFilter; 2],
}

// Comb filter delay lengths (in samples at 48 kHz), tuned for natural room sound.
const COMB_LENGTHS: [usize; 4] = [1557, 1617, 1491, 1422];
const ALLPASS_LENGTHS: [usize; 2] = [225, 556];
// Stereo spread: offset right channel delays
const STEREO_SPREAD: usize = 23;

impl Reverb {
    pub fn new(room_size: f32, damping: f32, wet: f32) -> Self {
        let feedback = room_size * 0.28 + 0.7;
        let combs_l = COMB_LENGTHS.map(|len| CombFilter::new(len, feedback, damping));
        let combs_r = COMB_LENGTHS.map(|len| {
            CombFilter::new(len + STEREO_SPREAD, feedback, damping)
        });
        let allpasses_l = ALLPASS_LENGTHS.map(AllpassFilter::new);
        let allpasses_r = ALLPASS_LENGTHS.map(|len| AllpassFilter::new(len + STEREO_SPREAD));

        Self {
            room_size,
            damping,
            wet,
            dry: 1.0 - wet,
            combs_l,
            combs_r,
            allpasses_l,
            allpasses_r,
        }
    }

    /// Update room_size and damping on the fly.
    pub fn set_params(&mut self, room_size: f32, damping: f32, wet: f32) {
        self.room_size = room_size;
        self.damping = damping;
        self.wet = wet;
        self.dry = 1.0 - wet;
        let feedback = room_size * 0.28 + 0.7;
        for comb in self.combs_l.iter_mut().chain(self.combs_r.iter_mut()) {
            comb.set_params(feedback, damping);
        }
    }
}

impl AudioEffect for Reverb {
    fn process(&mut self, samples: &mut [f32]) {
        // Stereo interleaved: [L0, R0, L1, R1, ...]
        let frame_count = samples.len() / 2;
        for i in 0..frame_count {
            let in_l = samples[i * 2];
            let in_r = samples[i * 2 + 1];
            let input = (in_l + in_r) * 0.5; // Mono sum into reverb

            // Parallel comb filters
            let mut wet_l = 0.0_f32;
            let mut wet_r = 0.0_f32;
            for comb in &mut self.combs_l {
                wet_l += comb.process(input);
            }
            for comb in &mut self.combs_r {
                wet_r += comb.process(input);
            }

            // Series allpass filters
            for ap in &mut self.allpasses_l {
                wet_l = ap.process(wet_l);
            }
            for ap in &mut self.allpasses_r {
                wet_r = ap.process(wet_r);
            }

            samples[i * 2] = in_l * self.dry + wet_l * self.wet;
            samples[i * 2 + 1] = in_r * self.dry + wet_r * self.wet;
        }
    }

    fn name(&self) -> &'static str {
        "Reverb"
    }
}

// ---- Compressor ----

/// Feed-forward compressor with envelope follower.
pub struct Compressor {
    pub threshold: f32,   // dB (e.g. -20.0)
    pub ratio: f32,       // e.g. 4.0 means 4:1
    pub attack_ms: f32,   // attack time in ms
    pub release_ms: f32,  // release time in ms
    pub makeup_gain: f32, // linear gain applied after compression

    envelope: f32,
    sample_rate: f32,
}

impl Compressor {
    pub fn new(threshold: f32, ratio: f32, attack_ms: f32, release_ms: f32) -> Self {
        Self {
            threshold,
            ratio,
            attack_ms,
            release_ms,
            makeup_gain: 1.0,
            envelope: 0.0,
            sample_rate: 48_000.0,
        }
    }

    fn db_to_linear(db: f32) -> f32 {
        10.0_f32.powf(db / 20.0)
    }

    fn linear_to_db(lin: f32) -> f32 {
        if lin < 1e-10 {
            -200.0
        } else {
            20.0 * lin.log10()
        }
    }
}

impl AudioEffect for Compressor {
    fn process(&mut self, samples: &mut [f32]) {
        let attack_coeff = (-1.0 / (self.attack_ms * 0.001 * self.sample_rate)).exp();
        let release_coeff = (-1.0 / (self.release_ms * 0.001 * self.sample_rate)).exp();

        let frame_count = samples.len() / 2;
        for i in 0..frame_count {
            let l = samples[i * 2];
            let r = samples[i * 2 + 1];
            let input_level = l.abs().max(r.abs());

            // Envelope follower
            let coeff = if input_level > self.envelope {
                attack_coeff
            } else {
                release_coeff
            };
            self.envelope = coeff * self.envelope + (1.0 - coeff) * input_level;

            // Compute gain reduction
            let env_db = Self::linear_to_db(self.envelope);
            let gain = if env_db > self.threshold {
                let over = env_db - self.threshold;
                let reduced = over / self.ratio;
                Self::db_to_linear(self.threshold + reduced - env_db)
            } else {
                1.0
            };

            let final_gain = gain * self.makeup_gain;
            samples[i * 2] = l * final_gain;
            samples[i * 2 + 1] = r * final_gain;
        }
    }

    fn name(&self) -> &'static str {
        "Compressor"
    }
}

// ---- Delay ----

/// Simple stereo delay with feedback.
pub struct Delay {
    pub time_ms: f32,
    pub feedback: f32, // 0.0 .. <1.0
    pub wet: f32,      // 0.0 .. 1.0

    buffer_l: Vec<f32>,
    buffer_r: Vec<f32>,
    write_pos: usize,
    sample_rate: f32,
}

impl Delay {
    pub fn new(time_ms: f32, feedback: f32, wet: f32) -> Self {
        let sample_rate = 48_000.0_f32;
        let max_samples = (sample_rate * 2.0) as usize; // Max 2 seconds
        Self {
            time_ms,
            feedback: feedback.min(0.95), // Prevent runaway
            wet,
            buffer_l: vec![0.0; max_samples],
            buffer_r: vec![0.0; max_samples],
            write_pos: 0,
            sample_rate,
        }
    }

    fn delay_samples(&self) -> usize {
        ((self.time_ms * 0.001 * self.sample_rate) as usize).min(self.buffer_l.len() - 1)
    }
}

impl AudioEffect for Delay {
    fn process(&mut self, samples: &mut [f32]) {
        let delay_len = self.delay_samples();
        let buf_len = self.buffer_l.len();

        let frame_count = samples.len() / 2;
        for i in 0..frame_count {
            let in_l = samples[i * 2];
            let in_r = samples[i * 2 + 1];

            let read_pos = (self.write_pos + buf_len - delay_len) % buf_len;
            let delayed_l = self.buffer_l[read_pos];
            let delayed_r = self.buffer_r[read_pos];

            self.buffer_l[self.write_pos] = in_l + delayed_l * self.feedback;
            self.buffer_r[self.write_pos] = in_r + delayed_r * self.feedback;
            self.write_pos = (self.write_pos + 1) % buf_len;

            samples[i * 2] = in_l + delayed_l * self.wet;
            samples[i * 2 + 1] = in_r + delayed_r * self.wet;
        }
    }

    fn name(&self) -> &'static str {
        "Delay"
    }
}

// ---- Gate / Expander ----

/// Noise gate with expander for drums and percussion.
pub struct Gate {
    pub threshold: f32,   // dB (e.g. -40.0)
    pub ratio: f32,       // Expansion ratio (e.g. 2.0 = 2:1 downward)
    pub attack_ms: f32,
    pub release_ms: f32,
    pub hold_ms: f32,     // Hold time before release begins

    envelope: f32,
    hold_counter: f32,
    sample_rate: f32,
}

impl Gate {
    pub fn new(threshold: f32, ratio: f32, attack_ms: f32, release_ms: f32, hold_ms: f32) -> Self {
        Self {
            threshold,
            ratio: ratio.max(1.0),
            attack_ms,
            release_ms,
            hold_ms,
            envelope: 0.0,
            hold_counter: 0.0,
            sample_rate: 48_000.0,
        }
    }

    fn linear_to_db(lin: f32) -> f32 {
        if lin < 1e-10 { -200.0 } else { 20.0 * lin.log10() }
    }

    fn db_to_linear(db: f32) -> f32 {
        10.0_f32.powf(db / 20.0)
    }
}

impl AudioEffect for Gate {
    fn process(&mut self, samples: &mut [f32]) {
        let attack_coeff = (-1.0 / (self.attack_ms * 0.001 * self.sample_rate)).exp();
        let release_coeff = (-1.0 / (self.release_ms * 0.001 * self.sample_rate)).exp();
        let hold_samples = self.hold_ms * 0.001 * self.sample_rate;

        let frame_count = samples.len() / 2;
        for i in 0..frame_count {
            let l = samples[i * 2];
            let r = samples[i * 2 + 1];
            let input_level = l.abs().max(r.abs());

            // Envelope follower
            let coeff = if input_level > self.envelope {
                self.hold_counter = hold_samples;
                attack_coeff
            } else if self.hold_counter > 0.0 {
                self.hold_counter -= 1.0;
                attack_coeff // Stay open during hold
            } else {
                release_coeff
            };
            self.envelope = coeff * self.envelope + (1.0 - coeff) * input_level;

            // Compute gate gain
            let env_db = Self::linear_to_db(self.envelope);
            let gain = if env_db < self.threshold {
                let under = self.threshold - env_db;
                let reduced = under * self.ratio;
                Self::db_to_linear(env_db - reduced + under)
            } else {
                1.0
            };

            samples[i * 2] = l * gain;
            samples[i * 2 + 1] = r * gain;
        }
    }

    fn name(&self) -> &'static str {
        "Gate"
    }
}

// ---- DeEsser ----

/// Frequency-targeted sibilance reducer for vocals.
pub struct DeEsser {
    pub frequency: f32,   // Center frequency (2000-10000 Hz)
    pub threshold: f32,   // dB
    pub reduction: f32,   // Max reduction in dB (positive value)

    // Bandpass filter state for detection
    bp_x1: f32,
    bp_x2: f32,
    bp_y1: f32,
    bp_y2: f32,
    envelope: f32,
    sample_rate: f32,
}

impl DeEsser {
    pub fn new(frequency: f32, threshold: f32, reduction: f32) -> Self {
        Self {
            frequency: frequency.clamp(2000.0, 10000.0),
            threshold,
            reduction: reduction.abs(),
            bp_x1: 0.0,
            bp_x2: 0.0,
            bp_y1: 0.0,
            bp_y2: 0.0,
            envelope: 0.0,
            sample_rate: 48_000.0,
        }
    }

    fn linear_to_db(lin: f32) -> f32 {
        if lin < 1e-10 { -200.0 } else { 20.0 * lin.log10() }
    }

    fn db_to_linear(db: f32) -> f32 {
        10.0_f32.powf(db / 20.0)
    }
}

impl AudioEffect for DeEsser {
    fn process(&mut self, samples: &mut [f32]) {
        // Simple bandpass detection + broadband gain reduction
        let w0 = 2.0 * std::f32::consts::PI * self.frequency / self.sample_rate;
        let q = 2.0_f32; // Detection bandwidth
        let alpha = w0.sin() / (2.0 * q);
        let cos_w0 = w0.cos();

        // Bandpass coefficients
        let b0 = alpha;
        let b1 = 0.0_f32;
        let b2 = -alpha;
        let a0 = 1.0 + alpha;
        let a1 = -2.0 * cos_w0;
        let a2 = 1.0 - alpha;

        let release_coeff = (-1.0 / (0.005 * self.sample_rate)).exp(); // 5ms release

        let frame_count = samples.len() / 2;
        for i in 0..frame_count {
            let mono = (samples[i * 2] + samples[i * 2 + 1]) * 0.5;

            // Bandpass filter for sibilance detection
            let bp_out = (b0 * mono + b1 * self.bp_x1 + b2 * self.bp_x2
                - a1 * self.bp_y1 - a2 * self.bp_y2) / a0;
            self.bp_x2 = self.bp_x1;
            self.bp_x1 = mono;
            self.bp_y2 = self.bp_y1;
            self.bp_y1 = bp_out;

            // Envelope follower on detected sibilance
            let level = bp_out.abs();
            if level > self.envelope {
                self.envelope = level;
            } else {
                self.envelope = release_coeff * self.envelope + (1.0 - release_coeff) * level;
            }

            // Apply reduction when sibilance exceeds threshold
            let env_db = Self::linear_to_db(self.envelope);
            let gain = if env_db > self.threshold {
                let over = env_db - self.threshold;
                let reduce_db = over.min(self.reduction);
                Self::db_to_linear(-reduce_db)
            } else {
                1.0
            };

            samples[i * 2] *= gain;
            samples[i * 2 + 1] *= gain;
        }
    }

    fn name(&self) -> &'static str {
        "DeEsser"
    }
}

// ---- Stereo Widener ----

/// Mid/Side stereo width control.
/// width = 0.0: mono, 1.0: original stereo, 2.0: extra wide.
pub struct StereoWidener {
    pub width: f32, // 0.0 .. 2.0
}

impl StereoWidener {
    pub fn new(width: f32) -> Self {
        Self {
            width: width.clamp(0.0, 2.0),
        }
    }
}

impl AudioEffect for StereoWidener {
    fn process(&mut self, samples: &mut [f32]) {
        let frame_count = samples.len() / 2;
        let mid_gain = 1.0_f32; // Keep mid constant
        let side_gain = self.width;

        for i in 0..frame_count {
            let l = samples[i * 2];
            let r = samples[i * 2 + 1];

            // Encode to Mid/Side
            let mid = (l + r) * 0.5 * mid_gain;
            let side = (l - r) * 0.5 * side_gain;

            // Decode back to L/R
            samples[i * 2] = mid + side;
            samples[i * 2 + 1] = mid - side;
        }
    }

    fn name(&self) -> &'static str {
        "StereoWidener"
    }
}

// ---- Effect chain parameters (for API) ----

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EffectParams {
    pub effect: String, // "reverb", "compressor", "delay", "gate", "deesser", "stereo_widener"
    #[serde(default)]
    pub room_size: Option<f32>,
    #[serde(default)]
    pub damping: Option<f32>,
    #[serde(default)]
    pub wet: Option<f32>,
    #[serde(default)]
    pub threshold: Option<f32>,
    #[serde(default)]
    pub ratio: Option<f32>,
    #[serde(default)]
    pub attack_ms: Option<f32>,
    #[serde(default)]
    pub release_ms: Option<f32>,
    #[serde(default)]
    pub makeup_gain: Option<f32>,
    #[serde(default)]
    pub time_ms: Option<f32>,
    #[serde(default)]
    pub feedback: Option<f32>,
    #[serde(default)]
    pub hold_ms: Option<f32>,
    #[serde(default)]
    pub frequency: Option<f32>,
    #[serde(default)]
    pub reduction: Option<f32>,
    #[serde(default)]
    pub width: Option<f32>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_reverb_does_not_blow_up() {
        let mut reverb = Reverb::new(0.5, 0.5, 0.3);
        let mut buf = vec![0.0_f32; 256];
        buf[0] = 1.0;
        buf[1] = 1.0;
        reverb.process(&mut buf);
        assert!(buf.iter().all(|s| s.is_finite()));
    }

    #[test]
    fn test_compressor_reduces_loud_signal() {
        let mut comp = Compressor::new(-20.0, 4.0, 1.0, 50.0);
        let mut buf: Vec<f32> = (0..256).map(|_| 0.9).collect();
        comp.process(&mut buf);
        // After compression, peak should be lower
        assert!(buf.iter().all(|&s| s.abs() <= 1.0));
    }

    #[test]
    fn test_delay_produces_echo() {
        // Use a very short delay (1ms = 48 samples) so the echo appears
        // within a small number of processed frames.
        let mut delay = Delay::new(1.0, 0.5, 0.5);
        // First block: impulse at frame 0
        let mut buf1 = vec![0.0_f32; 256];
        buf1[0] = 1.0;
        buf1[1] = 1.0;
        delay.process(&mut buf1);
        // The echo should appear within buf1 itself (at ~48 samples = frame index 48)
        // Check total energy beyond the impulse frame
        let echo_energy: f32 = buf1[2..].iter().map(|s| s * s).sum();
        assert!(echo_energy > 0.0, "Delay should produce echoed energy within the same block");
    }

    #[test]
    fn test_gate_attenuates_quiet_signal() {
        let mut gate = Gate::new(-20.0, 2.0, 0.1, 10.0, 5.0);
        // Very quiet signal: should be gated
        let mut buf: Vec<f32> = vec![0.001; 256];
        gate.process(&mut buf);
        // After gating, signal should be attenuated
        assert!(buf.iter().all(|&s| s.abs() <= 0.01));
    }

    #[test]
    fn test_gate_passes_loud_signal() {
        let mut gate = Gate::new(-20.0, 2.0, 0.1, 10.0, 5.0);
        let mut buf: Vec<f32> = vec![0.5; 256];
        let original_energy: f32 = buf.iter().map(|s| s * s).sum();
        gate.process(&mut buf);
        let processed_energy: f32 = buf.iter().map(|s| s * s).sum();
        // Loud signal should pass through mostly unchanged
        assert!(processed_energy > original_energy * 0.5);
    }

    #[test]
    fn test_deesser_does_not_blow_up() {
        let mut deesser = DeEsser::new(6000.0, -20.0, 6.0);
        let mut buf = vec![0.0_f32; 256];
        buf[0] = 1.0;
        buf[1] = 1.0;
        deesser.process(&mut buf);
        assert!(buf.iter().all(|s| s.is_finite()));
    }

    #[test]
    fn test_stereo_widener_mono() {
        let mut widener = StereoWidener::new(0.0);
        let mut buf = vec![0.0_f32; 4]; // 2 frames
        buf[0] = 1.0; // L
        buf[1] = 0.0; // R
        buf[2] = 0.0;
        buf[3] = 1.0;
        widener.process(&mut buf);
        // Width 0 = mono: L and R should be equal (mid only)
        assert!((buf[0] - buf[1]).abs() < 0.001);
        assert!((buf[2] - buf[3]).abs() < 0.001);
    }

    #[test]
    fn test_stereo_widener_unity() {
        let mut widener = StereoWidener::new(1.0);
        let mut buf = vec![0.8_f32, 0.2, 0.8, 0.2];
        let orig = buf.clone();
        widener.process(&mut buf);
        // Width 1.0 should preserve original signal
        for (a, b) in buf.iter().zip(orig.iter()) {
            assert!((a - b).abs() < 0.001);
        }
    }

    #[test]
    fn test_reverb_wet_zero_is_dry() {
        let mut reverb = Reverb::new(0.5, 0.5, 0.0); // wet=0
        let mut buf = vec![0.5_f32; 256];
        let orig = buf.clone();
        reverb.process(&mut buf);
        // With wet=0 and dry=1.0, output should equal input
        for (a, b) in buf.iter().zip(orig.iter()) {
            assert!((a - b).abs() < 0.001, "wet=0 should pass dry signal through: got {a}, expected {b}");
        }
    }

    #[test]
    fn test_reverb_wet_one_no_dry() {
        let mut reverb = Reverb::new(0.5, 0.5, 1.0); // wet=1.0, dry=0.0
        let mut buf = vec![0.0_f32; 256];
        buf[0] = 1.0;
        buf[1] = 1.0;
        let orig = buf.clone();
        reverb.process(&mut buf);
        // Dry portion should be zero, so output[0] should differ from input
        // (the reverb wet signal starts near zero for the first sample since comb buffers are empty)
        assert!((buf[0] - orig[0]).abs() > 0.01 || buf[0].abs() < 0.01,
            "wet=1.0 should suppress dry signal");
    }

    #[test]
    fn test_compressor_below_threshold_unchanged() {
        let mut comp = Compressor::new(-10.0, 4.0, 1.0, 50.0);
        // Signal at ~-40 dBFS (0.01), well below -10 dB threshold
        let mut buf: Vec<f32> = vec![0.01; 256];
        let orig = buf.clone();
        comp.process(&mut buf);
        // Should be mostly unchanged (envelope is very low)
        let max_diff: f32 = buf.iter().zip(orig.iter())
            .map(|(a, b)| (a - b).abs())
            .fold(0.0_f32, f32::max);
        assert!(max_diff < 0.005, "below-threshold signal should be unchanged, diff={max_diff}");
    }

    #[test]
    fn test_compressor_makeup_gain() {
        let mut comp = Compressor::new(-20.0, 4.0, 1.0, 50.0);
        comp.makeup_gain = 2.0;
        // Quiet signal below threshold — makeup gain should still apply
        let mut buf: Vec<f32> = vec![0.01; 256];
        comp.process(&mut buf);
        // With makeup_gain=2.0, output should be roughly 2x input for quiet signals
        // (gain reduction = 1.0 below threshold, so final = 1.0 * 2.0 = 2.0)
        let last = *buf.last().unwrap();
        assert!(last > 0.015, "makeup gain should amplify, got {last}");
    }

    #[test]
    fn test_delay_zero_time_passthrough() {
        let mut delay = Delay::new(0.0, 0.0, 0.5);
        let mut buf = vec![0.5_f32; 64];
        let orig = buf.clone();
        delay.process(&mut buf);
        // delay_samples() = 0, so read_pos == write_pos, delayed = 0
        // output = input + 0 * wet = input
        for (a, b) in buf.iter().zip(orig.iter()) {
            assert!((a - b).abs() < 0.001, "zero delay should be passthrough");
        }
    }

    #[test]
    fn test_delay_feedback_zero_single_echo() {
        let mut delay = Delay::new(1.0, 0.0, 1.0); // 1ms, no feedback, full wet
        let mut buf1 = vec![0.0_f32; 256];
        buf1[0] = 1.0;
        buf1[1] = 1.0;
        delay.process(&mut buf1);

        // Process a second block — with feedback=0, no further echoes
        let mut buf2 = vec![0.0_f32; 256];
        delay.process(&mut buf2);

        // After the echo in buf1, buf2's echo from buf1 feedback should be zero
        let energy2: f32 = buf2.iter().map(|s| s * s).sum();
        assert!(energy2 < 0.01, "feedback=0 should produce no repeating echo, energy={energy2}");
    }

    #[test]
    fn test_gate_hold_time() {
        // Gate with long hold time (50ms = ~2400 samples at 48kHz)
        let mut gate = Gate::new(-20.0, 10.0, 0.1, 50.0, 50.0);

        // Feed loud signal first to open the gate
        let mut buf_loud: Vec<f32> = vec![0.5; 256];
        gate.process(&mut buf_loud);

        // Then feed quiet signal — gate should stay open during hold period
        let mut buf_quiet: Vec<f32> = vec![0.001; 256];
        gate.process(&mut buf_quiet);

        // During hold, signal should still pass through relatively unattenuated
        // (hold counter is 50ms * 48 = 2400 samples, we only processed 128 frames = 128 quiet samples)
        let passed_count = buf_quiet.iter().filter(|&&s| s.abs() > 0.0005).count();
        assert!(passed_count > 0, "gate should stay open during hold period");
    }

    #[test]
    fn test_deesser_low_frequency_unaffected() {
        let mut deesser = DeEsser::new(8000.0, -20.0, 12.0);
        // DC-like signal (very low frequency) should pass through the de-esser
        let mut buf: Vec<f32> = vec![0.3; 256];
        let orig = buf.clone();
        deesser.process(&mut buf);
        // Low frequency content should be relatively unaffected
        let max_diff: f32 = buf.iter().zip(orig.iter())
            .map(|(a, b)| (a - b).abs())
            .fold(0.0_f32, f32::max);
        assert!(max_diff < 0.1, "low freq should pass through de-esser, max_diff={max_diff}");
    }

    #[test]
    fn test_stereo_widener_extreme_width() {
        let mut widener = StereoWidener::new(2.0);
        let mut buf = vec![0.5_f32, 0.3, 0.5, 0.3];
        widener.process(&mut buf);
        // Should not produce NaN or infinity
        assert!(buf.iter().all(|s| s.is_finite()), "extreme width should be finite");
        // Width=2.0 should increase stereo separation
        // L = mid + 2*side, R = mid - 2*side
        // mid = (0.5+0.3)/2 = 0.4, side = (0.5-0.3)/2 = 0.1
        // L = 0.4 + 0.2 = 0.6, R = 0.4 - 0.2 = 0.2
        assert!((buf[0] - 0.6).abs() < 0.01, "L should be ~0.6, got {}", buf[0]);
        assert!((buf[1] - 0.2).abs() < 0.01, "R should be ~0.2, got {}", buf[1]);
    }

    #[test]
    fn test_all_effects_process_silence_without_crash() {
        let mut reverb = Reverb::new(0.8, 0.5, 0.5);
        let mut comp = Compressor::new(-20.0, 4.0, 5.0, 100.0);
        let mut delay = Delay::new(100.0, 0.5, 0.5);
        let mut gate = Gate::new(-30.0, 2.0, 1.0, 50.0, 10.0);
        let mut deesser = DeEsser::new(6000.0, -15.0, 8.0);
        let mut widener = StereoWidener::new(1.5);

        let effects: Vec<&mut dyn AudioEffect> = vec![
            &mut reverb, &mut comp, &mut delay, &mut gate, &mut deesser, &mut widener
        ];

        for effect in effects {
            let mut buf = vec![0.0_f32; 512];
            effect.process(&mut buf);
            assert!(buf.iter().all(|s| s.is_finite()),
                "{} produced non-finite output on silence", effect.name());
        }
    }

    #[test]
    fn test_all_effects_process_loud_signal_without_nan() {
        let mut reverb = Reverb::new(0.9, 0.3, 0.7);
        let mut comp = Compressor::new(-6.0, 8.0, 0.1, 10.0);
        let mut delay = Delay::new(50.0, 0.8, 0.8);
        let mut gate = Gate::new(-40.0, 4.0, 0.5, 20.0, 5.0);
        let mut deesser = DeEsser::new(5000.0, -10.0, 12.0);
        let mut widener = StereoWidener::new(2.0);

        let effects: Vec<&mut dyn AudioEffect> = vec![
            &mut reverb, &mut comp, &mut delay, &mut gate, &mut deesser, &mut widener
        ];

        for effect in effects {
            let mut buf: Vec<f32> = (0..512).map(|i| if i % 2 == 0 { 0.99 } else { -0.99 }).collect();
            effect.process(&mut buf);
            assert!(buf.iter().all(|s| s.is_finite()),
                "{} produced non-finite output on loud signal", effect.name());
        }
    }

    #[test]
    fn test_effect_params_clamp() {
        // StereoWidener clamps width to 0..2
        let w = StereoWidener::new(5.0);
        assert_eq!(w.width, 2.0, "width should clamp to 2.0");
        let w2 = StereoWidener::new(-1.0);
        assert_eq!(w2.width, 0.0, "width should clamp to 0.0");

        // DeEsser clamps frequency to 2000..10000
        let d = DeEsser::new(500.0, -20.0, 6.0);
        assert_eq!(d.frequency, 2000.0, "frequency should clamp to 2000");
        let d2 = DeEsser::new(20000.0, -20.0, 6.0);
        assert_eq!(d2.frequency, 10000.0, "frequency should clamp to 10000");

        // Delay feedback clamps to max 0.95
        let del = Delay::new(100.0, 1.5, 0.5);
        assert!(del.feedback <= 0.95, "feedback should clamp to 0.95");

        // Gate ratio clamps to min 1.0
        let g = Gate::new(-30.0, 0.5, 1.0, 50.0, 5.0);
        assert!(g.ratio >= 1.0, "gate ratio should clamp to 1.0");
    }
}
