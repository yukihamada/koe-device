/// デバイスモードと電力管理。
///
/// モードはNVSキー "koe/mode" に保存。
/// 工場出荷時デフォルト: coin
/// ガイドモード書き込み: `nvs_set_str(handle, "mode", "guide")`

use esp_idf_svc::nvs::EspDefaultNvsPartition;
use log::info;

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum DeviceMode {
    /// Koe COIN — 双方向, フェス/ステージ向け
    Coin,
    /// Koe GUIDE — 受信専用, 低消費電力, イヤホン向け
    Guide,
}

impl DeviceMode {
    pub fn load(_nvs: &EspDefaultNvsPartition) -> Self {
        // TODO: NVS読み込み実装後に有効化
        // 現在はコンパイル時フィーチャーで切替
        #[cfg(feature = "guide")]
        return DeviceMode::Guide;
        #[cfg(not(feature = "guide"))]
        return DeviceMode::Coin;
    }
}

/// CPU 動的周波数スケーリング(DFS)を設定: アイドル時 80MHz / 負荷時も上限80MHz。
/// 要 `CONFIG_PM_ENABLE=y`(sdkconfig)。ガイドモードの省電力に効く。
/// ⚠ 実機未検証: octal PSRAM(80M)との相互作用は実機で要確認。失敗時はwarnして無視。
pub fn set_cpu_80mhz() {
    let cfg = esp_idf_sys::esp_pm_config_esp32s3_t {
        max_freq_mhz: 80,
        min_freq_mhz: 40,
        light_sleep_enable: false,
    };
    let err = unsafe {
        esp_idf_sys::esp_pm_configure(&cfg as *const _ as *const core::ffi::c_void)
    };
    if err != 0 {
        log::warn!("esp_pm_configure failed: {err} (CONFIG_PM_ENABLE 未設定?)");
        return;
    }
    info!("CPU DFS configured: 80MHz max / 40MHz min");
}

/// WiFi モデムスリープ有効化。
/// アクティブ受信中のみ RF を起動 → 平均電流 ~20mA (通常 ~130mA)。
pub fn enable_modem_sleep() {
    unsafe {
        esp_idf_sys::esp_wifi_set_ps(
            esp_idf_sys::wifi_ps_type_t_WIFI_PS_MIN_MODEM,
        );
    }
    info!("Modem sleep enabled");
}
