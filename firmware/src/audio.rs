use esp_idf_hal::gpio::{OutputPin, PinDriver, Output};
use esp_idf_hal::i2s::{I2sDriver, I2sRx, I2sTx, config::*};
use esp_idf_hal::peripheral::Peripheral;
use std::sync::atomic::{AtomicU8, AtomicBool, AtomicI8, Ordering};


// サンプルレート (NVSから切替可能: 16000 or 48000)
static mut SAMPLE_RATE: u32 = 16_000;
const VAD_ENERGY_THRESHOLD: i32 = 300 * 300;
const VAD_MIN_FRAMES: u8 = 5;
static VAD_VOICE_FRAMES: AtomicU8 = AtomicU8::new(0);

// AGC (自動ゲイン制御)
const AGC_TARGET_RMS: i32 = 10000; // 目標RMSレベル
const AGC_MIN_GAIN: i32 = 64;     // 0.25x (Q8 fixed point)
const AGC_MAX_GAIN: i32 = 1024;   // 4.0x
const AGC_ATTACK: i32 = 4;        // 速い追従
const AGC_RELEASE: i32 = 1;       // 緩やかな解放
static mut AGC_GAIN: i32 = 256;   // 1.0x (Q8)

// AEC (エコーキャンセル) — 簡易版: 再生中のオーディオを記録し、マイク入力から減算
static AEC_ACTIVE: AtomicBool = AtomicBool::new(false);
static mut AEC_REF_BUF: [u8; 2048] = [0u8; 2048];
static mut AEC_REF_LEN: usize = 0;

// ハイパスフィルタ (DCオフセット除去, 1次IIR)
// y[n] = x[n] - x[n-1] + α * y[n-1], α=0.997 ≈ 255/256
static mut HPF_PREV_IN: i16 = 0;
static mut HPF_PREV_OUT: i16 = 0;

// ノイズゲート
const NOISE_GATE_THRESHOLD: i32 = 100 * 100; // RMS² 閾値
const NOISE_GATE_HOLD_FRAMES: u8 = 10;
static mut NOISE_GATE_HOLD: u8 = 0;
static NOISE_GATE_OPEN: AtomicBool = AtomicBool::new(false);

// ボリューム (Q8: 256=1.0x, 512=2.0x, 128=0.5x)
static mut VOLUME: i32 = 256;

pub fn set_sample_rate(rate: u32) { unsafe { SAMPLE_RATE = rate; } }
pub fn get_sample_rate() -> u32 { unsafe { SAMPLE_RATE } }
pub fn set_volume(vol_q8: i32) { unsafe { VOLUME = vol_q8.clamp(32, 1024); } }
pub fn get_volume() -> i32 { unsafe { VOLUME } }

pub fn init_mic_i2s<'d>(
    i2s: impl Peripheral<P = impl esp_idf_hal::i2s::I2s> + 'd,
    bclk: impl Peripheral<P = impl esp_idf_hal::gpio::OutputPin + esp_idf_hal::gpio::InputPin> + 'd,
    ws: impl Peripheral<P = impl esp_idf_hal::gpio::OutputPin + esp_idf_hal::gpio::InputPin> + 'd,
    din: impl Peripheral<P = impl esp_idf_hal::gpio::InputPin> + 'd,
) -> Result<I2sDriver<'d, I2sRx>, Box<dyn std::error::Error>> {
    let rate = unsafe { SAMPLE_RATE };
    let config = StdConfig::philips(rate, DataBitWidth::Bits16);
    let i2s = I2sDriver::new_std_rx(i2s, &config, bclk, din, None::<esp_idf_hal::gpio::AnyIOPin>, ws)?;
    Ok(i2s)
}

pub fn init_spk_i2s<'d>(
    i2s: impl Peripheral<P = impl esp_idf_hal::i2s::I2s> + 'd,
    bclk: impl Peripheral<P = impl esp_idf_hal::gpio::OutputPin + esp_idf_hal::gpio::InputPin> + 'd,
    dout: impl Peripheral<P = impl esp_idf_hal::gpio::OutputPin> + 'd,
    ws: impl Peripheral<P = impl esp_idf_hal::gpio::OutputPin + esp_idf_hal::gpio::InputPin> + 'd,
) -> Result<I2sDriver<'d, I2sTx>, Box<dyn std::error::Error>> {
    let rate = unsafe { SAMPLE_RATE };
    let config = StdConfig::philips(rate, DataBitWidth::Bits16);
    let i2s = I2sDriver::new_std_tx(
        i2s, &config,
        bclk, dout,
        Option::<esp_idf_hal::gpio::AnyIOPin>::None, ws,
    )?;
    Ok(i2s)
}

/// ゼロアロケーションVAD + AGC + AEC
#[inline]
pub fn detect_voice(audio_data: &[u8]) -> bool {
    let n_samples = audio_data.len() / 2;
    if n_samples == 0 { return false; }

    let mut energy_sum: i64 = 0;
    let mut i = 0;
    while i + 1 < audio_data.len() {
        let sample = i16::from_le_bytes([audio_data[i], audio_data[i + 1]]) as i64;
        energy_sum += sample * sample;
        i += 2;
    }

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

/// AGC適用 — 音量を自動正規化 (in-place)
#[inline]
pub fn apply_agc(audio: &mut [u8]) {
    let n_samples = audio.len() / 2;
    if n_samples == 0 { return; }

    // RMS計算
    let mut energy: i64 = 0;
    let mut i = 0;
    while i + 1 < audio.len() {
        let s = i16::from_le_bytes([audio[i], audio[i + 1]]) as i64;
        energy += s * s;
        i += 2;
    }
    let rms = isqrt((energy / n_samples as i64) as u64) as i32;

    // ゲイン更新
    unsafe {
        if rms > 0 {
            let target_gain = ((AGC_TARGET_RMS as i64 * 256) / rms as i64).clamp(AGC_MIN_GAIN as i64, AGC_MAX_GAIN as i64) as i32;
            if target_gain < AGC_GAIN {
                AGC_GAIN -= AGC_ATTACK; // 速い: 大きい音にすぐ対応
            } else {
                AGC_GAIN += AGC_RELEASE; // 緩やか: 小さい音にゆっくり上げる
            }
            AGC_GAIN = AGC_GAIN.clamp(AGC_MIN_GAIN, AGC_MAX_GAIN);
        }

        // ゲイン適用
        i = 0;
        while i + 1 < audio.len() {
            let s = i16::from_le_bytes([audio[i], audio[i + 1]]) as i32;
            let amplified = ((s * AGC_GAIN) >> 8).clamp(-32768, 32767) as i16;
            let bytes = amplified.to_le_bytes();
            audio[i] = bytes[0];
            audio[i + 1] = bytes[1];
            i += 2;
        }
    }
}

/// AEC: 再生音をリファレンスとして記録
pub fn aec_set_reference(playback_audio: &[u8]) {
    unsafe {
        let len = playback_audio.len().min(2048);
        AEC_REF_BUF[..len].copy_from_slice(&playback_audio[..len]);
        AEC_REF_LEN = len;
    }
    AEC_ACTIVE.store(true, Ordering::Relaxed);
}

/// AEC: マイク入力から再生音を減算
pub fn aec_cancel(mic_audio: &mut [u8]) {
    if !AEC_ACTIVE.load(Ordering::Relaxed) { return; }

    unsafe {
        let ref_len = AEC_REF_LEN;
        if ref_len == 0 { return; }

        let mut i = 0;
        while i + 1 < mic_audio.len() && i + 1 < ref_len {
            let mic = i16::from_le_bytes([mic_audio[i], mic_audio[i + 1]]) as i32;
            let ref_sample = i16::from_le_bytes([AEC_REF_BUF[i], AEC_REF_BUF[i + 1]]) as i32;
            // 減衰係数0.7で減算 (完全除去は歪む)
            let cancelled = (mic - (ref_sample * 179 / 256)).clamp(-32768, 32767) as i16;
            let bytes = cancelled.to_le_bytes();
            mic_audio[i] = bytes[0];
            mic_audio[i + 1] = bytes[1];
            i += 2;
        }
        AEC_REF_LEN = 0;
    }
    AEC_ACTIVE.store(false, Ordering::Relaxed);
}

/// デュアルマイクビームフォーミング (遅延和)
/// ch_l, ch_r は左右マイクのPCMデータ (同一バッファのインターリーブ想定)
/// モノラル出力: 両チャンネルを加算平均 + 位相差によるノイズ除去
pub fn beamform_mono(stereo_data: &[u8], mono_out: &mut [u8]) -> usize {
    // ステレオ i16 interleaved → モノラル i16
    let n_frames = stereo_data.len() / 4; // 4 bytes per stereo frame
    let out_len = n_frames * 2;
    if mono_out.len() < out_len { return 0; }

    let mut i = 0;
    let mut o = 0;
    while i + 3 < stereo_data.len() {
        let l = i16::from_le_bytes([stereo_data[i], stereo_data[i + 1]]) as i32;
        let r = i16::from_le_bytes([stereo_data[i + 2], stereo_data[i + 3]]) as i32;
        // 加算平均 (同相成分=声が強調、逆相成分=ノイズが弱まる)
        let mono = ((l + r) / 2).clamp(-32768, 32767) as i16;
        let bytes = mono.to_le_bytes();
        mono_out[o] = bytes[0];
        mono_out[o + 1] = bytes[1];
        i += 4;
        o += 2;
    }
    out_len
}

/// ビープ音生成 (モード切替通知用)
pub fn generate_beep(freq_hz: u32, duration_ms: u32, out: &mut [u8]) -> usize {
    let rate = unsafe { SAMPLE_RATE };
    let n_samples = (rate * duration_ms / 1000) as usize;
    let out_len = (n_samples * 2).min(out.len());

    let period = rate / freq_hz;
    let mut i = 0;
    let mut sample_idx: u32 = 0;
    while i + 1 < out_len {
        // 矩形波 (sin波より軽量)
        let val: i16 = if (sample_idx % period) < period / 2 { 4000 } else { -4000 };
        // フェードアウト (最後20%をフェード)
        let fade_start = (n_samples as u32 * 80) / 100;
        let val = if sample_idx > fade_start {
            let remaining = n_samples as u32 - sample_idx;
            let fade_len = n_samples as u32 - fade_start;
            (val as i32 * remaining as i32 / fade_len as i32) as i16
        } else { val };

        let bytes = val.to_le_bytes();
        out[i] = bytes[0];
        out[i + 1] = bytes[1];
        i += 2;
        sample_idx += 1;
    }
    out_len
}

pub fn play_audio<'d>(
    i2s: &mut I2sDriver<'d, I2sTx>,
    sd_pin: &mut PinDriver<'_, impl OutputPin, Output>,
    audio_data: &[u8],
) -> Result<(), Box<dyn std::error::Error>> {
    // AEC: 再生音を記録
    aec_set_reference(audio_data);

    sd_pin.set_high()?;
    let mut offset = 0;
    while offset < audio_data.len() {
        let end = (offset + 1024).min(audio_data.len());
        let written = i2s.write(&audio_data[offset..end], 100)?;
        offset += written;
    }
    std::thread::sleep(std::time::Duration::from_millis(50));
    sd_pin.set_low()?;
    Ok(())
}

/// ハイパスフィルタ — DCオフセット・低周波ノイズ除去 (in-place)
#[inline]
pub fn apply_highpass(audio: &mut [u8]) {
    unsafe {
        let mut i = 0;
        while i + 1 < audio.len() {
            let x = i16::from_le_bytes([audio[i], audio[i + 1]]);
            // y = x - x_prev + 0.997 * y_prev (Q9: 511/512)
            let y = (x as i32 - HPF_PREV_IN as i32 + (HPF_PREV_OUT as i32 * 511 / 512))
                .clamp(-32768, 32767) as i16;
            HPF_PREV_IN = x;
            HPF_PREV_OUT = y;
            let bytes = y.to_le_bytes();
            audio[i] = bytes[0];
            audio[i + 1] = bytes[1];
            i += 2;
        }
    }
}

/// ノイズゲート — 無音時にゼロ出力 (帯域節約)
#[inline]
pub fn apply_noise_gate(audio: &mut [u8]) -> bool {
    let n_samples = audio.len() / 2;
    if n_samples == 0 { return false; }

    let mut energy: i64 = 0;
    let mut i = 0;
    while i + 1 < audio.len() {
        let s = i16::from_le_bytes([audio[i], audio[i + 1]]) as i64;
        energy += s * s;
        i += 2;
    }
    let mean = (energy / n_samples as i64) as i32;

    unsafe {
        if mean > NOISE_GATE_THRESHOLD {
            NOISE_GATE_HOLD = NOISE_GATE_HOLD_FRAMES;
            NOISE_GATE_OPEN.store(true, Ordering::Relaxed);
            true
        } else if NOISE_GATE_HOLD > 0 {
            NOISE_GATE_HOLD -= 1;
            true // ホールド中: まだ通す
        } else {
            NOISE_GATE_OPEN.store(false, Ordering::Relaxed);
            // ゼロ埋め
            for b in audio.iter_mut() { *b = 0; }
            false
        }
    }
}

/// ソフトリミッター — クリッピング防止 (in-place)
/// 閾値超えのサンプルをソフトに潰す (tanh風の近似)
#[inline]
pub fn apply_limiter(audio: &mut [u8]) {
    const THRESHOLD: i32 = 28000;
    let mut i = 0;
    while i + 1 < audio.len() {
        let s = i16::from_le_bytes([audio[i], audio[i + 1]]) as i32;
        let limited = if s > THRESHOLD {
            THRESHOLD + (s - THRESHOLD) / 4
        } else if s < -THRESHOLD {
            -THRESHOLD + (s + THRESHOLD) / 4
        } else {
            s
        };
        let bytes = limited.clamp(-32767, 32767) as i16;
        let b = bytes.to_le_bytes();
        audio[i] = b[0];
        audio[i + 1] = b[1];
        i += 2;
    }
}

/// ボリューム適用 (in-place)
#[inline]
pub fn apply_volume(audio: &mut [u8]) {
    let vol = unsafe { VOLUME };
    if vol == 256 { return; } // 1.0x = no-op
    let mut i = 0;
    while i + 1 < audio.len() {
        let s = i16::from_le_bytes([audio[i], audio[i + 1]]) as i32;
        let adjusted = ((s * vol) >> 8).clamp(-32768, 32767) as i16;
        let bytes = adjusted.to_le_bytes();
        audio[i] = bytes[0];
        audio[i + 1] = bytes[1];
        i += 2;
    }
}

/// Generate 19.5kHz ultrasonic chirp for acoustic ranging
/// Outputs mono 16-bit PCM at current sample rate, returns bytes written
pub fn generate_chirp(out: &mut [u8]) -> usize {
    let rate = unsafe { SAMPLE_RATE };
    let duration_ms = 10u32; // Short burst
    let freq = 19500u32;
    let n_samples = (rate * duration_ms / 1000) as usize;
    let out_len = (n_samples * 2).min(out.len());
    let period = rate / freq;
    if period == 0 { return 0; }

    let mut i = 0;
    let mut sample_idx: u32 = 0;
    while i + 1 < out_len {
        // Square wave at 19.5kHz (lightweight, strong harmonic content for detection)
        let val: i16 = if (sample_idx % period) < period / 2 { 16000 } else { -16000 };
        let bytes = val.to_le_bytes();
        out[i] = bytes[0];
        out[i + 1] = bytes[1];
        i += 2;
        sample_idx += 1;
    }
    out_len
}

/// Detect chirp in audio data — returns true if 19.5kHz energy spike detected
/// Uses Goertzel algorithm (single-frequency DFT, O(N), zero alloc)
pub fn detect_chirp(audio_data: &[u8]) -> bool {
    let rate = unsafe { SAMPLE_RATE } as f32;
    let target_freq = 19500.0f32;
    let n_samples = audio_data.len() / 2;
    if n_samples == 0 { return false; }

    // Goertzel coefficient
    let k = (target_freq * n_samples as f32 / rate) as i32;
    // Use fixed-point approximation: cos(2*pi*k/N)
    // For simplicity, compute with i32 scaled by 1024
    let w = (2.0 * core::f32::consts::PI * k as f32 / n_samples as f32) as f32;
    // cos approximation not needed — just use the float for the coefficient
    let coeff = (2.0f32 * cos_approx(w) * 1024.0) as i32;

    let mut s0: i64 = 0;
    let mut s1: i64 = 0;
    let mut s2: i64 = 0;

    let mut i = 0;
    while i + 1 < audio_data.len() {
        let sample = i16::from_le_bytes([audio_data[i], audio_data[i + 1]]) as i64;
        s0 = sample + ((coeff as i64 * s1) >> 10) - s2;
        s2 = s1;
        s1 = s0;
        i += 2;
    }

    // Power = s1² + s2² - coeff*s1*s2
    let power = s1 * s1 + s2 * s2 - ((coeff as i64 * s1 * s2) >> 10);

    // Also compute total energy for comparison
    let mut total_energy: i64 = 0;
    i = 0;
    while i + 1 < audio_data.len() {
        let s = i16::from_le_bytes([audio_data[i], audio_data[i + 1]]) as i64;
        total_energy += s * s;
        i += 2;
    }

    // Chirp detected if target frequency power is > 30% of total energy
    if total_energy == 0 { return false; }
    let ratio = power * 100 / (total_energy / n_samples as i64 + 1);
    ratio > 30
}

/// Cosine approximation (Bhaskara I, avoids libm dependency)
#[inline]
fn cos_approx(x: f32) -> f32 {
    // Normalize to [0, 2π]
    let pi = core::f32::consts::PI;
    let mut x = x % (2.0 * pi);
    if x < 0.0 { x += 2.0 * pi; }
    // Use identity: cos(x) = 1 - 2*sin²(x/2), with sin approx
    // Simpler: Taylor series truncated — good enough for coefficient
    let x2 = x * x;
    let x4 = x2 * x2;
    1.0 - x2 / 2.0 + x4 / 24.0
}

// ============================================================
// ピッチシフター
// ============================================================

/// 現在のピッチシフト量 (半音, -12〜+12)
static PITCH_SEMITONES: AtomicI8 = AtomicI8::new(0);

/// ピッチをサイクル: 0 → +5 → +12 → -5 → 0 (double-tapで呼ぶ)
pub fn cycle_pitch() {
    let cur = PITCH_SEMITONES.load(Ordering::Relaxed);
    let next: i8 = match cur {
        0  =>  5,
        5  =>  12,
        12 => -5,
        _  =>  0,
    };
    PITCH_SEMITONES.store(next, Ordering::Relaxed);
}

pub fn get_pitch_semitones() -> i8 { PITCH_SEMITONES.load(Ordering::Relaxed) }

/// ピッチシフト適用 (線形補間リサンプリング, in-place)
/// 半音 > 0 = 高く / < 0 = 低く
#[inline]
pub fn apply_pitch_shift(audio: &mut [u8]) {
    let semitones = PITCH_SEMITONES.load(Ordering::Relaxed);
    if semitones == 0 { return; }

    let n = audio.len() / 2;
    if n < 2 { return; }
    let count = n.min(512);

    let ratio_q16 = pitch_ratio_q16(semitones);

    // 一時バッファ (静的 → ヒープ不要)
    static mut PITCH_TMP: [i16; 512] = [0i16; 512];
    unsafe {
        for i in 0..count {
            PITCH_TMP[i] = i16::from_le_bytes([audio[i * 2], audio[i * 2 + 1]]);
        }
        for i in 0..count {
            let src_q16 = i as u64 * ratio_q16 as u64;
            let src_idx = (src_q16 >> 16) as usize;
            let frac    = (src_q16 & 0xFFFF) as i32;

            let s0 = if src_idx < count     { PITCH_TMP[src_idx]     as i32 } else { 0 };
            let s1 = if src_idx + 1 < count { PITCH_TMP[src_idx + 1] as i32 } else { s0 };

            let sample = ((s0 * (65536 - frac) + s1 * frac) >> 16)
                .clamp(-32768, 32767) as i16;
            let b = sample.to_le_bytes();
            audio[i * 2]     = b[0];
            audio[i * 2 + 1] = b[1];
        }
    }
}

/// 2^(semitones/12) を Q16 固定小数点で近似
fn pitch_ratio_q16(semitones: i8) -> u32 {
    match semitones {
        -12 =>  32768, // 0.5000
        -7  =>  43691, // 0.6674
        -5  =>  49086, // 0.7492
        -3  =>  55109, // 0.8409
        0   =>  65536, // 1.0000
        3   =>  77936, // 1.1892
        5   =>  87461, // 1.3348
        7   =>  98200, // 1.4983
        12  => 131072, // 2.0000
        _   =>  65536,
    }
}

// ============================================================
// 拍手検出 (エネルギー過渡)
// ============================================================

static mut CLAP_PREV_ENERGY: i64 = 0;

/// フレーム内に拍手トランジェントがあれば true
/// 条件: 平均エネルギー > 閾値 かつ 前フレームの6倍超
#[inline]
pub fn detect_clap(audio: &[u8]) -> bool {
    let n = audio.len() / 2;
    if n == 0 { return false; }

    let mut energy: i64 = 0;
    let mut i = 0;
    while i + 1 < audio.len() {
        let s = i16::from_le_bytes([audio[i], audio[i + 1]]) as i64;
        energy += s * s;
        i += 2;
    }
    let mean = energy / n as i64;

    let prev = unsafe { CLAP_PREV_ENERGY };
    unsafe { CLAP_PREV_ENERGY = mean; }

    // 閾値: 250² = 62500, 前フレームの6倍超, かつ前フレームが小さい (連続音でない)
    const THRESHOLD: i64 = 250 * 250;
    mean > THRESHOLD && mean > prev * 6 && prev < THRESHOLD * 4
}

/// 整数平方根 (Newton法、FPU不要)
#[inline]
fn isqrt(n: u64) -> u32 {
    if n == 0 { return 0; }
    let mut x = n;
    let mut y = (x + 1) / 2;
    while y < x {
        x = y;
        y = (x + n / x) / 2;
    }
    x as u32
}
