"""
KoeCodec v2 — ESP32-native neural-enhanced audio codec

Key changes from v1:
- Product Quantization: split 160-dim into 4 sub-vectors of 40-dim
- Codebook: 4 stages * 4 sub-vectors * 256 entries * 40 dim = 320KB
- Removed broken perceptual weighting (VQ on raw MDCT coefficients)
- Delta-coded envelope (4 bits per band, ~40 bits/frame)
- Target: 6-10 kbps at 15+ dB SNR
"""

import numpy as np
from pathlib import Path
import struct
import json


# =============================================================================
# MDCT Transform
# =============================================================================

class MDCT:
    def __init__(self, frame_size: int = 320, hop_size: int = 160):
        self.frame_size = frame_size
        self.hop_size = hop_size
        N2 = frame_size      # 2N in standard notation
        N = frame_size // 2   # N in standard notation
        n = np.arange(N2)
        self.window = np.sin(np.pi * (n + 0.5) / N2).astype(np.float32)
        k = np.arange(N)
        # Standard MDCT basis: cos(pi/N * (n + 0.5 + N/2) * (k + 0.5))
        self.basis = np.cos(
            np.pi / N * (n[:, None] + 0.5 + N / 2) * (k[None, :] + 0.5)
        ).astype(np.float32)

    def analyze(self, signal: np.ndarray) -> np.ndarray:
        pad_len = (self.hop_size - len(signal) % self.hop_size) % self.hop_size
        signal = np.pad(signal, (0, pad_len + self.frame_size))
        n_frames = (len(signal) - self.frame_size) // self.hop_size + 1
        frames = np.zeros((n_frames, self.frame_size // 2), dtype=np.float32)
        for i in range(n_frames):
            start = i * self.hop_size
            frame = signal[start:start + self.frame_size] * self.window
            frames[i] = frame @ self.basis
        return frames

    def synthesize(self, coeffs: np.ndarray) -> np.ndarray:
        n_frames = len(coeffs)
        N2 = self.frame_size          # 2N (window length)
        N = self.frame_size // 2       # N (half-window = num coefficients)
        out_len = (n_frames - 1) * self.hop_size + N2
        output = np.zeros(out_len, dtype=np.float32)
        inv_basis = self.basis.T * (2.0 / N)
        for i in range(n_frames):
            start = i * self.hop_size
            frame = (coeffs[i] @ inv_basis) * self.window
            output[start:start + N2] += frame
        return output


# =============================================================================
# Product Quantizer (sub-vector VQ)
# =============================================================================

class ProductVQ:
    """Gain-Shape Product VQ: normalize sub-vectors before quantization.

    Each sub-vector is split into gain (scalar energy) and shape (unit vector).
    VQ operates on shapes only → uniform quantization across frequencies.
    Gains are encoded separately as 6-bit log-quantized values.

    Memory: n_stages * M * K * sub_dim * 2 bytes (Q15)
    With defaults: 3 * 4 * 256 * 40 * 2 = 240 KB
    """

    def __init__(self, n_stages: int = 3, n_sub: int = 4,
                 codebook_size: int = 256, dim: int = 160):
        self.n_stages = n_stages
        self.n_sub = n_sub
        self.codebook_size = codebook_size
        self.dim = dim
        self.sub_dim = dim // n_sub  # 40
        self.bits_per_index = int(np.ceil(np.log2(codebook_size)))  # 8
        self.gain_bits = 6  # 6 bits per sub-vector gain

        # codebooks[stage][sub] = (K, sub_dim) — stores unit-norm shapes
        self.codebooks = [
            [np.random.randn(codebook_size, self.sub_dim).astype(np.float32) * 0.1
             for _ in range(n_sub)]
            for _ in range(n_stages)
        ]

    @staticmethod
    def _compute_gains(subs: list) -> list:
        """Compute RMS gain per sub-vector."""
        gains = []
        for s in subs:
            g = np.sqrt(np.mean(s ** 2, axis=1, keepdims=True) + 1e-10)
            gains.append(g)
        return gains

    @staticmethod
    def _normalize(subs: list, gains: list) -> list:
        """Normalize sub-vectors to unit RMS."""
        return [s / g for s, g in zip(subs, gains)]

    @staticmethod
    def _denormalize(subs: list, gains: list) -> list:
        """Restore original scale."""
        return [s * g for s, g in zip(subs, gains)]

    @staticmethod
    def _quantize_gain(gain: np.ndarray, bits: int = 6) -> tuple:
        """Log-quantize gain to n bits. Returns (quantized_gain, codes)."""
        levels = 2 ** bits
        log_gain = np.log2(gain + 1e-10)
        # Map to [0, levels-1] range — assume gain in [-20, 10] log2 range
        log_min, log_max = -20.0, 10.0
        codes = np.clip(
            ((log_gain - log_min) / (log_max - log_min) * (levels - 1)).astype(np.int32),
            0, levels - 1
        )
        # Dequantize
        dequant = 2.0 ** (codes.astype(np.float32) / (levels - 1) * (log_max - log_min) + log_min)
        return dequant, codes

    def train(self, data: np.ndarray, n_iters: int = 40, verbose: bool = True):
        """Train gain-shape codebooks."""
        # First: compute and store gains, train on normalized shapes
        subs = self._split(data)
        gains = self._compute_gains(subs)
        normalized = self._normalize(subs, gains)

        # Train first stage on normalized data
        residual_normalized = np.hstack(normalized)  # Back to full vector
        residual = residual_normalized.copy()
        cumulative = np.zeros_like(residual)

        for stage in range(self.n_stages):
            if verbose:
                print(f"  Stage {stage+1}/{self.n_stages}:")

            subs_r = self._split(residual)

            stage_recon = np.zeros_like(residual)
            for m in range(self.n_sub):
                cb = self._kmeans(subs_r[m], self.codebook_size, n_iters)
                self.codebooks[stage][m] = cb
                indices = self._nearest(subs_r[m], cb)
                stage_recon[:, m*self.sub_dim:(m+1)*self.sub_dim] = cb[indices]
                if verbose:
                    mse = np.mean((subs_r[m] - cb[indices]) ** 2)
                    print(f"    Sub {m}: MSE={mse:.6f}")

            cumulative += stage_recon
            residual = residual_normalized - cumulative

            if verbose:
                full_mse = np.mean(residual ** 2)
                full_snr = 10 * np.log10(np.mean(residual_normalized ** 2) / (full_mse + 1e-10))
                print(f"    → Cumulative SNR (shape): {full_snr:.1f} dB")

    def _split(self, data: np.ndarray) -> list:
        """Split vectors into sub-vectors."""
        return [data[:, m*self.sub_dim:(m+1)*self.sub_dim] for m in range(self.n_sub)]

    def _kmeans(self, data: np.ndarray, k: int, n_iters: int) -> np.ndarray:
        n = len(data)
        # Random sample init (fast, good enough with enough iterations)
        idx = np.random.choice(n, size=min(k, n), replace=False)
        centroids = data[idx].copy()
        # Pad if k > n
        if k > n:
            extra = data[np.random.randint(0, n, size=k - n)]
            centroids = np.vstack([centroids, extra])

        for it in range(n_iters):
            indices = self._nearest(data, centroids)
            new_centroids = np.zeros_like(centroids)
            for i in range(k):
                mask = indices == i
                if mask.any():
                    new_centroids[i] = data[mask].mean(axis=0)
                else:
                    new_centroids[i] = data[np.random.randint(n)]
            centroids = new_centroids

        return centroids

    def _nearest(self, data: np.ndarray, codebook: np.ndarray) -> np.ndarray:
        chunk_size = 8192
        indices = np.zeros(len(data), dtype=np.int32)
        cb_norm = np.sum(codebook ** 2, axis=1)
        for start in range(0, len(data), chunk_size):
            end = min(start + chunk_size, len(data))
            chunk = data[start:end]
            dists = np.sum(chunk ** 2, axis=1, keepdims=True) - 2 * chunk @ codebook.T + cb_norm
            indices[start:end] = np.argmin(dists, axis=1)
        return indices

    def encode(self, vectors: np.ndarray) -> tuple:
        """Encode to (shape_indices, gain_codes).
        shape_indices: (n, n_stages, n_sub) int32
        gain_codes: (n, n_sub) int32
        """
        n = len(vectors)

        # Gain-shape decomposition
        subs = self._split(vectors)
        gains = self._compute_gains(subs)
        normalized = self._normalize(subs, gains)
        norm_full = np.hstack(normalized)

        # Quantize gains
        gain_codes = np.zeros((n, self.n_sub), dtype=np.int32)
        quant_gains = []
        for m in range(self.n_sub):
            qg, gc = self._quantize_gain(gains[m], self.gain_bits)
            gain_codes[:, m] = gc.ravel()
            quant_gains.append(qg)

        # Residual VQ on normalized shapes
        all_indices = np.zeros((n, self.n_stages, self.n_sub), dtype=np.int32)
        residual = norm_full.copy()

        for stage in range(self.n_stages):
            subs_r = self._split(residual)
            for m in range(self.n_sub):
                all_indices[:, stage, m] = self._nearest(subs_r[m], self.codebooks[stage][m])

            reconstructed = np.zeros_like(norm_full)
            for m in range(self.n_sub):
                idx = all_indices[:, stage, m]
                reconstructed[:, m*self.sub_dim:(m+1)*self.sub_dim] = \
                    self.codebooks[stage][m][idx]
            residual = residual - reconstructed

        return all_indices, gain_codes

    def decode(self, shape_indices: np.ndarray, gain_codes: np.ndarray) -> np.ndarray:
        """Decode shape indices + gain codes back to vectors."""
        n = len(shape_indices)

        # Reconstruct normalized shapes
        result = np.zeros((n, self.dim), dtype=np.float32)
        for stage in range(self.n_stages):
            for m in range(self.n_sub):
                idx = shape_indices[:, stage, m]
                result[:, m*self.sub_dim:(m+1)*self.sub_dim] += \
                    self.codebooks[stage][m][idx]

        # Dequantize gains and apply
        levels = 2 ** self.gain_bits
        log_min, log_max = -20.0, 10.0
        for m in range(self.n_sub):
            gain = 2.0 ** (gain_codes[:, m].astype(np.float32) / (levels - 1) * (log_max - log_min) + log_min)
            result[:, m*self.sub_dim:(m+1)*self.sub_dim] *= gain[:, None]

        return result


# =============================================================================
# Bitstream
# =============================================================================

class BitstreamWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.bit_pos = 0
        self.current_byte = 0

    def write_bits(self, value: int, n_bits: int):
        for i in range(n_bits - 1, -1, -1):
            bit = (value >> i) & 1
            self.current_byte = (self.current_byte << 1) | bit
            self.bit_pos += 1
            if self.bit_pos == 8:
                self.buffer.append(self.current_byte)
                self.current_byte = 0
                self.bit_pos = 0

    def flush(self):
        if self.bit_pos > 0:
            self.current_byte <<= (8 - self.bit_pos)
            self.buffer.append(self.current_byte)
            self.current_byte = 0
            self.bit_pos = 0

    def get_bytes(self) -> bytes:
        self.flush()
        return bytes(self.buffer)


class BitstreamReader:
    def __init__(self, data: bytes):
        self.data = data
        self.byte_pos = 0
        self.bit_pos = 0

    def read_bits(self, n_bits: int) -> int:
        value = 0
        for _ in range(n_bits):
            if self.byte_pos >= len(self.data):
                return value
            bit = (self.data[self.byte_pos] >> (7 - self.bit_pos)) & 1
            value = (value << 1) | bit
            self.bit_pos += 1
            if self.bit_pos == 8:
                self.bit_pos = 0
                self.byte_pos += 1
        return value


# =============================================================================
# KoeCodec v2
# =============================================================================

class KoeCodec:
    """MDCT + Product VQ codec optimized for ESP32."""

    def __init__(self, sample_rate: int = 16000, frame_ms: int = 20,
                 n_stages: int = 3, n_sub: int = 4, codebook_size: int = 256):
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_size = sample_rate * frame_ms // 1000  # 320
        self.hop_size = self.frame_size // 2  # 160

        self.mdct = MDCT(self.frame_size, self.hop_size)
        self.pvq = ProductVQ(n_stages, n_sub, codebook_size, self.hop_size)

        self.n_stages = n_stages
        self.n_sub = n_sub
        self.codebook_size = codebook_size
        self.bits_per_index = int(np.ceil(np.log2(codebook_size)))  # 8

    def train_from_numpy(self, audio: np.ndarray, n_iters: int = 40):
        """Train from raw numpy audio."""
        # Normalize
        audio = audio / (np.max(np.abs(audio)) + 1e-10)
        coeffs = self.mdct.analyze(audio)
        print(f"Training on {len(coeffs)} frames ({len(coeffs) * self.frame_ms / 1000:.1f}s)")
        print(f"Codebook config: {self.n_stages} stages x {self.n_sub} subs x "
              f"{self.codebook_size} entries x {self.pvq.sub_dim} dim")
        self.pvq.train(coeffs, n_iters)

    def encode(self, audio: np.ndarray) -> bytes:
        """Encode audio to bitstream with gain-shape coding."""
        coeffs = self.mdct.analyze(audio)
        shape_indices, gain_codes = self.pvq.encode(coeffs)

        writer = BitstreamWriter()

        # Header
        writer.write_bits(len(coeffs), 16)
        writer.write_bits(self.n_stages, 4)
        writer.write_bits(self.n_sub, 4)
        writer.write_bits(self.bits_per_index, 4)
        writer.write_bits(self.pvq.gain_bits, 4)

        # Per-frame: gains + shape indices
        for i in range(len(coeffs)):
            # Gains: n_sub * gain_bits
            for m in range(self.n_sub):
                writer.write_bits(int(gain_codes[i, m]), self.pvq.gain_bits)
            # Shape indices: n_stages * n_sub * bits_per_index
            for s in range(self.n_stages):
                for m in range(self.n_sub):
                    writer.write_bits(int(shape_indices[i, s, m]), self.bits_per_index)

        return writer.get_bytes()

    def decode(self, bitstream: bytes) -> np.ndarray:
        """Decode bitstream to audio."""
        reader = BitstreamReader(bitstream)

        n_frames = reader.read_bits(16)
        n_stages = reader.read_bits(4)
        n_sub = reader.read_bits(4)
        bits_per_index = reader.read_bits(4)
        gain_bits = reader.read_bits(4)

        shape_indices = np.zeros((n_frames, n_stages, n_sub), dtype=np.int32)
        gain_codes = np.zeros((n_frames, n_sub), dtype=np.int32)

        for i in range(n_frames):
            for m in range(n_sub):
                gain_codes[i, m] = reader.read_bits(gain_bits)
            for s in range(n_stages):
                for m in range(n_sub):
                    shape_indices[i, s, m] = reader.read_bits(bits_per_index)

        coeffs = self.pvq.decode(shape_indices, gain_codes)
        return self.mdct.synthesize(coeffs)

    def compute_bitrate(self) -> float:
        """Theoretical bitrate in bps."""
        gain_bits_per_frame = self.n_sub * self.pvq.gain_bits  # 4*6 = 24
        shape_bits_per_frame = self.n_stages * self.n_sub * self.bits_per_index  # 3*4*8 = 96
        total = gain_bits_per_frame + shape_bits_per_frame  # 120
        fps = 1000 / self.frame_ms  # 50
        return total * fps  # 6000 bps = 6 kbps

    def codebook_memory_kb(self) -> float:
        """Codebook memory in KB (Q15 int16)."""
        total = self.n_stages * self.n_sub * self.codebook_size * self.pvq.sub_dim * 2
        return total / 1024

    # =========================================================================
    # Export
    # =========================================================================

    def export_codebooks_bin(self, path: str):
        """Export codebooks as binary for Rust/ESP32."""
        with open(path, 'wb') as f:
            f.write(b'KOE2')  # Magic v2
            f.write(struct.pack('<BBBB',
                                self.n_stages, self.n_sub,
                                self.codebook_size & 0xFF,  # 256 → 0 (wrap)
                                self.pvq.sub_dim))

            # Scale factors per stage per sub
            for stage in range(self.n_stages):
                for m in range(self.n_sub):
                    cb = self.pvq.codebooks[stage][m]
                    max_val = float(np.max(np.abs(cb)) + 1e-10)
                    f.write(struct.pack('<f', max_val))

            # Codebook data as Q15
            for stage in range(self.n_stages):
                for m in range(self.n_sub):
                    cb = self.pvq.codebooks[stage][m]
                    max_val = np.max(np.abs(cb)) + 1e-10
                    q15 = (cb / max_val * 32767).astype(np.int16)
                    f.write(q15.tobytes())

        size = Path(path).stat().st_size
        print(f"Exported: {path} ({size/1024:.1f} KB)")

    def export_codebooks_c(self, path: str):
        """Export as C header."""
        with open(path, 'w') as f:
            f.write("// KoeCodec v2 — auto-generated codebooks\n")
            f.write("#pragma once\n#include <stdint.h>\n\n")
            f.write(f"#define KOE_N_STAGES {self.n_stages}\n")
            f.write(f"#define KOE_N_SUB {self.n_sub}\n")
            f.write(f"#define KOE_CB_SIZE {self.codebook_size}\n")
            f.write(f"#define KOE_SUB_DIM {self.pvq.sub_dim}\n")
            f.write(f"#define KOE_BITS_PER_IDX {self.bits_per_index}\n\n")

            for stage in range(self.n_stages):
                for m in range(self.n_sub):
                    cb = self.pvq.codebooks[stage][m]
                    max_val = np.max(np.abs(cb)) + 1e-10
                    f.write(f"static const float koe_scale_{stage}_{m} = {max_val:.6f}f;\n")
                    f.write(f"static const int16_t koe_cb_{stage}_{m}"
                            f"[{self.codebook_size}][{self.pvq.sub_dim}] = {{\n")
                    q15 = (cb / max_val * 32767).astype(np.int16)
                    for i in range(self.codebook_size):
                        vals = ", ".join(str(v) for v in q15[i])
                        f.write(f"  {{{vals}}},\n")
                    f.write("};\n\n")

        print(f"Exported: {path}")

    def save(self, path: str):
        state = {
            'version': 2,
            'sample_rate': self.sample_rate,
            'frame_ms': self.frame_ms,
            'n_stages': self.n_stages,
            'n_sub': self.n_sub,
            'codebook_size': self.codebook_size,
            'codebooks': [
                [cb.tolist() for cb in stage]
                for stage in self.pvq.codebooks
            ],
        }
        with open(path, 'w') as f:
            json.dump(state, f)

    def load(self, path: str):
        with open(path, 'r') as f:
            state = json.load(f)
        self.pvq.codebooks = [
            [np.array(cb, dtype=np.float32) for cb in stage]
            for stage in state['codebooks']
        ]


# =============================================================================
# Test
# =============================================================================

def test_roundtrip():
    print("=" * 60)
    print("KoeCodec v2 — Roundtrip Test")
    print("=" * 60)

    sr = 16000
    duration = 10.0
    t = np.linspace(0, duration, int(sr * duration), dtype=np.float32)

    # Richer speech-like signal
    audio = np.zeros_like(t)
    f0 = 120 + 30 * np.sin(2 * np.pi * 3 * t)
    phase = np.cumsum(2 * np.pi * f0 / sr)
    for h, a in [(1, 0.4), (2, 0.2), (3, 0.15), (4, 0.1), (5, 0.08),
                  (6, 0.05), (7, 0.03), (8, 0.02)]:
        audio += a * np.sin(h * phase)

    # Syllable rhythm
    syllable = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * t)
    audio *= syllable
    # Add noise
    audio += 0.03 * np.random.randn(len(t)).astype(np.float32)
    audio = audio / np.max(np.abs(audio)) * 0.9

    print(f"Input: {len(audio)} samples, {duration}s @ {sr}Hz\n")

    # Test multiple configurations
    configs = [
        (2, 4, 256, "Light (2 stage)"),
        (3, 4, 256, "Standard (3 stage)"),
        (4, 4, 256, "High (4 stage)"),
    ]

    for n_stages, n_sub, cb_size, label in configs:
        print(f"--- {label}: {n_stages}×{n_sub}×{cb_size} ---")

        codec = KoeCodec(sr, n_stages=n_stages, n_sub=n_sub, codebook_size=cb_size)
        codec.train_from_numpy(audio, n_iters=30)

        # Encode
        bitstream = codec.encode(audio)
        actual_bitrate = len(bitstream) * 8 / duration

        # Decode
        decoded = codec.decode(bitstream)
        min_len = min(len(audio), len(decoded))
        orig = audio[:min_len]
        dec = decoded[:min_len]

        mse = np.mean((orig - dec) ** 2)
        snr = 10 * np.log10(np.mean(orig ** 2) / (mse + 1e-10))

        theoretical = codec.compute_bitrate()
        mem = codec.codebook_memory_kb()

        print(f"  Bitrate: {actual_bitrate/1000:.1f} kbps (theoretical: {theoretical/1000:.1f} kbps)")
        print(f"  SNR: {snr:.1f} dB")
        print(f"  Codebook: {mem:.0f} KB")
        print()

    # Export best config
    print("--- Exporting standard config ---")
    codec = KoeCodec(sr, n_stages=3, n_sub=4, codebook_size=256)
    codec.train_from_numpy(audio, n_iters=40)

    bitstream = codec.encode(audio)
    decoded = codec.decode(bitstream)
    min_len = min(len(audio), len(decoded))
    mse = np.mean((audio[:min_len] - decoded[:min_len]) ** 2)
    snr = 10 * np.log10(np.mean(audio[:min_len] ** 2) / (mse + 1e-10))
    bitrate = len(bitstream) * 8 / duration

    codec.export_codebooks_bin("codebooks_v2.bin")
    codec.export_codebooks_c("codebooks_v2.h")
    codec.save("koecodec_v2.json")

    print(f"\n{'=' * 60}")
    print(f"Final: {bitrate/1000:.1f} kbps, SNR {snr:.1f} dB, "
          f"codebook {codec.codebook_memory_kb():.0f} KB")
    print(f"vs IMA-ADPCM: 64 kbps, ~20 dB SNR, 0 KB")
    print(f"vs Opus 16kbps: ~25 dB SNR")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    test_roundtrip()
