"""
Train KoeCodec on real audio (pre-converted to 16kHz mono WAV via ffmpeg).
"""

import numpy as np
import wave
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from koe_codec import KoeCodec


def load_wav(path: str) -> np.ndarray:
    """Load 16kHz mono WAV as float32."""
    with wave.open(path, 'rb') as wf:
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def main():
    wav_dir = Path("/tmp/koecodec_train")
    wav_files = sorted(wav_dir.glob("*.wav"))
    print(f"Found {len(wav_files)} WAV files (16kHz mono)")
    print("=" * 70)

    # Load all
    all_audio = []
    for f in wav_files:
        audio = load_wav(str(f))
        dur = len(audio) / 16000
        all_audio.append(audio)
        print(f"  {f.name[:40]:40s} {dur:6.1f}s  {len(audio):>8} samples")

    total = sum(len(a) for a in all_audio) / 16000
    print(f"\nTotal: {total:.0f}s ({total/60:.1f} min)")

    # Concatenate + normalize (use first 60s for training — fast iteration)
    train_audio = np.concatenate(all_audio)
    max_train = 60 * 16000  # 60 seconds
    if len(train_audio) > max_train:
        train_audio = train_audio[:max_train]
        print(f"Using first {max_train/16000:.0f}s for training")
    train_audio = train_audio / (np.max(np.abs(train_audio)) + 1e-10) * 0.95

    # Test configs
    configs = [
        (2, 4, 256, "Light"),
        (3, 4, 256, "Standard"),
        (4, 4, 256, "High"),
    ]
    results = []

    for n_stages, n_sub, cb_size, label in configs:
        print(f"\n{'─' * 60}")
        print(f"Config: {label} ({n_stages}×{n_sub}×{cb_size})")
        print(f"{'─' * 60}")

        codec = KoeCodec(16000, n_stages=n_stages, n_sub=n_sub, codebook_size=cb_size)
        t0 = time.time()
        codec.train_from_numpy(train_audio, n_iters=20)
        print(f"Training: {time.time()-t0:.1f}s")

        # Evaluate each song (first 30s)
        snrs = []
        for i, audio in enumerate(all_audio):
            chunk = audio[:30 * 16000]
            chunk = chunk / (np.max(np.abs(chunk)) + 1e-10) * 0.95

            bitstream = codec.encode(chunk)
            decoded = codec.decode(bitstream)
            n = min(len(chunk), len(decoded))

            mse = np.mean((chunk[:n] - decoded[:n]) ** 2)
            snr = 10 * np.log10(np.mean(chunk[:n] ** 2) / (mse + 1e-10))
            bitrate = len(bitstream) * 8 / (len(chunk) / 16000)
            snrs.append(snr)
            print(f"  {wav_files[i].stem[:35]:35s} SNR={snr:5.1f}dB  {bitrate/1000:.1f}kbps")

        avg_snr = np.mean(snrs)
        br = codec.compute_bitrate()
        mem = codec.codebook_memory_kb()
        results.append((label, n_stages, br, avg_snr, mem))
        print(f"  → Average: {avg_snr:.1f} dB | {br/1000:.1f} kbps | {mem:.0f} KB")

    # Export standard
    print(f"\n{'=' * 60}")
    print("Exporting Standard config (trained on music)...")
    codec = KoeCodec(16000, n_stages=3, n_sub=4, codebook_size=256)
    codec.train_from_numpy(train_audio, n_iters=25)

    out = Path(__file__).parent
    codec.export_codebooks_bin(str(out / "codebooks_music.bin"))
    codec.export_codebooks_c(str(out / "codebooks_music.h"))
    codec.save(str(out / "koecodec_music.json"))

    # Also export a decoded sample for listening
    test_audio = all_audio[0][:30 * 16000]
    test_audio = test_audio / (np.max(np.abs(test_audio)) + 1e-10) * 0.95
    bitstream = codec.encode(test_audio)
    decoded = codec.decode(bitstream)
    n = min(len(test_audio), len(decoded))
    decoded_i16 = (np.clip(decoded[:n], -1, 1) * 32767).astype(np.int16)

    sample_path = str(out / "decoded_sample.wav")
    with wave.open(sample_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(decoded_i16.tobytes())
    print(f"Decoded sample: {sample_path}")

    # Also save original for A/B comparison
    orig_i16 = (np.clip(test_audio[:n], -1, 1) * 32767).astype(np.int16)
    orig_path = str(out / "original_sample.wav")
    with wave.open(orig_path, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(orig_i16.tobytes())
    print(f"Original sample: {orig_path}")

    # Final table
    print(f"\n{'=' * 70}")
    print(f"{'Config':<12} {'Stages':>6} {'Bitrate':>10} {'Avg SNR':>10} {'Memory':>8}")
    print(f"{'─' * 50}")
    for label, stages, br, snr, mem in results:
        print(f"{label:<12} {stages:>6} {br/1000:>9.1f}k {snr:>9.1f}dB {mem:>7.0f}KB")
    print(f"{'IMA-ADPCM':<12} {'—':>6} {'64.0':>9}k {'~20':>9}dB {'0':>7}KB")
    print(f"{'Opus 16k':<12} {'—':>6} {'16.0':>9}k {'~25':>9}dB {'N/A':>7}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
