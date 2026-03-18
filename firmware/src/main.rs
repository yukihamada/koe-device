use esp_idf_hal::gpio::PinDriver;
use esp_idf_hal::peripherals::Peripherals;
use esp_idf_svc::eventloop::EspSystemEventLoop;
use esp_idf_svc::nvs::{EspDefaultNvsPartition, EspNvs, NvsDefault};
use esp_idf_svc::wifi::{EspWifi, ClientConfiguration, Configuration};
use log::*;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

mod audio;
mod led;
mod cloud;
mod soluna;

const SAMPLE_RATE: u32 = 16_000;
const RING_BUFFER_SECONDS: usize = 5;
const RING_BUFFER_SIZE: usize = SAMPLE_RATE as usize * 2 * RING_BUFFER_SECONDS;

// === デバイスモード ===
// Koe: 音声入力 → クラウドへ送信 → 応答再生
// Soluna: チャンネル参加 → マイク音声を全デバイスに配信＋受信再生
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
    Listening = 2,   // Koe: マイク待機 / Soluna: チャンネル待機
    Processing = 3,  // Koe: クラウド送信中
    Speaking = 4,    // 再生中
    Error = 5,
    Syncing = 6,     // Soluna: ピア同期中
}

impl DeviceState {
    fn from_u8(v: u8) -> Self {
        match v {
            1 => Self::Connecting,
            2 => Self::Listening,
            3 => Self::Processing,
            4 => Self::Speaking,
            5 => Self::Error,
            6 => Self::Syncing,
            _ => Self::Booting,
        }
    }
}

static STATE: AtomicU8 = AtomicU8::new(0);
static MODE: AtomicU8 = AtomicU8::new(0); // 0=Koe, 1=Soluna
static RECORDING: AtomicBool = AtomicBool::new(true);

// Solunaノード — staticで rx_task からアクセス可能に
static SOLUNA_NODE: Mutex<Option<soluna::SolunaNode>> = Mutex::new(None);

#[inline]
fn set_state(s: DeviceState) {
    STATE.store(s as u8, Ordering::Relaxed);
}

#[inline]
pub fn get_state() -> DeviceState {
    DeviceState::from_u8(STATE.load(Ordering::Relaxed))
}

#[inline]
fn get_mode() -> DeviceMode {
    if MODE.load(Ordering::Relaxed) == 1 { DeviceMode::Soluna } else { DeviceMode::Koe }
}

fn toggle_mode() {
    let cur = MODE.load(Ordering::Relaxed);
    let new = if cur == 0 { 1 } else { 0 };
    MODE.store(new, Ordering::Relaxed);

    if new == 1 {
        soluna::set_active(true);
        set_state(DeviceState::Syncing);
        info!("Mode: Soluna");
    } else {
        soluna::set_active(false);
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
    info!("Koe+Soluna v0.3.0");

    let peripherals = Peripherals::take()?;
    let sysloop = EspSystemEventLoop::take()?;
    let nvs_partition = EspDefaultNvsPartition::take()?;
    let nvs = EspNvs::new(nvs_partition.clone(), "koe", true)?;

    // LED
    thread::Builder::new().stack_size(2048).spawn(|| {
        led::run_led_task();
    })?;

    // Button
    let button = PinDriver::input(peripherals.pins.gpio15)?;
    thread::Builder::new().stack_size(2048).spawn(move || {
        button_task(button);
    })?;

    // WiFi
    set_state(DeviceState::Connecting);
    let _wifi = connect_wifi(peripherals.modem, sysloop, nvs_partition, &nvs)?;
    info!("WiFi OK");

    // Koe クラウドクライアント
    let koe_client = cloud::SecureClient::new(&nvs);

    // Soluna ノード初期化
    let default_channel = {
        let mut buf = [0u8; 32];
        nvs.get_str("soluna_ch", &mut buf)
            .ok()
            .flatten()
            .map(|s| s.trim_end_matches('\0').to_string())
            .unwrap_or_else(|| "soluna".to_string())
    };

    {
        let mut node = SOLUNA_NODE.lock().unwrap();
        *node = Some(soluna::SolunaNode::new(&default_channel));
    }

    // mDNS登録
    let device_id = koe_client.device_id();
    let _ = soluna::register_mdns(device_id);

    // Soluna RX タスク (UDPマルチキャスト受信)
    thread::Builder::new().stack_size(4096).spawn(|| {
        soluna_rx_loop();
    })?;

    // UDP送信ソケット
    let tx_socket = std::net::UdpSocket::bind("0.0.0.0:0")?;

    // I2S
    let i2s_mic = audio::init_mic_i2s(
        peripherals.i2s0,
        peripherals.pins.gpio4,
        peripherals.pins.gpio5,
        peripherals.pins.gpio6,
    )?;

    let i2s_spk = audio::init_spk_i2s(
        peripherals.i2s1,
        peripherals.pins.gpio7,
    )?;
    let spk_enable = PinDriver::output(peripherals.pins.gpio8)?;

    set_state(DeviceState::Listening);
    info!("Ready (short=rec, medium=mode, long=pair)");

    // バッファ
    let mut ring_buffer = vec![0u8; RING_BUFFER_SIZE];
    let mut ring_pos: usize = 0;
    let mut read_buf = [0u8; 1024];

    // Koe用
    let mut voice_buf: Vec<u8> = Vec::with_capacity(SAMPLE_RATE as usize * 2 * 3);
    let mut silent_frames: u32 = 0;
    const SILENCE_TIMEOUT: u32 = 15;

    // Soluna再生バッファ
    let mut play_buf = [0u8; 1024];

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
            // Solunaモードなら受信バッファから再生
            if get_mode() == DeviceMode::Soluna {
                play_soluna_jitter(&i2s_spk, &spk_enable, &mut play_buf);
            }
            continue;
        }

        // リングバッファ
        let end = ring_pos + bytes_read;
        if end <= RING_BUFFER_SIZE {
            ring_buffer[ring_pos..end].copy_from_slice(&read_buf[..bytes_read]);
        } else {
            let first = RING_BUFFER_SIZE - ring_pos;
            ring_buffer[ring_pos..].copy_from_slice(&read_buf[..first]);
            ring_buffer[..bytes_read - first].copy_from_slice(&read_buf[first..bytes_read]);
        }
        ring_pos = (ring_pos + bytes_read) % RING_BUFFER_SIZE;

        match get_mode() {
            DeviceMode::Koe => {
                // === Koeモード: VAD → クラウド送信 ===
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
                // === Solunaモード: マイク音声をマルチキャスト送信 + 受信再生 ===

                // 送信: マイク音声をUDPマルチキャスト
                if audio::detect_voice(&read_buf[..bytes_read]) {
                    if let Ok(node) = SOLUNA_NODE.lock() {
                        if let Some(ref _n) = *node {
                            drop(node);
                            soluna_tx(&tx_socket, &read_buf[..bytes_read]);
                        }
                    }
                }

                // 受信バッファから再生
                play_soluna_jitter(&i2s_spk, &spk_enable, &mut play_buf);
            }
        }
    }
}

fn soluna_tx(socket: &std::net::UdpSocket, audio: &[u8]) {
    if let Ok(mut node_opt) = SOLUNA_NODE.lock() {
        if let Some(ref mut node) = *node_opt {
            let mut packet = [0u8; 1038]; // HEADER + MAX_AUDIO
            let len = node.build_packet(audio, &mut packet);
            let dest = format!("239.42.42.1:{}", 4242);
            let _ = socket.send_to(&packet[..len], &dest);
        }
    }
}

fn soluna_rx_loop() {
    use std::net::UdpSocket;

    let socket = match UdpSocket::bind("0.0.0.0:4242") {
        Ok(s) => s,
        Err(e) => {
            error!("Soluna RX bind: {:?}", e);
            return;
        }
    };

    if let Err(e) = socket.join_multicast_v4(
        &"239.42.42.1".parse().unwrap(),
        &std::net::Ipv4Addr::UNSPECIFIED,
    ) {
        error!("Multicast: {:?}", e);
        return;
    }

    let _ = socket.set_read_timeout(Some(Duration::from_millis(100)));

    let mut buf = [0u8; 1038];
    info!("Soluna RX ready :4242");

    loop {
        if !soluna::is_active() {
            thread::sleep(Duration::from_millis(200));
            continue;
        }

        match socket.recv_from(&mut buf) {
            Ok((n, _)) => {
                if let Ok(mut node_opt) = SOLUNA_NODE.lock() {
                    if let Some(ref mut node) = *node_opt {
                        node.handle_packet(&buf[..n]);
                    }
                }
            }
            Err(_) => {}
        }
    }
}

fn play_soluna_jitter(
    i2s_spk: &esp_idf_hal::i2s::I2sDriver<'_, esp_idf_hal::i2s::I2sTx>,
    spk_enable: &PinDriver<'_, impl esp_idf_hal::gpio::OutputPin, esp_idf_hal::gpio::Output>,
    play_buf: &mut [u8; 1024],
) {
    if let Ok(mut node_opt) = SOLUNA_NODE.lock() {
        if let Some(ref mut node) = *node_opt {
            if node.jitter.available() >= 1024 {
                let n = node.jitter.pop(play_buf);
                if n > 0 {
                    set_state(DeviceState::Speaking);
                    let _ = spk_enable.set_high();
                    let _ = i2s_spk.write(&play_buf[..n], Duration::from_millis(50));
                    let _ = spk_enable.set_low();
                    set_state(DeviceState::Syncing);
                }
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
                error!("Playback: {:?}", e);
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
                // 短押し: 録音ON/OFF
                let cur = RECORDING.load(Ordering::Relaxed);
                RECORDING.store(!cur, Ordering::Relaxed);
                info!("Rec: {}", !cur);
            } else if ms < 3000 {
                // 中押し: Koe ↔ Soluna モード切替
                toggle_mode();
            } else {
                // 長押し: BLEペアリング
                info!("BLE pair mode");
            }
        }
        thread::sleep(Duration::from_millis(30));
    }
}

fn connect_wifi(
    modem: impl esp_idf_hal::peripheral::Peripheral<P = esp_idf_hal::modem::Modem> + 'static,
    sysloop: EspSystemEventLoop,
    nvs_partition: EspDefaultNvsPartition,
    nvs: &EspNvs<NvsDefault>,
) -> Result<EspWifi<'static>, Box<dyn std::error::Error>> {
    let mut ssid_buf = [0u8; 64];
    let mut pass_buf = [0u8; 128];

    let ssid = nvs.get_str("wifi_ssid", &mut ssid_buf)?
        .ok_or("WiFi SSID not configured")?;
    let password = nvs.get_str("wifi_pass", &mut pass_buf)?
        .ok_or("WiFi password not configured")?;

    let ssid = ssid.trim_end_matches('\0');
    let password = password.trim_end_matches('\0');

    let mut wifi = EspWifi::new(modem, sysloop, Some(nvs_partition))?;

    wifi.set_configuration(&Configuration::Client(ClientConfiguration {
        ssid: ssid.try_into().map_err(|_| "SSID too long")?,
        password: password.try_into().map_err(|_| "Password too long")?,
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
