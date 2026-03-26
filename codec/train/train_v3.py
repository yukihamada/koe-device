"""
KoeCodec v3 — aggressive config sweep to find optimal quality/bitrate tradeoff.

Key changes:
- 8 sub-vectors (20-dim each) — halves curse of dimensionality
- 512 codebook entries (9 bits) — doubles expressiveness
- More stages (up to 6) for higher quality
- Full training data (all 35 min)
"""

import numpy as np
import wave
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from koe_codec import KoeCodec, MDCT, ProductVQ


def load_wav(path: str) -> np.ndarray:
    with wave.open(path, 'rb') as wf:
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def eval_codec(codec, wav_files, all_audio):
    """Evaluate codec on all songs (first 30s each)."""
    snrs = []
    for i, audio in enumerate(all_audio):
        chunk = audio[:30 * 16000]
        chunk = chunk / (np.max(np.abs(chunk)) + 1e-10) * 0.95
        bs = codec.encode(chunk)
        dec = codec.decode(bs)
        n = min(len(chunk), len(dec))
        mse = np.mean((chunk[:n] - dec[:n]) ** 2)
        snr = 10 * np.log10(np.mean(chunk[:n] ** 2) / (mse + 1e-10))
        snrs.append(snr)
    return np.mean(snrs), snrs


def main():
    wav_dir = Path("/tmp/koecodec_train")
    wav_files = sorted(wav_dir.glob("*.wav"))
    print(f"Loading {len(wav_files)} files...")

    all_audio = []
    for f in wav_files:
        all_audio.append(load_wav(str(f)))

    # Use 2 min for training (more data = better codebooks)
    train_audio = np.concatenate(all_audio)[:120 * 16000]
    train_audio = train_audio / (np.max(np.abs(train_audio)) + 1e-10) * 0.95
    print(f"Training data: {len(train_audio)/16000:.0f}s\n")

    # Config sweep
    configs = [
        # (n_stages, n_sub, cb_size, label)
        # Current baseline
        (3, 4, 256, "v2 baseline (3×4×256)"),
        # More sub-vectors (smaller = easier to quantize)
        (3, 8, 256, "8 subs (3×8×256)"),
        # Bigger codebooks
        (3, 8, 512, "8 subs + 512 (3×8×512)"),
        # More stages
        (4, 8, 512, "4 stages (4×8×512)"),
        (5, 8, 512, "5 stages (5×8×512)"),
        (6, 8, 512, "6 stages (6×8×512)"),
        # Extreme: lots of stages, smaller codebooks
        (8, 8, 256, "8 stages (8×8×256)"),
    ]

    results = []
    print(f"{'Config':<28} {'Stages':>3} {'Sub':>3} {'CB':>4} "
          f"{'Bitrate':>8} {'SNR':>6} {'Mem':>6} {'Time':>5}")
    print("─" * 70)

    for n_stages, n_sub, cb_size, label in configs:
        codec = KoeCodec(16000, n_stages=n_stages, n_sub=n_sub, codebook_size=cb_size)

        t0 = time.time()
        codec.train_from_numpy(train_audio, n_iters=20)
        train_time = time.time() - t0

        avg_snr, snrs = eval_codec(codec, wav_files, all_audio)
        bitrate = codec.compute_bitrate()
        mem = codec.codebook_memory_kb()

        results.append((label, n_stages, n_sub, cb_size, bitrate, avg_snr, mem, train_time))
        print(f"{label:<28} {n_stages:>3} {n_sub:>3} {cb_size:>4} "
              f"{bitrate/1000:>7.1f}k {avg_snr:>5.1f}dB {mem:>5.0f}KB {train_time:>4.1f}s")

    # Find best quality/bitrate tradeoff
    print(f"\n{'=' * 70}")
    print("Best configs:")
    for label, ns, nsub, cb, br, snr, mem, t in sorted(results, key=lambda x: -x[5]):
        efficiency = snr / (br / 1000)  # dB per kbps
        print(f"  {label:<28} {br/1000:>6.1f}kbps  {snr:>5.1f}dB  {mem:>4.0f}KB  "
              f"({efficiency:.2f} dB/kbps)")

    # Export best
    best = max(results, key=lambda x: x[5])
    label, ns, nsub, cb, br, snr, mem, t = best
    print(f"\nBest: {label} → {snr:.1f} dB @ {br/1000:.1f} kbps, {mem:.0f} KB")

    # Re-train best and export samples
    print(f"\nExporting best config...")
    codec = KoeCodec(16000, n_stages=ns, n_sub=nsub, codebook_size=cb)
    codec.train_from_numpy(train_audio, n_iters=25)

    out = Path(__file__).parent
    codec.export_codebooks_bin(str(out / "codebooks_v3.bin"))
    codec.save(str(out / "koecodec_v3.json"))

    # Save decoded samples
    test = all_audio[0][:30 * 16000]
    test = test / (np.max(np.abs(test)) + 1e-10) * 0.95
    bs = codec.encode(test)
    dec = codec.decode(bs)
    n = min(len(test), len(dec))

    for name, data in [("original_v3.wav", test[:n]), ("decoded_v3.wav", dec[:n])]:
        pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
        p = str(out / name)
        with wave.open(p, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(pcm.tobytes())

    print(f"\nSamples saved. Open with:")
    print(f"  open {out}/original_v3.wav {out}/decoded_v3.wav")

    # Comparison
    print(f"\n{'=' * 70}")
    print(f"  KoeCodec v3:  {br/1000:.1f} kbps, {snr:.1f} dB, {mem:.0f} KB")
    print(f"  IMA-ADPCM:    64.0 kbps, ~20 dB, 0 KB")
    print(f"  Ratio: {64/br*1000:.0f}x less bandwidth")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
