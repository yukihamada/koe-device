/// koe-firmware — ESP32-S3 Koe Device main entry point
///
/// Three tasks run concurrently sharing state via Arc<Mutex<…>>:
///
///   led_task   — drives WS2812B LED based on DeviceState (spawned thread)
///   api_task   — heartbeat every 5 s + session events on onset (spawned thread)
///   audio_task — reads I2S mic, fills ring buffer, detects onset (main thread)
///
/// NVS layout (namespace "koe"):
///   "wifi_ssid"  — WiFi SSID  (string, set at provisioning)
///   "wifi_pass"  — WiFi pass  (string, set at provisioning)
///   "device_id"  — device ID  (string, derived from MAC if absent)
///
/// GPIO assignments (see CLAUDE.md):
///   Mic I2S BCLK : GPIO14
///   Mic I2S WS   : GPIO15
///   Mic I2S DIN  : GPIO32
///   LED          : GPIO2

use anyhow::{anyhow, Result};
use esp_idf_hal::{
    i2s::{
        config::{DataBitWidth, SlotMode, StdClkConfig, StdConfig, StdSlotConfig},
        I2sDriver, I2sRx, I2S0,
    },
    gpio::{AnyIOPin, Gpio14, Gpio15, Gpio32},
    peripherals::Peripherals,
};
use esp_idf_svc::{
    eventloop::EspSystemEventLoop,
    nvs::{EspDefaultNvsPartition, EspNvs},
    sntp::{EspSntp, SntpConf, SyncMode},
    wifi::{AuthMethod, BlockingWifi, ClientConfiguration, Configuration, EspWifi},
    sys::esp_efuse_mac_get_default,
};
use log::{info, warn};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

mod audio;
mod api;
mod led;

use audio::{OnsetDetector, RingBuffer, FRAME_SAMPLES};
use led::{LedState, WS2812Driver};

// ---------------------------------------------------------------------------
// Firmware version — kept in sync with Cargo.toml
// ---------------------------------------------------------------------------
const FIRMWARE_VERSION: &str = env!("CARGO_PKG_VERSION");

// ---------------------------------------------------------------------------
// Default WiFi credentials (overridden by NVS at provisioning time).
// ---------------------------------------------------------------------------
const DEFAULT_WIFI_SSID: &str = "KoeNet";
const DEFAULT_WIFI_PASS: &str = "koedevice";

// ---------------------------------------------------------------------------
// Send wrapper — used to move !Send peripheral types across thread boundaries.
//
// SAFETY: Each wrapped peripheral is moved into exactly one thread and is
// never accessed from any other thread after the move.
// ---------------------------------------------------------------------------
struct SendWrap<T>(T);
unsafe impl<T> Send for SendWrap<T> {}

// ---------------------------------------------------------------------------
// Shared device state
// ---------------------------------------------------------------------------

/// Events sent from the audio task to the API task.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum AudioEvent {
    None,
    OnsetDetected,
    SessionEnded,
}

struct SharedState {
    led_state: LedState,
    audio_event: AudioEvent,
    /// Current active session ID (empty string = no active session).
    session_id: heapless::String<64>,
}

impl SharedState {
    fn new() -> Self {
        SharedState {
            led_state: LedState::Ready,
            audio_event: AudioEvent::None,
            session_id: heapless::String::new(),
        }
    }
}

// ---------------------------------------------------------------------------
// NVS helpers
// ---------------------------------------------------------------------------

fn nvs_get_string<const N: usize>(
    nvs: &EspNvs<esp_idf_svc::nvs::NvsDefault>,
    key: &str,
) -> Option<heapless::String<N>> {
    let mut buf = [0u8; N];
    match nvs.get_str(key, &mut buf) {
        Ok(Some(s)) => {
            let mut out = heapless::String::<N>::new();
            let _ = out.push_str(s);
            Some(out)
        }
        _ => None,
    }
}

// ---------------------------------------------------------------------------
// MAC → device ID helper
// ---------------------------------------------------------------------------

fn mac_to_device_id() -> heapless::String<32> {
    let mut mac = [0u8; 6];
    // SAFETY: standard esp-idf call, mac is a valid 6-byte buffer.
    unsafe { esp_efuse_mac_get_default(mac.as_mut_ptr()); }
    let mut id = heapless::String::<32>::new();
    let _ = core::fmt::write(
        &mut id,
        format_args!(
            "koe-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
            mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]
        ),
    );
    id
}

// ---------------------------------------------------------------------------
// SNTP wall-clock helper
// ---------------------------------------------------------------------------

fn epoch_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

// ---------------------------------------------------------------------------
// WiFi connection
// ---------------------------------------------------------------------------

fn connect_wifi(
    wifi: &mut BlockingWifi<EspWifi<'_>>,
    ssid: &str,
    password: &str,
) -> Result<()> {
    let config = Configuration::Client(ClientConfiguration {
        ssid: heapless::String::try_from(ssid)
            .map_err(|_| anyhow!("SSID too long"))?,
        password: heapless::String::try_from(password)
            .map_err(|_| anyhow!("password too long"))?,
        auth_method: if password.is_empty() {
            AuthMethod::None
        } else {
            AuthMethod::WPA2Personal
        },
        ..Default::default()
    });
    wifi.set_configuration(&config)?;
    wifi.start()?;
    wifi.connect()?;
    wifi.wait_netif_up()?;
    let ip = wifi.wifi().sta_netif().get_ip_info()?;
    info!("[wifi] connected ip={}", ip.ip);
    Ok(())
}

// ---------------------------------------------------------------------------
// Audio task — runs on the main thread
// ---------------------------------------------------------------------------

fn run_audio_task(
    state: Arc<Mutex<SharedState>>,
    i2s0: I2S0,
    bclk: Gpio14,
    ws: Gpio15,
    din: Gpio32,
) -> ! {
    info!("[audio] task start");

    let clk_cfg  = StdClkConfig::from_sample_rate_hz(16_000);
    let slot_cfg = StdSlotConfig::philips_slot_default(DataBitWidth::Bits16, SlotMode::Mono);
    let std_cfg  = StdConfig::new(clk_cfg, slot_cfg, Default::default());

    let no_mclk: Option<AnyIOPin> = None;
    let mut driver = match I2sDriver::<I2sRx>::new_std_rx(i2s0, &std_cfg, bclk, din, no_mclk, ws) {
        Ok(d) => d,
        Err(e) => {
            warn!("[audio] I2S init failed: {:?}", e);
            loop { thread::sleep(Duration::from_secs(60)); }
        }
    };

    if let Err(e) = driver.rx_enable() {
        warn!("[audio] rx_enable failed: {:?}", e);
        loop { thread::sleep(Duration::from_secs(60)); }
    }

    let mut ring     = RingBuffer::new();
    let mut detector = OnsetDetector::new();
    let mut raw_buf  = vec![0u8; FRAME_SAMPLES * 2];
    let mut samples  = vec![0i16; FRAME_SAMPLES];

    let mut in_session   = false;
    let mut quiet_frames: u32 = 0;
    // ~5 s of silence at ~32 ms/frame = 156 frames ends the session
    const QUIET_END_FRAMES: u32 = 156;

    loop {
        let bytes_read = match driver.read(&mut raw_buf, 100) {
            Ok(n) => n,
            Err(e) => {
                warn!("[audio] read error: {:?}", e);
                thread::sleep(Duration::from_millis(10));
                continue;
            }
        };

        // Convert raw LE bytes to i16 samples
        let n_samples = (bytes_read / 2).min(FRAME_SAMPLES);
        for i in 0..n_samples {
            samples[i] = i16::from_le_bytes([raw_buf[i * 2], raw_buf[i * 2 + 1]]);
        }
        let frame = &samples[..n_samples];

        ring.push(frame);
        let onset = detector.process_frame(frame);

        if onset && !in_session {
            info!("[audio] onset → requesting session");
            in_session   = true;
            quiet_frames = 0;
            let mut st = state.lock().unwrap();
            st.audio_event = AudioEvent::OnsetDetected;
            st.led_state   = LedState::Detected;
        } else if in_session {
            let current_rms = audio::rms(frame);
            if current_rms < detector.floor_rms() * 1.5 {
                quiet_frames += 1;
            } else {
                quiet_frames = 0;
            }

            if quiet_frames >= QUIET_END_FRAMES {
                info!("[audio] silence timeout → ending session");
                in_session   = false;
                quiet_frames = 0;
                let mut st = state.lock().unwrap();
                st.audio_event = AudioEvent::SessionEnded;
                st.led_state   = LedState::Ready;
            } else {
                let mut st = state.lock().unwrap();
                // Transition from brief flash to sustained recording glow
                if st.led_state != LedState::Detected {
                    st.led_state = LedState::Recording;
                }
            }
        }
    }
}

// ---------------------------------------------------------------------------
// API task
// ---------------------------------------------------------------------------

fn run_api_task(device_id: heapless::String<32>, state: Arc<Mutex<SharedState>>) -> ! {
    info!("[api] task start, device_id={}", device_id.as_str());

    let heartbeat_interval = Duration::from_secs(5);
    let mut last_heartbeat = std::time::Instant::now();

    loop {
        // Consume pending audio event
        let event = {
            let mut st = state.lock().unwrap();
            let e = st.audio_event;
            if e != AudioEvent::None {
                st.audio_event = AudioEvent::None;
            }
            e
        };

        match event {
            AudioEvent::OnsetDetected => {
                match api::create_session(device_id.as_str()) {
                    Ok(session_id) => {
                        let ts = epoch_ms();
                        if let Err(e) =
                            api::start_session(device_id.as_str(), session_id.as_str(), ts)
                        {
                            warn!("[api] start_session: {:?}", e);
                        }
                        let mut st = state.lock().unwrap();
                        st.session_id = session_id;
                        st.led_state  = LedState::Recording;
                    }
                    Err(e) => {
                        warn!("[api] create_session: {:?}", e);
                        state.lock().unwrap().led_state = LedState::Recording;
                    }
                }
            }

            AudioEvent::SessionEnded => {
                let (session_id, ts) = {
                    let st = state.lock().unwrap();
                    (st.session_id.clone(), epoch_ms())
                };
                if !session_id.is_empty() {
                    if let Err(e) =
                        api::end_session(device_id.as_str(), session_id.as_str(), ts)
                    {
                        warn!("[api] end_session: {:?}", e);
                    }
                    state.lock().unwrap().session_id.clear();
                }
            }

            AudioEvent::None => {}
        }

        // Periodic heartbeat every 5 s
        if last_heartbeat.elapsed() >= heartbeat_interval {
            if let Err(e) = api::send_heartbeat(device_id.as_str(), FIRMWARE_VERSION) {
                warn!("[api] heartbeat: {:?}", e);
            }
            last_heartbeat = std::time::Instant::now();
        }

        thread::sleep(Duration::from_millis(50));
    }
}

// ---------------------------------------------------------------------------
// main
// ---------------------------------------------------------------------------

fn main() -> Result<()> {
    esp_idf_svc::log::EspLogger::initialize_default();
    info!("koe-firmware v{} starting", FIRMWARE_VERSION);

    let peripherals  = Peripherals::take()?;
    let sys_loop     = EspSystemEventLoop::take()?;
    let nvs_partition = EspDefaultNvsPartition::take()?;

    // Open NVS namespace "koe"
    let nvs = EspNvs::new(nvs_partition.clone(), "koe", true)?;

    let ssid: heapless::String<32> = nvs_get_string::<32>(&nvs, "wifi_ssid")
        .unwrap_or_else(|| {
            let mut s = heapless::String::<32>::new();
            let _ = s.push_str(DEFAULT_WIFI_SSID);
            s
        });
    let pass: heapless::String<64> = nvs_get_string::<64>(&nvs, "wifi_pass")
        .unwrap_or_else(|| {
            let mut s = heapless::String::<64>::new();
            let _ = s.push_str(DEFAULT_WIFI_PASS);
            s
        });
    let device_id: heapless::String<32> = nvs_get_string::<32>(&nvs, "device_id")
        .unwrap_or_else(mac_to_device_id);
    info!("[main] device_id={}", device_id.as_str());

    // Connect to WiFi
    let mut wifi = BlockingWifi::wrap(
        EspWifi::new(peripherals.modem, sys_loop.clone(), Some(nvs_partition))?,
        sys_loop,
    )?;
    connect_wifi(&mut wifi, ssid.as_str(), pass.as_str())?;

    // SNTP time sync — wait up to 2 s for first sync
    let _sntp = EspSntp::new(&SntpConf {
        servers: ["pool.ntp.org", "time.cloudflare.com", "time.aws.com", "time.google.com"],
        sync_mode: SyncMode::Immediate,
        ..Default::default()
    })?;
    thread::sleep(Duration::from_secs(2));
    info!("[main] epoch_ms={}", epoch_ms());

    // --- Shared state ---
    let shared_state = Arc::new(Mutex::new(SharedState::new()));

    // --- LED task (spawned thread) ---
    // Wrap the !Send GPIO pin in SendWrap so it can be moved into the thread.
    // SAFETY: only the led thread will ever access GPIO2 after the move.
    let led_state_clone = Arc::clone(&shared_state);
    let sw_pin = SendWrap(peripherals.pins.gpio2);
    thread::Builder::new()
        .name("led".into())
        .stack_size(4096)
        .spawn(move || {
            let SendWrap(pin) = sw_pin;
            match WS2812Driver::new(pin) {
                Ok(driver) => led::led_task(driver, move || {
                    led_state_clone.lock().unwrap().led_state
                }),
                Err(e) => {
                    warn!("[led] init error: {:?}", e);
                    loop { thread::sleep(Duration::from_secs(60)); }
                }
            }
        })?;

    // --- API task (spawned thread) ---
    let api_state     = Arc::clone(&shared_state);
    let device_id_api = device_id.clone();
    thread::Builder::new()
        .name("api".into())
        .stack_size(16384)
        .spawn(move || run_api_task(device_id_api, api_state))?;

    // --- Audio task (main thread) ---
    run_audio_task(
        shared_state,
        peripherals.i2s0,
        peripherals.pins.gpio14,
        peripherals.pins.gpio15,
        peripherals.pins.gpio32,
    );
}
