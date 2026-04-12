# Koe Auracast Demo Plan -- Dev Kit Sprint

**Goal**: Working Auracast broadcast demo by Friday using off-the-shelf nRF5340 Audio DKs.
**Budget**: ~$600 total. **No custom PCBs needed.**

---

## What to Buy TODAY (DigiKey overnight to Tokyo)

| Qty | Part | DigiKey P/N | Unit Price | Total |
|-----|------|-------------|-----------|-------|
| 3 | nRF5340 Audio DK | [1490-NRF5340-AUDIO-DK-ND](https://www.digikey.com/en/products/detail/nordic-semiconductor-asa/NRF5340-AUDIO-DK/16653382) | $169.00 | $507.00 |
| 1 | nRF21540 FEM shield (optional, range boost) | [1490-NRF21540-EK-ND](https://www.digikey.com/en/products/detail/nordic-semiconductor-asa/NRF21540-EK/14312498) | $35.00 | $35.00 |
| 3 | 3.5mm AUX cable (M-M) | Any | ~$5 | $15.00 |
| 1 | USB-C hub (3 ports, for flashing) | Any | ~$15 | $15.00 |

**Subtotal**: ~$572
**Overnight shipping (DHL/FedEx to Tokyo)**: ~$50
**Total**: ~$620

### Why nRF5340 Audio DK?

- Nordic's official reference platform for LE Audio / Auracast
- Built-in CS47L63 codec, PDM microphone, speaker output (3.5mm + onboard)
- BLE 5.3 with Auracast (BAP Broadcast) in the SDK samples
- USB audio input for easy demo setup
- Well-documented, guaranteed to work with nRF Connect SDK samples

### Alternative: Mouser

- [NRF5340-AUDIO-DK on Mouser](https://www.mouser.com/ProductDetail/Nordic-Semiconductor/NRF5340-AUDIO-DK?qs=XeJtXLiO41R5KJwsvt1K%2Bg%3D%3D)
- Same price, check stock and shipping speed to Tokyo

---

## Demo Architecture

```
  [Phone/Laptop]
       |
    3.5mm AUX / USB Audio
       |
       v
  +------------------+
  | nRF5340 Audio DK |  <-- Transmitter (Broadcast Source)
  | BAP Broadcast Src|
  +------------------+
       |
    BLE 5.3 Auracast (LC3 codec, 48kHz/24bit)
       |
       +-------------------------------+
       |                               |
       v                               v
  +------------------+         +------------------+
  | nRF5340 Audio DK |         | nRF5340 Audio DK |
  | BAP Broadcast Snk|         | BAP Broadcast Snk|
  +------------------+         +------------------+
       |                               |
    3.5mm / Speaker                 3.5mm / Speaker
```

---

## Firmware Build Instructions

### 1. Install nRF Connect SDK (one-time, ~30 min)

```bash
# Install nRF Command Line Tools
# Download from: https://www.nordicsemi.com/Products/Development-tools/nRF-Command-Line-Tools/Download
# For macOS:
brew install --cask nordic-nrf-command-line-tools

# Install west (Zephyr meta-tool)
pip3 install west

# Initialize nRF Connect SDK workspace
mkdir -p ~/ncs && cd ~/ncs
west init -m https://github.com/nrfconnect/sdk-nrf --mr v2.9.0
west update
west zephyr-export
pip3 install -r zephyr/scripts/requirements.txt
pip3 install -r nrf/scripts/requirements.txt

# Install Zephyr SDK toolchain
# Download from: https://github.com/zephyrproject-rtos/sdk-ng/releases
# For macOS ARM64:
wget https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v0.17.0/zephyr-sdk-0.17.0_macos-aarch64.tar.xz
tar xf zephyr-sdk-0.17.0_macos-aarch64.tar.xz
cd zephyr-sdk-0.17.0
./setup.sh
```

### 2. Build Broadcast Source (Transmitter)

```bash
cd ~/ncs/nrf

# The LE Audio samples are in the nRF Connect SDK
# Broadcast source sample:
west build -b nrf5340_audio_dk/nrf5340/cpuapp \
  samples/bluetooth/audio/broadcast_source \
  -- -DCONFIG_TRANSPORT_BIS=y

# Flash to first DK (connect via USB)
west flash
```

### 3. Build Broadcast Sink (Receivers)

```bash
cd ~/ncs/nrf

# Broadcast sink sample:
west build -b nrf5340_audio_dk/nrf5340/cpuapp \
  samples/bluetooth/audio/broadcast_sink \
  -p  # pristine build (clean)

# Flash to second DK
west flash

# Repeat for third DK (reconnect USB)
west flash
```

### 4. Alternative: Use Nordic's Pre-built Firmware

If build issues arise, Nordic provides pre-built HEX files:

```bash
# Download nRF5340 Audio application from Nordic's website
# https://developer.nordicsemi.com/nRF_Connect_SDK/doc/latest/nrf/samples/bluetooth/audio/
# Flash using nRF Connect for Desktop -> Programmer app
```

### 5. Verify with nRF Connect for Mobile

```bash
# Install nRF Connect for Mobile on your phone (iOS/Android)
# It can scan for BLE broadcasts and verify the Auracast stream is active
# App Store: https://apps.apple.com/app/nrf-connect-for-mobile/id1054362403
```

---

## Demo Script (2 minutes, for investors/partners)

### Setup (before demo)
- Transmitter DK powered on, connected to phone via 3.5mm AUX
- Both receiver DKs powered on, placed across the room (5-10m away)
- Music app loaded on phone (pick something with clear vocals + beat)

### Script

> **[0:00]** "This is Auracast -- the next-generation Bluetooth audio broadcast standard."
>
> **[0:10]** *Press play on phone. Music plays from transmitter DK.*
> "I'm playing music into this Nordic development board. It's encoding the audio in LC3 and broadcasting it over Bluetooth LE."
>
> **[0:25]** *Point to receiver DKs across the room.*
> "These two boards -- 10 meters away -- are receiving the same broadcast. Listen."
> *Turn up volume on receivers. Same music, perfectly synced.*
>
> **[0:40]** *Pick up one receiver, walk 20-30m away.*
> "I'm now 30 meters from the transmitter. Still perfectly synced, no dropouts."
>
> **[0:55]** *Walk back, hold up a Koe COIN rendering on phone.*
> "Now imagine this entire system shrunk to the size of a coin. That's Koe COIN."
>
> **[1:10]** "One transmitter can broadcast to unlimited receivers simultaneously. At a festival, 5,000 people each wearing a COIN, all hearing the same music, perfectly synced. No speakers. No noise complaints."
>
> **[1:30]** "The technology works today. We're shipping COIN at $65 per unit. 5,000 units for a festival costs $325,000 -- one-third the price of a traditional L-Acoustics PA system."
>
> **[1:45]** "Questions?"

---

## Demo Video Recording Plan

### Equipment
- iPhone 15/16 Pro (4K 60fps)
- Simple tripod or ask someone to hold
- Quiet room with good lighting (natural light preferred)
- No fancy editing needed -- raw and authentic

### Shot List (shoot in order)

| Shot | Duration | Description |
|------|----------|-------------|
| 1 | 5s | Wide shot: 3 DK boards on table, labeled "TX" and "RX" |
| 2 | 10s | Close-up: Connect phone to transmitter via AUX, press play |
| 3 | 10s | Pan to receivers across room -- audio playing from both |
| 4 | 10s | Pick up receiver, walk away -- still playing at 20m+ |
| 5 | 5s | Text overlay: "Koe COIN -- Auracast in 26mm. $65. koe.live" |

### Post-production (10 min max)
```bash
# Simple trim + text overlay with ffmpeg
ffmpeg -i raw_demo.mov \
  -vf "drawtext=text='Koe COIN - Auracast in 26mm':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h-80:enable='between(t,35,45)'" \
  -c:v libx264 -crf 22 -c:a aac -b:a 128k \
  koe_auracast_demo.mp4
```

### Distribution
| Platform | Format | Notes |
|----------|--------|-------|
| Twitter/X | 60s max, MP4 | Tag @NordicSemi, #Auracast, #BLE |
| LinkedIn | 60s, professional tone | Tag Nordic, Bluetooth SIG |
| YouTube Shorts | <60s vertical crop | Title: "Auracast Demo - Broadcast Audio to Unlimited Devices" |
| TikTok | <60s vertical | Simple, techy, impressive |
| koe.live | Embed on landing page | Add to business.html hero section |

---

## Timeline

| Day | Date | Action | Done |
|-----|------|--------|------|
| 0 (TODAY) | Apr 10 | Order 3x nRF5340 Audio DK from DigiKey (overnight/express) | [ ] |
| 0 (TODAY) | Apr 10 | Install nRF Connect SDK + toolchain on dev machine | [ ] |
| 0 (TODAY) | Apr 10 | Pre-build firmware so it's ready when DKs arrive | [ ] |
| 1 | Apr 11 | DKs arrive. Flash transmitter + 2 receivers. | [ ] |
| 1 | Apr 11 | Verify Auracast broadcast works end-to-end | [ ] |
| 2 | Apr 12 | Record demo video (multiple takes, pick best) | [ ] |
| 2 | Apr 12 | Edit video (trim + text overlay, 10 min max) | [ ] |
| 3 | Apr 13 | Post video: Twitter/X, LinkedIn, YouTube Shorts | [ ] |
| 3 | Apr 13 | Update koe.live with demo video embed | [ ] |
| 4 | Apr 14 | Send first 5 outreach emails with video link | [ ] |
| 4 | Apr 14 | Follow up on social media engagement | [ ] |

---

## Troubleshooting

### DKs won't flash
```bash
# Reset the board: hold RESET button for 3 seconds
# Check USB connection:
nrfjprog --ids  # Should show connected DK serial numbers

# If locked:
nrfjprog --recover --snr <SERIAL>
west flash --snr <SERIAL>
```

### No audio from receivers
1. Check broadcast source is running: LED1 should blink on transmitter
2. Check sink is scanning: LED1 blinks on receiver until connected
3. Verify with nRF Connect for Mobile -- scan for BLE broadcasts
4. Check audio input: USB audio or LINE IN on transmitter DK
5. Increase volume on receiver: use onboard buttons or serial console

### Audio drops / sync issues
```bash
# Monitor over serial console
screen /dev/tty.usbmodem* 115200

# Check for error logs about:
# - BIS sync failures
# - LC3 decode errors
# - Clock drift
```

### Build errors
```bash
# Clean and rebuild
west build -p always -b nrf5340_audio_dk/nrf5340/cpuapp \
  samples/bluetooth/audio/broadcast_source

# Check SDK version compatibility
west list nrf  # Should show v2.9.0 or later

# Update if needed
cd ~/ncs
west update
```

---

## Key Links

- [nRF5340 Audio DK Product Page](https://www.nordicsemi.com/Products/Development-hardware/nRF5340-Audio-DK)
- [nRF Connect SDK LE Audio Samples](https://docs.nordicsemi.com/bundle/ncs-latest/page/nrf/samples/bluetooth/audio/index.html)
- [Auracast Official Site](https://www.bluetooth.com/auracast/)
- [LC3 Codec Specification](https://www.bluetooth.com/specifications/specs/low-complexity-communication-codec-1-0/)
- [DigiKey Order Page](https://www.digikey.com/en/products/detail/nordic-semiconductor-asa/NRF5340-AUDIO-DK/16653382)

---

## What This Proves

This demo validates the core Koe COIN value proposition:

1. **Auracast broadcast works** -- one source, unlimited receivers
2. **Sync is tight** -- LC3 codec ensures sub-ms synchronization
3. **Range is real** -- 30m+ with built-in antenna, 100m+ with FEM
4. **The tech is mature** -- Nordic's SDK has production-ready samples

**After this demo, the only question is form factor and price -- which our COIN design already answers.**
