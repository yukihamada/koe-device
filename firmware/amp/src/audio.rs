/// audio.rs — I2S microphone input, ring buffer, onset detection
///
/// 5-second circular ring buffer at 16 kHz mono i16 = 160,000 samples.
/// Onset detection: sliding-window RMS compared to a decaying background floor.
/// Trigger fires when current frame RMS is > ONSET_RATIO_DB dB above the floor.

pub const SAMPLE_RATE: usize = 16_000;
pub const LOOKBACK_SECS: usize = 5;
pub const BUF_SAMPLES: usize = SAMPLE_RATE * LOOKBACK_SECS; // 80_000 samples
pub const FRAME_SAMPLES: usize = 512; // ~32 ms per frame
pub const ONSET_RATIO_DB: f32 = 8.0; // dB above background floor to trigger onset

// Floor tracker time constants (exponential moving average)
const FLOOR_ATTACK: f32 = 0.95; // fast attack so floor rises quickly with loud ambient
const FLOOR_RELEASE: f32 = 0.9995; // very slow release so the floor only decays gradually

/// Circular ring buffer of i16 audio samples.
pub struct RingBuffer {
    buf: Vec<i16>,
    write_pos: usize,
    filled: bool,
}

impl RingBuffer {
    pub fn new() -> Self {
        Self {
            buf: vec![0i16; BUF_SAMPLES],
            write_pos: 0,
            filled: false,
        }
    }

    /// Push a slice of samples into the ring.  Returns `true` if the buffer
    /// is now fully populated (first 5 s have passed).
    pub fn push(&mut self, samples: &[i16]) -> bool {
        for &s in samples {
            self.buf[self.write_pos] = s;
            self.write_pos = (self.write_pos + 1) % BUF_SAMPLES;
            if self.write_pos == 0 {
                self.filled = true;
            }
        }
        self.filled
    }

    /// Copy the most recent `n` samples into `out`.  Panics if `n > BUF_SAMPLES`.
    pub fn recent(&self, n: usize, out: &mut [i16]) {
        assert!(n <= BUF_SAMPLES);
        assert!(out.len() >= n);
        let start = (self.write_pos + BUF_SAMPLES - n) % BUF_SAMPLES;
        for i in 0..n {
            out[i] = self.buf[(start + i) % BUF_SAMPLES];
        }
    }
}

impl Default for RingBuffer {
    fn default() -> Self {
        Self::new()
    }
}

/// RMS energy of a slice of i16 samples, returned as a linear f32 value.
pub fn rms(samples: &[i16]) -> f32 {
    if samples.is_empty() {
        return 0.0;
    }
    let sum_sq: f64 = samples.iter().map(|&s| (s as f64) * (s as f64)).sum();
    (sum_sq / samples.len() as f64).sqrt() as f32
}

/// Convert a linear RMS ratio to dB.
#[inline]
fn ratio_to_db(ratio: f32) -> f32 {
    if ratio <= 0.0 {
        return -f32::INFINITY;
    }
    20.0 * ratio.log10()
}

/// Onset detector using an exponential-moving-average background floor.
///
/// Call `process_frame()` with each new `FRAME_SAMPLES`-length slice.
/// Returns `true` on the first frame that exceeds the threshold, then
/// enforces a refractory period before it can fire again.
pub struct OnsetDetector {
    /// Background RMS floor (exponential moving average, linear scale).
    floor: f32,
    /// Minimum floor so we don't trigger on absolute silence turning into any signal.
    min_floor: f32,
    /// Refractory counter: how many frames remain before we can trigger again.
    refractory: u32,
    /// Refractory period after a trigger (frames).  At 32 ms/frame ≈ 1.5 s.
    refractory_frames: u32,
}

impl OnsetDetector {
    pub fn new() -> Self {
        Self {
            floor: 100.0, // start with a modest floor (~100 LSB RMS ≈ -50 dBFS)
            min_floor: 50.0,
            refractory: 0,
            refractory_frames: 48, // ~1.5 s at 32 ms/frame
        }
    }

    /// Process one frame of audio.  Returns `true` if an onset is detected.
    pub fn process_frame(&mut self, samples: &[i16]) -> bool {
        let current_rms = rms(samples);

        // Update background floor (only when we're not in a refractory window,
        // so loud sustained sound doesn't inflate the floor during recording).
        if self.refractory == 0 {
            if current_rms > self.floor {
                // Fast attack
                self.floor = FLOOR_ATTACK * self.floor + (1.0 - FLOOR_ATTACK) * current_rms;
            } else {
                // Slow release
                self.floor = FLOOR_RELEASE * self.floor + (1.0 - FLOOR_RELEASE) * current_rms;
            }
            // Never let the floor drop below the minimum
            if self.floor < self.min_floor {
                self.floor = self.min_floor;
            }
        }

        // Decrement refractory counter
        if self.refractory > 0 {
            self.refractory -= 1;
            return false;
        }

        // Check onset condition: current RMS must exceed floor by ONSET_RATIO_DB dB
        let db_above = ratio_to_db(current_rms / self.floor.max(1.0));
        if db_above >= ONSET_RATIO_DB {
            log::info!(
                "[audio] onset detected: rms={:.1} floor={:.1} db_above={:.1}",
                current_rms,
                self.floor,
                db_above
            );
            self.refractory = self.refractory_frames;
            return true;
        }

        false
    }

    pub fn floor_rms(&self) -> f32 {
        self.floor
    }
}

impl Default for OnsetDetector {
    fn default() -> Self {
        Self::new()
    }
}

// ---- Loop detection ----

/// Minimum interval between onsets to count as a rhythmic loop (2 seconds).
const LOOP_INTERVAL_MIN_MS: u32 = 2_000;
/// Maximum interval between onsets to count as a rhythmic loop (4 seconds).
const LOOP_INTERVAL_MAX_MS: u32 = 4_000;
/// Tolerance when comparing loop intervals: ±200 ms.
const LOOP_INTERVAL_TOLERANCE_MS: u32 = 200;
/// How many consistent intervals must repeat before we declare a loop detected.
const LOOP_MIN_REPEATS: usize = 2;

/// Detects rhythmic looping by tracking onset timestamps.
///
/// A "loop" is declared when:
/// - An onset fires again within 2–4 seconds of the previous onset
/// - This repeats at least 2 times with a consistent interval (±200 ms tolerance)
///
/// Typical use: call `record_onset()` whenever `OnsetDetector::process_frame()` returns `true`.
pub struct LoopDetector {
    /// Ring buffer of the last 8 onset timestamps (seconds since device start).
    onset_times: [f64; 8],
    /// Number of onsets recorded so far (saturates at 8 for the ring buffer index).
    onset_count: usize,
    /// Total number of loops detected over the lifetime of this detector.
    loop_count: u32,
    /// Detected loop interval in milliseconds, if a loop has been found.
    loop_interval_ms: Option<u32>,
}

impl LoopDetector {
    pub fn new() -> Self {
        Self {
            onset_times: [0.0f64; 8],
            onset_count: 0,
            loop_count: 0,
            loop_interval_ms: None,
        }
    }

    /// Record a new onset at `time_secs` (wall-clock seconds, e.g. from a monotonic counter).
    /// Returns `true` if this onset completes a detected loop pattern.
    pub fn record_onset(&mut self, time_secs: f64) -> bool {
        let idx = self.onset_count % 8;
        self.onset_times[idx] = time_secs;
        self.onset_count += 1;

        // Need at least LOOP_MIN_REPEATS + 1 onsets to have LOOP_MIN_REPEATS intervals.
        if self.onset_count < LOOP_MIN_REPEATS + 1 {
            return false;
        }

        // Look at the last min(onset_count, 8) onsets in chronological order.
        let available = self.onset_count.min(8);
        // Build a small sorted slice of the most recent timestamps.
        let mut recent = [0.0f64; 8];
        let start_slot = self.onset_count.saturating_sub(available);
        for i in 0..available {
            recent[i] = self.onset_times[(start_slot + i) % 8];
        }
        let times = &recent[..available];

        // Compute intervals between consecutive onsets.
        let mut intervals_ms = [0u32; 7];
        let n_intervals = available - 1;
        for i in 0..n_intervals {
            let diff_ms = ((times[i + 1] - times[i]) * 1000.0) as u32;
            intervals_ms[i] = diff_ms;
        }

        // Find a reference interval that falls within [LOOP_INTERVAL_MIN_MS, LOOP_INTERVAL_MAX_MS].
        // Then count how many subsequent intervals are consistent with it (±tolerance).
        // We only need the last few intervals (up to LOOP_MIN_REPEATS).
        let check_from = if n_intervals >= LOOP_MIN_REPEATS { n_intervals - LOOP_MIN_REPEATS } else { 0 };
        let ref_interval = intervals_ms[check_from];

        if ref_interval < LOOP_INTERVAL_MIN_MS || ref_interval > LOOP_INTERVAL_MAX_MS {
            return false;
        }

        let consistent = intervals_ms[check_from..n_intervals]
            .iter()
            .all(|&iv| {
                iv >= ref_interval.saturating_sub(LOOP_INTERVAL_TOLERANCE_MS)
                    && iv <= ref_interval + LOOP_INTERVAL_TOLERANCE_MS
            });

        if consistent {
            self.loop_count += 1;
            self.loop_interval_ms = Some(ref_interval);
            log::info!(
                "[audio] loop detected: interval={}ms total_loops={}",
                ref_interval,
                self.loop_count
            );
            return true;
        }

        false
    }

    /// Total number of loops detected.
    pub fn loop_count(&self) -> u32 {
        self.loop_count
    }

    /// The most recently detected loop interval in milliseconds, if any.
    pub fn loop_interval_ms(&self) -> Option<u32> {
        self.loop_interval_ms
    }

    /// Reset the detector state (call between sessions).
    pub fn reset(&mut self) {
        self.onset_times = [0.0f64; 8];
        self.onset_count = 0;
        self.loop_count = 0;
        self.loop_interval_ms = None;
    }
}

impl Default for LoopDetector {
    fn default() -> Self {
        Self::new()
    }
}

// ---- Instrument classification ----

/// Coarse instrument hint derived from onset RMS, decay RMS, and frame count.
///
/// This is intentionally simple — accurate classification requires an ML model.
/// The goal is a best-effort label suitable for display/logging on an embedded device.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum InstrumentHint {
    /// Sustained decay, mid RMS — e.g. strummed acoustic guitar.
    AcousticGuitar,
    /// Sustained signal with higher RMS — e.g. electric guitar through amp.
    ElectricGuitar,
    /// Low onset energy, slow decay — typical of bass guitar.
    Bass,
    /// Sharp onset with fast decay — drums, percussion, hand claps.
    Percussion,
    /// Continuous RMS with formant-like variation — human voice.
    Vocals,
    /// Could not classify with confidence.
    Unknown,
}

impl InstrumentHint {
    /// Returns a static string label suitable for JSON serialisation.
    pub fn as_str(&self) -> &'static str {
        match self {
            InstrumentHint::AcousticGuitar => "acoustic_guitar",
            InstrumentHint::ElectricGuitar => "electric_guitar",
            InstrumentHint::Bass           => "bass",
            InstrumentHint::Percussion     => "percussion",
            InstrumentHint::Vocals         => "vocals",
            InstrumentHint::Unknown        => "unknown",
        }
    }
}

/// Classify an instrument from three simple RMS features.
///
/// # Parameters
/// - `onset_rms`   — RMS of the frame that triggered the onset detector (peak energy).
/// - `decay_rms`   — RMS averaged over the following ~10 frames (~320 ms of tail).
/// - `frame_count` — Number of frames (each ~32 ms) for which the signal stayed above
///                   the noise floor after the onset.  Longer → more sustained.
pub fn classify_instrument(onset_rms: f32, decay_rms: f32, frame_count: u32) -> InstrumentHint {
    // Guard: treat silence as unknown
    if onset_rms < 50.0 {
        return InstrumentHint::Unknown;
    }

    let decay_ratio = if onset_rms > 0.0 { decay_rms / onset_rms } else { 0.0 };

    // Sharp percussive attack: fast decay (ratio < 0.25) regardless of level.
    if decay_ratio < 0.25 && frame_count < 15 {
        return InstrumentHint::Percussion;
    }

    // Very low onset energy with slow decay → bass
    if onset_rms < 400.0 && decay_ratio > 0.55 {
        return InstrumentHint::Bass;
    }

    // Vocals: moderate onset, continuous (long frame count), decay ratio in mid range
    if frame_count >= 30 && decay_ratio > 0.35 && decay_ratio < 0.80 && onset_rms < 3000.0 {
        return InstrumentHint::Vocals;
    }

    // Sustained with high RMS → electric guitar
    if onset_rms >= 1500.0 && decay_ratio > 0.30 {
        return InstrumentHint::ElectricGuitar;
    }

    // Sustained with mid RMS → acoustic guitar
    if onset_rms >= 300.0 && decay_ratio > 0.30 && frame_count >= 10 {
        return InstrumentHint::AcousticGuitar;
    }

    InstrumentHint::Unknown
}
