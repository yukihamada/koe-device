# Hawaii Hardware Order — Koe Amp × 4 Units

**Ship-to**: Oki's house, Hawaii (confirm exact address via Signal)
**Order by**: **June 14, 2026** (Amazon Prime ships to Hawaii in 2–5 days → arrives by June 19–21, leaving ample time before June 28 go-live)
**Budget**: ~$596 total (4 units × ~$149)

---

## Per-Unit BOM

| Qty | Part | Spec | ~Unit Price |
|-----|------|------|-------------|
| 1 | Raspberry Pi 5 (4GB) | Quad-core Cortex-A76, WiFi 5, USB-C power | $60 |
| 1 | ReSpeaker USB Mic Array v2.0 | Seeed Studio 107990056, 4-mic, 16kHz, USB plug-and-play | $40 |
| 1 | Raspberry Pi 27W USB-C Power Supply | Official RPi 5 PSU, white, US plug | $12 |
| 1 | 32GB microSD Card | Samsung PRO Endurance, Class 10 / A1 (high endurance for 24/7 logging) | $12 |
| 1 | Raspberry Pi 5 Case with Fan | Argon ONE V3 ACTIVE Cooling Case OR Official RPi 5 Active Cooler | $25 |
| **Total per unit** | | | **$149** |

**4 units total**: **~$596**

---

## Amazon.com Product Links (ships to Hawaii)

### Raspberry Pi 5 (4GB)
- **Seeed Studio via Amazon**: https://www.amazon.com/Raspberry-Pi-Quad-core-Cortex-A76-Processor/dp/B0CQ7PNMYB
- **CanaKit via Amazon**: https://www.amazon.com/CanaKit-Raspberry-Pi-Starter-Kit/dp/B0CRSNCJ6Y
- Search term: `"Raspberry Pi 5 4GB"` — buy from Seeed Studio, CanaKit, or Vilros (authorized resellers)
- **Note**: Official RPi Foundation stock at rpilocator.com if Amazon shows "usually ships in X weeks"
- Qty: **4**

### ReSpeaker USB Mic Array v2.0
- **Seeed Studio Part**: 107990056
- **Amazon listing**: https://www.amazon.com/seeed-studio-ReSpeaker-Microphone-Interface/dp/B07G59QWZP
- Search term: `"ReSpeaker USB Microphone Array v2"` or `"Seeed 107990056"`
- No drivers needed on Raspberry Pi OS — plug-and-play USB audio device
- Qty: **4**

### Official Raspberry Pi 27W USB-C Power Supply
- **Amazon listing**: https://www.amazon.com/Raspberry-Pi-27W-USB-C-Supply/dp/B0CH3LNFFX
- Search term: `"Raspberry Pi 5 USB-C power supply 27W"`
- Must be the official PSU — third-party 5A supplies may cause undervolt warnings
- US plug (Type A) — correct for Hawaii
- Qty: **4**

### 32GB microSD — Samsung PRO Endurance
- **Amazon listing**: https://www.amazon.com/SAMSUNG-Endurance-32GB-Micro-Adapter/dp/B09WB3KWXZ
- Model: MB-MJ32KA (PRO Endurance, 32GB)
- Rated for 43,800 hours of continuous video recording — ideal for 24/7 Pi logging
- Qty: **4**

### Raspberry Pi 5 Case with Active Cooling
Two options — either works:

**Option A (recommended): Argon ONE V3 ACTIVE**
- Amazon: https://www.amazon.com/Argon-ONE-Raspberry-Active-Cooling/dp/B0CRRQHPQ5
- Search: `"Argon ONE V3 Raspberry Pi 5 case"`
- Aluminum body + integrated fan + power button + full GPIO access
- Qty: **4**

**Option B (official): Raspberry Pi 5 Case (official)**
- Amazon: https://www.amazon.com/Raspberry-Pi-Case-Compatible-Computer/dp/B0CSB7M33Z
- + Official Active Cooler: https://www.amazon.com/Raspberry-Pi-Active-Cooler/dp/B0CTTGHJLV
- The official case does not include a fan — must add Active Cooler ($5) separately
- Qty: **4** cases + **4** coolers

---

## Total Cost Breakdown

| Item | Qty | Unit | Subtotal |
|------|-----|------|----------|
| Raspberry Pi 5 (4GB) | 4 | $60 | $240 |
| ReSpeaker USB Mic Array v2.0 | 4 | $40 | $160 |
| Official RPi 5 USB-C 27W PSU | 4 | $12 | $48 |
| Samsung PRO Endurance 32GB | 4 | $12 | $48 |
| Argon ONE V3 case w/ fan | 4 | $25 | $100 |
| **Grand total** | | | **$596** |

Tax + shipping to Hawaii: ~$40–60 (Prime 2-day free, tax varies)
**Estimated all-in: ~$640**

---

## SD Card Flashing (do this in Tokyo before shipping)

Each SD card must be flashed before the units ship to Hawaii. Use `hub/flash-sd.sh`:

```bash
# Amp-1 (living room)
sudo ./flash-sd.sh /dev/sdX koe-amp-hawaii-01 living_room "OKI_WIFI_SSID" "OKI_WIFI_PASS"

# Amp-2 (rehearsal room)
sudo ./flash-sd.sh /dev/sdX koe-amp-hawaii-02 rehearsal_room "OKI_WIFI_SSID" "OKI_WIFI_PASS"

# Amp-3 (master bedroom)
sudo ./flash-sd.sh /dev/sdX koe-amp-hawaii-03 master_bedroom "OKI_WIFI_SSID" "OKI_WIFI_PASS"

# Amp-4 (lanai / outdoor)
sudo ./flash-sd.sh /dev/sdX koe-amp-hawaii-04 lanai "OKI_WIFI_SSID" "OKI_WIFI_PASS"
```

Confirm WiFi SSID + password with Oki via Signal before flashing (do NOT commit to git).

After flashing, insert SD cards and power on in Tokyo to confirm first-boot provisioning works
(connect to a hotspot with the same SSID, or update credentials via `flash-sd.sh` for your
local test WiFi first).

---

## Oki On-site Instructions (zero-setup)

1. Unbox each unit: Pi 5 in case, ReSpeaker plugged into USB, USB-C power cable
2. Plug USB-C power into the wall — device boots automatically
3. Within 2 minutes: koe-amp service starts, device appears at https://koe.live/api/devices
4. Nothing else required

Verify all 4 units are online:
```bash
curl -s https://koe.live/api/devices | python3 -m json.tool
# Expected: koe-amp-hawaii-01 through 04, last_seen < 30s ago
```

---

## Shipping Timeline

| Date | Action |
|------|--------|
| **June 14** | Place Amazon.com orders (Prime delivery) |
| **June 19–21** | Hardware arrives at destination or Yuki's address |
| **June 22–24** | Flash SD cards, test boot in Tokyo |
| **June 25** | Ship pre-configured units to Oki (or carry if traveling) |
| **June 28** | On-site final verification per `tasks/hawaii-deploy.md` Phase 3 |
| **July 1** | ONE OK ROCK arrives — devices operational |
