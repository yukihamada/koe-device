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

pub fn run_led_task() {
    init_rmt();

    let mut brightness: u8 = 0;
    let mut rising = true;
    let mut blink_on = true;

    loop {
        let state = get_state();
        let mode = get_mode();
        let peers = soluna::peer_count();

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

        thread::sleep(Duration::from_millis(50));
    }
}
