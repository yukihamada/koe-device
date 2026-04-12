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
    rmt::{
        config::{TransmitConfig, TxChannelConfig},
        encoder::CopyEncoder,
        PinState, Pulse, PulseTicks, Symbol, TxChannelDriver,
    },
    units::FromValueType,
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

// ---------------------------------------------------------------------------
// WS2812B bit timing (in µs ticks at 1 MHz resolution)
// T0H = 0.4 µs → 400 ns  ≈  1 tick @ 1 MHz (round to 1 µs since min is 1)
// We use 80 MHz resolution (80 ticks/µs) for better accuracy.
// Resolution: 80 MHz → 1 tick = 12.5 ns
// T0H = 400 ns → 32 ticks  T0L = 850 ns → 68 ticks
// T1H = 800 ns → 64 ticks  T1L = 450 ns → 36 ticks
// ---------------------------------------------------------------------------

const RMT_RESOLUTION_HZ: u32 = 10_000_000; // 10 MHz → 1 tick = 100 ns

// At 10 MHz: 1 tick = 100 ns
// T0H = 400 ns → 4 ticks,  T0L = 850 ns → 9 ticks (→ 900 ns, slight +5%)
// T1H = 800 ns → 8 ticks,  T1L = 450 ns → 5 ticks (→ 500 ns, slight +11%)
const T0H_TICKS: u16 = 4;
const T0L_TICKS: u16 = 9;
const T1H_TICKS: u16 = 8;
const T1L_TICKS: u16 = 5;

fn make_symbol(one: bool) -> Symbol {
    let (h_ticks, l_ticks) = if one {
        (T1H_TICKS, T1L_TICKS)
    } else {
        (T0H_TICKS, T0L_TICKS)
    };
    Symbol::new(
        Pulse::new(PinState::High, PulseTicks::new(h_ticks).unwrap()),
        Pulse::new(PinState::Low, PulseTicks::new(l_ticks).unwrap()),
    )
}

/// Drive a single WS2812B via RMT.
pub struct WS2812Driver<'d> {
    tx: TxChannelDriver<'d>,
    transmit_cfg: TransmitConfig,
}

impl<'d> WS2812Driver<'d> {
    pub fn new(pin: impl OutputPin + 'd) -> Result<Self> {
        let channel_cfg = TxChannelConfig {
            resolution: RMT_RESOLUTION_HZ.Hz().into(),
            ..Default::default()
        };
        let tx = TxChannelDriver::new(pin, &channel_cfg)?;
        Ok(Self {
            tx,
            transmit_cfg: TransmitConfig::default(),
        })
    }

    /// Write a single GRB colour to the LED.
    ///
    /// WS2812B expects bytes in G-R-B order, MSB first.
    pub fn write_color(&mut self, r: u8, g: u8, b: u8) -> Result<()> {
        let bytes = [g, r, b]; // GRB order
        let mut symbols = [Symbol::new(
            Pulse::new(PinState::Low, PulseTicks::zero()),
            Pulse::new(PinState::Low, PulseTicks::zero()),
        ); 24];
        let mut idx = 0usize;
        for byte in bytes {
            for bit_pos in (0..8u8).rev() {
                let one = (byte >> bit_pos) & 1 != 0;
                symbols[idx] = make_symbol(one);
                idx += 1;
            }
        }
        let encoder = CopyEncoder::new()?;
        self.tx.send_and_wait(encoder, &symbols, &self.transmit_cfg)?;
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
