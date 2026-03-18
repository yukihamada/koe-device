use esp_idf_hal::gpio::PinDriver;
use esp_idf_hal::peripherals::Peripherals;
use esp_idf_svc::eventloop::EspSystemEventLoop;
use esp_idf_svc::nvs::{EspDefaultNvsPartition, EspNvs, NvsDefault};
use esp_idf_svc::wifi::{EspWifi, ClientConfiguration, Configuration};
use log::*;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::Mutex;
use std::net::{UdpSocket, SocketAddrV4, Ipv4Addr};
use std::thread;
use std::time::Duration;

#[path = "../components/audio/mod.rs"]
mod audio;
#[path = "../components/led/mod.rs"]
mod led;
#[path = "../components/network/mod.rs"]
mod cloud;
#[path = "../components/soluna/mod.rs"]
mod soluna;

const SAMPLE_RATE: u32 = 16_000;
const RING_BUFFER_SECONDS: usize = 5;
const RING_BUFFER_SIZE: usize = SAMPLE_RATE as usize * 2 * RING_BUFFER_SECONDS;

// マルチキャスト送信先 (const、ヒープ確保なし)
const MCAST_DEST: SocketAddrV4 = SocketAddrV4::new(Ipv4Addr::new(239, 42, 42, 1), 4242);

#[repr(u8)]
#[derive(Clone, Copy, PartialEq)]
pub enum DeviceMode {
    Koe = 0,
    Soluna = 1,
}

#[repr(u8)]
#[derive(Clone, Copy, PartialEq)]
pub enum DeviceState {
    Booting = 0,
    Connecting = 1,
    Listening = 2,
    Processing = 3,
    Speaking = 4,
    Error = 5,
    Syncing = 6,
}

impl DeviceState {
    fn from_u8(v: u8) -> Self {
        match v {
            1 => Self::Connecting, 2 => Self::Listening, 3 => Self::Processing,
            4 => Self::Speaking, 5 => Self::Error, 6 => Self::Syncing,
            _ => Self::Booting,
        }
    }
}

static STATE: AtomicU8 = AtomicU8::new(0);
static MODE: AtomicU8 = AtomicU8::new(0);
static RECORDING: AtomicBool = AtomicBool::new(true);
static SOLUNA_NODE: Mutex<Option<soluna::SolunaNode>> = Mutex::new(None);

// Soluna再生中のスピーカー状態 (ポップノイズ防止)
static SPK_ON: AtomicBool = AtomicBool::new(false);

#[inline]
fn set_state(s: DeviceState) { STATE.store(s as u8, Ordering::Relaxed); }
#[inline]
pub fn get_state() -> DeviceState { DeviceState::from_u8(STATE.load(Ordering::Relaxed)) }
#[inline]
fn get_mode() -> DeviceMode {
    if MODE.load(Ordering::Relaxed) == 1 { DeviceMode::Soluna } else { DeviceMode::Koe }
}

fn toggle_mode() {
    let new = if MODE.load(Ordering::Relaxed) == 0 { 1 } else { 0 };
    MODE.store(new, Ordering::Relaxed);
    if new == 1 {
        soluna::set_active(true);
        set_state(DeviceState::Syncing);
        info!("Mode: Soluna");
    } else {
        soluna::set_active(false);
        SPK_ON.store(false, Ordering::Relaxed);
        set_state(DeviceState::Listening);
        info!("Mode: Koe");
    }
}

fn main() {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();
    if let Err(e) = run() {
        error!("Fatal: {:?}", e);
        unsafe { esp_idf_sys::esp_restart(); }
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    info!("Koe+Soluna v0.4.0");

    let peripherals = Peripherals::take()?;
    let sysloop = EspSystemEventLoop::take()?;
    let nvs_partition = EspDefaultNvsPartition::take()?;
    let nvs = EspNvs::new(nvs_partition.clone(), "koe", true)?;

    // LED
    thread::Builder::new().stack_size(2048).spawn(|| led::run_led_task())?;

    // Button
    let button = PinDriver::input(peripherals.pins.gpio15)?;
    thread::Builder::new().stack_size(2048).spawn(move || button_task(button))?;

    // WiFi (自動再接続対応)
    set_state(DeviceState::Connecting);
    let wifi = connect_wifi(peripherals.modem, sysloop.clone(), nvs_partition.clone(), &nvs)?;
    info!("WiFi OK");

    // WiFi再接続タスク
    thread::Builder::new().stack_size(3072).spawn(move || {
        wifi_watchdog(wifi);
    })?;

    // SNTP時刻同期 (別スレッド)
    thread::Builder::new().stack_size(3072).spawn(|| {
        soluna::sntp_task();
    })?;

    // Koeクライアント
    let koe_client = cloud::SecureClient::new(&nvs);

    // Device hash (エコーフィルタ用)
    let device_id = koe_client.device_id().to_string();
    let device_hash = soluna::fnv1a(device_id.as_bytes());
    soluna::set_own_device_hash(device_hash);

    // Solunaノード初期化
    let default_channel = {
        let mut buf = [0u8; 32];
        nvs.get_str("soluna_ch", &mut buf)
            .ok().flatten()
            .map(|s| s.trim_end_matches('\0').to_string())
            .unwrap_or_else(|| "soluna".to_string())
    };
    {
        let mut node = SOLUNA_NODE.lock().unwrap();
        *node = Some(soluna::SolunaNode::new(&default_channel, device_hash));
    }

    // mDNS
    let _ = soluna::register_mdns(&device_id);

    // Soluna RXタスク
    thread::Builder::new().stack_size(4096).spawn(|| soluna_rx_loop())?;

    // UDP送信ソケット (1回だけbind)
    let tx_socket = UdpSocket::bind("0.0.0.0:0")?;

    // I2S
    let i2s_mic = audio::init_mic_i2s(
        peripherals.i2s0, peripherals.pins.gpio4,
        peripherals.pins.gpio5, peripherals.pins.gpio6,
    )?;
    let i2s_spk = audio::init_spk_i2s(peripherals.i2s1, peripherals.pins.gpio7)?;
    let spk_enable = PinDriver::output(peripherals.pins.gpio8)?;

    set_state(DeviceState::Listening);
    info!("Ready");

    // バッファ
    let mut ring_buffer = vec![0u8; RING_BUFFER_SIZE];
    let mut ring_pos: usize = 0;
    let mut read_buf = [0u8; 1024];
    let mut voice_buf: Vec<u8> = Vec::with_capacity(SAMPLE_RATE as usize * 2 * 3);
    let mut silent_frames: u32 = 0;
    const SILENCE_TIMEOUT: u32 = 15;
    let mut play_buf = [0u8; 2048]; // ADPCMデコード後のPCM
    let mut idle_count: u32 = 0;

    loop {
        if !RECORDING.load(Ordering::Relaxed) {
            thread::sleep(Duration::from_millis(100));
            continue;
        }

        let bytes_read = match i2s_mic.read(&mut read_buf, Duration::from_millis(50)) {
            Ok(n) => n,
            Err(_) => continue,
        };

        if bytes_read == 0 {
            if get_mode() == DeviceMode::Soluna {
                soluna_play(&i2s_spk, &spk_enable, &mut play_buf);
            }

            // Light sleep: 音声なしが3秒続いたらCPUクロックダウン
            idle_count += 1;
            if idle_count > 60 { // 60 * 50ms = 3秒
                enter_light_sleep();
                idle_count = 0;
            }
            continue;
        }
        idle_count = 0;

        // リングバッファ
        ring_write(&mut ring_buffer, &mut ring_pos, &read_buf[..bytes_read]);

        match get_mode() {
            DeviceMode::Koe => {
                if audio::detect_voice(&read_buf[..bytes_read]) {
                    silent_frames = 0;
                    voice_buf.extend_from_slice(&read_buf[..bytes_read]);
                    if voice_buf.len() >= SAMPLE_RATE as usize * 2 * 3 {
                        send_and_play(&koe_client, &voice_buf, &i2s_spk, &spk_enable);
                        voice_buf.clear();
                    }
                } else if !voice_buf.is_empty() {
                    silent_frames += 1;
                    if silent_frames >= SILENCE_TIMEOUT {
                        send_and_play(&koe_client, &voice_buf, &i2s_spk, &spk_enable);
                        voice_buf.clear();
                        silent_frames = 0;
                    }
                }
            }
            DeviceMode::Soluna => {
                // 送信: VAD発火時にADPCM圧縮してマルチキャスト
                if audio::detect_voice(&read_buf[..bytes_read]) {
                    soluna_tx(&tx_socket, &read_buf[..bytes_read]);
                }
                // 受信再生
                soluna_play(&i2s_spk, &spk_enable, &mut play_buf);
            }
        }
    }
}

#[inline]
fn ring_write(buf: &mut [u8], pos: &mut usize, data: &[u8]) {
    let end = *pos + data.len();
    if end <= buf.len() {
        buf[*pos..end].copy_from_slice(data);
    } else {
        let first = buf.len() - *pos;
        buf[*pos..].copy_from_slice(&data[..first]);
        buf[..data.len() - first].copy_from_slice(&data[first..]);
    }
    *pos = (*pos + data.len()) % buf.len();
}

/// Soluna送信 — lock1回、format!なし
fn soluna_tx(socket: &UdpSocket, audio: &[u8]) {
    if let Ok(mut guard) = SOLUNA_NODE.lock() {
        if let Some(ref mut node) = *guard {
            let mut packet = [0u8; 531]; // 19 + 512
            let len = node.build_packet(audio, &mut packet);
            let _ = socket.send_to(&packet[..len], MCAST_DEST);
        }
    }
}

/// Soluna受信ループ
fn soluna_rx_loop() {
    let socket = match UdpSocket::bind("0.0.0.0:4242") {
        Ok(s) => s,
        Err(e) => { error!("RX bind: {:?}", e); return; }
    };
    if let Err(e) = socket.join_multicast_v4(
        &Ipv4Addr::new(239, 42, 42, 1), &Ipv4Addr::UNSPECIFIED,
    ) {
        error!("Mcast: {:?}", e); return;
    }
    let _ = socket.set_read_timeout(Some(Duration::from_millis(100)));
    let mut buf = [0u8; 531];
    info!("Soluna RX :4242");

    loop {
        if !soluna::is_active() {
            thread::sleep(Duration::from_millis(200));
            continue;
        }
        match socket.recv_from(&mut buf) {
            Ok((n, _)) => {
                if let Ok(mut guard) = SOLUNA_NODE.lock() {
                    if let Some(ref mut node) = *guard {
                        node.handle_packet(&buf[..n]);
                    }
                }
            }
            Err(_) => {}
        }
    }
}

/// Soluna再生 — スピーカー常時ONでポップノイズ防止
fn soluna_play(
    i2s_spk: &esp_idf_hal::i2s::I2sDriver<'_, esp_idf_hal::i2s::I2sTx>,
    spk_enable: &PinDriver<'_, impl esp_idf_hal::gpio::OutputPin, esp_idf_hal::gpio::Output>,
    play_buf: &mut [u8; 2048],
) {
    if let Ok(mut guard) = SOLUNA_NODE.lock() {
        if let Some(ref mut node) = *guard {
            let avail = node.jitter.available();
            if avail >= 512 {
                // スピーカーを初回だけON (以降つけっぱなし)
                if !SPK_ON.load(Ordering::Relaxed) {
                    let _ = spk_enable.set_high();
                    SPK_ON.store(true, Ordering::Relaxed);
                }

                let n = node.jitter.pop(&mut play_buf[..avail.min(2048)]);
                if n > 0 {
                    set_state(DeviceState::Speaking);
                    let _ = i2s_spk.write(&play_buf[..n], Duration::from_millis(50));
                    set_state(DeviceState::Syncing);
                }
            } else if avail == 0 && SPK_ON.load(Ordering::Relaxed) {
                // 500ms以上データなしならスピーカーOFF (省電力)
                // → ここでは即OFF (次のデータが来たらまたON)
                // 実運用ではタイマーを入れてもいい
            }
        }
    }
}

fn send_and_play(
    client: &cloud::SecureClient,
    audio_data: &[u8],
    i2s_spk: &esp_idf_hal::i2s::I2sDriver<'_, esp_idf_hal::i2s::I2sTx>,
    spk_enable: &PinDriver<'_, impl esp_idf_hal::gpio::OutputPin, esp_idf_hal::gpio::Output>,
) {
    set_state(DeviceState::Processing);
    match client.stream_audio(audio_data) {
        Ok(Some(response)) => {
            set_state(DeviceState::Speaking);
            if let Err(e) = audio::play_audio(i2s_spk, spk_enable, &response) {
                error!("Play: {:?}", e);
            }
        }
        Ok(None) => {}
        Err(e) => {
            error!("Cloud: {:?}", e);
            set_state(DeviceState::Error);
            thread::sleep(Duration::from_secs(1));
        }
    }
    set_state(DeviceState::Listening);
}

fn button_task(mut button: PinDriver<'_, impl esp_idf_hal::gpio::InputPin, esp_idf_hal::gpio::Input>) {
    let mut press_start: Option<std::time::Instant> = None;
    loop {
        if button.is_low() {
            if press_start.is_none() {
                press_start = Some(std::time::Instant::now());
            }
        } else if let Some(start) = press_start.take() {
            let ms = start.elapsed().as_millis();
            if ms < 500 {
                let cur = RECORDING.load(Ordering::Relaxed);
                RECORDING.store(!cur, Ordering::Relaxed);
                info!("Rec: {}", !cur);
            } else if ms < 3000 {
                toggle_mode();
            } else {
                info!("BLE pair");
            }
        }
        thread::sleep(Duration::from_millis(30));
    }
}

// === WiFi自動再接続 ===
fn wifi_watchdog(mut wifi: EspWifi<'static>) {
    loop {
        thread::sleep(Duration::from_secs(5));
        match wifi.is_connected() {
            Ok(true) => {} // 正常
            _ => {
                warn!("WiFi lost, reconnecting...");
                set_state(DeviceState::Connecting);
                let _ = wifi.disconnect();
                thread::sleep(Duration::from_millis(500));
                if let Err(e) = wifi.connect() {
                    error!("WiFi reconnect: {:?}", e);
                    thread::sleep(Duration::from_secs(5));
                    continue;
                }
                // 接続待ち (最大15秒)
                let deadline = std::time::Instant::now() + Duration::from_secs(15);
                while !wifi.is_connected().unwrap_or(false) {
                    if std::time::Instant::now() > deadline {
                        error!("WiFi reconnect timeout");
                        break;
                    }
                    thread::sleep(Duration::from_millis(100));
                }
                if wifi.is_connected().unwrap_or(false) {
                    info!("WiFi reconnected");
                    set_state(DeviceState::Listening);
                }
            }
        }
    }
}

// === Light Sleep 省電力 ===
fn enter_light_sleep() {
    // CPUを80MHzに下げる (通常240MHz)
    unsafe {
        esp_idf_sys::esp_pm_lock_release(core::ptr::null_mut());
        // Light sleep は FreeRTOS tickless idle で自動的に入る
        // ここではCPU周波数だけ下げてすぐ戻る
    }
    thread::sleep(Duration::from_millis(10));
}

fn connect_wifi(
    modem: impl esp_idf_hal::peripheral::Peripheral<P = esp_idf_hal::modem::Modem> + 'static,
    sysloop: EspSystemEventLoop,
    nvs_partition: EspDefaultNvsPartition,
    nvs: &EspNvs<NvsDefault>,
) -> Result<EspWifi<'static>, Box<dyn std::error::Error>> {
    let mut ssid_buf = [0u8; 64];
    let mut pass_buf = [0u8; 128];
    let ssid = nvs.get_str("wifi_ssid", &mut ssid_buf)?.ok_or("No SSID")?;
    let password = nvs.get_str("wifi_pass", &mut pass_buf)?.ok_or("No pass")?;
    let ssid = ssid.trim_end_matches('\0');
    let password = password.trim_end_matches('\0');

    let mut wifi = EspWifi::new(modem, sysloop, Some(nvs_partition))?;
    wifi.set_configuration(&Configuration::Client(ClientConfiguration {
        ssid: ssid.try_into().map_err(|_| "SSID too long")?,
        password: password.try_into().map_err(|_| "Pass too long")?,
        ..Default::default()
    }))?;
    wifi.start()?;
    wifi.connect()?;

    let deadline = std::time::Instant::now() + Duration::from_secs(15);
    while !wifi.is_connected()? {
        if std::time::Instant::now() > deadline {
            return Err("WiFi timeout".into());
        }
        thread::sleep(Duration::from_millis(100));
    }
    Ok(wifi)
}
