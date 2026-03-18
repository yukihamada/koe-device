<div align="center">

# 声 Koe

**群衆を楽器にするデバイス。**

1台は記憶。100台はオーケストラ。

[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/yukihamada/koe-device?style=flat-square)](https://github.com/yukihamada/koe-device)
[![Status](https://img.shields.io/badge/status-prototype-orange?style=flat-square)]()

**[Website](https://yukihamada.github.io/koe-device/)** · **[日本語](https://yukihamada.github.io/koe-device/ja.html)** · **[Soluna Edition](https://yukihamada.github.io/koe-device/soluna-edition.html)** · **[Dashboard Demo](https://yukihamada.github.io/koe-device/dashboard.html)**

**[日本語はこちら](README.ja.md)** · **[Documentation Portal](https://yukihamada.github.io/koe-device/docs.html)**

</div>

---

## What is Koe?

Koe is a tiny open-hardware device that listens, remembers, and connects people through sound.

- **Solo mode (Koe):** Always-on AI voice companion. Records your day, understands context, talks back through earbuds.
- **Crowd mode (Soluna):** P2P audio mesh. Multiple devices on the same WiFi sync instantly. Speak into one, everyone hears it. At a festival, the crowd becomes the speaker system.

### Three experiences no smartphone can deliver

| | Experience | What happens |
|---|---|---|
| 01 | **Crowd Orchestra** | 1000 people hum → AI generates harmony in real-time → all devices play the missing parts |
| 02 | **Sound Memory** | "What was the name of that restaurant?" → plays back the exact audio moment |
| 03 | **Spatial Crowd** | 1000 mics create a real-time 3D sound map of an entire venue |

## 5 Form Factors

| Model | Form | Size | Use case |
|-------|------|------|----------|
| **Pick** | Guitar pick pendant | 30 x 30 x 8mm | Daily wear, musician's DNA |
| **Ear Cuff** | Titanium ear clip | 20 x 8 x 5mm | Closest to your voice |
| **Coin** | Perfect circle disc | 26mm ⌀ x 6mm | Pocket, fidget, coin-sized |
| **Band** | Wristband + speaker grille | 40 x 18 x 11mm | Active, festivals |
| **Lantern** | 360° cylindrical stage unit | 100 x 150mm | Events, Pi CM5 powered |

## Architecture

```
[Device] ESP32-S3 + MEMS Mic + Speaker
    |
    |  WiFi / UDP multicast (Soluna P2P)
    |  WiFi / HTTPS (Koe AI)
    |
[Cloud] api.chatweb.ai
    |
    +-- Agent 1: Listener (STT, context)
    +-- Agent 2: Thinker (reasoning)
    +-- Agent 3: Researcher (web search)
    +-- Agent 4: Responder (TTS)
    +-- Agent 5: Memory (long-term learning)
```

### Soluna sync protocol

```
[GPS Satellite] → 1PPS → [STAGE: Pi CM5 + TCXO]
                              |
                        PTP Grand Master
                              |
              WiFi/4G multicast (Opus encoded + GPS timestamp)
                              |
                     [CROWD x N: ESP32-S3]
                              |
                     GPS coordinate → distance to STAGE
                              |
                     delay = distance / speed_of_sound(temperature)
                              |
                     Playback synced to STAGE direct sound arrival
```

## Quick Start

### Buy parts

See **[BUY_NOW.md](BUY_NOW.md)** for a complete prototype parts list. Everything is available on Amazon.co.jp for ~¥5,200-6,800.

### Sync demo (2 ESP32-S3 boards)

```bash
# Install toolchain
cargo install espup && espup install
cargo install espflash ldproxy

# Flash sender (hold GPIO15 button during boot)
cd firmware/demo
WIFI_SSID="YourWiFi" WIFI_PASS="YourPass" cargo espflash flash --monitor

# Flash receiver (don't hold button)
# Speak into sender → hear from receiver
```

See [firmware/demo/README.md](firmware/demo/README.md) for details.

### Full firmware

```bash
cd firmware
cargo build --release
```

## Project structure

```
koe-device/
├── docs/                    # Website (GitHub Pages)
│   ├── index.html           # EN
│   ├── ja.html              # JA
│   ├── soluna-edition.html  # Festival-grade audio
│   ├── dashboard.html       # Management dashboard demo
│   └── images/              # Product renders (Gemini AI)
├── firmware/
│   ├── src/                 # Main firmware (Koe + Soluna)
│   │   ├── main.rs          # Entry point, dual mode
│   │   ├── audio.rs         # I2S, VAD, DSP
│   │   ├── cloud.rs         # HTTPS to chatweb.ai
│   │   ├── soluna.rs        # UDP multicast P2P protocol
│   │   └── led.rs           # WS2812B status LED
│   └── demo/                # Minimal sync demo (2 boards)
├── hardware/
│   ├── kicad/               # Schematic + netlist
│   ├── bom/                 # BOM: Mini ($12), STAGE ($260), CROWD ($52)
│   └── docs/                # Design specs, acoustic analysis, vision
├── enclosure/               # 3D printable case specs
├── LICENSE                  # MIT
└── CONTRIBUTING.md          # How to contribute
```

## Hardware BOM

| Model | BOM Cost | Key Components |
|-------|----------|----------------|
| **Pick/Ear Cuff/Coin** | ~$12 | ESP32-S3, INMP441, MAX98357A, LiPo |
| **Band** | ~$52 | + GPS (MAX-M10S), LTE-M (SIM7080G), 40mm driver |
| **Lantern STAGE** | ~$260 | Pi CM5, HiFiBerry DAC, TPA3255, 130mm coaxial, GPS (NEO-M9N), 4G |

Full BOM: [hardware/bom/](hardware/bom/)

## Status

| Area | Progress | Notes |
|------|----------|-------|
| Hardware design | 70% | Schematic done, parts being ordered |
| Firmware | 40% | Compiles, needs real hardware test |
| Koe software | 100% | [koe.elio.love](https://koe.elio.love) (macOS/Windows) |
| Prototype | 20% | Waiting for parts |
| Soluna Edition | 30% | Pi CM5 architecture designed |

## Roadmap

- [ ] **This week:** Order ESP32-S3 + INMP441 + MAX98357A from Amazon.co.jp
- [ ] **Next week:** Flash sync demo, measure sync accuracy with oscilloscope
- [ ] **2 weeks:** Demo video → post on site
- [ ] **1 month:** Pi CM5 STAGE prototype + web dashboard with real data
- [ ] **3 months:** Field test at 30-person event, 技適 pre-consultation
- [ ] **6 months:** Custom PCB (JLCPCB), injection mold tooling
- [ ] **9 months:** Pilot: 4 STAGE + 50 CROWD to one event company
- [ ] **12 months:** First batch sales

## Links

- **Website:** https://yukihamada.github.io/koe-device/
- **Koe software:** https://koe.elio.love
- **Soluna:** https://solun.art/soluna
- **EnablerDAO:** https://github.com/enablerdao

## License

MIT — see [LICENSE](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)
