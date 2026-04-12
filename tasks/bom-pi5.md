# Koe Device — Pi 5 BOM (Hawaii Deployment, Plug-and-Play)

**Deadline**: Must arrive in Hawaii before **July 1, 2026** (ONE OK ROCK arrival)
**Order deadline**: **June 23, 2026** (5-day Hawaii delivery buffer before June 28 setup day)
**Today**: April 12, 2026 → ~72 days remaining
**Approach**: Raspberry Pi 5 + ReSpeaker USB mic — no soldering, no firmware flashing, plug-and-play

---

## Section 1: Amp Units (Pi 5 based, plug-and-play) × 4

Each Amp unit is a Raspberry Pi 5 running `hub/` software with a USB mic array.
No soldering required. Pre-flash SD cards in Tokyo, ship to Hawaii.

| # | Part | Unit USD | Source | Part # |
|---|------|----------|--------|--------|
| 1 | Raspberry Pi 5 4GB | $60.00 | Amazon.com: [B0CK7H1V9W](https://www.amazon.com/dp/B0CK7H1V9W) / Adafruit #5813 | RPi5-4GB |
| 2 | ReSpeaker USB Mic Array v2.0 | $40.00 | Seeed Studio: [107990056](https://www.seeedstudio.com/ReSpeaker-USB-Mic-Array-p-4247.html) / Amazon: search "ReSpeaker USB Mic Array v2" | 107990056 |
| 3 | Raspberry Pi 27W USB-C Power Supply | $12.00 | Amazon: [B0CG9KVS4D](https://www.amazon.com/dp/B0CG9KVS4D) | — |
| 4 | Samsung PRO Endurance 32GB microSD | $12.00 | Amazon: [B09W9XXBN9](https://www.amazon.com/dp/B09W9XXBN9) | — |
| 5 | Raspberry Pi 5 Case with fan (official) | $12.00 | Amazon: [B0CSNFNWPQ](https://www.amazon.com/dp/B0CSNFNWPQ) | — |

**Subtotal per unit: ~$136**
**4 units: ~$544**

### What "plug-and-play" means
- SD card pre-flashed with Koe Hub OS image in Tokyo (via `hub/flash-sd.sh`)
- Unit powers on → connects to Oki's WiFi → registers with `koe.live` automatically
- No serial cable, no `espflash`, no NVS partition tool needed on-site

---

## Section 2: Stone (use existing Bluetooth speakers for Hawaii prototype)

The nRF5340-based Stone hardware (Auracast BLE Audio) is not yet shipping.
For the Hawaii prototype, use AirPlay 2-capable speakers as stand-ins —
near-synchronous playback without custom firmware.

### Option A — Recommended (best sync)
| Item | Unit USD | Qty | Subtotal | Notes |
|------|----------|-----|----------|-------|
| Sonos Era 100 | $249 | 4 | $996 | AirPlay 2 multi-room sync, best stand-in for Auracast |

### Option B — Budget
| Item | Unit USD | Qty | Subtotal | Notes |
|------|----------|-----|----------|-------|
| IKEA SYMFONISK (Sonos-based) | $99 | 4 | $396 | Same AirPlay 2 stack, smaller form factor |

### Option C — Zero cost
Use whatever speakers are already at Oki's house (HomePod mini, etc.).
The Amp recording pipeline works independently of playback speakers.
Stone can be skipped entirely for this prototype without affecting session capture.

> **Note**: The real Stone hardware (nRF5340 + LC3 BLE Audio Auracast broadcast) ships
> in a later production run. These speaker stand-ins prove the multi-room experience
> without custom RF firmware.

---

## Section 3: Pick (skip for Hawaii July 1)

The Pick piezo sensor requires a custom PCB (28mm round, ESP32-C3, LiPo) that is
not yet manufactured.

**Decision: skip Pick for Hawaii.** The Amp units capture acoustic guitar well via
room microphone when placed within 2m of the playing position.

> **Placement note**: Position Amp-2 (rehearsal room) within **2m of guitar playing
> position** for reliable onset detection. The ReSpeaker array's beamforming and
> noise suppression give better pickup than the bare INMP441 in the old BOM.

Pick will ship in a post-Hawaii revision once custom PCBs are back from JLCPCB.

---

## Section 4: Total and Ordering

### Minimum viable Hawaii setup (Amp only)

| Line item | Cost |
|-----------|------|
| 4× Pi 5 bundle | ~$544 |
| **Total** | **~$544** |

- Order via **Amazon Prime**: 2-day delivery in contiguous US, ~5-day delivery to Hawaii
- **Order deadline: June 23, 2026** (5-day buffer before June 28 setup day)

### Recommended enhanced setup (Amp + Stone)

| Line item | Cost |
|-----------|------|
| 4× Pi 5 bundle | ~$544 |
| 4× Sonos Era 100 | ~$996 |
| **Total** | **~$1,540** |

### Budget-conscious enhanced setup

| Line item | Cost |
|-----------|------|
| 4× Pi 5 bundle | ~$544 |
| 4× IKEA SYMFONISK | ~$396 |
| **Total** | **~$940** |

---

## Section 5: Pre-configuration Steps (what Yuki does in Tokyo)

Before shipping to Hawaii, do the following at the Tokyo office:

1. **Order hardware** → deliver to Tokyo address (2-day domestic Amazon)

2. **Flash SD cards** — run for each of the 4 units:
   ```bash
   cd /Users/yuki/workspace/koe-device/hub
   # device_id is unique per unit (01–04)
   ./flash-sd.sh --device-id koe-amp-hawaii-01 --wifi-ssid <OKI_SSID> --wifi-pass <OKI_PASS>
   ./flash-sd.sh --device-id koe-amp-hawaii-02 --wifi-ssid <OKI_SSID> --wifi-pass <OKI_PASS>
   ./flash-sd.sh --device-id koe-amp-hawaii-03 --wifi-ssid <OKI_SSID> --wifi-pass <OKI_PASS>
   ./flash-sd.sh --device-id koe-amp-hawaii-04 --wifi-ssid <OKI_SSID> --wifi-pass <OKI_PASS>
   ```
   WiFi credentials are baked into the image — units auto-connect on first boot.

3. **Bench test each unit** in Tokyo before boxing:
   - Power on Pi 5 → wait 60 seconds → verify it appears in `koe.live/api/v1/room/state`
   - Plug in ReSpeaker USB mic array → confirm it shows up: `arecord -l` (via SSH)
   - Clap near unit → verify a session appears in `koe.live` dashboard

4. **Box and ship to Oki's Hawaii address** via FedEx International Priority
   - Estimated transit: 3–5 business days from Tokyo to Hawaii
   - Ship by **June 22** to guarantee June 27 arrival (1-day buffer before setup)

---

## Comparison: Old BOM vs This BOM

| Aspect | bom-prototype.md (ESP32-S3) | bom-pi5.md (Pi 5) |
|--------|----------------------------|-------------------|
| Microphone | INMP441 I2S breakout (requires wiring) | ReSpeaker USB array (plug-in) |
| Firmware | Rust ESP-IDF (flash via espflash) | Linux Hub software (SD card image) |
| Soldering required | Yes (breadboard + Dupont jumpers) | No |
| NVS provisioning | esptool.py flash 0x9000 | Baked into SD image |
| Amp unit cost | ~$42/unit | ~$136/unit |
| Total Amp (×4) | ~$168 | ~$544 |
| Setup complexity | High (wiring + firmware) | Low (plug and boot) |
| Reliability | Dev kit — acceptable for prototype | Higher (USB-C PSU, active cooling, SD endurance) |
| Pick support | ESP32-C3 SuperMini (planned) | Skipped for July 1 |
| Stone support | nRF5340-DK dev kit | AirPlay 2 speakers (stand-in) |
