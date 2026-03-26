// Soluna protocol — ADPCM codec & packet builder/parser
// Must match ESP32 firmware (firmware/src/soluna.rs)

const MAGIC = [0x53, 0x4C]; // "SL"
const HEADER_SIZE = 19;

const FLAG_ADPCM     = 0x01;
const FLAG_ENCRYPTED = 0x02;
const FLAG_HEARTBEAT = 0x04;
const FLAG_CHIRP     = 0x08;
const FLAG_GOSSIP    = 0x10;

const CHANNELS = ['soluna', 'voice', 'music', 'ambient'];

// FNV-1a 32-bit hash
function fnv1a(data) {
  let h = 0x811c9dc5;
  for (let i = 0; i < data.length; i++) {
    h ^= data[i];
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

function fnv1aStr(str) {
  const enc = new TextEncoder().encode(str);
  return fnv1a(enc);
}

// --- Packet builder ---
function buildPacket(deviceHash, seq, channelHash, flags, audioData) {
  const audioLen = audioData ? audioData.length : 0;
  const buf = new ArrayBuffer(HEADER_SIZE + audioLen);
  const view = new DataView(buf);
  const u8 = new Uint8Array(buf);

  u8[0] = MAGIC[0];
  u8[1] = MAGIC[1];
  view.setUint32(2, deviceHash, true);
  view.setUint32(6, seq, true);
  view.setUint32(10, channelHash, true);
  view.setUint32(14, Date.now() & 0xFFFFFFFF, true);
  u8[18] = flags;

  if (audioData && audioLen > 0) {
    u8.set(audioData, HEADER_SIZE);
  }

  return u8;
}

// --- Packet parser ---
function parsePacket(data) {
  if (data.length < HEADER_SIZE) return null;
  if (data[0] !== MAGIC[0] || data[1] !== MAGIC[1]) return null;

  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  return {
    deviceHash: view.getUint32(2, true),
    seq: view.getUint32(6, true),
    channelHash: view.getUint32(10, true),
    timestamp: view.getUint32(14, true),
    flags: data[18],
    audio: data.length > HEADER_SIZE ? data.slice(HEADER_SIZE) : null,
    isADPCM: (data[18] & FLAG_ADPCM) !== 0,
    isHeartbeat: (data[18] & FLAG_HEARTBEAT) !== 0,
    isChirp: (data[18] & FLAG_CHIRP) !== 0,
  };
}

// --- IMA-ADPCM codec ---
const STEP_TABLE = [
  7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31,
  34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
  157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544,
  598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707,
  1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871,
  5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635,
  13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767,
];

const INDEX_TABLE = [-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8];

class AdpcmState {
  constructor() {
    this.predicted = 0;
    this.stepIndex = 0;
  }

  reset() {
    this.predicted = 0;
    this.stepIndex = 0;
  }
}

// Encode PCM Int16Array → ADPCM Uint8Array
function adpcmEncode(pcmSamples, state) {
  const outLen = Math.ceil(pcmSamples.length / 2);
  const out = new Uint8Array(outLen);
  let outIdx = 0;
  let nibbleHi = false;

  for (let i = 0; i < pcmSamples.length; i++) {
    const sample = pcmSamples[i];
    const step = STEP_TABLE[state.stepIndex];

    let diff = sample - state.predicted;
    let code = 0;
    if (diff < 0) {
      code = 8;
      diff = -diff;
    }

    if (diff >= step) { code |= 4; diff -= step; }
    if (diff >= (step >> 1)) { code |= 2; diff -= (step >> 1); }
    if (diff >= (step >> 2)) { code |= 1; }

    // Decode to update prediction (encoder-embedded decoder)
    let delta = step >> 3;
    if (code & 4) delta += step;
    if (code & 2) delta += step >> 1;
    if (code & 1) delta += step >> 2;
    if (code & 8) delta = -delta;

    state.predicted = Math.max(-32768, Math.min(32767, state.predicted + delta));

    const newIdx = state.stepIndex + INDEX_TABLE[code];
    state.stepIndex = Math.max(0, Math.min(88, newIdx));

    if (nibbleHi) {
      out[outIdx] |= (code << 4);
      outIdx++;
    } else {
      out[outIdx] = code & 0x0F;
    }
    nibbleHi = !nibbleHi;
  }

  return out;
}

// Decode ADPCM Uint8Array → PCM Int16Array
function adpcmDecode(adpcm, state) {
  const nSamples = adpcm.length * 2;
  const out = new Int16Array(nSamples);
  let outIdx = 0;

  for (let i = 0; i < adpcm.length; i++) {
    const byte = adpcm[i];
    for (let nibbleIdx = 0; nibbleIdx < 2; nibbleIdx++) {
      const code = nibbleIdx === 0 ? (byte & 0x0F) : (byte >> 4);
      const step = STEP_TABLE[state.stepIndex];

      let delta = step >> 3;
      if (code & 4) delta += step;
      if (code & 2) delta += step >> 1;
      if (code & 1) delta += step >> 2;
      if (code & 8) delta = -delta;

      state.predicted = Math.max(-32768, Math.min(32767, state.predicted + delta));

      const newIdx = state.stepIndex + INDEX_TABLE[code];
      state.stepIndex = Math.max(0, Math.min(88, newIdx));

      out[outIdx++] = state.predicted;
    }
  }

  return out;
}

// Convert Float32 [-1,1] to Int16
function float32ToInt16(float32) {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 32768 : s * 32767;
  }
  return int16;
}

// Convert Int16 to Float32 [-1,1]
function int16ToFloat32(int16) {
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768;
  }
  return float32;
}

// Export for use in other scripts
window.Soluna = {
  MAGIC, HEADER_SIZE, FLAG_ADPCM, FLAG_ENCRYPTED, FLAG_HEARTBEAT,
  FLAG_CHIRP, FLAG_GOSSIP, CHANNELS,
  fnv1a, fnv1aStr,
  buildPacket, parsePacket,
  AdpcmState, adpcmEncode, adpcmDecode,
  float32ToInt16, int16ToFloat32,
};
