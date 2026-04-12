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
