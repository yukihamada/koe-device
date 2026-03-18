// Soluna — 超軽量デバイス間音声同期プロトコル
// ゼロサーバーでLAN内のデバイスが自動同期して同じ音を出す
//
// プロトコル: UDP マルチキャスト (239.42.42.1:4242)
// パケット: [magic 2B][seq 4B][channel_hash 4B][timestamp 4B][audio PCM]
// 発見: mDNS _soluna._udp.local
// 合計オーバーヘッド: 14 bytes/packet

use log::*;
use std::sync::atomic::{AtomicBool, AtomicU8, Ordering};

// --- プロトコル定数 ---
const MULTICAST_ADDR: &str = "239.42.42.1";
const MULTICAST_PORT: u16 = 4242;
const MAGIC: [u8; 2] = [0x53, 0x4C]; // "SL"
const HEADER_SIZE: usize = 14; // magic(2) + seq(4) + channel(4) + timestamp(4)
const MAX_AUDIO_PER_PACKET: usize = 1024; // 512 samples = 32ms @ 16kHz
const PACKET_BUF_SIZE: usize = HEADER_SIZE + MAX_AUDIO_PER_PACKET;

// ジッタバッファ: 3パケット分 (96ms) — 同期精度とレイテンシのバランス
const JITTER_SLOTS: usize = 4;
const JITTER_BUF_SIZE: usize = MAX_AUDIO_PER_PACKET * JITTER_SLOTS;

// グローバル状態
static SOLUNA_ACTIVE: AtomicBool = AtomicBool::new(false);
static PEER_COUNT: AtomicU8 = AtomicU8::new(0);

#[inline]
pub fn is_active() -> bool {
    SOLUNA_ACTIVE.load(Ordering::Relaxed)
}

#[inline]
pub fn peer_count() -> u8 {
    PEER_COUNT.load(Ordering::Relaxed)
}

pub fn set_active(active: bool) {
    SOLUNA_ACTIVE.store(active, Ordering::Relaxed);
}

/// チャンネル名→4バイトハッシュ (FNV-1a 32bit, 軽量)
#[inline]
fn channel_hash(name: &str) -> u32 {
    let mut h: u32 = 0x811c9dc5;
    for b in name.bytes() {
        h ^= b as u32;
        h = h.wrapping_mul(0x01000193);
    }
    h
}

/// パケットヘッダを構築 (スタックバッファに書き込み、ゼロアロケーション)
#[inline]
fn write_header(buf: &mut [u8], seq: u32, ch_hash: u32, timestamp: u32) {
    buf[0..2].copy_from_slice(&MAGIC);
    buf[2..6].copy_from_slice(&seq.to_le_bytes());
    buf[6..10].copy_from_slice(&ch_hash.to_le_bytes());
    buf[10..14].copy_from_slice(&timestamp.to_le_bytes());
}

/// ヘッダをパース (有効なSolunaパケットならSome)
#[inline]
fn parse_header(buf: &[u8]) -> Option<(u32, u32, u32)> {
    if buf.len() < HEADER_SIZE || buf[0] != MAGIC[0] || buf[1] != MAGIC[1] {
        return None;
    }
    let seq = u32::from_le_bytes([buf[2], buf[3], buf[4], buf[5]]);
    let ch = u32::from_le_bytes([buf[6], buf[7], buf[8], buf[9]]);
    let ts = u32::from_le_bytes([buf[10], buf[11], buf[12], buf[13]]);
    Some((seq, ch, ts))
}

// --- ジッタバッファ (リングバッファ、ゼロアロケーション) ---
pub struct JitterBuffer {
    buf: [u8; JITTER_BUF_SIZE],
    write_pos: usize,
    read_pos: usize,
    len: usize,
}

impl JitterBuffer {
    pub const fn new() -> Self {
        Self {
            buf: [0u8; JITTER_BUF_SIZE],
            write_pos: 0,
            read_pos: 0,
            len: 0,
        }
    }

    /// 音声データをバッファに追加
    #[inline]
    pub fn push(&mut self, audio: &[u8]) {
        let avail = JITTER_BUF_SIZE - self.len;
        let to_write = audio.len().min(avail);
        if to_write == 0 { return; } // バッファフル → 古いデータを捨てる方が良いが、シンプルに無視

        for i in 0..to_write {
            self.buf[self.write_pos] = audio[i];
            self.write_pos = (self.write_pos + 1) % JITTER_BUF_SIZE;
        }
        self.len += to_write;
    }

    /// 再生用にデータを読み出し
    #[inline]
    pub fn pop(&mut self, out: &mut [u8]) -> usize {
        let to_read = out.len().min(self.len);
        for i in 0..to_read {
            out[i] = self.buf[self.read_pos];
            self.read_pos = (self.read_pos + 1) % JITTER_BUF_SIZE;
        }
        self.len -= to_read;
        to_read
    }

    #[inline]
    pub fn available(&self) -> usize {
        self.len
    }

    pub fn clear(&mut self) {
        self.write_pos = 0;
        self.read_pos = 0;
        self.len = 0;
    }
}

// --- Soluna ノード ---
pub struct SolunaNode {
    channel_name: [u8; 32], // 固定長バッファ、Stringアロケーション回避
    channel_len: usize,
    ch_hash: u32,
    seq: u32,
    pub jitter: JitterBuffer,
    // ピア管理: 最大8台、IPではなくdevice_hashで識別
    peers: [u32; 8],
    peer_last_seen: [u32; 8], // タイムスタンプ (秒)
}

impl SolunaNode {
    pub fn new(channel: &str) -> Self {
        let mut name = [0u8; 32];
        let len = channel.len().min(32);
        name[..len].copy_from_slice(&channel.as_bytes()[..len]);

        Self {
            channel_name: name,
            channel_len: len,
            ch_hash: channel_hash(channel),
            seq: 0,
            jitter: JitterBuffer::new(),
            peers: [0u32; 8],
            peer_last_seen: [0u32; 8],
        }
    }

    pub fn channel(&self) -> &str {
        core::str::from_utf8(&self.channel_name[..self.channel_len]).unwrap_or("soluna")
    }

    /// 送信パケット構築 (ゼロアロケーション)
    pub fn build_packet(&mut self, audio: &[u8], out: &mut [u8; PACKET_BUF_SIZE]) -> usize {
        let audio_len = audio.len().min(MAX_AUDIO_PER_PACKET);
        let ts = unsafe { (esp_idf_sys::esp_timer_get_time() / 1000) as u32 }; // ms
        write_header(out, self.seq, self.ch_hash, ts);
        out[HEADER_SIZE..HEADER_SIZE + audio_len].copy_from_slice(&audio[..audio_len]);
        self.seq = self.seq.wrapping_add(1);
        HEADER_SIZE + audio_len
    }

    /// 受信パケット処理 — 同じチャンネルのみ受け入れ
    pub fn handle_packet(&mut self, packet: &[u8]) -> bool {
        let (seq, ch, _ts) = match parse_header(packet) {
            Some(v) => v,
            None => return false,
        };

        // チャンネル不一致 → 無視
        if ch != self.ch_hash {
            return false;
        }

        // ピア登録
        let now = unsafe { (esp_idf_sys::esp_timer_get_time() / 1_000_000) as u32 };
        self.register_peer(seq, now);

        // 音声データをジッタバッファに投入
        let audio = &packet[HEADER_SIZE..];
        if !audio.is_empty() {
            self.jitter.push(audio);
        }

        true
    }

    fn register_peer(&mut self, peer_hash: u32, now: u32) {
        // 既存ピアなら更新
        for i in 0..8 {
            if self.peers[i] == peer_hash {
                self.peer_last_seen[i] = now;
                return;
            }
        }
        // 新規 or 期限切れスロットに追加
        for i in 0..8 {
            if self.peers[i] == 0 || now.wrapping_sub(self.peer_last_seen[i]) > 30 {
                self.peers[i] = peer_hash;
                self.peer_last_seen[i] = now;
                // ピアカウント更新
                let count = self.peers.iter().filter(|&&p| {
                    p != 0 && now.wrapping_sub(self.peer_last_seen[
                        self.peers.iter().position(|&x| x == p).unwrap_or(0)
                    ]) <= 30
                }).count();
                PEER_COUNT.store(count as u8, Ordering::Relaxed);
                info!("Peer +1 (total: {})", count);
                return;
            }
        }
    }

    pub fn set_channel(&mut self, channel: &str) {
        let len = channel.len().min(32);
        self.channel_name[..len].copy_from_slice(&channel.as_bytes()[..len]);
        self.channel_len = len;
        self.ch_hash = channel_hash(channel);
        self.seq = 0;
        self.jitter.clear();
        self.peers = [0u32; 8];
        PEER_COUNT.store(0, Ordering::Relaxed);
        info!("Channel: {}", channel);
    }
}

// --- UDP送受信タスク ---

/// Soluna受信タスク — 別スレッドで常時動作
pub fn rx_task(node: &'static std::sync::Mutex<SolunaNode>) {
    use std::net::UdpSocket;

    let socket = match UdpSocket::bind(format!("0.0.0.0:{}", MULTICAST_PORT)) {
        Ok(s) => s,
        Err(e) => {
            error!("UDP bind: {:?}", e);
            return;
        }
    };

    // マルチキャストグループ参加
    if let Err(e) = socket.join_multicast_v4(
        &MULTICAST_ADDR.parse().unwrap(),
        &std::net::Ipv4Addr::UNSPECIFIED,
    ) {
        error!("Multicast join: {:?}", e);
        return;
    }

    let _ = socket.set_read_timeout(Some(std::time::Duration::from_millis(100)));

    let mut buf = [0u8; PACKET_BUF_SIZE];
    info!("Soluna RX on :{}", MULTICAST_PORT);

    loop {
        if !SOLUNA_ACTIVE.load(Ordering::Relaxed) {
            std::thread::sleep(std::time::Duration::from_millis(200));
            continue;
        }

        match socket.recv_from(&mut buf) {
            Ok((n, _addr)) => {
                if let Ok(mut node) = node.lock() {
                    node.handle_packet(&buf[..n]);
                }
            }
            Err(_) => {} // タイムアウト → 正常
        }
    }
}

/// マイクからの音声をマルチキャスト送信
pub fn tx_audio(
    node: &std::sync::Mutex<SolunaNode>,
    socket: &std::net::UdpSocket,
    audio: &[u8],
) {
    if !SOLUNA_ACTIVE.load(Ordering::Relaxed) {
        return;
    }

    let mut packet = [0u8; PACKET_BUF_SIZE];
    let len = if let Ok(mut node) = node.lock() {
        node.build_packet(audio, &mut packet)
    } else {
        return;
    };

    let dest = format!("{}:{}", MULTICAST_ADDR, MULTICAST_PORT);
    let _ = socket.send_to(&packet[..len], &dest);
}

/// mDNS登録 — _soluna._udp.local で自動発見可能にする
pub fn register_mdns(device_id: &str) -> Result<(), Box<dyn std::error::Error>> {
    unsafe {
        let hostname = std::ffi::CString::new(device_id)?;
        let instance = std::ffi::CString::new("Soluna Device")?;
        let service_type = std::ffi::CString::new("_soluna")?;
        let proto = std::ffi::CString::new("_udp")?;

        esp_idf_sys::mdns_init();
        esp_idf_sys::mdns_hostname_set(hostname.as_ptr());
        esp_idf_sys::mdns_instance_name_set(instance.as_ptr());
        esp_idf_sys::mdns_service_add(
            instance.as_ptr(),
            service_type.as_ptr(),
            proto.as_ptr(),
            MULTICAST_PORT,
            core::ptr::null_mut(),
            0,
        );
    }
    info!("mDNS: {}.local _soluna._udp", device_id);
    Ok(())
}
