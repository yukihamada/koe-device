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

mod audio;
mod led;
mod cloud;
mod soluna;
mod ble;
mod ota;
mod battery;

const SAMPLE_RATE: u32 = 16_000;
const RING_BUFFER_SIZE: usize = SAMPLE_RATE as usize * 2 * 5;
const MCAST_DEST: SocketAddrV4 = SocketAddrV4::new(Ipv4Addr::new(239, 42, 42, 1), 4242);
const VERSION: &str = env!("CARGO_PKG_VERSION");

#[repr(u8)]
#[derive(Clone, Copy, PartialEq)]
pub enum DeviceMode { Koe = 0, Soluna = 1 }

#[repr(u8)]
#[derive(Clone, Copy, PartialEq)]
pub enum DeviceState {
    Booting = 0, Connecting = 1, Listening = 2, Processing = 3,
    Speaking = 4, Error = 5, Syncing = 6,
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
static SPK_ON: AtomicBool = AtomicBool::new(false);
static SOLUNA_NODE: Mutex<Option<soluna::SolunaNode>> = Mutex::new(None);
// ボタンイベント: 0=none,1=short,2=mode,3=ble,4=double-tap,5=factory-reset,6=vol-up,7=vol-down
static BTN_EVENT: AtomicU8 = AtomicU8::new(0);

#[inline] fn set_state(s: DeviceState) { STATE.store(s as u8, Ordering::Relaxed); }
#[inline] pub fn get_state() -> DeviceState { DeviceState::from_u8(STATE.load(Ordering::Relaxed)) }
#[inline] pub fn get_mode() -> DeviceMode {
    if MODE.load(Ordering::Relaxed) == 1 { DeviceMode::Soluna } else { DeviceMode::Koe }
}

fn toggle_mode(
    i2s_spk: &esp_idf_hal::i2s::I2sDriver<'_, esp_idf_hal::i2s::I2sTx>,
    spk_enable: &PinDriver<'_, impl esp_idf_hal::gpio::OutputPin, esp_idf_hal::gpio::Output>,
) {
    let new = if MODE.load(Ordering::Relaxed) == 0 { 1 } else { 0 };
    MODE.store(new, Ordering::Relaxed);
    if new == 1 {
        soluna::set_active(true);
        set_state(DeviceState::Syncing);
        play_beep(i2s_spk, spk_enable, 880, 80);
        play_beep(i2s_spk, spk_enable, 1100, 80);
    } else {
        soluna::set_active(false);
        SPK_ON.store(false, Ordering::Relaxed);
        set_state(DeviceState::Listening);
        play_beep(i2s_spk, spk_enable, 440, 120);
    }
}

fn play_beep(
    i2s_spk: &esp_idf_hal::i2s::I2sDriver<'_, esp_idf_hal::i2s::I2sTx>,
    spk_enable: &PinDriver<'_, impl esp_idf_hal::gpio::OutputPin, esp_idf_hal::gpio::Output>,
    freq: u32, ms: u32,
) {
    let mut buf = [0u8; 4096];
    let len = audio::generate_beep(freq, ms, &mut buf);
    if len > 0 {
        let _ = spk_enable.set_high();
        let _ = i2s_spk.write(&buf[..len], 200);
        thread::sleep(Duration::from_millis(30));
        let _ = spk_enable.set_low();
    }
}

fn main() {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    // クラッシュダンプ: 前回のパニック情報をチェック
    check_crash_dump();

    // ハードウェアWDT (30秒)
    init_watchdog();

    if let Err(e) = run() {
        error!("Fatal: {:?}", e);
        // クラッシュダンプ保存
        save_crash_dump(&format!("{:?}", e));
        unsafe { esp_idf_sys::esp_restart(); }
    }
}

fn run() -> Result<(), Box<dyn std::error::Error>> {
    info!("Koe+Soluna v{}", VERSION);

    let peripherals = Peripherals::take()?;
    let sysloop = EspSystemEventLoop::take()?;
    let nvs_partition = EspDefaultNvsPartition::take()?;
    let mut nvs = EspNvs::new(nvs_partition.clone(), "koe", true)?;

    // サンプルレート
    let mut rate_buf = [0u8; 8];
    if let Ok(Some(r)) = nvs.get_str("sample_rate", &mut rate_buf) {
        if r.trim_end_matches('\0') == "48000" { audio::set_sample_rate(48_000); }
    }

    // ボリューム復元
    let mut vol_buf = [0u8; 8];
    if let Ok(Some(v)) = nvs.get_str("volume", &mut vol_buf) {
        if let Ok(vol) = v.trim_end_matches('\0').parse::<i32>() {
            audio::set_volume(vol);
        }
    }

    // LED + バッテリー
    thread::Builder::new().stack_size(2048).spawn(|| led::run_led_task())?;
    thread::Builder::new().stack_size(2048).spawn(|| battery::monitor_task())?;

    // WiFi
    set_state(DeviceState::Connecting);
    let wifi = match connect_wifi(peripherals.modem, sysloop.clone(), nvs_partition.clone(), &nvs) {
        Ok(w) => w,
        Err(_) => {
            ble::start_pairing(&nvs);
            return Err("Restarting after pairing".into());
        }
    };
    info!("WiFi OK");

    thread::Builder::new().stack_size(3072).spawn(move || wifi_watchdog(wifi))?;
    thread::Builder::new().stack_size(3072).spawn(|| soluna::sntp_task())?;

    // OTA
    let koe_client = cloud::SecureClient::new(&mut nvs);
    let ota_device_id = koe_client.device_id().to_string();
    thread::Builder::new().stack_size(4096).spawn(move || {
        thread::sleep(Duration::from_secs(30));
        let _ = ota::check_and_update(&ota_device_id);
    })?;

    // Soluna
    let device_id = koe_client.device_id().to_string();
    let device_hash = soluna::fnv1a(device_id.as_bytes());
    soluna::set_own_device_hash(device_hash);

    let default_channel = {
        let mut buf = [0u8; 32];
        nvs.get_str("soluna_ch", &mut buf).ok().flatten()
            .map(|s| s.trim_end_matches('\0').to_string())
            .unwrap_or_else(|| "soluna".to_string())
    };
    { let mut n = SOLUNA_NODE.lock().unwrap(); *n = Some(soluna::SolunaNode::new(&default_channel, device_hash)); }
    let _ = soluna::register_mdns(&device_id);

    // Soluna RX + Heartbeat
    thread::Builder::new().stack_size(4096).spawn(|| soluna_rx_loop())?;
    let tx_socket = UdpSocket::bind("0.0.0.0:0")?;
    let hb_socket = UdpSocket::bind("0.0.0.0:0")?;
    thread::Builder::new().stack_size(2048).spawn(move || {
        soluna::heartbeat_task(&hb_socket, MCAST_DEST);
    })?;

    // ステータス送信 (5分ごと)
    let status_device_id = koe_client.device_id().to_string();
    thread::Builder::new().stack_size(3072).spawn(move || {
        status_report_task(&status_device_id);
    })?;

    // I2S
    let i2s_mic = audio::init_mic_i2s(
        peripherals.i2s0, peripherals.pins.gpio4,
        peripherals.pins.gpio5, peripherals.pins.gpio6,
    )?;
    let i2s_spk = audio::init_spk_i2s(peripherals.i2s1, peripherals.pins.gpio7)?;
    let spk_enable = PinDriver::output(peripherals.pins.gpio8)?;

    // Button
    let button = PinDriver::input(peripherals.pins.gpio15)?;
    thread::Builder::new().stack_size(2048).spawn(move || button_task(button))?;

    play_beep(&i2s_spk, &spk_enable, 660, 60);
    set_state(DeviceState::Listening);
    info!("Ready v{}", VERSION);

    // バッファ
    let mut ring_buffer = vec![0u8; RING_BUFFER_SIZE];
    let mut ring_pos: usize = 0;
    let mut read_buf = [0u8; 1024];
    let mut voice_buf: Vec<u8> = Vec::with_capacity(SAMPLE_RATE as usize * 2 * 3);
    let mut silent_frames: u32 = 0;
    const SILENCE_TIMEOUT: u32 = 15;
    let mut play_buf = [0u8; 2048];

    loop {
        // WDTフィード
        feed_watchdog();

        // ボタンイベント
        let btn = BTN_EVENT.swap(0, Ordering::Relaxed);
        match btn {
            1 => {
                let cur = RECORDING.load(Ordering::Relaxed);
                RECORDING.store(!cur, Ordering::Relaxed);
            }
            2 => toggle_mode(&i2s_spk, &spk_enable),
            3 => {
                play_beep(&i2s_spk, &spk_enable, 330, 200);
                ble::start_pairing(&nvs);
            }
            4 => {
                if get_mode() == DeviceMode::Soluna {
                    if let Ok(mut g) = SOLUNA_NODE.lock() {
                        if let Some(ref mut node) = *g { node.next_channel(); }
                    }
                    play_beep(&i2s_spk, &spk_enable, 550, 50);
                    play_beep(&i2s_spk, &spk_enable, 770, 50);
                }
            }
            5 => factory_reset(&mut nvs, &i2s_spk, &spk_enable), // 5連打
            6 => { // ボリュームアップ (トリプルタップ上)
                let vol = audio::get_volume();
                audio::set_volume(vol + 64);
                play_beep(&i2s_spk, &spk_enable, 880, 30);
            }
            7 => { // ボリュームダウン
                let vol = audio::get_volume();
                audio::set_volume(vol - 64);
                play_beep(&i2s_spk, &spk_enable, 330, 30);
            }
            _ => {}
        }

        if !RECORDING.load(Ordering::Relaxed) {
            thread::sleep(Duration::from_millis(100));
            continue;
        }

        let bytes_read = match i2s_mic.read(&mut read_buf, 50) {
            Ok(n) => n,
            Err(_) => continue,
        };

        if bytes_read == 0 {
            if get_mode() == DeviceMode::Soluna {
                soluna_play(&i2s_spk, &spk_enable, &mut play_buf);
            }
            continue;
        }

        // === DSPパイプライン ===
        // 1. ハイパスフィルタ (DCオフセット除去)
        audio::apply_highpass(&mut read_buf[..bytes_read]);
        // 2. AEC (エコーキャンセル)
        audio::aec_cancel(&mut read_buf[..bytes_read]);
        // 3. ノイズゲート
        let gate_open = audio::apply_noise_gate(&mut read_buf[..bytes_read]);
        // 4. AGC (自動ゲイン制御)
        if gate_open { audio::apply_agc(&mut read_buf[..bytes_read]); }
        // 5. リミッター (クリッピング防止)
        audio::apply_limiter(&mut read_buf[..bytes_read]);
        // 6. ボリューム
        audio::apply_volume(&mut read_buf[..bytes_read]);

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
                // ノイズゲートが閉じてたら送信しない (帯域節約)
                if gate_open && audio::detect_voice(&read_buf[..bytes_read]) {
                    soluna_tx(&tx_socket, &read_buf[..bytes_read]);
                }
                soluna_play(&i2s_spk, &spk_enable, &mut play_buf);
            }
        }
    }
}

// === ヘルパー関数 ===

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

fn soluna_tx(socket: &UdpSocket, audio: &[u8]) {
    if let Ok(mut g) = SOLUNA_NODE.lock() {
        if let Some(ref mut node) = *g {
            let mut packet = [0u8; 531];
            let len = node.build_packet(audio, &mut packet);
            let _ = socket.send_to(&packet[..len], MCAST_DEST);
        }
    }
}

fn soluna_rx_loop() {
    let socket = match UdpSocket::bind("0.0.0.0:4242") {
        Ok(s) => s,
        Err(e) => { error!("RX: {:?}", e); return; }
    };
    let _ = socket.join_multicast_v4(&Ipv4Addr::new(239,42,42,1), &Ipv4Addr::UNSPECIFIED);
    let _ = socket.set_read_timeout(Some(Duration::from_millis(100)));
    let mut buf = [0u8; 531];
    loop {
        if !soluna::is_active() { thread::sleep(200); continue; }
        match socket.recv_from(&mut buf) {
            Ok((n, _)) => {
                if let Ok(mut g) = SOLUNA_NODE.lock() {
                    if let Some(ref mut node) = *g { node.handle_packet(&buf[..n]); }
                }
            }
            Err(_) => {}
        }
    }
}

fn soluna_play(
    i2s_spk: &esp_idf_hal::i2s::I2sDriver<'_, esp_idf_hal::i2s::I2sTx>,
    spk_enable: &PinDriver<'_, impl esp_idf_hal::gpio::OutputPin, esp_idf_hal::gpio::Output>,
    play_buf: &mut [u8; 2048],
) {
    if let Ok(mut g) = SOLUNA_NODE.lock() {
        if let Some(ref mut node) = *g {
            if node.jitter.available() >= 512 {
                if !SPK_ON.load(Ordering::Relaxed) {
                    let _ = spk_enable.set_high();
                    SPK_ON.store(true, Ordering::Relaxed);
                }
                let n = node.jitter.pop(&mut play_buf[..node.jitter.available().min(2048)]);
                if n > 0 {
                    set_state(DeviceState::Speaking);
                    audio::aec_set_reference(&play_buf[..n]);
                    let _ = i2s_spk.write(&play_buf[..n], 50);
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
            let _ = audio::play_audio(i2s_spk, spk_enable, &response);
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

// === ボタン (5連打=ファクトリーリセット検出追加) ===

fn button_task(mut button: PinDriver<'_, impl esp_idf_hal::gpio::InputPin, esp_idf_hal::gpio::Input>) {
    let mut press_start: Option<std::time::Instant> = None;
    let mut last_short_press: Option<std::time::Instant> = None;
    let mut rapid_count: u8 = 0;
    let mut rapid_window: Option<std::time::Instant> = None;

    loop {
        if button.is_low() {
            if press_start.is_none() { press_start = Some(std::time::Instant::now()); }
        } else if let Some(start) = press_start.take() {
            let ms = start.elapsed().as_millis();
            if ms < 500 {
                // 5連打検出
                if let Some(w) = rapid_window {
                    if w.elapsed().as_millis() < 2000 {
                        rapid_count += 1;
                        if rapid_count >= 5 {
                            BTN_EVENT.store(5, Ordering::Relaxed); // factory reset
                            rapid_count = 0;
                            rapid_window = None;
                            continue;
                        }
                    } else {
                        rapid_count = 1;
                    }
                } else {
                    rapid_count = 1;
                }
                rapid_window = Some(std::time::Instant::now());

                // ダブルタップ検出
                if let Some(last) = last_short_press {
                    if last.elapsed().as_millis() < 400 {
                        BTN_EVENT.store(4, Ordering::Relaxed);
                        last_short_press = None;
                        continue;
                    }
                }
                last_short_press = Some(std::time::Instant::now());
            } else if ms < 3000 {
                BTN_EVENT.store(2, Ordering::Relaxed);
            } else {
                BTN_EVENT.store(3, Ordering::Relaxed);
            }
        }

        if let Some(last) = last_short_press {
            if last.elapsed().as_millis() >= 400 {
                BTN_EVENT.store(1, Ordering::Relaxed);
                last_short_press = None;
            }
        }

        thread::sleep(Duration::from_millis(20));
    }
}

// === ファクトリーリセット ===

fn factory_reset(
    nvs: &mut EspNvs<NvsDefault>,
    i2s_spk: &esp_idf_hal::i2s::I2sDriver<'_, esp_idf_hal::i2s::I2sTx>,
    spk_enable: &PinDriver<'_, impl esp_idf_hal::gpio::OutputPin, esp_idf_hal::gpio::Output>,
) {
    info!("Factory reset!");
    // 下降ビープ3回
    play_beep(i2s_spk, spk_enable, 880, 100);
    play_beep(i2s_spk, spk_enable, 660, 100);
    play_beep(i2s_spk, spk_enable, 440, 200);

    // NVS全消去
    for key in &["wifi_ssid", "wifi_pass", "api_key", "device_id", "soluna_ch", "sample_rate", "volume"] {
        let _ = nvs.remove(key);
    }
    info!("NVS cleared, restarting...");
    thread::sleep(Duration::from_secs(1));
    unsafe { esp_idf_sys::esp_restart(); }
}

// === ハードウェアWDT ===

fn init_watchdog() {
    unsafe {
        // タスクWDTに現在のタスクを登録 (30秒タイムアウト)
        esp_idf_sys::esp_task_wdt_config_t {
            timeout_ms: 30_000,
            idle_core_mask: 0,
            trigger_panic: true,
        };
        esp_idf_sys::esp_task_wdt_add(core::ptr::null_mut());
    }
}

fn feed_watchdog() {
    unsafe { esp_idf_sys::esp_task_wdt_reset(); }
}

// === クラッシュダンプ ===

fn save_crash_dump(msg: &str) {
    // NVSに最後のエラーを保存 (最大127文字)
    if let Ok(nvs_partition) = EspDefaultNvsPartition::take() {
        if let Ok(mut nvs) = EspNvs::new(nvs_partition, "crash", true) {
            let truncated: String = msg.chars().take(127).collect();
            let _ = nvs.set_str("last_error", &truncated);
        }
    }
}

fn check_crash_dump() {
    if let Ok(nvs_partition) = EspDefaultNvsPartition::take() {
        if let Ok(mut nvs) = EspNvs::new(nvs_partition, "crash", true) {
            let mut buf = [0u8; 128];
            if let Ok(Some(msg)) = nvs.get_str("last_error", &mut buf) {
                let msg = msg.trim_end_matches('\0');
                if !msg.is_empty() {
                    warn!("Previous crash: {}", msg);
                    let _ = nvs.remove("last_error");
                }
            }
        }
    }
}

// === ステータスレポート (5分ごと) ===

fn status_report_task(device_id: &str) {
    loop {
        thread::sleep(Duration::from_secs(300));

        let bat = battery::level();
        let peers = soluna::peer_count();
        let mode = if get_mode() == DeviceMode::Soluna { "soluna" } else { "koe" };
        let state = get_state() as u8;

        // HTTPでステータス送信
        let config = esp_idf_svc::http::client::Configuration {
            buffer_size: Some(1024),
            timeout: Some(Duration::from_secs(5)),
            ..Default::default()
        };
        let mut client = match esp_idf_svc::http::client::EspHttpConnection::new(&config) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let body = format!(
            "{{\"device_id\":\"{}\",\"version\":\"{}\",\"battery\":{},\"peers\":{},\"mode\":\"{}\",\"state\":{}}}",
            device_id, VERSION, bat, peers, mode, state
        );
        let headers = [
            ("Content-Type", "application/json"),
            ("X-Device-Id", device_id),
        ];
        if client.initiate_request(
            esp_idf_svc::http::Method::Post,
            "https://api.chatweb.ai/api/v1/device/status",
            &headers,
        ).is_err() {
            continue;
        }
        let _ = client.write(body.as_bytes());
        let _ = client.initiate_response();
    }
}

// === WiFi ===

fn wifi_watchdog(mut wifi: EspWifi<'static>) {
    loop {
        thread::sleep(Duration::from_secs(5));
        if wifi.is_connected().unwrap_or(false) { continue; }
        warn!("WiFi lost");
        set_state(DeviceState::Connecting);
        let _ = wifi.disconnect();
        thread::sleep(Duration::from_millis(500));
        if wifi.connect().is_err() { thread::sleep(Duration::from_secs(5)); continue; }
        let deadline = std::time::Instant::now() + Duration::from_secs(15);
        while !wifi.is_connected().unwrap_or(false) {
            if std::time::Instant::now() > deadline { break; }
            thread::sleep(Duration::from_millis(100));
        }
        if wifi.is_connected().unwrap_or(false) {
            info!("WiFi OK");
            set_state(DeviceState::Listening);
        }
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
    let ssid = nvs.get_str("wifi_ssid", &mut ssid_buf)?.ok_or("No SSID")?;
    let password = nvs.get_str("wifi_pass", &mut pass_buf)?.ok_or("No pass")?;
    let ssid = ssid.trim_end_matches('\0');
    let password = password.trim_end_matches('\0');
    let mut wifi = EspWifi::new(modem, sysloop, Some(nvs_partition))?;
    wifi.set_configuration(&Configuration::Client(ClientConfiguration {
        ssid: ssid.try_into().map_err(|_| "SSID")?,
        password: password.try_into().map_err(|_| "Pass")?,
        ..Default::default()
    }))?;
    wifi.start()?;
    wifi.connect()?;
    let deadline = std::time::Instant::now() + Duration::from_secs(15);
    while !wifi.is_connected()? {
        if std::time::Instant::now() > deadline { return Err("WiFi timeout".into()); }
        thread::sleep(Duration::from_millis(100));
    }
    Ok(wifi)
}
