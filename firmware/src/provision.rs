// WiFi provisioning - NVSに書き込んで再起動
use esp_idf_svc::nvs::{EspDefaultNvsPartition, EspNvs};

pub fn write_wifi_config() {
    let nvs_partition = EspDefaultNvsPartition::take().unwrap();
    let mut nvs = EspNvs::new(nvs_partition, "koe", true).unwrap();

    nvs.set_str("wifi_ssid", "Hama-Fi-IoT").unwrap();
    nvs.set_str("wifi_pass", "sushiramen").unwrap();

    println!("WiFi config written to NVS");
    println!("  SSID: Hama-Fi-IoT");
    println!("  Restarting...");

    std::thread::sleep(std::time::Duration::from_secs(1));
    unsafe { esp_idf_sys::esp_restart(); }
}
