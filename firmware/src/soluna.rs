// Soluna v2 — 超軽量デバイス間音声同期プロトコル
// UDP マルチキャスト + IMA-ADPCM 4:1圧縮 + オーディオミキシング + SNTP同期
//
// パケット: [magic 2B][device_id 4B][seq 4B][channel 4B][ntp_ms 4B][flags 1B][audio ADPCM]
// ヘッダ: 19 bytes
// 圧縮: IMA-ADPCM (16bit PCM → 4bit = 75%帯域削減)

use log::*;
use std::sync::atomic::{AtomicBool, AtomicU8, AtomicU32, Ordering};
use std::net::SocketAddrV4;

// --- プロトコル定数 ---
const MULTICAST_ADDR: [u8; 4] = [239, 42, 42, 1];
const MULTICAST_PORT: u16 = 4242;
const MAGIC: [u8; 2] = [0x53, 0x4C]; // "SL"
const HEADER_SIZE: usize = 19;
const MAX_AUDIO_PER_PACKET: usize = 512; // ADPCM圧縮後 = 1024 PCM samples = 64ms
const PACKET_BUF_SIZE: usize = HEADER_SIZE + MAX_AUDIO_PER_PACKET;

// フラグ
const FLAG_ADPCM: u8 = 0x01;
const FLAG_ENCRYPTED: u8 = 0x02;
const FLAG_HEARTBEAT: u8 = 0x04;

// Heartbeat間隔
const HEARTBEAT_INTERVAL_MS: u64 = 5_000;
// ピアタイムアウト (Heartbeatベース)
const PEER_TIMEOUT_SEC: u32 = 10;

// ジッタバッファ: 8スロット (512ms分、ミキシング対応で大きめ)
const JITTER_BUF_SIZE: usize = MAX_AUDIO_PER_PACKET * 8;

// 送信先アドレス (format!回避、起動時に1回だけ構築)
static DEST_ADDR: SocketAddrV4 = SocketAddrV4::new(
    std::net::Ipv4Addr::new(239, 42, 42, 1),
    MULTICAST_PORT,
);

// グローバル状態
static SOLUNA_ACTIVE: AtomicBool = AtomicBool::new(false);
static PEER_COUNT: AtomicU8 = AtomicU8::new(0);
static OWN_DEVICE_HASH: AtomicU32 = AtomicU32::new(0);
// SNTP同期オフセット (ms): デバイスローカル時刻 + offset = NTP時刻
static NTP_OFFSET_MS: AtomicU32 = AtomicU32::new(0);

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

pub fn set_own_device_hash(hash: u32) {
    OWN_DEVICE_HASH.store(hash, Ordering::Relaxed);
}

/// NTPオフセット設定 (sntp_task から呼ばれる)
pub fn set_ntp_offset(offset_ms: u32) {
    NTP_OFFSET_MS.store(offset_ms, Ordering::Relaxed);
}

/// 現在のNTP同期済みタイムスタンプ (ms)
#[inline]
fn ntp_now_ms() -> u32 {
    let local_ms = unsafe { (esp_idf_sys::esp_timer_get_time() / 1000) as u32 };
    local_ms.wrapping_add(NTP_OFFSET_MS.load(Ordering::Relaxed))
}

/// FNV-1a 32bit ハッシュ
#[inline]
pub fn fnv1a(data: &[u8]) -> u32 {
    let mut h: u32 = 0x811c9dc5;
    for &b in data {
        h ^= b as u32;
        h = h.wrapping_mul(0x01000193);
    }
    h
}

// =====================================================
// IMA-ADPCM コーデック (4:1 圧縮、ゼロアロケーション)
// =====================================================

const STEP_TABLE: [i16; 89] = [
    7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
    34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
    157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544,
    598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707,
    1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871,
    5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635,
    13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
];

const INDEX_TABLE: [i8; 16] = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8];

#[derive(Clone, Copy)]
pub struct AdpcmState {
    pub predicted: i16,
    pub step_index: u8,
}

impl AdpcmState {
    pub const fn new() -> Self {
        Self { predicted: 0, step_index: 0 }
    }
}

/// PCM i16 → ADPCM 4bit (2サンプル/バイト)
/// 入力: PCMバイト列 (little-endian i16)
/// 出力: ADPCMバイト列 (入力の1/4サイズ)
#[inline]
pub fn adpcm_encode(pcm: &[u8], out: &mut [u8], state: &mut AdpcmState) -> usize {
    let n_samples = pcm.len() / 2;
    let out_len = (n_samples + 1) / 2;
    if out.len() < out_len { return 0; }

    let mut out_idx = 0;
    let mut nibble_hi = false;

    let mut i = 0;
    while i + 1 < pcm.len() {
        let sample = i16::from_le_bytes([pcm[i], pcm[i + 1]]);
        let step = STEP_TABLE[state.step_index as usize] as i32;

        let mut diff = sample as i32 - state.predicted as i32;
        let mut code: u8 = 0;
        if diff < 0 {
            code = 8;
            diff = -diff;
        }

        if diff >= step { code |= 4; diff -= step; }
        if diff >= step >> 1 { code |= 2; diff -= step >> 1; }
        if diff >= step >> 2 { code |= 1; }

        // デコードして予測値更新 (エンコーダ内蔵デコーダ)
        let mut delta = step >> 3;
        if code & 4 != 0 { delta += step; }
        if code & 2 != 0 { delta += step >> 1; }
        if code & 1 != 0 { delta += step >> 2; }
        if code & 8 != 0 { delta = -delta; }

        state.predicted = (state.predicted as i32 + delta).clamp(-32768, 32767) as i16;

        let new_idx = (state.step_index as i8 + INDEX_TABLE[code as usize]).clamp(0, 88);
        state.step_index = new_idx as u8;

        if nibble_hi {
            out[out_idx] |= code << 4;
            out_idx += 1;
        } else {
            out[out_idx] = code & 0x0F;
        }
        nibble_hi = !nibble_hi;

        i += 2;
    }

    out_len
}

/// ADPCM 4bit → PCM i16
#[inline]
pub fn adpcm_decode(adpcm: &[u8], out: &mut [u8], state: &mut AdpcmState) -> usize {
    let n_samples = adpcm.len() * 2;
    let out_len = n_samples * 2; // i16 = 2 bytes
    if out.len() < out_len { return 0; }

    let mut out_idx = 0;
    for &byte in adpcm {
        for nibble_idx in 0..2u8 {
            let code = if nibble_idx == 0 { byte & 0x0F } else { byte >> 4 };
            let step = STEP_TABLE[state.step_index as usize] as i32;

            let mut delta = step >> 3;
            if code & 4 != 0 { delta += step; }
            if code & 2 != 0 { delta += step >> 1; }
            if code & 1 != 0 { delta += step >> 2; }
            if code & 8 != 0 { delta = -delta; }

            state.predicted = (state.predicted as i32 + delta).clamp(-32768, 32767) as i16;

            let new_idx = (state.step_index as i8 + INDEX_TABLE[code as usize]).clamp(0, 88);
            state.step_index = new_idx as u8;

            let bytes = state.predicted.to_le_bytes();
            out[out_idx] = bytes[0];
            out[out_idx + 1] = bytes[1];
            out_idx += 2;
        }
    }

    out_len
}

// =====================================================
// ジッタバッファ (リング、オーバーフロー時は古いデータ上書き)
// =====================================================

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

    /// 音声データ追加 — バッファフル時は古いデータを上書き
    #[inline]
    pub fn push(&mut self, audio: &[u8]) {
        for &byte in audio {
            if self.len == JITTER_BUF_SIZE {
                // 満杯: read_posを進めて古いデータを捨てる
                self.read_pos = (self.read_pos + 1) % JITTER_BUF_SIZE;
                self.len -= 1;
            }
            self.buf[self.write_pos] = byte;
            self.write_pos = (self.write_pos + 1) % JITTER_BUF_SIZE;
            self.len += 1;
        }
    }

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

// =====================================================
// オーディオミキサー (複数ピアの音声を加算合成)
// =====================================================

/// PCMバイト列を加算ミキシング (飽和加算、クリッピング防止)
#[inline]
pub fn mix_audio(dst: &mut [u8], src: &[u8]) {
    let len = dst.len().min(src.len());
    let mut i = 0;
    while i + 1 < len {
        let a = i16::from_le_bytes([dst[i], dst[i + 1]]) as i32;
        let b = i16::from_le_bytes([src[i], src[i + 1]]) as i32;
        let mixed = (a + b).clamp(-32768, 32767) as i16;
        let bytes = mixed.to_le_bytes();
        dst[i] = bytes[0];
        dst[i + 1] = bytes[1];
        i += 2;
    }
}

// =====================================================
// Soluna ノード
// =====================================================

// プリセットチャンネル (ダブルタップで巡回)
pub const CHANNELS: &[&str] = &["soluna", "voice", "music", "ambient"];

pub struct SolunaNode {
    channel_name: [u8; 32],
    channel_len: usize,
    ch_hash: u32,
    device_hash: u32,
    seq: u32,
    pub jitter: JitterBuffer,
    encode_state: AdpcmState,
    decode_state: AdpcmState,
    // ピア管理
    peers: [u32; 8],
    peer_last_seen: [u32; 8],
    peer_decode_state: [AdpcmState; 8],
    // PLC (パケットロス補間)
    last_good_frame: [u8; 2048],
    last_good_len: usize,
    expected_seq: [u32; 8], // ピアごとの次期待seq
    channel_index: usize,  // 現在のチャンネルインデックス
}

impl SolunaNode {
    pub fn new(channel: &str, device_hash: u32) -> Self {
        let mut name = [0u8; 32];
        let len = channel.len().min(32);
        name[..len].copy_from_slice(&channel.as_bytes()[..len]);
        let ch_idx = CHANNELS.iter().position(|&c| c == channel).unwrap_or(0);

        Self {
            channel_name: name,
            channel_len: len,
            ch_hash: fnv1a(channel.as_bytes()),
            device_hash,
            seq: 0,
            jitter: JitterBuffer::new(),
            encode_state: AdpcmState::new(),
            decode_state: AdpcmState::new(),
            peers: [0u32; 8],
            peer_last_seen: [0u32; 8],
            peer_decode_state: [AdpcmState::new(); 8],
            last_good_frame: [0u8; 2048],
            last_good_len: 0,
            expected_seq: [0u32; 8],
            channel_index: ch_idx,
        }
    }

    /// 送信パケット構築 (PCM → ADPCM圧縮 → パケット)
    pub fn build_packet(&mut self, pcm_audio: &[u8], out: &mut [u8; PACKET_BUF_SIZE]) -> usize {
        // ヘッダ
        out[0..2].copy_from_slice(&MAGIC);
        out[2..6].copy_from_slice(&self.device_hash.to_le_bytes());
        out[6..10].copy_from_slice(&self.seq.to_le_bytes());
        out[10..14].copy_from_slice(&self.ch_hash.to_le_bytes());
        out[14..18].copy_from_slice(&ntp_now_ms().to_le_bytes());
        out[18] = FLAG_ADPCM;

        // ADPCM エンコード
        let adpcm_len = adpcm_encode(
            pcm_audio,
            &mut out[HEADER_SIZE..],
            &mut self.encode_state,
        );

        self.seq = self.seq.wrapping_add(1);
        HEADER_SIZE + adpcm_len
    }

    /// 受信パケット処理 — 自分のパケットはフィルタ
    pub fn handle_packet(&mut self, packet: &[u8]) -> bool {
        if packet.len() < HEADER_SIZE || packet[0] != MAGIC[0] || packet[1] != MAGIC[1] {
            return false;
        }

        let sender_hash = u32::from_le_bytes([packet[2], packet[3], packet[4], packet[5]]);
        let ch = u32::from_le_bytes([packet[10], packet[11], packet[12], packet[13]]);

        // 自分自身のパケット → フィルタ (エコー防止)
        if sender_hash == self.device_hash {
            return false;
        }

        // チャンネル不一致 → 無視
        if ch != self.ch_hash {
            return false;
        }

        let flags = packet[18];

        // Heartbeatパケット: ピア存在だけ更新、音声なし
        if flags & FLAG_HEARTBEAT != 0 {
            let now = unsafe { (esp_idf_sys::esp_timer_get_time() / 1_000_000) as u32 };
            self.register_peer(sender_hash, now);
            return true;
        }

        let audio_data = &packet[HEADER_SIZE..];
        if audio_data.is_empty() {
            return false;
        }

        // ピア登録 & デコードstate取得
        let now = unsafe { (esp_idf_sys::esp_timer_get_time() / 1_000_000) as u32 };
        let peer_idx = self.register_peer(sender_hash, now);

        let recv_seq = u32::from_le_bytes([packet[6], packet[7], packet[8], packet[9]]);

        // ADPCM デコード → PCM
        if flags & FLAG_ADPCM != 0 {
            let decode_state = if let Some(idx) = peer_idx {
                // PLC: seqギャップ検出 → 前フレームをリピート
                let expected = self.expected_seq[idx];
                if expected > 0 && recv_seq > expected {
                    let gap = (recv_seq - expected) as usize;
                    if gap <= 3 && self.last_good_len > 0 {
                        // 欠落フレーム分、前フレームを減衰リピート
                        for g in 0..gap {
                            let attenuation = 256 - (g as i32 * 64); // 段階的に減衰
                            if attenuation <= 0 { break; }
                            let mut plc_buf = [0u8; 2048];
                            let len = self.last_good_len;
                            plc_buf[..len].copy_from_slice(&self.last_good_frame[..len]);
                            // 減衰適用
                            let mut k = 0;
                            while k + 1 < len {
                                let s = i16::from_le_bytes([plc_buf[k], plc_buf[k+1]]) as i32;
                                let faded = ((s * attenuation) / 256) as i16;
                                let bytes = faded.to_le_bytes();
                                plc_buf[k] = bytes[0];
                                plc_buf[k+1] = bytes[1];
                                k += 2;
                            }
                            self.jitter.push(&plc_buf[..len]);
                        }
                    }
                }
                self.expected_seq[idx] = recv_seq + 1;
                &mut self.peer_decode_state[idx]
            } else {
                &mut self.decode_state
            };

            let mut pcm_buf = [0u8; 2048];
            let pcm_len = adpcm_decode(audio_data, &mut pcm_buf, decode_state);

            if pcm_len > 0 {
                // 正常フレームを記録 (PLC用)
                self.last_good_frame[..pcm_len].copy_from_slice(&pcm_buf[..pcm_len]);
                self.last_good_len = pcm_len;
                self.jitter.push(&pcm_buf[..pcm_len]);
            }
        } else {
            self.jitter.push(audio_data);
        }

        true
    }

    fn register_peer(&mut self, peer_hash: u32, now: u32) -> Option<usize> {
        // 既存ピア
        for i in 0..8 {
            if self.peers[i] == peer_hash {
                self.peer_last_seen[i] = now;
                return Some(i);
            }
        }
        // 新規 or 期限切れスロット
        for i in 0..8 {
            if self.peers[i] == 0 || now.wrapping_sub(self.peer_last_seen[i]) > PEER_TIMEOUT_SEC {
                self.peers[i] = peer_hash;
                self.peer_last_seen[i] = now;
                self.peer_decode_state[i] = AdpcmState::new();

                let count = self.peers.iter()
                    .zip(self.peer_last_seen.iter())
                    .filter(|(&p, &t)| p != 0 && now.wrapping_sub(t) <= PEER_TIMEOUT_SEC)
                    .count();
                PEER_COUNT.store(count as u8, Ordering::Relaxed);
                info!("Peer +1 ({})", count);
                return Some(i);
            }
        }
        None
    }

    pub fn set_channel(&mut self, channel: &str) {
        let len = channel.len().min(32);
        self.channel_name = [0u8; 32];
        self.channel_name[..len].copy_from_slice(&channel.as_bytes()[..len]);
        self.channel_len = len;
        self.ch_hash = fnv1a(channel.as_bytes());
        self.seq = 0;
        self.jitter.clear();
        self.encode_state = AdpcmState::new();
        self.decode_state = AdpcmState::new();
        self.peers = [0u32; 8];
        self.peer_decode_state = [AdpcmState::new(); 8];
        self.last_good_len = 0;
        self.expected_seq = [0u32; 8];
        self.channel_index = CHANNELS.iter().position(|&c| c == channel).unwrap_or(0);
        PEER_COUNT.store(0, Ordering::Relaxed);
        info!("Ch: {}", channel);
    }

    /// 次のチャンネルに切替 (ダブルタップ用)
    pub fn next_channel(&mut self) {
        self.channel_index = (self.channel_index + 1) % CHANNELS.len();
        let ch = CHANNELS[self.channel_index];
        self.set_channel(ch);
    }

    pub fn channel_name_str(&self) -> &str {
        core::str::from_utf8(&self.channel_name[..self.channel_len]).unwrap_or("soluna")
    }
}

// =====================================================
// SNTP 時刻同期タスク
// =====================================================

pub fn sntp_task() {
    info!("SNTP sync starting");
    unsafe {
        let server = std::ffi::CString::new("pool.ntp.org").unwrap();
        esp_idf_sys::sntp_setoperatingmode(esp_idf_sys::SNTP_OPMODE_POLL as u8);
        esp_idf_sys::sntp_setservername(0, server.as_ptr() as *mut _);
        esp_idf_sys::sntp_init();
    }

    // 同期完了を待つ (最大10秒)
    for _ in 0..100 {
        let mut tv: esp_idf_sys::timeval = unsafe { core::mem::zeroed() };
        unsafe { esp_idf_sys::gettimeofday(&mut tv, core::ptr::null_mut()) };
        if tv.tv_sec > 1_700_000_000 {
            // 有効な時刻取得成功
            let ntp_ms = (tv.tv_sec as u32).wrapping_mul(1000) + (tv.tv_usec as u32 / 1000);
            let local_ms = unsafe { (esp_idf_sys::esp_timer_get_time() / 1000) as u32 };
            let offset = ntp_ms.wrapping_sub(local_ms);
            NTP_OFFSET_MS.store(offset, Ordering::Relaxed);
            info!("SNTP synced (offset: {}ms)", offset);
            return;
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }
    warn!("SNTP sync timeout — using local time");
}

// =====================================================
// mDNS
// =====================================================

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
    info!("mDNS: {}.local", device_id);
    Ok(())
}

// =====================================================
// ChaCha20 簡易暗号化 (LAN盗聴防止)
// =====================================================

/// ChaCha20 quarter round (ゼロアロケーション)
#[inline]
fn qr(s: &mut [u32; 16], a: usize, b: usize, c: usize, d: usize) {
    s[a] = s[a].wrapping_add(s[b]); s[d] ^= s[a]; s[d] = s[d].rotate_left(16);
    s[c] = s[c].wrapping_add(s[d]); s[b] ^= s[c]; s[b] = s[b].rotate_left(12);
    s[a] = s[a].wrapping_add(s[b]); s[d] ^= s[a]; s[d] = s[d].rotate_left(8);
    s[c] = s[c].wrapping_add(s[d]); s[b] ^= s[c]; s[b] = s[b].rotate_left(7);
}

/// ChaCha20 ブロック生成
fn chacha20_block(key: &[u8; 32], nonce: &[u8; 12], counter: u32) -> [u8; 64] {
    let mut state = [0u32; 16];
    // "expand 32-byte k"
    state[0] = 0x61707865; state[1] = 0x3320646e;
    state[2] = 0x79622d32; state[3] = 0x6b206574;
    for i in 0..8 {
        state[4 + i] = u32::from_le_bytes([key[i*4], key[i*4+1], key[i*4+2], key[i*4+3]]);
    }
    state[12] = counter;
    for i in 0..3 {
        state[13 + i] = u32::from_le_bytes([nonce[i*4], nonce[i*4+1], nonce[i*4+2], nonce[i*4+3]]);
    }

    let mut working = state;
    for _ in 0..10 { // 20 rounds = 10 double rounds
        qr(&mut working, 0,4,8,12); qr(&mut working, 1,5,9,13);
        qr(&mut working, 2,6,10,14); qr(&mut working, 3,7,11,15);
        qr(&mut working, 0,5,10,15); qr(&mut working, 1,6,11,12);
        qr(&mut working, 2,7,8,13); qr(&mut working, 3,4,9,14);
    }

    let mut out = [0u8; 64];
    for i in 0..16 {
        let val = working[i].wrapping_add(state[i]);
        out[i*4..i*4+4].copy_from_slice(&val.to_le_bytes());
    }
    out
}

/// パケットペイロードをXOR暗号化/復号 (対称)
pub fn encrypt_payload(data: &mut [u8], channel_key: &[u8; 32], seq: u32) {
    let mut nonce = [0u8; 12];
    nonce[0..4].copy_from_slice(&seq.to_le_bytes());

    let mut offset = 0;
    let mut counter = 0u32;
    while offset < data.len() {
        let keystream = chacha20_block(channel_key, &nonce, counter);
        let chunk = (data.len() - offset).min(64);
        for i in 0..chunk {
            data[offset + i] ^= keystream[i];
        }
        offset += chunk;
        counter += 1;
    }
}

/// チャンネル名からChaCha20キーを派生 (FNV-1aの繰り返しハッシュで32バイト)
pub fn derive_channel_key(channel: &str) -> [u8; 32] {
    let mut key = [0u8; 32];
    for i in 0..8 {
        let mut input = channel.as_bytes().to_vec();
        input.push(i as u8);
        let h = fnv1a(&input);
        key[i*4..i*4+4].copy_from_slice(&h.to_le_bytes());
    }
    key
}

// =====================================================
// Heartbeat — ピア存在確認 (5秒間隔)
// =====================================================

/// Heartbeatパケット構築 (音声なし、19Bヘッダのみ)
pub fn build_heartbeat(device_hash: u32, ch_hash: u32, out: &mut [u8; PACKET_BUF_SIZE]) -> usize {
    out[0..2].copy_from_slice(&MAGIC);
    out[2..6].copy_from_slice(&device_hash.to_le_bytes());
    out[6..10].copy_from_slice(&0u32.to_le_bytes()); // seq=0 for heartbeat
    out[10..14].copy_from_slice(&ch_hash.to_le_bytes());
    out[14..18].copy_from_slice(&ntp_now_ms().to_le_bytes());
    out[18] = FLAG_HEARTBEAT;
    HEADER_SIZE // ヘッダのみ、音声なし
}

/// Heartbeat送信タスク
pub fn heartbeat_task(socket: &std::net::UdpSocket, dest: std::net::SocketAddrV4) {
    loop {
        if !SOLUNA_ACTIVE.load(Ordering::Relaxed) {
            std::thread::sleep(std::time::Duration::from_millis(500));
            continue;
        }

        let device_hash = OWN_DEVICE_HASH.load(Ordering::Relaxed);
        // ch_hashをSolunaNodeから取得せず、直接計算不可なのでheartbeat用の簡易版
        // handle_packet側でFLAG_HEARTBEATを見てピアlast_seenを更新
        let mut packet = [0u8; PACKET_BUF_SIZE];
        let len = build_heartbeat(device_hash, 0, &mut packet);
        let _ = socket.send_to(&packet[..len], dest);

        std::thread::sleep(std::time::Duration::from_millis(HEARTBEAT_INTERVAL_MS));
    }
}

// =====================================================
// WAN WebSocket リレー (Fly.ioサーバー経由)
// =====================================================

const RELAY_URL: &str = "https://api.chatweb.ai/api/v1/soluna/relay";

/// WANリレーにパケット転送 (HTTP POST, UDPの代替)
/// サーバー側で同じチャンネルの他デバイスにWebSocket pushする
pub fn relay_send(device_id: &str, channel: &str, packet: &[u8]) {
    let config = esp_idf_svc::http::client::Configuration {
        buffer_size: Some(2048),
        timeout: Some(std::time::Duration::from_secs(3)),
        ..Default::default()
    };

    let client = match esp_idf_svc::http::client::EspHttpConnection::new(&config) {
        Ok(c) => c,
        Err(_) => return,
    };

    let headers = [
        ("Content-Type", "application/octet-stream"),
        ("X-Device-Id", device_id),
        ("X-Channel", channel),
    ];

    let mut req = match client.initiate_request(
        esp_idf_svc::http::Method::Post,
        RELAY_URL,
        &headers,
    ) {
        Ok(r) => r,
        Err(_) => return,
    };

    let _ = req.write(packet);
    let _ = req.submit();
    // Fire and forget — レスポンスは無視
}
