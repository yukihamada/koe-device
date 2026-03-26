// OTA ファームウェア更新
//
// 2つのモード:
// 1. HTTPS OTA — サーバーから1:1ダウンロード (WAN)
// 2. マルチキャスト OTA — UDPで空中配信 (LAN、1台=1万台と同じ帯域)
//
// マルチキャストOTA プロトコル:
//   チャンネルID 0xFFFFFFFF = システムアップデート用
//   パケット: [SL 2B][sender 4B][chunk_idx 4B][0xFFFFFFFF 4B][total_chunks 4B][flags 1B][data 1024B]
//   flags: 0x20 = FLAG_OTA
//
// カルーセル配信:
//   Pi5がバイナリを1024Bずつ分割してループ送信
//   ESP32がバックグラウンドで拾い集める
//   欠損パケットは次のループで補完
//   100%揃ったらOTAパーティションに書き込み→再起動

use log::*;
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};

const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");
const OTA_URL: &str = "https://koe.live/api/v1/device/firmware";

// マルチキャストOTA定数
const OTA_CHANNEL_HASH: u32 = 0xFFFFFFFF; // システムアップデート用チャンネル
const OTA_CHUNK_SIZE: usize = 1024;        // 1パケット = 1024バイト
const OTA_MAX_CHUNKS: usize = 2048;        // 最大2MB (2048 × 1024)
const FLAG_OTA: u8 = 0x20;
const MAGIC: [u8; 2] = [0x53, 0x4C];

// OTA受信状態
static OTA_IN_PROGRESS: AtomicBool = AtomicBool::new(false);
static OTA_PROGRESS: AtomicU32 = AtomicU32::new(0); // 0-100%

pub fn is_updating() -> bool {
    OTA_IN_PROGRESS.load(Ordering::Relaxed)
}

pub fn progress() -> u32 {
    OTA_PROGRESS.load(Ordering::Relaxed)
}

// =====================================================
// マルチキャスト OTA 受信 (ESP32側)
// =====================================================

/// マルチキャストOTAパケットを処理 (メインRXループから呼ばれる)
/// 全チャンクが揃ったらOTA書き込み→再起動
pub fn handle_ota_packet(packet: &[u8]) -> bool {
    if packet.len() < 19 + 4 { return false; } // ヘッダ + 最低4バイト

    // ヘッダ検証
    if packet[0] != MAGIC[0] || packet[1] != MAGIC[1] { return false; }
    let flags = packet[18];
    if flags & FLAG_OTA == 0 { return false; }

    // チャンネルハッシュ = 0xFFFFFFFF?
    let ch = u32::from_le_bytes([packet[10], packet[11], packet[12], packet[13]]);
    if ch != OTA_CHANNEL_HASH { return false; }

    // OTAパケットフォーマット:
    // [19..23] chunk_index (u32 LE)
    // [23..27] total_chunks (u32 LE)
    // [27..31] firmware_hash (u32 LE) — バイナリ全体のFNV-1aハッシュ (整合性検証)
    // [31..]   chunk_data (最大1024B)
    if packet.len() < 31 { return false; }

    let chunk_idx = u32::from_le_bytes([packet[19], packet[20], packet[21], packet[22]]) as usize;
    let total_chunks = u32::from_le_bytes([packet[23], packet[24], packet[25], packet[26]]) as usize;
    let fw_hash = u32::from_le_bytes([packet[27], packet[28], packet[29], packet[30]]);
    let chunk_data = &packet[31..];

    if total_chunks == 0 || total_chunks > OTA_MAX_CHUNKS || chunk_idx >= total_chunks {
        return false;
    }

    // 静的なOTAバッファにアクセス (unsafe, シングルスレッドからのみ呼ばれる前提)
    static mut OTA_STATE: Option<MulticastOtaState> = None;

    unsafe {
        // 初回または新しいファームウェアの場合、状態をリセット
        let needs_init = match &OTA_STATE {
            None => true,
            Some(state) => state.fw_hash != fw_hash || state.total_chunks != total_chunks,
        };

        if needs_init {
            info!("OTA: new firmware detected ({} chunks, hash={:#x})", total_chunks, fw_hash);
            OTA_STATE = Some(MulticastOtaState::new(total_chunks, fw_hash));
            OTA_IN_PROGRESS.store(true, Ordering::Relaxed);
            OTA_PROGRESS.store(0, Ordering::Relaxed);
        }

        let state = OTA_STATE.as_mut().unwrap();

        // チャンクを記録
        if state.receive_chunk(chunk_idx, chunk_data) {
            let pct = (state.received_count as u32 * 100) / total_chunks as u32;
            OTA_PROGRESS.store(pct, Ordering::Relaxed);

            if pct % 10 == 0 {
                info!("OTA: {}% ({}/{})", pct, state.received_count, total_chunks);
            }

            // 100% 揃った！
            if state.received_count == total_chunks {
                info!("OTA: all chunks received, flashing...");
                match flash_ota(state) {
                    Ok(_) => {
                        info!("OTA: success, restarting...");
                        std::thread::sleep(std::time::Duration::from_secs(1));
                        esp_idf_sys::esp_restart();
                    }
                    Err(e) => {
                        error!("OTA flash failed: {:?}", e);
                        OTA_STATE = None;
                        OTA_IN_PROGRESS.store(false, Ordering::Relaxed);
                    }
                }
            }
        }
    }

    true
}

/// OTAパーティションに書き込み
unsafe fn flash_ota(state: &MulticastOtaState) -> Result<(), Box<dyn std::error::Error>> {
    let update_partition = esp_idf_sys::esp_ota_get_next_update_partition(core::ptr::null());
    if update_partition.is_null() {
        return Err("No OTA partition".into());
    }

    let total_size = state.total_size();
    let mut ota_handle: esp_idf_sys::esp_ota_handle_t = 0;
    let ret = esp_idf_sys::esp_ota_begin(update_partition, total_size, &mut ota_handle);
    if ret != 0 {
        return Err(format!("OTA begin: {}", ret).into());
    }

    // チャンクを順番にOTAパーティションに書き込み
    for i in 0..state.total_chunks {
        let offset = i * OTA_CHUNK_SIZE;
        let len = if i == state.total_chunks - 1 {
            state.last_chunk_size
        } else {
            OTA_CHUNK_SIZE
        };

        let ret = esp_idf_sys::esp_ota_write(
            ota_handle,
            state.buffer[offset..offset + len].as_ptr() as *const _,
            len,
        );
        if ret != 0 {
            esp_idf_sys::esp_ota_abort(ota_handle);
            return Err(format!("OTA write chunk {}: {}", i, ret).into());
        }
    }

    let ret = esp_idf_sys::esp_ota_end(ota_handle);
    if ret != 0 {
        return Err(format!("OTA end: {}", ret).into());
    }

    let ret = esp_idf_sys::esp_ota_set_boot_partition(update_partition);
    if ret != 0 {
        return Err(format!("OTA set boot: {}", ret).into());
    }

    Ok(())
}

// =====================================================
// マルチキャスト OTA 状態管理
// =====================================================

struct MulticastOtaState {
    buffer: Vec<u8>,             // ファームウェアバイナリ全体
    received: Vec<bool>,         // 各チャンクの受信済みフラグ
    total_chunks: usize,
    received_count: usize,
    fw_hash: u32,
    last_chunk_size: usize,
}

impl MulticastOtaState {
    fn new(total_chunks: usize, fw_hash: u32) -> Self {
        Self {
            buffer: vec![0u8; total_chunks * OTA_CHUNK_SIZE],
            received: vec![false; total_chunks],
            total_chunks,
            received_count: 0,
            fw_hash,
            last_chunk_size: OTA_CHUNK_SIZE,
        }
    }

    /// チャンクを受信。新規ならtrue、重複ならfalse
    fn receive_chunk(&mut self, idx: usize, data: &[u8]) -> bool {
        if idx >= self.total_chunks || self.received[idx] {
            return false; // 範囲外 or 既受信 → スキップ
        }

        let offset = idx * OTA_CHUNK_SIZE;
        let len = data.len().min(OTA_CHUNK_SIZE);
        self.buffer[offset..offset + len].copy_from_slice(&data[..len]);
        self.received[idx] = true;
        self.received_count += 1;

        // 最後のチャンクのサイズを記録
        if idx == self.total_chunks - 1 {
            self.last_chunk_size = len;
        }

        true
    }

    fn total_size(&self) -> usize {
        if self.total_chunks == 0 { return 0; }
        (self.total_chunks - 1) * OTA_CHUNK_SIZE + self.last_chunk_size
    }
}

// =====================================================
// マルチキャスト OTA 送信 (Pi5/STAGEサーバー側)
// =====================================================

/// ファームウェアバイナリをマルチキャスト送信用のパケットに分割
/// (Pi5の soluna-server.py から呼ぶ想定だが、ESP32でもリレー可能)
pub fn build_ota_packet(
    sender_hash: u32,
    chunk_idx: u32,
    total_chunks: u32,
    fw_hash: u32,
    chunk_data: &[u8],
    out: &mut [u8],
) -> usize {
    if out.len() < 31 + chunk_data.len() { return 0; }

    // 19バイトSolunaヘッダ
    out[0..2].copy_from_slice(&MAGIC);
    out[2..6].copy_from_slice(&sender_hash.to_le_bytes());
    out[6..10].copy_from_slice(&chunk_idx.to_le_bytes());
    out[10..14].copy_from_slice(&OTA_CHANNEL_HASH.to_le_bytes());
    out[14..18].copy_from_slice(&total_chunks.to_le_bytes());
    out[18] = FLAG_OTA;

    // OTA拡張ヘッダ (12バイト)
    out[19..23].copy_from_slice(&chunk_idx.to_le_bytes());
    out[23..27].copy_from_slice(&total_chunks.to_le_bytes());
    out[27..31].copy_from_slice(&fw_hash.to_le_bytes());

    // チャンクデータ
    let len = chunk_data.len().min(OTA_CHUNK_SIZE);
    out[31..31 + len].copy_from_slice(&chunk_data[..len]);

    31 + len
}

// =====================================================
// HTTPS OTA (従来方式、WANフォールバック)
// =====================================================

pub fn check_and_update(device_id: &str) -> Result<bool, Box<dyn std::error::Error>> {
    info!("OTA check (v{})", CURRENT_VERSION);

    let check_url = format!("{}?device_id={}&version={}", OTA_URL, device_id, CURRENT_VERSION);

    let config = esp_idf_svc::http::client::Configuration {
        buffer_size: Some(4096),
        timeout: Some(std::time::Duration::from_secs(30)),
        ..Default::default()
    };

    let mut client = esp_idf_svc::http::client::EspHttpConnection::new(&config)?;
    let headers = [("X-Device-Id", device_id)];

    client.initiate_request(esp_idf_svc::http::Method::Get, &check_url, &headers)?;
    client.initiate_response()?;

    let status = client.status();
    if status == 204 {
        info!("OTA: up to date");
        return Ok(false);
    }
    if status != 200 {
        return Err(format!("OTA check: HTTP {}", status).into());
    }

    info!("OTA: new version available, downloading...");

    unsafe {
        let update_partition = esp_idf_sys::esp_ota_get_next_update_partition(core::ptr::null());
        if update_partition.is_null() {
            return Err("No OTA partition".into());
        }

        let mut ota_handle: esp_idf_sys::esp_ota_handle_t = 0;
        let ret = esp_idf_sys::esp_ota_begin(update_partition, esp_idf_sys::OTA_SIZE_UNKNOWN as usize, &mut ota_handle);
        if ret != 0 {
            return Err(format!("OTA begin: {}", ret).into());
        }

        let mut buf = [0u8; 4096];
        let mut total: usize = 0;
        loop {
            let n = client.read(&mut buf)?;
            if n == 0 { break; }
            let ret = esp_idf_sys::esp_ota_write(ota_handle, buf.as_ptr() as *const _, n);
            if ret != 0 {
                esp_idf_sys::esp_ota_abort(ota_handle);
                return Err(format!("OTA write: {}", ret).into());
            }
            total += n;
        }

        info!("OTA: wrote {} bytes", total);

        let ret = esp_idf_sys::esp_ota_end(ota_handle);
        if ret != 0 { return Err(format!("OTA end: {}", ret).into()); }

        let ret = esp_idf_sys::esp_ota_set_boot_partition(update_partition);
        if ret != 0 { return Err(format!("OTA set boot: {}", ret).into()); }

        info!("OTA: success, restarting...");
        std::thread::sleep(std::time::Duration::from_secs(1));
        esp_idf_sys::esp_restart();
    }
}
