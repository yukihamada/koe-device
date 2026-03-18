use esp_idf_svc::http::client::{Configuration, EspHttpConnection};
use esp_idf_svc::nvs::{EspNvs, NvsDefault};
use log::*;

const API_ENDPOINT: &str = "https://api.chatweb.ai/api/v1/device/audio";

// Device ID: NVSから読み込み、なければ生成して保存
fn get_device_id(nvs: &mut EspNvs<NvsDefault>) -> String {
    let mut buf = [0u8; 64];
    if let Ok(Some(id)) = nvs.get_str("device_id", &mut buf) {
        return id.trim_end_matches('\0').to_string();
    }
    // 初回起動: ランダムID生成 (ESP32 HW RNG使用)
    let mut id_bytes = [0u8; 16];
    unsafe {
        for b in id_bytes.iter_mut() {
            *b = esp_idf_sys::esp_random() as u8;
        }
    }
    let id = format!("koe-{}", hex_encode(&id_bytes[..8]));
    let _ = nvs.set_str("device_id", &id);
    info!("New device: {}", id);
    id
}

// API Key: NVSから読み込み (ペアリング時に設定)
fn get_api_key(nvs: &EspNvs<NvsDefault>) -> Option<String> {
    let mut buf = [0u8; 128];
    nvs.get_str("api_key", &mut buf)
        .ok()
        .flatten()
        .map(|s| s.trim_end_matches('\0').to_string())
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

// HMAC-SHA256でリクエスト署名 (mbedTLSのHMAC使用)
fn sign_request(api_key: &str, device_id: &str, timestamp: u64, body_len: usize) -> String {
    // 署名対象: "POST\n/api/v1/device/audio\n{timestamp}\n{body_len}\n{device_id}"
    let message = format!(
        "POST\n/api/v1/device/audio\n{}\n{}\n{}",
        timestamp, body_len, device_id
    );
    // ESP32 mbedTLS HMAC-SHA256
    let mut output = [0u8; 32];
    unsafe {
        let mut ctx: esp_idf_sys::mbedtls_md_context_t = core::mem::zeroed();
        esp_idf_sys::mbedtls_md_init(&mut ctx);
        let md_info = esp_idf_sys::mbedtls_md_info_from_type(
            esp_idf_sys::mbedtls_md_type_t_MBEDTLS_MD_SHA256,
        );
        esp_idf_sys::mbedtls_md_setup(&mut ctx, md_info, 1); // 1 = HMAC
        esp_idf_sys::mbedtls_md_hmac_starts(
            &mut ctx,
            api_key.as_ptr(),
            api_key.len(),
        );
        esp_idf_sys::mbedtls_md_hmac_update(
            &mut ctx,
            message.as_ptr(),
            message.len(),
        );
        esp_idf_sys::mbedtls_md_hmac_finish(&mut ctx, output.as_mut_ptr());
        esp_idf_sys::mbedtls_md_free(&mut ctx);
    }
    hex_encode(&output)
}

pub struct SecureClient {
    device_id: String,
    api_key: Option<String>,
}

impl SecureClient {
    pub fn new(nvs: &mut EspNvs<NvsDefault>) -> Self {
        Self {
            device_id: get_device_id(nvs),
            api_key: get_api_key(nvs),
        }
    }

    pub fn device_id(&self) -> &str {
        &self.device_id
    }

    pub fn stream_audio(&self, audio_chunk: &[u8]) -> Result<Option<Vec<u8>>, Box<dyn std::error::Error>> {
        let api_key = match &self.api_key {
            Some(k) => k,
            None => {
                warn!("No API key — skipping upload");
                return Ok(None);
            }
        };

        let config = Configuration {
            buffer_size: Some(4096),
            timeout: Some(std::time::Duration::from_secs(10)),
            // ESP-IDF EspHttpConnection はデフォルトでTLS証明書検証する
            // (CONFIG_MBEDTLS_CERTIFICATE_BUNDLEが有効な場合)
            ..Default::default()
        };

        let mut client = EspHttpConnection::new(&config)?;

        // タイムスタンプ (リプレイ攻撃防止)
        let timestamp = unsafe { esp_idf_sys::esp_timer_get_time() as u64 / 1_000_000 };

        // HMAC署名
        let signature = sign_request(api_key, &self.device_id, timestamp, audio_chunk.len());

        // タイムスタンプとシグネチャをStringで保持
        let ts_str = format!("{}", timestamp);

        let headers = [
            ("Content-Type", "application/octet-stream"),
            ("X-Device-Id", &self.device_id),
            ("X-Timestamp", &ts_str),
            ("X-Signature", &signature),
            ("X-Sample-Rate", "16000"),
            ("X-Encoding", "pcm-s16le"),
        ];

        client.initiate_request(
            esp_idf_svc::http::Method::Post,
            API_ENDPOINT,
            &headers,
        )?;

        client.write(audio_chunk)?;
        client.initiate_response()?;

        match client.status() {
            200 => {
                let mut response_data = Vec::new();
                let mut buf = [0u8; 1024];
                loop {
                    let n = client.read(&mut buf)?;
                    if n == 0 { break; }
                    response_data.extend_from_slice(&buf[..n]);
                }
                if response_data.is_empty() {
                    Ok(None)
                } else {
                    Ok(Some(response_data))
                }
            }
            202 => Ok(None),
            401 => {
                error!("Auth failed — check API key");
                Ok(None)
            }
            s => {
                warn!("API {}", s);
                Ok(None)
            }
        }
    }
}
