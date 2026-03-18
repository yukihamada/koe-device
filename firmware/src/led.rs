use std::thread;
use std::time::Duration;

use super::{get_state, DeviceState, get_mode, DeviceMode};
use super::soluna;

// WS2812B GRB タイミング (RMT)
// T0H=400ns T0L=850ns T1H=800ns T1L=450ns Reset=50us
const RMT_CLK_DIV: u8 = 2; // 40MHz → 25ns/tick
const T0H: u16 = 16;  // 400ns
const T0L: u16 = 34;  // 850ns
const T1H: u16 = 32;  // 800ns
const T1L: u16 = 18;  // 450ns

/// RMT経由でWS2812Bに1バイト送信
#[inline]
unsafe fn rmt_send_byte(channel: u32, byte: u8) {
    for bit in (0..8).rev() {
        let (h, l) = if (byte >> bit) & 1 == 1 { (T1H, T1L) } else { (T0H, T0L) };
        // ESP-IDF RMT raw write
        let item = esp_idf_sys::rmt_item32_t {
            __bindgen_anon_1: esp_idf_sys::rmt_item32_t__bindgen_ty_1 {
                __bindgen_anon_1: esp_idf_sys::rmt_item32_t__bindgen_ty_1__bindgen_ty_1 {
                    _bitfield_1: esp_idf_sys::rmt_item32_t__bindgen_ty_1__bindgen_ty_1::new_bitfield_1(
                        h as u32, 1, l as u32, 0,
                    ),
                    ..core::mem::zeroed()
                },
            },
        };
        esp_idf_sys::rmt_write_items(channel, &item, 1, true);
    }
}

/// WS2812Bに色を書き込み (GRB順)
unsafe fn ws2812_write(color: [u8; 3]) {
    // GPIO16 = RMT channel 0
    rmt_send_byte(0, color[0]); // Green
    rmt_send_byte(0, color[1]); // Red
    rmt_send_byte(0, color[2]); // Blue
}

/// RMTペリフェラル初期化 (GPIO16)
pub fn init_rmt() {
    unsafe {
        let config = esp_idf_sys::rmt_config_t {
            rmt_mode: esp_idf_sys::rmt_mode_t_RMT_MODE_TX,
            channel: 0,
            gpio_num: 16,
            clk_div: RMT_CLK_DIV,
            mem_block_num: 1,
            flags: 0,
            __bindgen_anon_1: esp_idf_sys::rmt_config_t__bindgen_ty_1 {
                tx_config: esp_idf_sys::rmt_tx_config_t {
                    carrier_freq_hz: 0,
                    carrier_level: 0,
                    idle_level: 0,
                    carrier_duty_percent: 0,
                    loop_count: 0,
                    carrier_en: false,
                    loop_en: false,
                    idle_output_en: true,
                },
            },
        };
        esp_idf_sys::rmt_config(&config);
        esp_idf_sys::rmt_driver_install(0, 0, 0);
    }
}

/// Solunaパターンから色を計算
fn compute_soluna_pattern(cmd: &soluna::LedCommand, tick: u32) -> [u8; 3] {
    let intensity = cmd.intensity as u16;
    // speed → 周期制御: speed=0 → 遅い(period大), speed=255 → 速い(period小)
    let period = 512u32.saturating_sub(cmd.speed as u32 * 2).max(4);

    match cmd.pattern {
        soluna::LedPattern::Off => [0, 0, 0],

        soluna::LedPattern::Solid => {
            // GRB順、intensity適用
            let g = ((cmd.g as u16 * intensity) / 255) as u8;
            let r = ((cmd.r as u16 * intensity) / 255) as u8;
            let b = ((cmd.b as u16 * intensity) / 255) as u8;
            [g, r, b]
        }

        soluna::LedPattern::Pulse => {
            // 三角波パルス
            let phase = (tick % period) as u16;
            let half = (period / 2) as u16;
            let bright = if phase < half {
                (phase * 255 / half) as u8
            } else {
                ((half * 2 - phase) * 255 / half) as u8
            };
            let scale = (bright as u16 * intensity) / 255;
            let g = ((cmd.g as u16 * scale) / 255) as u8;
            let r = ((cmd.r as u16 * scale) / 255) as u8;
            let b = ((cmd.b as u16 * scale) / 255) as u8;
            [g, r, b]
        }

        soluna::LedPattern::Rainbow => {
            // HSV hue cycle
            let hue = ((tick % period) * 360 / period) as u16;
            let (r, g, b) = hsv_to_rgb(hue, 255, intensity as u8);
            [g, r, b] // GRB
        }

        soluna::LedPattern::WaveLR | soluna::LedPattern::WaveRL => {
            // 5 LED位置をシミュレート: LED 0 のみ表示 (単LED デバイス)
            // 波が通過する瞬間だけ点灯
            let wave_pos = (tick % period) * 5 / period; // 0-4
            let target = if cmd.pattern == soluna::LedPattern::WaveLR { 0 } else { 4 };
            let dist = if wave_pos as i32 - target as i32 >= 0 {
                (wave_pos as i32 - target as i32) as u32
            } else {
                (target as i32 - wave_pos as i32) as u32
            };
            let bright = if dist == 0 { intensity as u8 } else if dist == 1 { (intensity / 3) as u8 } else { 0 };
            let g = ((cmd.g as u16 * bright as u16) / 255) as u8;
            let r = ((cmd.r as u16 * bright as u16) / 255) as u8;
            let b = ((cmd.b as u16 * bright as u16) / 255) as u8;
            [g, r, b]
        }

        soluna::LedPattern::Strobe => {
            // 高速点滅 — speedで周期変更
            let strobe_period = (256u32.saturating_sub(cmd.speed as u32)).max(2);
            let on = (tick / (strobe_period / 2)) % 2 == 0;
            if on {
                let g = ((cmd.g as u16 * intensity) / 255) as u8;
                let r = ((cmd.r as u16 * intensity) / 255) as u8;
                let b = ((cmd.b as u16 * intensity) / 255) as u8;
                [g, r, b]
            } else {
                [0, 0, 0]
            }
        }

        soluna::LedPattern::Breathe => {
            // サイン波近似 (テーブルレス): 二次関数で近似
            let phase = (tick % period) as i32;
            let half = (period / 2) as i32;
            // 0→1→0 をパラボラで: y = 1 - ((x - half) / half)^2
            let x = phase - half;
            let bright = (255i32 - (x * x * 255 / (half * half))).max(0) as u16;
            let scale = (bright * intensity) / 255;
            let g = ((cmd.g as u16 * scale) / 255) as u8;
            let r = ((cmd.r as u16 * scale) / 255) as u8;
            let b = ((cmd.b as u16 * scale) / 255) as u8;
            [g, r, b]
        }
    }
}

/// HSV → RGB (h: 0-359, s/v: 0-255)
fn hsv_to_rgb(h: u16, s: u8, v: u8) -> (u8, u8, u8) {
    if s == 0 { return (v, v, v); }
    let region = h / 60;
    let remainder = ((h % 60) * 255 / 60) as u16;
    let p = (v as u16 * (255 - s as u16) / 255) as u8;
    let q = (v as u16 * (255 - (s as u16 * remainder / 255)) / 255) as u8;
    let t = (v as u16 * (255 - (s as u16 * (255 - remainder) / 255)) / 255) as u8;
    match region {
        0 => (v, t, p),
        1 => (q, v, p),
        2 => (p, v, t),
        3 => (p, q, v),
        4 => (t, p, v),
        _ => (v, p, q),
    }
}

pub fn run_led_task() {
    init_rmt();

    let mut brightness: u8 = 0;
    let mut rising = true;
    let mut blink_on = true;
    let mut tick: u32 = 0;

    loop {
        let state = get_state();
        let mode = get_mode();
        let peers = soluna::peer_count();

        // Soluna LEDコマンドが有効ならパターン実行
        if mode == DeviceMode::Soluna {
            if let Some(cmd) = soluna::get_led_command() {
                if cmd.pattern != soluna::LedPattern::Off {
                    let color = compute_soluna_pattern(&cmd, tick);
                    unsafe { ws2812_write(color); }
                    tick = tick.wrapping_add(1);
                    thread::sleep(Duration::from_millis(20));
                    continue;
                }
            }
        }

        // フォールバック: 既存のデバイス状態LED
        // パルスエフェクト
        if rising {
            brightness = brightness.saturating_add(8);
            if brightness >= 248 { rising = false; }
        } else {
            brightness = brightness.saturating_sub(8);
            if brightness <= 8 { rising = true; }
        }

        let color: [u8; 3] = match state {
            DeviceState::Booting => [brightness, brightness, brightness],
            DeviceState::Connecting => [0, 0, brightness],
            DeviceState::Listening => {
                if mode == DeviceMode::Soluna {
                    // Solunaモード: ピア数に応じた色
                    match peers {
                        0 => [20, 10, 0],     // dim amber (待機)
                        1 => [0, 50, 0],      // green (1ピア)
                        2..=3 => [0, 0, 80],  // blue (2-3ピア)
                        _ => [60, 0, 60],     // purple (4+ピア)
                    }
                } else {
                    [30, 0, 0] // Koe: dim green
                }
            }
            DeviceState::Processing => [0, brightness / 2, brightness],
            DeviceState::Speaking => [128, 128, 0],
            DeviceState::Error => {
                blink_on = !blink_on;
                if blink_on { [0, 255, 0] } else { [0, 0, 0] }
            }
            DeviceState::Syncing => {
                // ピア数でパルス速度変化
                let b = if peers > 0 { brightness } else { brightness / 3 };
                [b, b / 3, 0] // amber pulse
            }
        };

        unsafe { ws2812_write(color); }
        tick = tick.wrapping_add(1);

        thread::sleep(Duration::from_millis(50));
    }
}
