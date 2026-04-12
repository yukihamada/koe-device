/// led.rs — WS2812B single-LED control via RMT peripheral
///
/// GPIO2 drives the LED strip (single NeoPixel / WS2812B).
///
/// States
/// ------
/// `Ready`     — slow violet sine-wave pulse (period ≈ 2 s)
/// `Recording` — solid violet glow (full brightness)
/// `Detected`  — short bright white flash then transitions to Recording
///
/// Colour palette:
///   Violet = (R:80, G:0, B:140)  — warm violet hue
///   Flash  = (R:255, G:255, B:255)

use esp_idf_hal::{
    gpio::OutputPin,
    peripheral::Peripheral,
    rmt::{
        config::TransmitConfig,
        FixedLengthSignal, PinState, Pulse, RmtChannel, TxRmtDriver,
    },
};
use anyhow::Result;
use std::time::{Duration, Instant};

/// Current device LED state (shared between audio task and led task).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum LedState {
    /// Waiting for onset — slow violet pulse.
    Ready,
    /// Onset detected, instrument recording in progress — solid violet.
    Recording,
    /// Brief flash (stays for a few frames then reverts to Recording).
    Detected,
}

/// WS2812B bit timing constants (nanoseconds).
///
/// T0H = 400 ns, T0L = 850 ns
/// T1H = 800 ns, T1L = 450 ns
const T0H_NS: u64 = 400;
const T0L_NS: u64 = 850;
const T1H_NS: u64 = 800;
const T1L_NS: u64 = 450;

/// Drive a single WS2812B via RMT.
///
/// The `'d` lifetime ties the driver to the lifetime of the peripheral
/// references it holds.  In the firmware main we create the driver and pass
/// it to `led_task` which runs forever (`-> !`), so the lifetime effectively
/// becomes `'static`.
pub struct WS2812Driver<'d> {
    tx: TxRmtDriver<'d>,
}

impl<'d> WS2812Driver<'d> {
    pub fn new(
        channel: impl Peripheral<P = impl RmtChannel> + 'd,
        pin: impl Peripheral<P = impl OutputPin> + 'd,
    ) -> Result<Self> {
        let cfg = TransmitConfig::new().clock_divider(1);
        let tx = TxRmtDriver::new(channel, pin, &cfg)?;
        Ok(Self { tx })
    }

    /// Write a single GRB colour to the LED.
    ///
    /// WS2812B expects bytes in G-R-B order, MSB first.
    pub fn write_color(&mut self, r: u8, g: u8, b: u8) -> Result<()> {
        let bytes = [g, r, b]; // GRB order
        let mut signal = FixedLengthSignal::<24>::new();
        let mut idx = 0usize;
        for byte in bytes {
            for bit_pos in (0..8u8).rev() {
                let one = (byte >> bit_pos) & 1 != 0;
                let (h_ns, l_ns) = if one {
                    (T1H_NS, T1L_NS)
                } else {
                    (T0H_NS, T0L_NS)
                };
                let high = Pulse::new_with_duration(
                    PinState::High,
                    &Duration::from_nanos(h_ns),
                )?;
                let low = Pulse::new_with_duration(
                    PinState::Low,
                    &Duration::from_nanos(l_ns),
                )?;
                signal.set(idx, &(high, low))?;
                idx += 1;
            }
        }
        self.tx.start_blocking(&signal)?;
        Ok(())
    }

    /// Turn the LED off.
    #[allow(dead_code)]
    pub fn off(&mut self) -> Result<()> {
        self.write_color(0, 0, 0)
    }
}

// ---------------------------------------------------------------------------
// High-level LED state machine
// ---------------------------------------------------------------------------

/// Run the LED state machine.  This is intended to be called in its own
/// OS thread and never returns (`-> !`).
///
/// `get_state` — closure called each iteration to read current shared state.
///
/// Flash behaviour: when `Detected` is seen for the first time, a counter is
/// set to 6 frames (~180 ms).  While the counter > 0 we flash white and
/// decrement.  Once it reaches 0 we emit solid violet.  The audio task will
/// transition shared state to `Recording` on the next lock acquisition.
pub fn led_task<F>(mut driver: WS2812Driver<'_>, get_state: F) -> !
where
    F: Fn() -> LedState,
{
    let start = Instant::now();
    // How many more white-flash frames to emit (non-zero → still flashing).
    let mut flash_frames_left: u32 = 0;

    loop {
        let state = get_state();

        match state {
            LedState::Ready => {
                flash_frames_left = 0;
                // Slow sine pulse: full period = 2 s → use 0.5 Hz sine
                let t_secs = start.elapsed().as_millis() as f32 / 1000.0;
                let phase = (t_secs * core::f32::consts::PI).sin(); // -1 .. +1
                // Map to brightness 0.1 .. 0.7
                let brightness = (phase + 1.0) / 2.0 * 0.6 + 0.1;
                let r = (80.0_f32 * brightness) as u8;
                let b = (140.0_f32 * brightness) as u8;
                if let Err(e) = driver.write_color(r, 0, b) {
                    log::warn!("[led] write_color: {:?}", e);
                }
                std::thread::sleep(Duration::from_millis(33)); // ~30 fps
            }

            LedState::Recording => {
                flash_frames_left = 0;
                if let Err(e) = driver.write_color(80, 0, 140) {
                    log::warn!("[led] write_color: {:?}", e);
                }
                std::thread::sleep(Duration::from_millis(50));
            }

            LedState::Detected => {
                if flash_frames_left == 0 {
                    // First time we see Detected — arm the flash counter
                    flash_frames_left = 6; // 6 × 30 ms = 180 ms
                }
                if flash_frames_left > 0 {
                    flash_frames_left -= 1;
                    if let Err(e) = driver.write_color(255, 255, 255) {
                        log::warn!("[led] write_color: {:?}", e);
                    }
                } else {
                    // Flash done — hold solid violet until state changes
                    if let Err(e) = driver.write_color(80, 0, 140) {
                        log::warn!("[led] write_color: {:?}", e);
                    }
                }
                std::thread::sleep(Duration::from_millis(30));
            }
        }
    }
}
