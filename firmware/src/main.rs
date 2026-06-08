/// Koe Device firmware — ESP32-S3 + ES8388 audio codec.
///
/// 2つの動作モード (NVSキー "mode" で切替):
///
///   "coin"  — Koe COIN: 双方向 (送信+受信), フェス・ステージ向け
///              Mic → ADPCM → UDP 239.42.42.1:4242
///              UDP 4242 → ADPCM → ES8388 DAC → スピーカー
///
///   "guide" — Koe GUIDE: 受信専用, 低消費電力, イヤホン向け
///              UDP 4242 → ADPCM → ES8388 DAC → 3.5mmジャック
///              WiFiモデムスリープ + CPU 80MHz → 約20mA → 500mAhで25時間
///
/// ピン配置:
///   I2S BCLK=14, WS=15, DOUT=25, DIN=32
///   ES8388 SDA=18, SCL=23
///   Amp/Jack SD=21, Button=33, LED=2

mod audio;
mod es8388;
mod led;
mod network;
mod ota;
mod power;

use std::net::{Ipv4Addr, SocketAddrV4, UdpSocket};
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use esp_idf_hal::gpio::PinDriver;
use esp_idf_hal::i2c::{I2cConfig, I2cDriver};
use esp_idf_hal::i2s::{
    config::{Config, DataBitWidth, Role, SlotMode, StdConfig},
    I2sDriver,
};
use esp_idf_hal::peripherals::Peripherals;
use esp_idf_hal::units::Hertz;
use esp_idf_svc::eventloop::EspSystemEventLoop;
use esp_idf_svc::nvs::EspDefaultNvsPartition;
use log::{info, warn};

use crate::audio::{AdpcmDecoder, AdpcmEncoder};
use crate::es8388::{AdcInput, Es8388, Volume};
use crate::led::Led;
use crate::network::{connect_wifi, sync_ntp};
use crate::ota::check_ota;
use crate::power::DeviceMode;

const SOLUNA_MAGIC: [u8; 2] = [0x53, 0x4C];
const SOLUNA_MCAST: &str = "239.42.42.1";
const SOLUNA_PORT: u16 = 4242;
const SOLUNA_HEADER: usize = 19;
const FLAG_PCM16: u8 = 0x02;   // raw PCM (低遅延モード)
const FLAG_ADPCM: u8 = 0x01;   // ADPCM (後方互換)
const FLAG_HEARTBEAT: u8 = 0x04;

// ---- レイテンシー最適化パラメータ ----
//
// 128サンプル @ 48kHz = 2.67ms/パケット  (デフォルト、hubと互換)
//  32サンプル @ 48kHz = 0.67ms/パケット  (低遅延モード、-2ms)
//
// `low_latency` featureでコンパイル時切替:
//   cargo build --release --features low_latency
#[cfg(feature = "low_latency")]
const SAMPLES_PER_PACKET: usize = 32;
#[cfg(not(feature = "low_latency"))]
const SAMPLES_PER_PACKET: usize = 128;

fn main() -> anyhow::Result<()> {
    esp_idf_svc::sys::link_patches();
    esp_idf_svc::log::EspLogger::initialize_default();

    let peripherals = Peripherals::take()?;
    let pins = peripherals.pins;
    let sysloop = EspSystemEventLoop::take()?;
    let nvs = EspDefaultNvsPartition::take()?;

    // モード読み込み（NVS → デフォルトは coin）
    let mode = DeviceMode::load(&nvs);
    info!("Device mode: {:?}", mode);

    // ---- ガイドモードは CPU 80MHz + WiFi モデムスリープ ----
    if mode == DeviceMode::Guide {
        power::set_cpu_80mhz();
        info!("Guide mode: CPU 80MHz, modem sleep enabled");
    }

    // ---- スピーカー/ジャックアンプ: 初期化中はミュート ----
    let mut amp_sd = PinDriver::output(pins.gpio21)?;
    amp_sd.set_low()?;

    // ---- LED ----
    let led = Arc::new(Led::new(pins.gpio2)?);
    led.set_color(0, 0, 50)?; // 青 = 起動中

    // ---- ES8388 初期化 ----
    let i2c_cfg = I2cConfig::new().baudrate(Hertz(400_000));
    let i2c = I2cDriver::new(peripherals.i2c0, pins.gpio18, pins.gpio23, &i2c_cfg)?;
    let mut codec = Es8388::new(i2c);
    // GUIDE: イヤホン出力のみ / COIN: マイク入力も有効
    let adc_input = if mode == DeviceMode::Guide {
        AdcInput::SingleEnded // 受信専用: ADCほぼ不使用
    } else {
        AdcInput::MicBias // 送信あり: エレクトレットマイク
    };
    codec.init(adc_input)?;
    codec.set_volume(Volume::FULL)?;
    info!("ES8388 ready ({:?})", adc_input);

    // ---- I2S (双方向, ESP32がマスター) ----
    let i2s_cfg = Config::new()
        .role(Role::Master)
        .sample_rate(Hertz(48_000))
        .data_bit_width(DataBitWidth::Bits16)
        .slot_mode(SlotMode::Stereo);
    let std_cfg = StdConfig::philips(i2s_cfg);
    let i2s = Arc::new(I2sDriver::new_std_bidir(
        peripherals.i2s0,
        &std_cfg,
        pins.gpio14, // BCLK
        pins.gpio25, // DOUT → ES8388 DAC → イヤホン/スピーカー
        pins.gpio32, // DIN  ← ES8388 ADC ← マイク
        pins.gpio15, // WS
    )?);

    // ---- WiFi ----
    led.set_color(0, 50, 50)?; // シアン = 接続中
    let _wifi = connect_wifi(peripherals.modem, sysloop, nvs.clone(), mode)?;
    info!("WiFi connected");

    // ガイドモード: WiFiモデムスリープ有効化（アクティブ受信時のみRF起動・平均電流↓）
    if mode == DeviceMode::Guide {
        power::enable_modem_sleep();
    }

    // ---- NTP ----
    sync_ntp()?;

    // ---- OTA ----
    let device_id = network::device_id();
    check_ota(device_id).unwrap_or_else(|e| warn!("OTA: {}", e));

    // ---- アンプ有効化 ----
    amp_sd.set_high()?;
    led.set_color(0, 50, 0)?; // 緑 = 準備完了

    info!("Koe ready — id=0x{:08x} mode={:?}", device_id, mode);

    // ============================================================
    // RX タスク (全モード共通): 受信 → ADPCM decode → I2S DAC
    // ============================================================
    {
        let i2s_rx = Arc::clone(&i2s);
        let led_rx = Arc::clone(&led);

        thread::Builder::new()
            .stack_size(8192)
            .name("koe-rx".into())
            .spawn(move || {
                let socket =
                    UdpSocket::bind(SocketAddrV4::new(Ipv4Addr::UNSPECIFIED, SOLUNA_PORT))
                        .expect("bind rx");
                socket
                    .join_multicast_v4(
                        &SOLUNA_MCAST.parse::<Ipv4Addr>().unwrap(),
                        &Ipv4Addr::UNSPECIFIED,
                    )
                    .ok();
                socket.set_read_timeout(Some(Duration::from_millis(500))).ok();

                // WiFi QoS: 音声トラフィックを AC_VO キューへ (jitter -3〜5ms)
                // DSCP EF (0x2E) = Expedited Forwarding = 最高優先度
                set_socket_qos(&socket, 0xB8); // DSCP EF = 46 << 2 = 0xB8

                let mut buf = [0u8; 512];
                let mut decoder = AdpcmDecoder::new();

                loop {
                    let (len, _) = match socket.recv_from(&mut buf) {
                        Ok(r) => r,
                        Err(_) => continue,
                    };
                    if len < SOLUNA_HEADER + 1 || buf[0..2] != SOLUNA_MAGIC { continue; }

                    let flags = buf[18];
                    let src_id = u32::from_le_bytes([buf[2], buf[3], buf[4], buf[5]]);
                    if flags & FLAG_HEARTBEAT != 0 { continue; }
                    if mode != DeviceMode::Guide && src_id == device_id { continue; }

                    let audio_data = &buf[SOLUNA_HEADER..len];

                    // raw PCM (低遅延) と ADPCM の両方を受信
                    let mono: Vec<i16> = if flags & FLAG_PCM16 != 0 {
                        // raw PCM16 LE: encode/decodeなし → -2ms
                        audio_data.chunks_exact(2)
                            .map(|c| i16::from_le_bytes([c[0], c[1]]))
                            .collect()
                    } else {
                        decoder.decode(audio_data)
                    };

                    let stereo: Vec<i16> = mono.iter().flat_map(|&s| [s, s]).collect();
                    if let Err(e) = i2s_rx.write_i16(&stereo, 50) {
                        warn!("I2S write: {}", e);
                    }

                    if mode == DeviceMode::Guide {
                        led_rx.set_color(0, 0, 100).ok();
                    }
                }
            })?;
    }

    // ============================================================
    // TX タスク (COIN モードのみ): マイク → ADPCM → UDP送信
    // ============================================================
    if mode == DeviceMode::Coin {
        let i2s_tx = Arc::clone(&i2s);
        let led_tx = Arc::clone(&led);
        let seq = Arc::new(AtomicU32::new(0));
        let recording = Arc::new(AtomicBool::new(true));

        // ボタン長押しで録音ON/OFF
        {
            let rec = Arc::clone(&recording);
            let led_b = Arc::clone(&led_tx);
            thread::Builder::new()
                .stack_size(4096)
                .name("koe-btn".into())
                .spawn(move || {
                    let btn = PinDriver::input(unsafe {
                        esp_idf_hal::gpio::AnyInputPin::new(33)
                    }).expect("btn");
                    let mut prev = false;
                    loop {
                        let pressed = btn.is_low();
                        if pressed && !prev {
                            let r = !rec.load(Ordering::Relaxed);
                            rec.store(r, Ordering::Relaxed);
                            led_b.set_color(if r { 0 } else { 50 }, if r { 50 } else { 0 }, 0).ok();
                        }
                        prev = pressed;
                        thread::sleep(Duration::from_millis(20));
                    }
                })?;
        }

        let seq_tx = Arc::clone(&seq);
        let rec_tx = Arc::clone(&recording);
        thread::Builder::new()
            .stack_size(8192)
            .name("koe-tx".into())
            .spawn(move || {
                let socket = UdpSocket::bind("0.0.0.0:0").expect("bind tx");
                let dest = SocketAddrV4::new(
                    SOLUNA_MCAST.parse::<Ipv4Addr>().unwrap(), SOLUNA_PORT,
                );
                socket.set_multicast_ttl_v4(4).ok();
                // WiFi QoS: 送信側も AC_VO へ
                set_socket_qos(&socket, 0xB8);

                #[cfg(not(feature = "low_latency"))]
                let mut encoder = AdpcmEncoder::new();
                let mut rx_buf = [0i16; SAMPLES_PER_PACKET * 2];

                loop {
                    if !rec_tx.load(Ordering::Relaxed) {
                        thread::sleep(Duration::from_millis(10));
                        continue;
                    }
                    if i2s_tx.read_i16(&mut rx_buf, 100).is_err() { continue; }

                    let mono: Vec<i16> = rx_buf.chunks_exact(2)
                        .map(|p| ((p[0] as i32 + p[1] as i32) / 2) as i16)
                        .collect();

                    let s = seq_tx.fetch_add(1, Ordering::Relaxed);
                    let ntp = network::ntp_ms() as u32;

                    // low_latency: raw PCM16 (encode/decodeなし, -2ms)
                    // 通常:        ADPCM (hubと後方互換)
                    #[cfg(feature = "low_latency")]
                    let (audio_bytes, flag): (Vec<u8>, u8) = {
                        let bytes: Vec<u8> = mono.iter()
                            .flat_map(|&s| s.to_le_bytes())
                            .collect();
                        (bytes, FLAG_PCM16)
                    };
                    #[cfg(not(feature = "low_latency"))]
                    let (audio_bytes, flag): (Vec<u8>, u8) = {
                        (encoder.encode(&mono), FLAG_ADPCM)
                    };

                    let mut pkt = Vec::with_capacity(SOLUNA_HEADER + audio_bytes.len());
                    pkt.extend_from_slice(&SOLUNA_MAGIC);
                    pkt.extend_from_slice(&device_id.to_le_bytes());
                    pkt.extend_from_slice(&s.to_le_bytes());
                    pkt.extend_from_slice(&0u32.to_le_bytes());
                    pkt.extend_from_slice(&ntp.to_le_bytes());
                    pkt.push(flag);
                    pkt.extend_from_slice(&audio_bytes);
                    socket.send_to(&pkt, dest).ok();

                    let peak = mono.iter().map(|&s| s.unsigned_abs()).max().unwrap_or(0);
                    led_tx.set_color(0, (peak >> 8).min(50) as u8, 0).ok();
                }
            })?;

        // ハートビート (COIN のみ)
        let seq_hb = Arc::clone(&seq);
        thread::Builder::new()
            .stack_size(4096)
            .name("koe-hb".into())
            .spawn(move || {
                let sock = UdpSocket::bind("0.0.0.0:0").unwrap();
                let dest = SocketAddrV4::new(
                    SOLUNA_MCAST.parse::<Ipv4Addr>().unwrap(), SOLUNA_PORT,
                );
                loop {
                    thread::sleep(Duration::from_secs(5));
                    let s = seq_hb.fetch_add(1, Ordering::Relaxed);
                    let mut pkt = [0u8; SOLUNA_HEADER];
                    pkt[0..2].copy_from_slice(&SOLUNA_MAGIC);
                    pkt[2..6].copy_from_slice(&device_id.to_le_bytes());
                    pkt[6..10].copy_from_slice(&s.to_le_bytes());
                    pkt[18] = FLAG_HEARTBEAT;
                    sock.send_to(&pkt, dest).ok();
                }
            })?;
    }

    // ガイドモード: LED を暗くして待機
    if mode == DeviceMode::Guide {
        led.set_color(0, 0, 10)?;
    }

    loop {
        thread::sleep(Duration::from_secs(60));
    }
}

/// UDP ソケットに WiFi QoS (DSCP) を設定する。
/// tos=0xB8 → DSCP EF(46) → WiFi AC_VO キュー → jitter -3〜5ms。
fn set_socket_qos(socket: &UdpSocket, tos: u8) {
    use std::os::unix::io::AsRawFd;
    unsafe {
        libc::setsockopt(
            socket.as_raw_fd(),
            libc::IPPROTO_IP,
            libc::IP_TOS,
            &(tos as libc::c_int) as *const _ as *const libc::c_void,
            std::mem::size_of::<libc::c_int>() as libc::socklen_t,
        );
    }
}

mod libc {
    pub use core::ffi::c_void;
    pub type c_int = i32;
    pub type socklen_t = u32;
    pub const IPPROTO_IP: c_int = 0;
    pub const IP_TOS: c_int = 1;
    extern "C" {
        pub fn setsockopt(
            sockfd: c_int, level: c_int, optname: c_int,
            optval: *const c_void, optlen: socklen_t,
        ) -> c_int;
    }
}
