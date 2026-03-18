fn main() {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();
    log::info!("Koe+Soluna v0.6.0 - minimal boot test");
    loop {
        std::thread::sleep(std::time::Duration::from_secs(1));
    }
}
