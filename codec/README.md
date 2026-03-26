# KoeCodec — ESP32-native neural-enhanced audio codec

Lighter than Opus, better quality at low bitrates, runs on ESP32-S3.

## Architecture

```
Encoder (Python/Server)          Decoder (Rust/ESP32)
┌─────────────────────┐          ┌──────────────────────┐
│ PCM 16kHz mono      │          │ Bitstream in         │
│   ↓                 │          │   ↓                  │
│ MDCT (20ms frames)  │          │ Entropy decode (ANS) │
│   ↓                 │          │   ↓                  │
│ RVQ (4-stage, 1024) │          │ Codebook lookup      │
│   ↓                 │          │   ↓                  │
│ Entropy code (ANS)  │          │ Inverse MDCT         │
│   ↓                 │          │   ↓                  │
│ Bitstream out       │          │ Overlap-add          │
│ (8-16 kbps)         │          │   ↓                  │
└─────────────────────┘          │ PCM out              │
                                 └──────────────────────┘
```

## Key Design Decisions

- **MDCT** for time-frequency transform (same as Opus/MP3, proven efficient)
- **Residual VQ** with learned codebooks (better than scalar quantization)
- **ANS entropy coding** (faster than Huffman, better than arithmetic)
- **Decoder-only NN**: tiny bandwidth extension network (~50KB INT8)
- **no_std Rust**: zero-alloc, runs on ESP32-S3 at <20% CPU

## Target Specs

| Metric | KoeCodec | Opus | IMA-ADPCM |
|--------|----------|------|-----------|
| Bitrate | 8-12 kbps | 16-32 kbps | 64 kbps |
| Quality (PESQ) | ~3.5 | ~3.5 | ~2.5 |
| Decode CPU (ESP32) | ~15% | N/A* | ~5% |
| Decode RAM | ~80KB | N/A* | ~2KB |
| Model size | ~200KB | 0 | 0 |
| Latency | 20ms | 20ms | 0ms |

*Opus doesn't run on ESP32 without significant porting effort

## Directory Structure

```
codec/
├── train/          # Python: codebook training + encoder
├── decoder/        # Rust no_std: ESP32 decoder
└── eval/           # Quality evaluation scripts
```

## Bitstream Format

```
Frame (20ms = 320 samples @ 16kHz):
┌──────────┬──────────┬──────────┬──────────┐
│ VQ idx 0 │ VQ idx 1 │ VQ idx 2 │ VQ idx 3 │
│ 10 bits  │ 10 bits  │ 10 bits  │ 10 bits  │
└──────────┴──────────┴──────────┴──────────┘
= 40 bits / 20ms = 2000 bps (base layer)

+ ANS-coded spectral envelope: ~100-200 bits/frame
+ Total: ~8-12 kbps depending on signal complexity
```
