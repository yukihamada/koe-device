// BLEペアリング — NimBLE GATTサーバーで WiFi設定をNVSに書き込み
// スマホアプリから接続 → WiFi SSID/Pass を送信 → NVS保存
//
// Service UUID: 0xFFE0 (Koe Config)
// Char 0xFFE1: WiFi SSID (write)
// Char 0xFFE2: WiFi Password (write)
// Char 0xFFE3: Status (read/notify)
// Char 0xFFE4: Device Info (read)

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

/// BLEアドバタイズ開始（非ブロッキング）
/// NimBLE GATTサーバーを起動してバックグラウンドで実行
pub fn start_pairing(_nvs: &esp_idf_svc::nvs::EspNvs<esp_idf_svc::nvs::NvsDefault>) {
    PAIRING_ACTIVE.store(true, Ordering::Relaxed);
    info!("BLE: starting advertising");

    unsafe {
        // NimBLE初期化
        let ret = esp_idf_sys::nimble_port_init();
        if ret != 0 {
            error!("BLE: NimBLE init failed: {}", ret);
            PAIRING_ACTIVE.store(false, Ordering::Relaxed);
            return;
        }

        // デバイス名
        let name = std::ffi::CString::new("Koe-Device").unwrap();
        esp_idf_sys::ble_svc_gap_device_name_set(name.as_ptr());

        // GAP/GATTサービス初期化
        esp_idf_sys::ble_svc_gap_init();
        esp_idf_sys::ble_svc_gatt_init();

        // NimBLEをバックグラウンドスレッドで実行
        esp_idf_sys::nimble_port_freertos_init(Some(nimble_host_task));
    }

    // Advertising開始（NimBLEスタックが起動してから少し待つ）
    std::thread::sleep(std::time::Duration::from_millis(500));

    unsafe {
        let mut adv_params: esp_idf_sys::ble_gap_adv_params = core::mem::zeroed();
        adv_params.conn_mode = esp_idf_sys::BLE_GAP_CONN_MODE_UND as u8;
        adv_params.disc_mode = esp_idf_sys::BLE_GAP_DISC_MODE_GEN as u8;
        adv_params.itvl_min = 0x20;
        adv_params.itvl_max = 0x40;

        let ret = esp_idf_sys::ble_gap_adv_start(
            esp_idf_sys::BLE_OWN_ADDR_PUBLIC as u8,
            core::ptr::null(),
            i32::MAX,
            &adv_params,
            Some(gap_event_cb),
            core::ptr::null_mut(),
        );

        if ret != 0 {
            error!("BLE: adv_start failed: {}", ret);
        } else {
            info!("BLE: advertising as 'Koe-Device'");
        }
    }
}

/// NimBLE ホストタスク（FreeRTOSタスクとして実行）
extern "C" fn nimble_host_task(_param: *mut core::ffi::c_void) {
    info!("BLE: host task started");
    unsafe {
        esp_idf_sys::nimble_port_run();
    }
}

/// GAP イベントコールバック
extern "C" fn gap_event_cb(event: *mut esp_idf_sys::ble_gap_event, _arg: *mut core::ffi::c_void) -> i32 {
    unsafe {
        let ev = &*event;
        match ev.type_ as u32 {
            esp_idf_sys::BLE_GAP_EVENT_CONNECT => {
                let status = ev.__bindgen_anon_1.connect.status;
                if status == 0 {
                    info!("BLE: device connected");
                } else {
                    warn!("BLE: connect failed: {}", status);
                    // 再アドバタイズ
                    restart_advertising();
                }
            }
            esp_idf_sys::BLE_GAP_EVENT_DISCONNECT => {
                info!("BLE: device disconnected");
                restart_advertising();
            }
            _ => {}
        }
    }
    0
}

fn restart_advertising() {
    unsafe {
        let mut adv_params: esp_idf_sys::ble_gap_adv_params = core::mem::zeroed();
        adv_params.conn_mode = esp_idf_sys::BLE_GAP_CONN_MODE_UND as u8;
        adv_params.disc_mode = esp_idf_sys::BLE_GAP_DISC_MODE_GEN as u8;
        adv_params.itvl_min = 0x20;
        adv_params.itvl_max = 0x40;
        esp_idf_sys::ble_gap_adv_start(
            esp_idf_sys::BLE_OWN_ADDR_PUBLIC as u8,
            core::ptr::null(),
            i32::MAX,
            &adv_params,
            Some(gap_event_cb),
            core::ptr::null_mut(),
        );
    }
}
