// BLEペアリング + iPhoneブリッジモード
//
// Service UUID: 0xFFE0 (Koe Config)
// FFE1: WiFi SSID (write)         — WiFi直接設定
// FFE2: WiFi Password (write)      — WiFi直接設定
// FFE3: Status (read)              — "ready" / "ok"
// FFE5: Audio TX (notify)          — ESP32→iPhone PCMチャンク (ブリッジモード)
// FFE6: Audio RX (write-no-rsp)   — iPhone→ESP32 PCMチャンク (ブリッジモード)
//
// プロトコル: 512バイト以下のPCMチャンクを連続送信、終端は [0x00] 1バイトパケット

use log::*;
use std::sync::atomic::{AtomicBool, AtomicU16, AtomicU8, Ordering};
use std::sync::Mutex;

static PAIRING_ACTIVE: AtomicBool = AtomicBool::new(false);
static PAIRING_DONE: AtomicBool = AtomicBool::new(false);
static BLE_CONNECTED: AtomicBool = AtomicBool::new(false);

// 接続ハンドル (notify送信に必要)
static CONN_HANDLE: AtomicU16 = AtomicU16::new(u16::MAX);

// WiFi認証情報バッファ
static WIFI_SSID: Mutex<[u8; 64]> = Mutex::new([0u8; 64]);
static WIFI_PASS: Mutex<[u8; 128]> = Mutex::new([0u8; 128]);
static SSID_LEN: AtomicU8 = AtomicU8::new(0);
static PASS_LEN: AtomicU8 = AtomicU8::new(0);

// 受信音声キュー (iPhone→ESP32, ブリッジモード)
static RX_AUDIO: Mutex<Vec<Vec<u8>>> = Mutex::new(Vec::new());
static RX_AUDIO_DONE: AtomicBool = AtomicBool::new(false); // EOU受信

// ─── 公開API ─────────────────────────────────────────────────

pub fn is_pairing() -> bool { PAIRING_ACTIVE.load(Ordering::Relaxed) }
pub fn is_done() -> bool { PAIRING_DONE.load(Ordering::Relaxed) }
pub fn is_connected() -> bool { BLE_CONNECTED.load(Ordering::Relaxed) }

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

/// 音声チャンクをFFE5 notify で送信 (ブリッジモード)
pub fn notify_audio(data: &[u8]) -> bool {
    let conn = CONN_HANDLE.load(Ordering::Relaxed);
    if conn == u16::MAX { return false; }
    unsafe {
        let handle = AUDIO_TX_HANDLE;
        if handle == 0 { return false; }
        // チャンクを512バイト以下に分割
        for chunk in data.chunks(512) {
            let om = esp_idf_sys::ble_hs_mbuf_from_flat(
                chunk.as_ptr() as *const _,
                chunk.len() as u16,
            );
            if om.is_null() { return false; }
            let rc = esp_idf_sys::ble_gatts_notify_custom(conn, handle, om);
            if rc != 0 { return false; }
        }
    }
    true
}

/// 発話終了マーカー [0x00] を送信
pub fn notify_audio_end() -> bool {
    let conn = CONN_HANDLE.load(Ordering::Relaxed);
    if conn == u16::MAX { return false; }
    unsafe {
        let handle = AUDIO_TX_HANDLE;
        if handle == 0 { return false; }
        let eou: [u8; 1] = [0x00];
        let om = esp_idf_sys::ble_hs_mbuf_from_flat(
            eou.as_ptr() as *const _,
            1,
        );
        if om.is_null() { return false; }
        esp_idf_sys::ble_gatts_notify_custom(conn, handle, om) == 0
    }
}

/// iPhoneから受信した音声チャンクを取り出す
pub fn pop_rx_chunk() -> Option<Vec<u8>> {
    RX_AUDIO.lock().ok()?.pop()
}

/// EOU受信済みかどうか (レスポンス音声全体の受信完了)
pub fn rx_audio_complete() -> bool {
    RX_AUDIO_DONE.swap(false, Ordering::Relaxed)
}

// ─── GATTテーブル ────────────────────────────────────────────

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
static AUDIO_TX_UUID16: esp_idf_sys::ble_uuid16_t = esp_idf_sys::ble_uuid16_t {
    u: esp_idf_sys::ble_uuid_t { type_: esp_idf_sys::BLE_UUID_TYPE_16 as u8 },
    value: 0xFFE5,
};
static AUDIO_RX_UUID16: esp_idf_sys::ble_uuid16_t = esp_idf_sys::ble_uuid16_t {
    u: esp_idf_sys::ble_uuid_t { type_: esp_idf_sys::BLE_UUID_TYPE_16 as u8 },
    value: 0xFFE6,
};

static mut SSID_HANDLE: u16 = 0;
static mut PASS_HANDLE: u16 = 0;
static mut STATUS_HANDLE: u16 = 0;
static mut AUDIO_TX_HANDLE: u16 = 0;  // FFE5 notify
static mut AUDIO_RX_HANDLE: u16 = 0;  // FFE6 write

// [FFE1, FFE2, FFE3, FFE5, FFE6, Terminator]
static mut GATT_CHRS: [esp_idf_sys::ble_gatt_chr_def; 6] = unsafe { core::mem::zeroed() };
static mut GATT_SVCS: [esp_idf_sys::ble_gatt_svc_def; 2] = unsafe { core::mem::zeroed() };

unsafe fn init_gatt_table() {
    let wr = (esp_idf_sys::BLE_GATT_CHR_F_WRITE | esp_idf_sys::BLE_GATT_CHR_F_WRITE_NO_RSP) as u16;
    let rd = esp_idf_sys::BLE_GATT_CHR_F_READ as u16;
    let ntf = (esp_idf_sys::BLE_GATT_CHR_F_NOTIFY | esp_idf_sys::BLE_GATT_CHR_F_READ) as u16;
    let wronly = esp_idf_sys::BLE_GATT_CHR_F_WRITE_NO_RSP as u16;

    GATT_CHRS[0] = chr(&SSID_UUID16, Some(gatt_cb), wr,    &mut SSID_HANDLE);
    GATT_CHRS[1] = chr(&PASS_UUID16, Some(gatt_cb), wr,    &mut PASS_HANDLE);
    GATT_CHRS[2] = chr(&STATUS_UUID16, Some(gatt_cb), rd,  &mut STATUS_HANDLE);
    GATT_CHRS[3] = chr(&AUDIO_TX_UUID16, Some(gatt_cb), ntf, &mut AUDIO_TX_HANDLE);
    GATT_CHRS[4] = chr(&AUDIO_RX_UUID16, Some(gatt_cb), wronly, &mut AUDIO_RX_HANDLE);
    // GATT_CHRS[5] = zeroed (terminator)

    GATT_SVCS[0] = esp_idf_sys::ble_gatt_svc_def {
        type_: esp_idf_sys::BLE_GATT_SVC_TYPE_PRIMARY as u8,
        uuid: &SVC_UUID16.u as *const _,
        includes: core::ptr::null_mut(),
        characteristics: GATT_CHRS.as_ptr(),
    };
    // GATT_SVCS[1] = zeroed (terminator)
}

unsafe fn chr(
    uuid16: &'static esp_idf_sys::ble_uuid16_t,
    cb: esp_idf_sys::ble_gatt_access_fn,
    flags: u16,
    handle: *mut u16,
) -> esp_idf_sys::ble_gatt_chr_def {
    esp_idf_sys::ble_gatt_chr_def {
        uuid: &uuid16.u as *const _,
        access_cb: cb,
        arg: core::ptr::null_mut(),
        descriptors: core::ptr::null_mut(),
        flags,
        min_key_size: 0,
        val_handle: handle,
        cpfd: core::ptr::null_mut(),
    }
}

// ─── GATTコールバック ─────────────────────────────────────────

extern "C" fn gatt_cb(
    _conn: u16,
    attr_handle: u16,
    ctxt: *mut esp_idf_sys::ble_gatt_access_ctxt,
    _arg: *mut core::ffi::c_void,
) -> i32 {
    unsafe {
        let op = (*ctxt).op as u32;

        // ─ 読み取り (Status FFE3) ─
        if op == esp_idf_sys::BLE_GATT_ACCESS_OP_READ_CHR {
            let msg = if PAIRING_DONE.load(Ordering::Relaxed) { b"ok" as &[u8] } else { b"ready" };
            let rc = esp_idf_sys::os_mbuf_append((*ctxt).om, msg.as_ptr() as *const _, msg.len() as u16);
            return if rc == 0 { 0 } else { esp_idf_sys::BLE_ATT_ERR_INSUFFICIENT_RES as i32 };
        }

        if op != esp_idf_sys::BLE_GATT_ACCESS_OP_WRITE_CHR { return 0; }

        // ─ 書き込みデータ読み取り ─
        let mut buf = [0u8; 512];
        let mut out_len: u16 = 0;
        let rc = esp_idf_sys::ble_hs_mbuf_to_flat(
            (*ctxt).om, buf.as_mut_ptr() as *mut _, buf.len() as u16, &mut out_len,
        );
        if rc != 0 { return rc; }
        let data = &buf[..out_len as usize];

        if attr_handle == SSID_HANDLE {
            if data.starts_with(b"{") {
                if let Ok(s) = core::str::from_utf8(data) {
                    if let (Some(ssid), Some(pass)) = (json_str(s, "ssid"), json_str(s, "pass")) {
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
        } else if attr_handle == AUDIO_RX_HANDLE {
            // iPhoneからのTTS音声チャンク受信
            if out_len == 1 && data[0] == 0x00 {
                // EOU: レスポンス全体受信完了
                RX_AUDIO_DONE.store(true, Ordering::Relaxed);
                info!("BLE: RX audio complete");
            } else {
                if let Ok(mut q) = RX_AUDIO.lock() {
                    q.push(data.to_vec());
                }
            }
        }
    }
    0
}

fn store_ssid(data: &[u8]) {
    let len = data.len().min(63);
    if let Ok(mut buf) = WIFI_SSID.lock() { buf[..len].copy_from_slice(&data[..len]); }
    SSID_LEN.store(len as u8, Ordering::Relaxed);
    info!("BLE: SSID {}B", len);
}

fn store_pass(data: &[u8]) {
    let len = data.len().min(127);
    if let Ok(mut buf) = WIFI_PASS.lock() { buf[..len].copy_from_slice(&data[..len]); }
    PASS_LEN.store(len as u8, Ordering::Relaxed);
    info!("BLE: Pass {}B", len);
}

fn check_complete() {
    if SSID_LEN.load(Ordering::Relaxed) > 0 {
        PAIRING_DONE.store(true, Ordering::Relaxed);
        info!("BLE: provisioning complete");
    }
}

fn json_str(json: &str, key: &str) -> Option<String> {
    let search = format!("\"{}\":\"", key);
    let start = json.find(&search)? + search.len();
    let end = json[start..].find('"')?;
    Some(json[start..start + end].to_string())
}

// ─── BLE起動 ─────────────────────────────────────────────────

pub fn start_pairing(_nvs: &esp_idf_svc::nvs::EspNvs<esp_idf_svc::nvs::NvsDefault>) {
    PAIRING_ACTIVE.store(true, Ordering::Relaxed);
    info!("BLE: starting NimBLE GATT server (FFE0/FFE1/FFE2/FFE5/FFE6)");

    unsafe {
        let ret = esp_idf_sys::nimble_port_init();
        if ret != 0 {
            error!("BLE: init failed: {}", ret);
            PAIRING_ACTIVE.store(false, Ordering::Relaxed);
            return;
        }

        let name = std::ffi::CString::new("Koe-Device").unwrap();
        esp_idf_sys::ble_svc_gap_device_name_set(name.as_ptr());
        esp_idf_sys::ble_svc_gap_init();
        esp_idf_sys::ble_svc_gatt_init();

        init_gatt_table();

        let rc = esp_idf_sys::ble_gatts_count_cfg(GATT_SVCS.as_ptr());
        if rc != 0 { error!("BLE: count_cfg: {}", rc); }
        let rc = esp_idf_sys::ble_gatts_add_svcs(GATT_SVCS.as_ptr());
        if rc != 0 { error!("BLE: add_svcs: {}", rc); }

        esp_idf_sys::ble_hs_cfg.sync_cb = Some(on_sync);
        esp_idf_sys::ble_hs_cfg.reset_cb = Some(on_reset);

        esp_idf_sys::nimble_port_freertos_init(Some(nimble_host_task));
    }
}

extern "C" fn on_sync() {
    info!("BLE: synced → advertising");
    unsafe {
        let name = b"Koe-Device";
        let mut adv: esp_idf_sys::ble_hs_adv_fields = core::mem::zeroed();
        adv.flags = (esp_idf_sys::BLE_HS_ADV_F_DISC_GEN | esp_idf_sys::BLE_HS_ADV_F_BREDR_UNSUP) as u8;
        adv.set_tx_pwr_lvl_is_present(1);
        adv.tx_pwr_lvl = esp_idf_sys::BLE_HS_ADV_TX_PWR_LVL_AUTO as i8;
        adv.name = name.as_ptr();
        adv.name_len = name.len() as u8;
        adv.set_name_is_complete(1);

        let svc_uuid = esp_idf_sys::ble_uuid16_t {
            u: esp_idf_sys::ble_uuid_t { type_: esp_idf_sys::BLE_UUID_TYPE_16 as u8 },
            value: 0xFFE0,
        };
        adv.uuids16 = &svc_uuid;
        adv.num_uuids16 = 1;
        adv.set_uuids16_is_complete(1);

        let rc = esp_idf_sys::ble_gap_adv_set_fields(&adv);
        if rc != 0 { error!("BLE: set_adv_fields: {}", rc); }

        let mut params: esp_idf_sys::ble_gap_adv_params = core::mem::zeroed();
        params.conn_mode = esp_idf_sys::BLE_GAP_CONN_MODE_UND as u8;
        params.disc_mode = esp_idf_sys::BLE_GAP_DISC_MODE_GEN as u8;
        params.itvl_min = 0x30;
        params.itvl_max = 0x60;

        let rc = esp_idf_sys::ble_gap_adv_start(
            esp_idf_sys::BLE_OWN_ADDR_PUBLIC as u8,
            core::ptr::null(), i32::MAX,
            &params, Some(gap_cb), core::ptr::null_mut(),
        );
        if rc == 0 { info!("BLE: advertising 'Koe-Device'"); }
        else { error!("BLE: adv_start: {}", rc); }
    }
}

extern "C" fn on_reset(reason: i32) {
    warn!("BLE: reset reason={}", reason);
}

extern "C" fn nimble_host_task(_: *mut core::ffi::c_void) {
    unsafe { esp_idf_sys::nimble_port_run(); }
}

extern "C" fn gap_cb(event: *mut esp_idf_sys::ble_gap_event, _: *mut core::ffi::c_void) -> i32 {
    unsafe {
        let ev = &*event;
        match ev.type_ as u32 {
            esp_idf_sys::BLE_GAP_EVENT_CONNECT => {
                let status = ev.__bindgen_anon_1.connect.status;
                if status == 0 {
                    let conn_handle = ev.__bindgen_anon_1.connect.conn_handle;
                    CONN_HANDLE.store(conn_handle, Ordering::Relaxed);
                    BLE_CONNECTED.store(true, Ordering::Relaxed);
                    info!("BLE: connected (handle={})", conn_handle);
                } else {
                    warn!("BLE: connect failed: {}", status);
                    restart_adv();
                }
            }
            esp_idf_sys::BLE_GAP_EVENT_DISCONNECT => {
                CONN_HANDLE.store(u16::MAX, Ordering::Relaxed);
                BLE_CONNECTED.store(false, Ordering::Relaxed);
                info!("BLE: disconnected");
                if !PAIRING_DONE.load(Ordering::Relaxed) {
                    restart_adv();
                }
            }
            _ => {}
        }
    }
    0
}

fn restart_adv() {
    unsafe {
        let mut params: esp_idf_sys::ble_gap_adv_params = core::mem::zeroed();
        params.conn_mode = esp_idf_sys::BLE_GAP_CONN_MODE_UND as u8;
        params.disc_mode = esp_idf_sys::BLE_GAP_DISC_MODE_GEN as u8;
        params.itvl_min = 0x20;
        params.itvl_max = 0x40;
        esp_idf_sys::ble_gap_adv_start(
            esp_idf_sys::BLE_OWN_ADDR_PUBLIC as u8,
            core::ptr::null(), i32::MAX,
            &params, Some(gap_cb), core::ptr::null_mut(),
        );
    }
}
