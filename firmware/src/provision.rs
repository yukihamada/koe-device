// WiFi provisioning - NVSに書き込んで再起動
use esp_idf_svc::nvs::{EspDefaultNvsPartition, EspNvs};

/// BLE経由で受信したSSID/パスワードをNVSに書き込んで再起動
pub fn write_wifi_config_to_nvs(nvs_partition: &EspDefaultNvsPartition, ssid: &str, password: &str) {
    let mut nvs = EspNvs::new(nvs_partition.clone(), "koe", true).unwrap();

    nvs.set_str("wifi_ssid", ssid).unwrap();
    nvs.set_str("wifi_pass", password).unwrap();

    println!("WiFi config written to NVS");
    println!("  SSID: {}", ssid);
    println!("  Restarting...");

    std::thread::sleep(std::time::Duration::from_secs(1));
    unsafe { esp_idf_sys::esp_restart(); }
}
