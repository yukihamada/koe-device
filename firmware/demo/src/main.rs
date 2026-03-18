///! Minimal synchronized audio playback demo for ESP32-S3.
///!
///! SENDER mode (hold GPIO15 button at boot):
///!   Reads I2S mic -> sends PCM via UDP multicast with timestamps.
///!
///! RECEIVER mode (default):
///!   Receives UDP multicast -> jitter buffer -> plays through I2S speaker.

use anyhow::{bail, Result};
use esp_idf_hal::gpio::PinDriver;
use esp_idf_hal::prelude::Peripherals;
use esp_idf_svc::eventloop::EspSystemEventLoop;
use esp_idf_svc::nvs::EspDefaultNvsPartition;
use esp_idf_svc::wifi::{BlockingWifi, ClientConfiguration, Configuration, EspWifi};
use esp_idf_sys as _;
use log::*;
use std::net::{Ipv4Addr, SocketAddrV4, UdpSocket};
use std::time::Duration;

// ── Build-time config ──────────────────────────────────────────────
const WIFI_SSID: &str = env!("WIFI_SSID");
const WIFI_PASS: &str = env!("WIFI_PASS");

// ── Network ────────────────────────────────────────────────────────
const MULTICAST_ADDR: Ipv4Addr = Ipv4Addr::new(239, 42, 42, 1);
const MULTICAST_PORT: u16 = 4242;

// ── Audio ──────────────────────────────────────────────────────────
const SAMPLE_RATE: u32 = 16_000;
const CHUNK_SAMPLES: usize = 512; // 512 samples = 32ms @ 16kHz
const CHUNK_BYTES: usize = CHUNK_SAMPLES * 2; // s16le = 2 bytes/sample

// ── Packet header ──────────────────────────────────────────────────
const MAGIC: [u8; 2] = [0x53, 0x4C]; // "SL"
const HEADER_SIZE: usize = 14;
const MAX_PACKET: usize = HEADER_SIZE + CHUNK_BYTES;

// ── Jitter buffer ──────────────────────────────────────────────────
const JITTER_SLOTS: usize = 8;
const JITTER_TARGET_MS: u32 = 40; // target latency: 40ms

// ── GPIO assignments ───────────────────────────────────────────────
// Mic I2S:     BCLK=4, WS=5, DIN=6
// Speaker I2S: BCLK=14, WS=21, DOUT=7, SD_MODE=8
// Button:      GPIO15 (pull-up, active LOW = sender)
// LED WS2812B: GPIO16

// ── Role ───────────────────────────────────────────────────────────
#[derive(Debug, Clone, Copy, PartialEq)]
enum Role {
    Sender,
    Receiver,
}

// ── LED colors via RMT (WS2812B on GPIO16) ─────────────────────────
/// Set WS2812B LED color using raw RMT bit-banging.
/// GRB order, 800kHz protocol.
fn set_led(r: u8, g: u8, b: u8) {
    unsafe {
        // Use raw GPIO bit-bang for WS2812B - simplest approach.
        // For a demo, we just set the GPIO high/low with nops for timing.
        // A proper implementation would use RMT peripheral, but this is
        // sufficient to show state.
        use esp_idf_sys::*;

        let pin = 16;
        gpio_reset_pin(pin);
        gpio_set_direction(pin, gpio_mode_t_GPIO_MODE_OUTPUT);

        // WS2812B expects GRB, MSB first
        let bits: [u8; 3] = [g, r, b];

        // Disable interrupts for timing-critical section
        let mux = portMUX_INITIALIZE();
        let mux_ptr = &mux as *const _ as *mut _;
        vPortEnterCritical(mux_ptr);

        for byte in &bits {
            for bit_idx in (0..8).rev() {
                let bit = (byte >> bit_idx) & 1;
                if bit == 1 {
                    // T1H ~800ns, T1L ~450ns
                    gpio_set_level(pin, 1);
                    esp_rom_delay_us(1); // ~800ns with overhead
                    gpio_set_level(pin, 0);
                    // short low
                } else {
                    // T0H ~400ns, T0L ~850ns
                    gpio_set_level(pin, 1);
                    // minimal high
                    gpio_set_level(pin, 0);
                    esp_rom_delay_us(1); // ~850ns with overhead
                }
            }
        }

        vPortExitCritical(mux_ptr);

        // Reset: >50us low
        gpio_set_level(pin, 0);
        esp_rom_delay_us(80);
    }
}

fn led_green() {
    set_led(0, 80, 0);
}
fn led_orange() {
    set_led(80, 40, 0);
}
fn led_cyan() {
    set_led(0, 40, 80);
}
fn led_off() {
    set_led(0, 0, 0);
}

// ── Timestamps ─────────────────────────────────────────────────────
fn now_us() -> u32 {
    unsafe { esp_idf_sys::esp_timer_get_time() as u32 }
}

// ── Packet encode/decode ───────────────────────────────────────────
fn encode_packet(buf: &mut [u8], seq: u32, ts_us: u32, audio: &[u8]) -> usize {
    buf[0] = MAGIC[0];
    buf[1] = MAGIC[1];
    buf[2..6].copy_from_slice(&seq.to_le_bytes());
    buf[6..10].copy_from_slice(&ts_us.to_le_bytes());
    buf[10..14].fill(0); // reserved
    let audio_len = audio.len().min(CHUNK_BYTES);
    buf[14..14 + audio_len].copy_from_slice(&audio[..audio_len]);
    HEADER_SIZE + audio_len
}

struct PacketHeader {
    seq: u32,
    timestamp_us: u32,
}

fn decode_header(buf: &[u8]) -> Option<PacketHeader> {
    if buf.len() < HEADER_SIZE {
        return None;
    }
    if buf[0] != MAGIC[0] || buf[1] != MAGIC[1] {
        return None;
    }
    let seq = u32::from_le_bytes([buf[2], buf[3], buf[4], buf[5]]);
    let timestamp_us = u32::from_le_bytes([buf[6], buf[7], buf[8], buf[9]]);
    Some(PacketHeader { seq, timestamp_us })
}

// ── I2S helpers (raw esp-idf calls) ────────────────────────────────
/// Configure I2S0 as microphone input (PDM or standard I2S).
unsafe fn i2s_init_mic() {
    use esp_idf_sys::*;

    let i2s_config = i2s_config_t {
        mode: (i2s_mode_t_I2S_MODE_MASTER | i2s_mode_t_I2S_MODE_RX) as i2s_mode_t,
        sample_rate: SAMPLE_RATE as i32,
        bits_per_sample: i2s_bits_per_sample_t_I2S_BITS_PER_SAMPLE_16BIT,
        channel_format: i2s_channel_fmt_t_I2S_CHANNEL_FMT_ONLY_LEFT,
        communication_format: i2s_comm_format_t_I2S_COMM_FORMAT_STAND_I2S,
        intr_alloc_flags: 0,
        dma_buf_count: 4,
        dma_buf_len: CHUNK_SAMPLES as i32,
        use_apll: false,
        tx_desc_auto_clear: false,
        fixed_mclk: 0,
        mclk_multiple: i2s_mclk_multiple_t_I2S_MCLK_MULTIPLE_256,
        bits_per_chan: i2s_bits_per_chan_t_I2S_BITS_PER_CHAN_DEFAULT,
        ..Default::default()
    };

    let pin_config = i2s_pin_config_t {
        bck_io_num: 4,  // BCLK
        ws_io_num: 5,   // WS
        data_out_num: -1,
        data_in_num: 6,  // DIN
        mck_io_num: -1,
    };

    let ret = i2s_driver_install(0, &i2s_config, 0, std::ptr::null_mut());
    if ret != ESP_OK {
        error!("i2s_driver_install (mic) failed: {}", ret);
    }
    let ret = i2s_set_pin(0, &pin_config);
    if ret != ESP_OK {
        error!("i2s_set_pin (mic) failed: {}", ret);
    }
    i2s_zero_dma_buffer(0);

    info!("I2S mic initialized: BCLK=4, WS=5, DIN=6, 16kHz mono");
}

/// Configure I2S1 as speaker output.
unsafe fn i2s_init_speaker() {
    use esp_idf_sys::*;

    let i2s_config = i2s_config_t {
        mode: (i2s_mode_t_I2S_MODE_MASTER | i2s_mode_t_I2S_MODE_TX) as i2s_mode_t,
        sample_rate: SAMPLE_RATE as i32,
        bits_per_sample: i2s_bits_per_sample_t_I2S_BITS_PER_SAMPLE_16BIT,
        channel_format: i2s_channel_fmt_t_I2S_CHANNEL_FMT_ONLY_LEFT,
        communication_format: i2s_comm_format_t_I2S_COMM_FORMAT_STAND_I2S,
        intr_alloc_flags: 0,
        dma_buf_count: 4,
        dma_buf_len: CHUNK_SAMPLES as i32,
        use_apll: false,
        tx_desc_auto_clear: true,
        fixed_mclk: 0,
        mclk_multiple: i2s_mclk_multiple_t_I2S_MCLK_MULTIPLE_256,
        bits_per_chan: i2s_bits_per_chan_t_I2S_BITS_PER_CHAN_DEFAULT,
        ..Default::default()
    };

    let pin_config = i2s_pin_config_t {
        bck_io_num: 14,  // BCLK
        ws_io_num: 21,   // WS
        data_out_num: 7,  // DOUT
        data_in_num: -1,
        mck_io_num: -1,
    };

    let ret = i2s_driver_install(1, &i2s_config, 0, std::ptr::null_mut());
    if ret != ESP_OK {
        error!("i2s_driver_install (spk) failed: {}", ret);
    }
    let ret = i2s_set_pin(1, &pin_config);
    if ret != ESP_OK {
        error!("i2s_set_pin (spk) failed: {}", ret);
    }
    i2s_zero_dma_buffer(1);

    // Enable SD_MODE on GPIO8 (MAX98357A enable pin, active HIGH)
    gpio_reset_pin(8);
    gpio_set_direction(8, gpio_mode_t_GPIO_MODE_OUTPUT);
    gpio_set_level(8, 1);

    info!("I2S speaker initialized: BCLK=14, WS=21, DOUT=7, SD_MODE=8(HIGH), 16kHz mono");
}

// ── Jitter buffer ──────────────────────────────────────────────────
struct JitterSlot {
    seq: u32,
    timestamp_us: u32,
    audio: [u8; CHUNK_BYTES],
    audio_len: usize,
    valid: bool,
}

impl Default for JitterSlot {
    fn default() -> Self {
        Self {
            seq: 0,
            timestamp_us: 0,
            audio: [0u8; CHUNK_BYTES],
            audio_len: 0,
            valid: false,
        }
    }
}

struct JitterBuffer {
    slots: [JitterSlot; JITTER_SLOTS],
    next_play_seq: u32,
    synced: bool,
}

impl JitterBuffer {
    fn new() -> Self {
        Self {
            slots: Default::default(),
            next_play_seq: 0,
            synced: false,
        }
    }

    /// Insert a received packet into the jitter buffer.
    fn insert(&mut self, seq: u32, ts_us: u32, audio: &[u8]) {
        if !self.synced {
            // First packet: initialize sequence
            self.next_play_seq = seq;
            self.synced = true;
            info!("Jitter buffer synced, starting at seq={}", seq);
        }

        // Drop packets that are too old
        if seq < self.next_play_seq {
            return;
        }

        let idx = (seq as usize) % JITTER_SLOTS;
        let slot = &mut self.slots[idx];
        let len = audio.len().min(CHUNK_BYTES);
        slot.seq = seq;
        slot.timestamp_us = ts_us;
        slot.audio[..len].copy_from_slice(&audio[..len]);
        slot.audio_len = len;
        slot.valid = true;
    }

    /// Get the next chunk to play. Returns None if not ready.
    fn pop(&mut self) -> Option<(&[u8], u32)> {
        if !self.synced {
            return None;
        }

        let idx = (self.next_play_seq as usize) % JITTER_SLOTS;
        let slot = &mut self.slots[idx];
        if slot.valid && slot.seq == self.next_play_seq {
            slot.valid = false;
            self.next_play_seq = self.next_play_seq.wrapping_add(1);
            Some((&slot.audio[..slot.audio_len], slot.timestamp_us))
        } else {
            // Packet missing - insert silence, advance
            self.next_play_seq = self.next_play_seq.wrapping_add(1);
            None
        }
    }

    /// Number of valid packets buffered ahead.
    fn buffered_count(&self) -> usize {
        self.slots.iter().filter(|s| s.valid).count()
    }
}

// ── WiFi ───────────────────────────────────────────────────────────
fn connect_wifi(
    sysloop: EspSystemEventLoop,
    nvs: EspDefaultNvsPartition,
    modem: esp_idf_hal::modem::Modem,
) -> Result<Box<BlockingWifi<EspWifi<'static>>>> {
    let mut wifi = BlockingWifi::wrap(EspWifi::new(modem, sysloop.clone(), Some(nvs))?, sysloop)?;

    let mut ssid_buf = heapless::String::<32>::new();
    ssid_buf.push_str(WIFI_SSID).ok();
    let mut pass_buf = heapless::String::<64>::new();
    pass_buf.push_str(WIFI_PASS).ok();

    wifi.set_configuration(&Configuration::Client(ClientConfiguration {
        ssid: ssid_buf,
        password: pass_buf,
        ..Default::default()
    }))?;

    wifi.start()?;
    info!("WiFi started, connecting to '{}'...", WIFI_SSID);
    wifi.connect()?;
    wifi.wait_netif_up()?;

    let ip_info = wifi.wifi().sta_netif().get_ip_info()?;
    info!("WiFi connected! IP: {}", ip_info.ip);

    Ok(Box::new(wifi))
}

// ── Sender loop ────────────────────────────────────────────────────
fn run_sender(sock: &UdpSocket) -> Result<()> {
    info!("=== SENDER MODE ===");
    info!("Reading from I2S mic, sending to {}:{}", MULTICAST_ADDR, MULTICAST_PORT);

    unsafe { i2s_init_mic(); }

    let dest = SocketAddrV4::new(MULTICAST_ADDR, MULTICAST_PORT);
    let mut seq: u32 = 0;
    let mut audio_buf = [0u8; CHUNK_BYTES];
    let mut pkt_buf = [0u8; MAX_PACKET];

    led_green(); // green = listening/recording

    loop {
        // Read from I2S mic
        let mut bytes_read: usize = 0;
        unsafe {
            let ret = esp_idf_sys::i2s_read(
                0,
                audio_buf.as_mut_ptr() as *mut _,
                CHUNK_BYTES,
                &mut bytes_read as *mut _,
                1000, // timeout ms (portMAX_DELAY equivalent)
            );
            if ret != esp_idf_sys::ESP_OK {
                warn!("i2s_read error: {}", ret);
                continue;
            }
        }

        if bytes_read == 0 {
            continue;
        }

        let ts = now_us();
        let pkt_len = encode_packet(&mut pkt_buf, seq, ts, &audio_buf[..bytes_read]);

        match sock.send_to(&pkt_buf[..pkt_len], dest) {
            Ok(_) => {}
            Err(e) => warn!("UDP send error: {}", e),
        }

        if seq % 100 == 0 {
            info!("TX seq={} ts={}us bytes={}", seq, ts, bytes_read);
        }
        seq = seq.wrapping_add(1);
    }
}

// ── Receiver loop ──────────────────────────────────────────────────
fn run_receiver(sock: &UdpSocket) -> Result<()> {
    info!("=== RECEIVER MODE ===");
    info!("Listening on {}:{}, will play through I2S speaker", MULTICAST_ADDR, MULTICAST_PORT);

    unsafe { i2s_init_speaker(); }

    let mut jbuf = JitterBuffer::new();
    let mut recv_buf = [0u8; MAX_PACKET];
    let silence = [0u8; CHUNK_BYTES];

    // Non-blocking receive with short timeout so we can also drain the jitter buffer
    sock.set_read_timeout(Some(Duration::from_millis(5)))?;

    let mut buffering = true;
    let mut play_count: u32 = 0;

    led_orange(); // orange = waiting for first packet

    loop {
        // Receive as many packets as available
        loop {
            match sock.recv_from(&mut recv_buf) {
                Ok((len, _src)) => {
                    if let Some(hdr) = decode_header(&recv_buf[..len]) {
                        let audio = &recv_buf[HEADER_SIZE..len];
                        jbuf.insert(hdr.seq, hdr.timestamp_us, audio);
                    }
                }
                Err(_) => break, // timeout or would-block
            }
        }

        // Wait until we have enough buffer before starting playback
        if buffering {
            let count = jbuf.buffered_count();
            if count >= 3 {
                info!("Jitter buffer filled ({} chunks), starting playback", count);
                buffering = false;
                led_cyan(); // cyan = playing
            } else {
                if jbuf.synced {
                    led_orange(); // syncing
                }
                std::thread::sleep(Duration::from_millis(1));
                continue;
            }
        }

        // Play next chunk from jitter buffer
        let audio_to_play = if let Some((audio, ts)) = jbuf.pop() {
            if play_count % 100 == 0 {
                let local_ts = now_us();
                let latency = local_ts.wrapping_sub(ts);
                info!("RX play seq, latency={}us, buffered={}", latency, jbuf.buffered_count());
            }
            audio.to_vec() // copy out since we need it after the borrow
        } else {
            // No packet available - play silence
            silence.to_vec()
        };

        // Write to I2S speaker
        let mut bytes_written: usize = 0;
        unsafe {
            let ret = esp_idf_sys::i2s_write(
                1,
                audio_to_play.as_ptr() as *const _,
                audio_to_play.len(),
                &mut bytes_written as *mut _,
                1000,
            );
            if ret != esp_idf_sys::ESP_OK {
                warn!("i2s_write error: {}", ret);
            }
        }

        play_count = play_count.wrapping_add(1);

        // If buffer runs dry, go back to buffering
        if jbuf.synced && jbuf.buffered_count() == 0 {
            buffering = true;
            led_orange();
        }
    }
}

// ── Main ───────────────────────────────────────────────────────────
fn main() -> Result<()> {
    // Initialize ESP-IDF
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    info!("╔══════════════════════════════════════╗");
    info!("║     Sync Demo - ESP32-S3             ║");
    info!("╚══════════════════════════════════════╝");

    let peripherals = Peripherals::take()?;
    let sysloop = EspSystemEventLoop::take()?;
    let nvs = EspDefaultNvsPartition::take()?;

    // Detect role: GPIO15 LOW at boot = SENDER
    let button = PinDriver::input(peripherals.pins.gpio15)?;
    // Small delay to let pin settle
    std::thread::sleep(Duration::from_millis(100));
    let role = if button.is_low() {
        Role::Sender
    } else {
        Role::Receiver
    };
    // Drop button pin driver so it doesn't conflict
    drop(button);

    info!("Role detected: {:?}", role);
    match role {
        Role::Sender => led_green(),
        Role::Receiver => led_orange(),
    }

    // Connect WiFi
    let _wifi = connect_wifi(sysloop, nvs, peripherals.modem)?;

    // Set up UDP multicast socket
    let bind_addr = SocketAddrV4::new(Ipv4Addr::UNSPECIFIED, MULTICAST_PORT);
    let sock = UdpSocket::bind(bind_addr)?;

    // Join multicast group
    sock.join_multicast_v4(&MULTICAST_ADDR, &Ipv4Addr::UNSPECIFIED)?;

    // Set multicast TTL
    sock.set_multicast_ttl_v4(2)?;

    info!("UDP multicast socket ready on port {}", MULTICAST_PORT);

    match role {
        Role::Sender => run_sender(&sock)?,
        Role::Receiver => run_receiver(&sock)?,
    }

    Ok(())
}
