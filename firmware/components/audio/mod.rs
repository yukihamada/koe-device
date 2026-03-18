use esp_idf_hal::gpio::{OutputPin, PinDriver, Output};
use esp_idf_hal::i2s::{I2sDriver, I2sRx, I2sTx, config::*};
use esp_idf_hal::peripheral::Peripheral;
use std::sync::atomic::{AtomicU8, Ordering};
use std::time::Duration;

const SAMPLE_RATE: u32 = 16_000;
const VAD_ENERGY_THRESHOLD: i32 = 500 * 500; // 閾値² — sqrtを避ける
const VAD_MIN_FRAMES: u8 = 5;

static VAD_VOICE_FRAMES: AtomicU8 = AtomicU8::new(0);

pub fn init_mic_i2s<'d>(
    i2s: impl Peripheral<P = impl esp_idf_hal::i2s::I2s> + 'd,
    bclk: impl Peripheral<P = impl esp_idf_hal::gpio::OutputPin + esp_idf_hal::gpio::InputPin> + 'd,
    ws: impl Peripheral<P = impl esp_idf_hal::gpio::OutputPin + esp_idf_hal::gpio::InputPin> + 'd,
    din: impl Peripheral<P = impl esp_idf_hal::gpio::InputPin> + 'd,
) -> Result<I2sDriver<'d, I2sRx>, Box<dyn std::error::Error>> {
    let config = StdConfig::philips(SAMPLE_RATE, DataBitWidth::Bits16);
    let i2s = I2sDriver::new_std_rx(i2s, &config, bclk, din, None::<esp_idf_hal::gpio::AnyIOPin>, ws)?;
    Ok(i2s)
}

pub fn init_spk_i2s<'d>(
    i2s: impl Peripheral<P = impl esp_idf_hal::i2s::I2s> + 'd,
    dout: impl Peripheral<P = impl esp_idf_hal::gpio::OutputPin> + 'd,
) -> Result<I2sDriver<'d, I2sTx>, Box<dyn std::error::Error>> {
    let config = StdConfig::philips(SAMPLE_RATE, DataBitWidth::Bits16);
    let i2s = I2sDriver::new_std_tx(
        i2s, &config,
        None::<esp_idf_hal::gpio::AnyIOPin>,
        dout,
        None::<esp_idf_hal::gpio::AnyIOPin>,
        None::<esp_idf_hal::gpio::AnyIOPin>,
    )?;
    Ok(i2s)
}

/// ゼロアロケーションVAD — Vec排除、sqrt排除、整数演算のみ
#[inline]
pub fn detect_voice(audio_data: &[u8]) -> bool {
    let n_samples = audio_data.len() / 2;
    if n_samples == 0 {
        return false;
    }

    // i16サンプルを直接バイト列から読み、i32で二乗和を累積
    let mut energy_sum: i64 = 0;
    let mut i = 0;
    while i + 1 < audio_data.len() {
        let sample = i16::from_le_bytes([audio_data[i], audio_data[i + 1]]) as i64;
        energy_sum += sample * sample;
        i += 2;
    }

    // 平均エネルギー (RMS²) — sqrtしない、閾値も²で比較
    let mean_energy = (energy_sum / n_samples as i64) as i32;

    if mean_energy > VAD_ENERGY_THRESHOLD {
        let prev = VAD_VOICE_FRAMES.load(Ordering::Relaxed);
        VAD_VOICE_FRAMES.store(prev.saturating_add(1), Ordering::Relaxed);
    } else {
        let prev = VAD_VOICE_FRAMES.load(Ordering::Relaxed);
        VAD_VOICE_FRAMES.store(prev.saturating_sub(1), Ordering::Relaxed);
    }
    VAD_VOICE_FRAMES.load(Ordering::Relaxed) >= VAD_MIN_FRAMES
}

pub fn play_audio<'d>(
    i2s: &I2sDriver<'d, I2sTx>,
    sd_pin: &PinDriver<'_, impl OutputPin, Output>,
    audio_data: &[u8],
) -> Result<(), Box<dyn std::error::Error>> {
    sd_pin.set_high()?;

    let mut offset = 0;
    while offset < audio_data.len() {
        let end = (offset + 1024).min(audio_data.len());
        let written = i2s.write(&audio_data[offset..end], Duration::from_millis(100))?;
        offset += written;
    }

    std::thread::sleep(Duration::from_millis(50));
    sd_pin.set_low()?;
    Ok(())
}
