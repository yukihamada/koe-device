// バッテリー監視 — ADC経由で電圧読み取り、残量推定
// GPIO1 → ADC1_CH0, 分圧 (100K/100K = 1:2)
// LiPo: 4.2V(100%) → 3.0V(0%)

use log::*;
use std::sync::atomic::{AtomicU8, Ordering};

static BATTERY_PERCENT: AtomicU8 = AtomicU8::new(255); // 255 = 未計測

/// バッテリー残量 (0-100, 255=不明)
pub fn level() -> u8 {
    BATTERY_PERCENT.load(Ordering::Relaxed)
}

/// バッテリー監視タスク (30秒ごとに計測)
pub fn monitor_task() {
    // ADC初期化
    unsafe {
        let mut config: esp_idf_sys::adc_oneshot_unit_init_cfg_t = core::mem::zeroed();
        config.unit_id = esp_idf_sys::adc_unit_t_ADC_UNIT_1;

        let mut adc_handle: esp_idf_sys::adc_oneshot_unit_handle_t = core::ptr::null_mut();
        let ret = esp_idf_sys::adc_oneshot_new_unit(&config, &mut adc_handle);
        if ret != 0 {
            warn!("ADC init failed: {}", ret);
            return;
        }

        // チャンネル設定 (GPIO1 = ADC1_CH0)
        let mut chan_cfg: esp_idf_sys::adc_oneshot_chan_cfg_t = core::mem::zeroed();
        chan_cfg.bitwidth = esp_idf_sys::adc_bitwidth_t_ADC_BITWIDTH_12;
        chan_cfg.atten = esp_idf_sys::adc_atten_t_ADC_ATTEN_DB_12;
        esp_idf_sys::adc_oneshot_config_channel(
            adc_handle,
            esp_idf_sys::adc_channel_t_ADC_CHANNEL_0,
            &chan_cfg,
        );

        loop {
            let mut raw: i32 = 0;
            let ret = esp_idf_sys::adc_oneshot_read(
                adc_handle,
                esp_idf_sys::adc_channel_t_ADC_CHANNEL_0,
                &mut raw,
            );

            if ret == 0 {
                // ADC 12bit (0-4095), Vref=3.3V, 分圧1:2
                // 実電圧 = (raw / 4095) * 3.3 * 2
                let mv = (raw as u32 * 6600) / 4095;

                // LiPo電圧 → 残量 (線形近似)
                let percent = if mv >= 4200 { 100u8 }
                    else if mv <= 3000 { 0 }
                    else { ((mv - 3000) * 100 / 1200) as u8 };

                BATTERY_PERCENT.store(percent, Ordering::Relaxed);

                if percent <= 10 {
                    warn!("Battery low: {}% ({}mV)", percent, mv);
                }
            }

            std::thread::sleep(std::time::Duration::from_secs(30));
        }
    }
}
