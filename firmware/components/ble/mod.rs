// BLEペアリング — NimBLE GATTサーバーで WiFi + APIキーをNVSに書き込み
// スマホアプリから接続 → WiFi SSID/Pass + API Key を送信 → NVS保存 → 再起動
//
// Service UUID: 0xFFE0 (Koe Config)
// Char 0xFFE1: WiFi SSID (write)
// Char 0xFFE2: WiFi Password (write)
// Char 0xFFE3: API Key (write)
// Char 0xFFE4: Soluna Channel (write)
// Char 0xFFE5: Status (read/notify) — "ok" or error

use esp_idf_svc::nvs::{EspNvs, NvsDefault};
use log::*;
use std::sync::atomic::{AtomicBool, Ordering};

static PAIRING_ACTIVE: AtomicBool = AtomicBool::new(false);
static PAIRING_DONE: AtomicBool = AtomicBool::new(false);

pub fn is_pairing() -> bool {
    PAIRING_ACTIVE.load(Ordering::Relaxed)
}

pub fn is_done() -> bool {
    PAIRING_DONE.load(Ordering::Relaxed)
}

/// BLEペアリングモード開始
/// NimBLE GATTサーバーを起動し、WiFi/APIキーの書き込みを待つ
pub fn start_pairing(nvs: &EspNvs<NvsDefault>) {
    PAIRING_ACTIVE.store(true, Ordering::Relaxed);
    info!("BLE pairing mode");

    // ESP-IDF NimBLE を直接使用
    unsafe {
        // BLE初期化
        let ret = esp_idf_sys::nimble_port_init();
        if ret != 0 {
            error!("NimBLE init failed: {}", ret);
            PAIRING_ACTIVE.store(false, Ordering::Relaxed);
            return;
        }

        // デバイス名設定
        let name = std::ffi::CString::new("Koe-Device").unwrap();
        esp_idf_sys::ble_svc_gap_device_name_set(name.as_ptr());

        // GATTサービス登録
        esp_idf_sys::ble_svc_gap_init();
        esp_idf_sys::ble_svc_gatt_init();

        // Advertisingパラメータ
        let mut adv_params: esp_idf_sys::ble_gap_adv_params = core::mem::zeroed();
        adv_params.conn_mode = esp_idf_sys::BLE_GAP_CONN_MODE_UND as u8;
        adv_params.disc_mode = esp_idf_sys::BLE_GAP_DISC_MODE_GEN as u8;
        adv_params.itvl_min = 0x20; // 20ms
        adv_params.itvl_max = 0x40; // 40ms

        // Advertising開始
        esp_idf_sys::ble_gap_adv_start(
            esp_idf_sys::BLE_OWN_ADDR_PUBLIC as u8,
            core::ptr::null(),
            i32::MAX, // 無期限
            &adv_params,
            None, // gap_event_cb — 簡易版はコールバックなし
            core::ptr::null_mut(),
        );
    }

    info!("BLE advertising (connect with app to configure WiFi)");

    // 60秒タイムアウト
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(60);
    while std::time::Instant::now() < deadline {
        if PAIRING_DONE.load(Ordering::Relaxed) {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    // BLE停止
    unsafe {
        esp_idf_sys::ble_gap_adv_stop();
        esp_idf_sys::nimble_port_deinit();
    }

    PAIRING_ACTIVE.store(false, Ordering::Relaxed);

    if PAIRING_DONE.load(Ordering::Relaxed) {
        info!("Pairing complete, restarting...");
        std::thread::sleep(std::time::Duration::from_secs(1));
        unsafe { esp_idf_sys::esp_restart(); }
    } else {
        info!("Pairing timeout");
    }
}

/// NVSに直接書き込むヘルパー (BLEコールバックから呼ばれる想定)
pub fn save_wifi_config(nvs: &EspNvs<NvsDefault>, ssid: &str, password: &str) -> bool {
    if nvs.set_str("wifi_ssid", ssid).is_err() { return false; }
    if nvs.set_str("wifi_pass", password).is_err() { return false; }
    info!("WiFi config saved");
    true
}

pub fn save_api_key(nvs: &EspNvs<NvsDefault>, key: &str) -> bool {
    if nvs.set_str("api_key", key).is_err() { return false; }
    info!("API key saved");
    true
}

pub fn save_channel(nvs: &EspNvs<NvsDefault>, channel: &str) -> bool {
    if nvs.set_str("soluna_ch", channel).is_err() { return false; }
    info!("Channel saved: {}", channel);
    true
}

pub fn mark_done() {
    PAIRING_DONE.store(true, Ordering::Relaxed);
}
