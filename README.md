# Koe Device

**常時録音 AI コンパニオンデバイス** — 35x40x12mm、ESP32-S3ベース

## Architecture

```
[Dual MEMS Mic] → [ESP32-S3] → WiFi → [chatweb.ai API]
                       ↓                      ↓
                  [Ring Buffer]          [5 AI Agents]
                       ↓                      ↓
                  [VAD Trigger]          [TTS Response]
                       ↓                      ↓
                  [Cloud Stream] ←←←← [Audio Response]
                       ↓
                  [I2S Speaker]
```

## Hardware
- **MCU**: ESP32-S3-MINI-1 (N8R2) — 8MB Flash, 2MB PSRAM
- **Mic**: INMP441 x2 (I2S, stereo beamforming)
- **Speaker**: MAX98357A + 15x10mm micro speaker
- **Power**: 800mAh LiPo, USB-C charging (MCP73831)
- **LED**: WS2812B-2020 RGB status indicator
- **BOM cost**: ~$12/unit (excl. PCB/assembly)

## Status LED
| Color | State |
|-------|-------|
| White pulse | Booting |
| Blue pulse | Connecting WiFi |
| Green dim | Listening (idle) |
| Purple pulse | Processing (AI thinking) |
| Cyan solid | Speaking (playing response) |
| Red blink | Error |

## Build

```bash
# Prerequisites
cargo install espup
espup install
cargo install cargo-espflash

# Build
cd firmware
cargo build --release --target xtensa-esp32s3-espidf

# Flash
cargo espflash flash --release --monitor
```

## Project Structure
```
koe-device/
  hardware/
    kicad/          # Schematic + PCB (KiCad 7)
    bom/            # Bill of Materials
    docs/           # Design specs
  firmware/
    main/           # Entry point
    components/
      audio/        # I2S mic + speaker + VAD
      network/      # WiFi + HTTP/WebSocket to cloud
      led/          # WS2812B status LED
  enclosure/        # 3D printable case specs
```

## Next Steps
1. [ ] KiCad schematic entry + PCB layout
2. [ ] Order dev board (ESP32-S3-DevKitC) + breakout modules for prototyping
3. [ ] Firmware: I2S mic recording → serial dump (validate audio quality)
4. [ ] Firmware: WiFi + HTTP POST to chatweb.ai
5. [ ] chatweb.ai: Add `/api/v1/device/audio` endpoint
6. [ ] Custom PCB v0.1 → JLCPCB order
7. [ ] 3D print enclosure prototype
8. [ ] Field test: 8hr battery life validation
