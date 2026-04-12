<div align="center">

# Koe — Sound That Connects

**1 device remembers. 100 devices become an orchestra.**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/yukihamada/koe-device?style=flat-square)](https://github.com/yukihamada/koe-device)
[![Status](https://img.shields.io/badge/status-prototype-orange?style=flat-square)]()

**[Website](https://koe.live/)** · **[Koe Pro](https://koe.live/pro)** · **[Busker](https://koe.live/busker)** · **[Classroom](https://koe.live/classroom)** · **[Moji](https://koe.live/moji)** · **[SolunaOS](https://koe.live/soluna-os)**

**[日本語](README.ja.md)** · **[Documentation](https://koe.live/docs.html)**

</div>

---

## Products

### Hardware

| Device | Description | Key Specs | BOM | Target Price |
|--------|-------------|-----------|-----|-------------|
| **Koe Pro** | Ultra-low latency wireless audio transmitter for musicians | ESP32-S3 + DW3000 UWB, 48kHz/24bit, <15ms | ~$35 | $199 |
| **Koe Hub** | Real-time mixer & streaming server | Pi CM5, 8-channel, EQ/reverb/comp, SRT/RTMP | ~$120 | $399 |
| **COIN** | Personal audio device for crowds | ESP32-S3, Soluna P2P sync, 26mm disc | ~$24 | $65 |
| **COIN Lite** | Receive-only festival device | ESP32-C3, minimal BOM | ~$6 | $29 |
| **Koe Seed** | Auracast receiver, 5 form factors | nRF5340 + nRF21540, 28mm PCB, Find My tracker | ~$8.30 | $35 |
| **FILL** | Powered speaker | Pi CM5 + 50W Class-D amp, 8" + 1" horn | — | $1,500 |
| **STAGE** | Festival bridge | Pi CM5, GPS sync, PA routing | — | $800 |
| **SUB** | Subwoofer | 15", 1000W | — | $1,200 |

### Software

| App | Description | URL |
|-----|-------------|-----|
| **Busker** | Street performance: audience phones become wireless speakers + tip jar | [koe.live/busker](https://koe.live/busker) |
| **Classroom** | Teacher/guide voice to everyone's earphones, no app needed | [koe.live/classroom](https://koe.live/classroom) |
| **Moji** | Real-time speech translation (JA/EN/ZH/KO/ES/FR) | [koe.live/moji](https://koe.live/moji) |
| **SolunaOS** | Festival management dashboard (timeline, LED show, routing, tickets) | [koe.live/soluna-os](https://koe.live/soluna-os) |

## Architecture

```
[Instruments] --> [Koe Pro] --WiFi+UWB--> [Koe Hub]
[Phones]      --> [Busker/Classroom] -->    |-> STAGE -> FILL -> SUB (PA)
[Voice]       --> [Moji]            -->    |-> COIN / COIN Lite (crowd)
                                           |-> SRT/RTMP (stream)
                                           +-> SolunaOS (management)
```

## Latency

| Path | Latency |
|------|---------|
| Koe Pro -> Hub -> PA | ~14ms |
| Phone -> Busker/Classroom | ~50ms (WebRTC) |
| Soluna crowd sync | ~110ms |
| Moji translation | ~800ms |

## Koe Seed — One PCB, Five Form Factors

The Seed uses a single 28mm round PCB (nRF5340 + nRF21540) that fits in five different enclosures:

| Form Factor | Case | Use Case |
|-------------|------|----------|
| **Wristband** | 35x30x12mm oval pod | Festivals, concerts — slides into silicone band |
| **Keychain** | 32mm disc, 10mm thick | Everyday carry, keys, bag |
| **Clip-On** | 35x25x12mm + spring clip | Backpack strap, belt loop, pocket edge |
| **Badge** | 55x35x8mm rectangle | Conferences, museum tours, corporate events |
| **Pendant** | 35x28x10mm teardrop | Guided tours, jewelry — wear on cord |

Additional ultra-thin option: **Sticker** (32mm, 6mm thick) — stick on phone, laptop, helmet.

### Built-in Tracker (Find My Compatible)

Every Seed broadcasts an [OpenHaystack](https://github.com/seemoo-lab/openhaystack)-compatible BLE beacon in parallel with Auracast reception. This enables lost-item tracking via Apple's Find My network:

- Broadcasts every 2 seconds (~0.01mA power impact)
- Public key rotates every 15 minutes for privacy
- Any nearby iPhone relays the encrypted location to Apple's servers
- Owner retrieves location via the OpenHaystack macOS app

This runs **always** (even during audio playback) using a secondary BLE advertising set on the nRF5340.

## Directory Structure

```
koe-device/
├── docs/                    # Website (koe.live, served by Fly.io)
│   ├── index.html           # Landing page
│   ├── pro.html             # Koe Pro + Hub product page
│   ├── busker.html          # Busker mode
│   ├── classroom.html       # Classroom mode
│   ├── moji.html            # Real-time translation
│   ├── soluna-os.html       # Festival dashboard
│   ├── app/                 # P2P web app (Soluna)
│   └── images/              # Product renders
├── firmware/                # ESP32-S3 Rust firmware
│   ├── src/
│   │   ├── main.rs          # Entry point, dual mode (Koe/Soluna)
│   │   ├── audio.rs         # I2S, VAD, DSP
│   │   ├── pro.rs           # Koe Pro low-latency transmitter
│   │   ├── uwb.rs           # DW3000 UWB clock sync
│   │   ├── soluna.rs        # UDP multicast P2P protocol
│   │   ├── cloud.rs         # HTTPS to chatweb.ai
│   │   └── led.rs           # WS2812B status LED
│   ├── coin-lite/           # COIN Lite (ESP32-C3) firmware
│   └── demo/                # Minimal sync demo (2 boards)
├── hub/                     # Koe Hub software (Pi CM5, Rust)
├── server/                  # koe.live Axum server (static + OTA API)
├── hardware/
│   ├── kicad/               # Schematic + PCB
│   └── bom/                 # Bill of materials
├── manufacturing/           # JLCPCB BOM/CPL
├── regulatory/              # Regulatory docs (技適 etc.)
├── enclosure/               # 3D printable cases
├── tools/                   # guitar-stream.py, led-send.py, led-show.py
└── stage/                   # STAGE device software
```

## Quick Start

### Firmware (ESP32-S3)

```bash
# Install toolchain
cargo install espup && espup install
cargo install espflash ldproxy

# Build
cd firmware && cargo build --release

# Flash
cargo espflash flash --release --monitor
```

### Hub (Pi CM5)

```bash
cd hub && cargo run --release
# Dashboard: http://localhost:3000
```

### COIN Lite (ESP32-C3)

```bash
cd firmware/coin-lite && cargo build --release
```

### Deploy Site

```bash
fly deploy --remote-only -a koe-live
```

### OTA Firmware Update

```bash
cd firmware
./deploy-ota.sh --release --token $KOE_ADMIN_TOKEN
```

## Protocols

### Soluna (crowd sync)

- UDP multicast `239.42.42.1:4242`
- IMA-ADPCM 4:1 compression, 16kHz mono
- NTP + GPS time sync
- WebSocket bridge at `wss://koe.live/ws/soluna`

### Koe Pro (low-latency)

- UDP unicast port 4244
- PCM24 48kHz, 128-sample buffer
- UWB (DW3000) sub-microsecond clock sync
- WebRTC signaling at `wss://koe.live/ws/signal`

## Links

- **Website:** https://koe.live/
- **Koe Software:** https://app.koe.live
- **GitHub:** https://github.com/yukihamada/koe-device
- **EnablerDAO:** https://github.com/enablerdao

## License

MIT — see [LICENSE](LICENSE)
