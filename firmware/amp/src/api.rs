/// api.rs — HTTP client for koe.live API
///
/// Endpoints used by the firmware:
///   POST /api/v1/device/heartbeat        — keep-alive every 5 s
///   POST /api/v1/sessions                — create a new session → returns session_id
///   POST /api/v1/sessions/:id/start      — mark session as started
///   POST /api/v1/sessions/:id/end        — mark session as ended
///
/// All requests send a JSON body with `device_id` so the server can identify
/// the device without requiring a separate Bearer token on the device.

use anyhow::{anyhow, Result};
use esp_idf_svc::http::client::{Configuration as HttpConfig, EspHttpConnection};
use embedded_svc::http::client::Client as HttpClient;
use embedded_svc::http::Method;

const BASE_URL: &str = "https://koe.live";

/// Thin HTTP client wrapper.  Constructed fresh for each request because
/// EspHttpConnection does not implement `Clone` and keeping it open is
/// tricky with the esp-idf TLS stack.
fn make_client() -> Result<HttpClient<EspHttpConnection>> {
    let cfg = HttpConfig {
        use_global_ca_store: true,
        crt_bundle_attach: Some(esp_idf_svc::sys::esp_crt_bundle_attach),
        ..Default::default()
    };
    let conn = EspHttpConnection::new(&cfg)?;
    Ok(HttpClient::wrap(conn))
}

/// Low-level helper: send a POST request with a JSON body and return the
/// HTTP status code together with up to 4 KiB of the response body.
fn post_json(url: &str, body: &str) -> Result<(u16, heapless::String<4096>)> {
    let mut client = make_client()?;
    let body_bytes = body.as_bytes();
    let headers = [
        ("Content-Type", "application/json"),
        ("Accept", "application/json"),
    ];
    let mut request = client.request(Method::Post, url, &headers)?;
    request.write(body_bytes)?;
    let mut response = request.submit()?;

    let status = response.status();
    let mut resp_buf = heapless::String::<4096>::new();

    // Read response body (best-effort, cap at buffer size)
    let mut tmp = [0u8; 256];
    use embedded_svc::io::Read as IoRead;
    loop {
        match response.read(&mut tmp) {
            Ok(0) => break,
            Ok(n) => {
                let chunk = core::str::from_utf8(&tmp[..n]).unwrap_or("");
                let _ = resp_buf.push_str(chunk);
            }
            Err(_) => break,
        }
    }

    Ok((status, resp_buf))
}

/// POST /api/v1/device/heartbeat
///
/// Body: `{"device_id":"<id>","firmware_version":"<ver>"}`
/// Expected: 200 OK `{"ok":true}`
pub fn send_heartbeat(device_id: &str, firmware_version: &str) -> Result<()> {
    let url = format!("{}/api/v1/device/heartbeat", BASE_URL);
    let body = format!(
        r#"{{"device_id":"{device_id}","firmware_version":"{firmware_version}"}}"#
    );
    let (status, resp) = post_json(&url, &body)?;
    if status == 200 || status == 204 {
        log::info!("[api] heartbeat ok ({})", status);
        Ok(())
    } else {
        log::warn!("[api] heartbeat failed status={} body={}", status, resp.as_str());
        Err(anyhow!("heartbeat HTTP {}", status))
    }
}

/// POST /api/v1/sessions
///
/// Body: `{"device_id":"<id>"}`
/// Expected: 200/201 `{"session_id":"<uuid>"}`
/// Returns the new session_id string.
pub fn create_session(device_id: &str) -> Result<heapless::String<64>> {
    let url = format!("{}/api/v1/sessions", BASE_URL);
    let body = format!(r#"{{"device_id":"{device_id}"}}"#);
    let (status, resp) = post_json(&url, &body)?;
    if status == 200 || status == 201 {
        // Parse session_id from JSON: look for "session_id":"<value>"
        let id = extract_json_str(resp.as_str(), "session_id")
            .ok_or_else(|| anyhow!("no session_id in response: {}", resp.as_str()))?;
        log::info!("[api] session created id={}", id.as_str());
        Ok(id)
    } else {
        log::warn!("[api] create_session failed status={} body={}", status, resp.as_str());
        Err(anyhow!("create_session HTTP {}", status))
    }
}

/// POST /api/v1/sessions/:id/start
///
/// Body: `{"device_id":"<id>","timestamp_ms":<ms>}`
pub fn start_session(device_id: &str, session_id: &str, timestamp_ms: u64) -> Result<()> {
    let url = format!("{}/api/v1/sessions/{}/start", BASE_URL, session_id);
    let body = format!(
        r#"{{"device_id":"{device_id}","timestamp_ms":{timestamp_ms}}}"#
    );
    let (status, resp) = post_json(&url, &body)?;
    if status == 200 || status == 204 {
        log::info!("[api] session {} started", session_id);
        Ok(())
    } else {
        log::warn!("[api] start_session failed status={} body={}", status, resp.as_str());
        Err(anyhow!("start_session HTTP {}", status))
    }
}

/// POST /api/v1/sessions/:id/end
///
/// Body: `{"device_id":"<id>","timestamp_ms":<ms>}`
pub fn end_session(device_id: &str, session_id: &str, timestamp_ms: u64) -> Result<()> {
    let url = format!("{}/api/v1/sessions/{}/end", BASE_URL, session_id);
    let body = format!(
        r#"{{"device_id":"{device_id}","timestamp_ms":{timestamp_ms}}}"#
    );
    let (status, resp) = post_json(&url, &body)?;
    if status == 200 || status == 204 {
        log::info!("[api] session {} ended", session_id);
        Ok(())
    } else {
        log::warn!("[api] end_session failed status={} body={}", status, resp.as_str());
        Err(anyhow!("end_session HTTP {}", status))
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Minimal JSON string-field extractor — avoids pulling in serde_json on the
/// device just for simple key extraction.  Looks for `"key":"value"` patterns.
fn extract_json_str(json: &str, key: &str) -> Option<heapless::String<64>> {
    let needle = format!(r#""{key}":""#);
    let start = json.find(needle.as_str())? + needle.len();
    let rest = &json[start..];
    let end = rest.find('"')?;
    let mut out = heapless::String::<64>::new();
    out.push_str(&rest[..end]).ok()?;
    Some(out)
}
