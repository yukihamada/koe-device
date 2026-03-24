// BLEペアリング — NimBLE GATTサーバーで WiFi設定をNVSに書き込み
// スマホアプリから接続 → WiFi SSID/Pass を送信 → NVS保存 → 再起動
//
// Service UUID: 0xFFE0 (Koe Config)
// Char 0xFFE1: WiFi SSID (write / write-no-rsp)
// Char 0xFFE2: WiFi Password (write / write-no-rsp)
// Char 0xFFE3: Status (read)  — "ready" or "ok"

use log::*;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::Mutex;

static PAIRING_ACTIVE: AtomicBool = AtomicBool::new(false);
static PAIRING_DONE: AtomicBool = AtomicBool::new(false);

// 受信バッファ (最大64/128バイト)
static WIFI_SSID: Mutex<[u8; 64]> = Mutex::new([0u8; 64]);
static WIFI_PASS: Mutex<[u8; 128]> = Mutex::new([0u8; 128]);
static SSID_LEN: AtomicU8 = AtomicU8::new(0);
static PASS_LEN: AtomicU8 = AtomicU8::new(0);

pub fn is_pairing() -> bool {
    PAIRING_ACTIVE.load(Ordering::Relaxed)
}

pub fn is_done() -> bool {
    PAIRING_DONE.load(Ordering::Relaxed)
}

/// 受信したWiFi認証情報を取得 (main.rsがNVS書き込みに使用)
pub fn get_wifi_ssid() -> Option<String> {
    let len = SSID_LEN.load(Ordering::Relaxed) as usize;
    if len == 0 { return None; }
    let buf = WIFI_SSID.lock().ok()?;
    String::from_utf8(buf[..len].to_vec()).ok()
}

pub fn get_wifi_pass() -> Option<String> {
    let len = PASS_LEN.load(Ordering::Relaxed) as usize;
    let buf = WIFI_PASS.lock().ok()?;
    String::from_utf8(buf[..len].to_vec()).ok()
}

// ─────────────────────────────────────────────────────────────
// GATTサービステーブル (static mut — NimBLEが参照し続けるため)
// ─────────────────────────────────────────────────────────────

// 16-bit UUID定義
static SVC_UUID16: esp_idf_sys::ble_uuid16_t = esp_idf_sys::ble_uuid16_t {
    u: esp_idf_sys::ble_uuid_t { type_: esp_idf_sys::BLE_UUID_TYPE_16 as u8 },
    value: 0xFFE0,
};
static SSID_UUID16: esp_idf_sys::ble_uuid16_t = esp_idf_sys::ble_uuid16_t {
    u: esp_idf_sys::ble_uuid_t { type_: esp_idf_sys::BLE_UUID_TYPE_16 as u8 },
    value: 0xFFE1,
};
static PASS_UUID16: esp_idf_sys::ble_uuid16_t = esp_idf_sys::ble_uuid16_t {
    u: esp_idf_sys::ble_uuid_t { type_: esp_idf_sys::BLE_UUID_TYPE_16 as u8 },
    value: 0xFFE2,
};
static STATUS_UUID16: esp_idf_sys::ble_uuid16_t = esp_idf_sys::ble_uuid16_t {
    u: esp_idf_sys::ble_uuid_t { type_: esp_idf_sys::BLE_UUID_TYPE_16 as u8 },
    value: 0xFFE3,
};

// 特性ハンドル (NimBLE登録時に設定される)
static mut SSID_HANDLE: u16 = 0;
static mut PASS_HANDLE: u16 = 0;
static mut STATUS_HANDLE: u16 = 0;

// 特性テーブル [SSID, Pass, Status, Terminator]
static mut GATT_CHRS: [esp_idf_sys::ble_gatt_chr_def; 4] = unsafe { core::mem::zeroed() };
// サービステーブル [KoeConfig, Terminator]
static mut GATT_SVCS: [esp_idf_sys::ble_gatt_svc_def; 2] = unsafe { core::mem::zeroed() };

/// GATTテーブルを初期化 (nimble_port_init後, freertos_init前に呼ぶ)
unsafe fn init_gatt_table() {
    let wr_flags = (esp_idf_sys::BLE_GATT_CHR_F_WRITE
        | esp_idf_sys::BLE_GATT_CHR_F_WRITE_NO_RSP) as u16;
    let rd_flags = esp_idf_sys::BLE_GATT_CHR_F_READ as u16;

    // 0xFFE1 SSID
    GATT_CHRS[0] = esp_idf_sys::ble_gatt_chr_def {
        uuid: &SSID_UUID16.u as *const _,
        access_cb: Some(gatt_access_cb),
        arg: core::ptr::null_mut(),
        descriptors: core::ptr::null_mut(),
        flags: wr_flags,
        min_key_size: 0,
        val_handle: &mut SSID_HANDLE as *mut u16,
        cpfd: core::ptr::null_mut(),
    };
    // 0xFFE2 Password
    GATT_CHRS[1] = esp_idf_sys::ble_gatt_chr_def {
        uuid: &PASS_UUID16.u as *const _,
        access_cb: Some(gatt_access_cb),
        arg: core::ptr::null_mut(),
        descriptors: core::ptr::null_mut(),
        flags: wr_flags,
        min_key_size: 0,
        val_handle: &mut PASS_HANDLE as *mut u16,
        cpfd: core::ptr::null_mut(),
    };
    // 0xFFE3 Status (read)
    GATT_CHRS[2] = esp_idf_sys::ble_gatt_chr_def {
        uuid: &STATUS_UUID16.u as *const _,
        access_cb: Some(gatt_access_cb),
        arg: core::ptr::null_mut(),
        descriptors: core::ptr::null_mut(),
        flags: rd_flags,
        min_key_size: 0,
        val_handle: &mut STATUS_HANDLE as *mut u16,
        cpfd: core::ptr::null_mut(),
    };
    // Terminator (index 3 は zeroed のまま)

    // Service
    GATT_SVCS[0] = esp_idf_sys::ble_gatt_svc_def {
        type_: esp_idf_sys::BLE_GATT_SVC_TYPE_PRIMARY as u8,
        uuid: &SVC_UUID16.u as *const _,
        includes: core::ptr::null_mut(),
        characteristics: GATT_CHRS.as_ptr(),
    };
    // Terminator (index 1 は zeroed のまま)
}

// ─────────────────────────────────────────────────────────────
// GATT アクセスコールバック
// ─────────────────────────────────────────────────────────────

extern "C" fn gatt_access_cb(
    _conn_handle: u16,
    attr_handle: u16,
    ctxt: *mut esp_idf_sys::ble_gatt_access_ctxt,
    _arg: *mut core::ffi::c_void,
) -> i32 {
    unsafe {
        let op = (*ctxt).op as u32;

        if op == esp_idf_sys::BLE_GATT_ACCESS_OP_READ_CHR {
            // Status読み込み → "ready" を返す
            let status = if PAIRING_DONE.load(Ordering::Relaxed) { b"ok" as &[u8] } else { b"ready" };
            let rc = esp_idf_sys::os_mbuf_append(
                (*ctxt).om,
                status.as_ptr() as *const _,
                status.len() as u16,
            );
            return if rc == 0 { 0 } else { esp_idf_sys::BLE_ATT_ERR_INSUFFICIENT_RES as i32 };
        }

        if op != esp_idf_sys::BLE_GATT_ACCESS_OP_WRITE_CHR {
            return 0;
        }

        // 書き込みデータを読み取る
        let mut buf = [0u8; 256];
        let mut out_len: u16 = 0;
        let rc = esp_idf_sys::ble_hs_mbuf_to_flat(
            (*ctxt).om,
            buf.as_mut_ptr() as *mut _,
            buf.len() as u16,
            &mut out_len,
        );
        if rc != 0 {
            warn!("BLE: mbuf_to_flat failed: {}", rc);
            return rc;
        }

        let data = &buf[..out_len as usize];

        if attr_handle == SSID_HANDLE {
            // JSON {"ssid":"...","pass":"..."} かどうか試みる
            if data.starts_with(b"{") {
                if let Ok(s) = core::str::from_utf8(data) {
                    if let (Some(ssid), Some(pass)) = (extract_json_str(s, "ssid"), extract_json_str(s, "pass")) {
                        store_ssid(ssid.as_bytes());
                        store_pass(pass.as_bytes());
                        check_complete();
                        return 0;
                    }
                }
            }
            store_ssid(data);
            check_complete();
        } else if attr_handle == PASS_HANDLE {
            store_pass(data);
            check_complete();
        }
    }
    0
}

fn store_ssid(data: &[u8]) {
    let len = data.len().min(63);
    if let Ok(mut buf) = WIFI_SSID.lock() {
        buf[..len].copy_from_slice(&data[..len]);
        SSID_LEN.store(len as u8, Ordering::Relaxed);
    }
    info!("BLE: SSID received ({} bytes)", data.len());
}

fn store_pass(data: &[u8]) {
    let len = data.len().min(127);
    if let Ok(mut buf) = WIFI_PASS.lock() {
        buf[..len].copy_from_slice(&data[..len]);
        PASS_LEN.store(len as u8, Ordering::Relaxed);
    }
    info!("BLE: Pass received ({} bytes)", data.len());
}

fn check_complete() {
    let has_ssid = SSID_LEN.load(Ordering::Relaxed) > 0;
    let has_pass = PASS_LEN.load(Ordering::Relaxed) > 0;
    // SSIDだけあればパスワードなしオープンWiFiも許可
    if has_ssid || (has_ssid && has_pass) {
        PAIRING_DONE.store(true, Ordering::Relaxed);
        info!("BLE: WiFi credentials complete, provisioning done");
    }
}

/// JSONから簡易キー値を抽出 (依存なし)
fn extract_json_str<'a>(json: &'a str, key: &str) -> Option<String> {
    let search = format!("\"{}\":\"", key);
    let start = json.find(&search)? + search.len();
    let rest = &json[start..];
    let end = rest.find('"')?;
    Some(rest[..end].to_string())
}

// ─────────────────────────────────────────────────────────────
// BLE起動
// ─────────────────────────────────────────────────────────────

/// BLEアドバタイズ開始（非ブロッキング）
pub fn start_pairing(_nvs: &esp_idf_svc::nvs::EspNvs<esp_idf_svc::nvs::NvsDefault>) {
    PAIRING_ACTIVE.store(true, Ordering::Relaxed);
    info!("BLE: starting NimBLE GATT server");

    unsafe {
        // NimBLE初期化
        let ret = esp_idf_sys::nimble_port_init();
        if ret != 0 {
            error!("BLE: NimBLE init failed: {}", ret);
            PAIRING_ACTIVE.store(false, Ordering::Relaxed);
            return;
        }

        // デバイス名設定
        let name = std::ffi::CString::new("Koe-Device").unwrap();
        esp_idf_sys::ble_svc_gap_device_name_set(name.as_ptr());

        // GAP/GATTサービス初期化
        esp_idf_sys::ble_svc_gap_init();
        esp_idf_sys::ble_svc_gatt_init();

        // カスタムGATTテーブル初期化
        init_gatt_table();

        // サービスリソースカウント登録
        let rc = esp_idf_sys::ble_gatts_count_cfg(GATT_SVCS.as_ptr());
        if rc != 0 {
            error!("BLE: gatts_count_cfg failed: {}", rc);
        }

        // サービス登録
        let rc = esp_idf_sys::ble_gatts_add_svcs(GATT_SVCS.as_ptr());
        if rc != 0 {
            error!("BLE: gatts_add_svcs failed: {}", rc);
        }

        // sync_cb を設定してアドバタイズをスタック起動後に行う
        esp_idf_sys::ble_hs_cfg.sync_cb = Some(on_sync);
        esp_idf_sys::ble_hs_cfg.reset_cb = Some(on_reset);

        // NimBLEをバックグラウンドスレッドで実行
        esp_idf_sys::nimble_port_freertos_init(Some(nimble_host_task));
    }
}

/// NimBLE同期完了コールバック — アドバタイズ開始
extern "C" fn on_sync() {
    info!("BLE: host synced, starting advertising");
    unsafe {
        // アドバタイズデータ設定
        let device_name = b"Koe-Device";
        let mut adv_fields: esp_idf_sys::ble_hs_adv_fields = core::mem::zeroed();
        adv_fields.flags = (esp_idf_sys::BLE_HS_ADV_F_DISC_GEN
            | esp_idf_sys::BLE_HS_ADV_F_BREDR_UNSUP) as u8;
        adv_fields.set_tx_pwr_lvl_is_present(1);
        adv_fields.tx_pwr_lvl = esp_idf_sys::BLE_HS_ADV_TX_PWR_LVL_AUTO as i8;
        adv_fields.name = device_name.as_ptr();
        adv_fields.name_len = device_name.len() as u8;
        adv_fields.set_name_is_complete(1);

        // サービスUUID FFE0
        let svc_uuid = esp_idf_sys::ble_uuid16_t {
            u: esp_idf_sys::ble_uuid_t { type_: esp_idf_sys::BLE_UUID_TYPE_16 as u8 },
            value: 0xFFE0,
        };
        adv_fields.uuids16 = &svc_uuid;
        adv_fields.num_uuids16 = 1;
        adv_fields.set_uuids16_is_complete(1);

        let rc = esp_idf_sys::ble_gap_adv_set_fields(&adv_fields);
        if rc != 0 {
            error!("BLE: set_adv_fields failed: {}", rc);
        }

        // Advertising開始
        let mut adv_params: esp_idf_sys::ble_gap_adv_params = core::mem::zeroed();
        adv_params.conn_mode = esp_idf_sys::BLE_GAP_CONN_MODE_UND as u8;
        adv_params.disc_mode = esp_idf_sys::BLE_GAP_DISC_MODE_GEN as u8;
        adv_params.itvl_min = 0x30; // 30ms
        adv_params.itvl_max = 0x60; // 60ms

        let rc = esp_idf_sys::ble_gap_adv_start(
            esp_idf_sys::BLE_OWN_ADDR_PUBLIC as u8,
            core::ptr::null(),
            i32::MAX,
            &adv_params,
            Some(gap_event_cb),
            core::ptr::null_mut(),
        );
        if rc != 0 {
            error!("BLE: adv_start failed: {}", rc);
        } else {
            info!("BLE: advertising as 'Koe-Device' (FFE0/FFE1/FFE2)");
        }
    }
}

extern "C" fn on_reset(reason: i32) {
    warn!("BLE: host reset, reason={}", reason);
}

/// NimBLE ホストタスク（FreeRTOSタスクとして実行）
extern "C" fn nimble_host_task(_param: *mut core::ffi::c_void) {
    info!("BLE: host task started");
    unsafe {
        esp_idf_sys::nimble_port_run();
    }
}

/// GAP イベントコールバック
extern "C" fn gap_event_cb(
    event: *mut esp_idf_sys::ble_gap_event,
    _arg: *mut core::ffi::c_void,
) -> i32 {
    unsafe {
        let ev = &*event;
        match ev.type_ as u32 {
            esp_idf_sys::BLE_GAP_EVENT_CONNECT => {
                let status = ev.__bindgen_anon_1.connect.status;
                if status == 0 {
                    info!("BLE: device connected");
                } else {
                    warn!("BLE: connect failed: {}", status);
                    restart_advertising();
                }
            }
            esp_idf_sys::BLE_GAP_EVENT_DISCONNECT => {
                info!("BLE: device disconnected");
                if !PAIRING_DONE.load(Ordering::Relaxed) {
                    restart_advertising();
                }
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
