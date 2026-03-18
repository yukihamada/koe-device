// OTAファームウェア更新 — HTTPS経由でバイナリ取得 → ota_1に書き込み → 再起動
//
// フロー:
// 1. サーバーに現バージョンを問い合わせ
// 2. 新バージョンがあればダウンロード
// 3. OTAパーティションに書き込み
// 4. ブートパーティションを切り替え
// 5. 再起動

use log::*;

const OTA_URL: &str = "https://api.chatweb.ai/api/v1/device/firmware";
const CURRENT_VERSION: &str = env!("CARGO_PKG_VERSION");

pub fn check_and_update(device_id: &str) -> Result<bool, Box<dyn std::error::Error>> {
    info!("OTA check (v{})", CURRENT_VERSION);

    // バージョンチェック
    let check_url = format!("{}?device_id={}&version={}", OTA_URL, device_id, CURRENT_VERSION);

    let config = esp_idf_svc::http::client::Configuration {
        buffer_size: Some(4096),
        timeout: Some(std::time::Duration::from_secs(30)),
        ..Default::default()
    };

    let mut client = esp_idf_svc::http::client::EspHttpConnection::new(&config)?;
    let headers = [("X-Device-Id", device_id)];

    client.initiate_request(
        esp_idf_svc::http::Method::Get,
        &check_url,
        &headers,
    )?;
    client.initiate_response()?;

    let status = client.status();
    if status == 204 {
        info!("OTA: up to date");
        return Ok(false);
    }
    if status != 200 {
        return Err(format!("OTA check: HTTP {}", status).into());
    }

    // ファームウェアダウンロード + OTA書き込み
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

        // ストリーミング書き込み
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
        if ret != 0 {
            return Err(format!("OTA end: {}", ret).into());
        }

        let ret = esp_idf_sys::esp_ota_set_boot_partition(update_partition);
        if ret != 0 {
            return Err(format!("OTA set boot: {}", ret).into());
        }

        info!("OTA: success, restarting...");
        std::thread::sleep(std::time::Duration::from_secs(1));
        esp_idf_sys::esp_restart();
    }
}
