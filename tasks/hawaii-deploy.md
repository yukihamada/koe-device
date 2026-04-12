# Hawaii Deployment Checklist — Oki's House (June 28, 2026)

**Venue**: 濱田優貴 (Oki) residence, Hawaii
**Guests**: ONE OK ROCK band + crew, arrive July 1, 2026
**Hard deadline**: Everything verified and working by **June 28, 2026 18:00 HST**
**Devices**: 4× Amp (ESP32-S3), 2× Stone (nRF5340), 1× Pick (ESP32-C3)
**Session archive slug**: `hawaii-2026-07` | Password: `KOE2026`

---

## Phase 0 — Pre-arrival Prep (complete before flying to Hawaii)

- [ ] Flash all firmware locally in Tokyo (see Phase 2)
- [ ] Verify `koe.live` server is healthy: `curl https://koe.live/health`
- [ ] Confirm `KOE_ADMIN_TOKEN` is set: `fly ssh console -a koe-live --command "printenv KOE_ADMIN_TOKEN"`
- [ ] Deploy latest firmware OTA binary:
  ```bash
  cd /Users/yuki/workspace/koe-device/firmware/amp
  ./deploy-ota.sh --release --token $KOE_ADMIN_TOKEN
  ```
- [ ] Pack: ESP32-S3 devkits × 4, INMP441 mics × 8, MAX98357A × 4, WS2812B × 4, USB-C supplies × 4, breadboards, jumpers, USB-UART programmer, soldering iron, solder, foam tape
- [ ] Pack: nRF5340-DK × 2, 3W speakers × 2
- [ ] Pack: ESP32-C3 SuperMini × 1 (Pick unit for guitar)
- [ ] Print this checklist

---

## Phase 1 — Hardware Setup

### 1-A: Room Assignments

| Room | Device | Device ID | Role |
|------|--------|-----------|------|
| Living room | Amp-1 | `koe-amp-hawaii-01` | Primary listening — main PA feed |
| Rehearsal room | Amp-2 | `koe-amp-hawaii-02` | Guitar onset detection anchor |
| Master bedroom | Amp-3 | `koe-amp-hawaii-03` | Ambient |
| Lanai / outdoor | Amp-4 | `koe-amp-hawaii-04` | Outdoor fill |
| Living room | Stone-1 | `koe-stone-hawaii-01` | Auracast broadcast (earphone listening) |
| Rehearsal room | Stone-2 | `koe-stone-hawaii-02` | Auracast broadcast |

- [ ] Place Amp-1 in living room — near power outlet, mic facing into room, LED visible
- [ ] Place Amp-2 in rehearsal room — within 2m of guitar playing position
- [ ] Place Amp-3 in master bedroom — on bedside shelf or dresser
- [ ] Place Amp-4 on lanai — weatherproof placement (keep out of direct rain/sun)
- [ ] Place Stone-1 on living room bookshelf or TV stand — 1PPS GPS antenna near window if available
- [ ] Place Stone-2 on rehearsal room shelf — clear line-of-sight to ceiling

### 1-B: WiFi Configuration

Oki's house WiFi credentials must be provisioned into NVS before deployment (see Phase 2).
Record actual credentials here (do NOT commit to git):

```
SSID: ___________________________
Pass: ___________________________
```

- [ ] Confirm 2.4 GHz band available (ESP32-S3 does not support 5 GHz)
- [ ] Confirm all device placement locations have signal ≥ -70 dBm (test with phone)
- [ ] Confirm internet reachability: `curl https://koe.live/health` from WiFi

### 1-C: Power

- [ ] Amp-1: USB-C 5V 2A wall adapter → DevKit USB-C port
- [ ] Amp-2: USB-C 5V 2A wall adapter
- [ ] Amp-3: USB-C 5V 2A wall adapter
- [ ] Amp-4: USB-C 5V 2A wall adapter (outdoor-rated extension cable if needed)
- [ ] Stone-1: USB Micro-B from USB wall adapter
- [ ] Stone-2: USB Micro-B from USB wall adapter
- [ ] All cables are strain-relieved / taped down to avoid accidental disconnection
- [ ] No device is on an outlet controlled by a light switch

---

## Phase 2 — Firmware Flashing & NVS Provisioning

Run these commands on each device before placing in its room.
Requires: `espflash` + `esptool.py` + `cargo` (Rust toolchain) on the deployment laptop.

### 2-A: Flash firmware binary (first time only)

```bash
# Connect ESP32-S3 DevKit via USB-UART programmer
# Check port: ls /dev/tty.usbserial-* or ls /dev/ttyUSB*

cd /Users/yuki/workspace/koe-device/firmware/amp

# Build release binary
cargo build --release

# Flash to device (replace /dev/tty.usbserial-0001 with actual port)
espflash flash --chip esp32s3 --port /dev/tty.usbserial-0001 \
  target/xtensa-esp32s3-espidf/release/koe-firmware
```

- [ ] Amp-1 flashed
- [ ] Amp-2 flashed
- [ ] Amp-3 flashed
- [ ] Amp-4 flashed

### 2-B: Provision NVS (WiFi + device_id)

NVS namespace: `koe`, keys: `wifi_ssid`, `wifi_pass`, `device_id`

```bash
# Generate NVS CSV for each device:
# nvs_partition_gen.py from esp-idf tools

# Example for Amp-1 (repeat per device, change device_id each time):
python3 $IDF_PATH/components/nvs_flash/nvs_partition_generator/nvs_partition_gen.py \
  generate nvs_amp1.csv nvs_amp1.bin 0x6000

# nvs_amp1.csv contents:
# key,type,encoding,value
# koe,namespace,,
# wifi_ssid,data,string,<OKI_WIFI_SSID>
# wifi_pass,data,string,<OKI_WIFI_PASS>
# device_id,data,string,koe-amp-hawaii-01

# Flash NVS partition (offset 0x9000):
esptool.py --port /dev/tty.usbserial-0001 write_flash 0x9000 nvs_amp1.bin
```

- [ ] Amp-1 NVS: `device_id=koe-amp-hawaii-01` + Oki WiFi
- [ ] Amp-2 NVS: `device_id=koe-amp-hawaii-02` + Oki WiFi
- [ ] Amp-3 NVS: `device_id=koe-amp-hawaii-03` + Oki WiFi
- [ ] Amp-4 NVS: `device_id=koe-amp-hawaii-04` + Oki WiFi
- [ ] Securely delete all `nvs_amp*.csv` files after flashing

### 2-C: Stone NVS (serial number)

Stone firmware uses NVS key `serial` (NVS_KEY_SERIAL = 1) in Zephyr NVS.

```bash
# Flash Stone firmware via nRF Connect Programmer or west
cd /Users/yuki/workspace/koe-device/firmware/stone
west build -b nrf5340dk/nrf5340/cpuapp
west flash

# Set serial via UART shell after boot:
uart:~$ nvs write 1 "KOE-STONE-HI-01"
```

- [ ] Stone-1 serial: `KOE-STONE-HI-01`
- [ ] Stone-2 serial: `KOE-STONE-HI-02`

---

## Phase 3 — API Verification

Run these from a laptop/phone on Oki's WiFi after devices are powered on and placed.
Allow 60 seconds after power-on for WiFi + SNTP sync.

### 3-A: Heartbeat check

```bash
# Each device should be sending heartbeats every 5 seconds.
# Check server-side device list:
curl -s https://koe.live/api/devices | python3 -m json.tool

# Expected: all 4 device_ids appear with last_seen < 30s ago
```

- [ ] `koe-amp-hawaii-01` appears in `/api/devices`
- [ ] `koe-amp-hawaii-02` appears in `/api/devices`
- [ ] `koe-amp-hawaii-03` appears in `/api/devices`
- [ ] `koe-amp-hawaii-04` appears in `/api/devices`

### 3-B: Session creation

```bash
# Manually trigger a test session on Amp-2 (rehearsal room):
curl -s -X POST https://koe.live/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"device_id":"koe-amp-hawaii-02"}' | python3 -m json.tool
# Expected: {"session_id":"<uuid>"}

SESSION_ID=<uuid from above>

# Start it:
curl -s -X POST https://koe.live/api/v1/sessions/$SESSION_ID/start \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"koe-amp-hawaii-02\",\"timestamp_ms\":$(date +%s%3N)}"

# End it:
curl -s -X POST https://koe.live/api/v1/sessions/$SESSION_ID/end \
  -H "Content-Type: application/json" \
  -d "{\"device_id\":\"koe-amp-hawaii-02\",\"timestamp_ms\":$(date +%s%3N)}"
```

- [ ] Session create returns 200/201 with valid `session_id`
- [ ] Session start returns 200/204
- [ ] Session end returns 200/204

### 3-C: OTA version check

```bash
# Device should respond 204 (already up to date):
curl -I "https://koe.live/api/v1/device/firmware?version=0.3.1&device_id=koe-amp-hawaii-01"
# Expected: HTTP/2 204
```

- [ ] OTA endpoint returns 204 for all 4 Amp devices

---

## Phase 4 — Room Display Setup

Goal: A TV or tablet in the living room and rehearsal room shows `koe.live/app`
in full-screen kiosk mode so guests can see the live session visualizer.

### 4-A: TV setup (if smart TV available)

- [ ] Open browser on Smart TV → navigate to `https://koe.live/app`
- [ ] Enable "keep screen on" / disable screen saver in TV settings
- [ ] Set TV input to browser app (so it's the default on power-on)

### 4-B: Tablet / laptop kiosk (fallback)

```bash
# macOS kiosk mode (replace with actual URL):
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --kiosk --noerrdialogs --disable-session-crashed-bubble \
  --disable-infobars "https://koe.live/app"

# Or on iPad: open koe.live/app in Safari, "Add to Home Screen",
# then Settings → Accessibility → Guided Access → ON
```

- [ ] Living room display showing `koe.live/app` — full screen, no browser chrome
- [ ] Rehearsal room display showing `koe.live/app`
- [ ] Both displays set to never sleep / auto-lock disabled

---

## Phase 5 — Sessions Archive Share

The `hawaii-2026-07` archive will contain all sessions recorded during the stay.
Share link with band manager before July 1.

- [ ] Confirm sessions are being stored under slug `hawaii-2026-07`:
  ```bash
  curl -s "https://koe.live/sessions/hawaii-2026-07" | head -20
  ```
- [ ] Send the following to band manager via email/Line:

  ```
  Koe sessions archive for your Hawaii stay:
  URL: https://koe.live/sessions/hawaii-2026-07
  Password: KOE2026

  This archive records all sound moments captured by the Koe devices
  in the house during your stay (July 1–15). Sessions are saved
  automatically whenever the devices detect music or voice onset.
  ```

- [ ] Confirm band manager has received and can access the link

---

## Phase 6 — Pick Attachment (Guitar)

The Pick unit attaches to the guitar body and detects string onset via piezo transducer.

### 6-A: Attach to guitar

- [ ] Identify guitar to instrument (Taka's acoustic or house guitar — confirm with Oki)
- [ ] Clean guitar body surface near lower bout with isopropyl alcohol — dry completely
- [ ] Attach 27mm piezo disk to guitar top (near bridge, not on seam) using 3M foam tape
- [ ] Route thin silicone strap around guitar body (below sound hole) to hold Pick unit
- [ ] Secure ESP32-C3 SuperMini unit in strap pocket — USB-C charge port accessible
- [ ] Confirm piezo wire connection is secure (hot-glue strain relief if needed)

### 6-B: Verify onset detection

```bash
# Monitor BLE advertisements from Pick (use phone BLE scanner or nRF Connect app)
# Or check Amp-2 logs if Pick is paired: LED on Amp-2 should flash on guitar strum

# Manual API check after a strum:
curl -s "https://koe.live/api/devices" | python3 -m json.tool | grep -A5 "amp-hawaii-02"
# Expect: audio_level > 0.1 within 2s of strum
```

- [ ] Pick is physically secure — does not rattle or buzz
- [ ] Hard strum → LED flash visible on Amp-2 within 2 seconds
- [ ] Gentle fingerpicking → no false triggers
- [ ] Pick battery charged to 100% (check USB-C indicator LED)

---

## Phase 7 — Day-of Checklist (June 28, 2026)

Run through this final list the morning of June 28 before guests arrive July 1.

### Hardware
- [ ] All 4 Amp units powered on and LED showing idle pattern (slow pulse)
- [ ] Both Stone units powered on and Auracast broadcast active (verify with BLE scanner: look for "KOE-STONE-HI-01" in LE Audio broadcasts)
- [ ] Pick unit charged, attached to guitar, onset detection working
- [ ] No loose cables visible in common areas

### Network
- [ ] `curl https://koe.live/api/devices` — all 4 device IDs present, `last_seen` < 30s
- [ ] Oki's WiFi router is on a UPS or has been confirmed stable (no scheduled restarts)

### Displays
- [ ] Living room display: `koe.live/app` — full screen, no sleep
- [ ] Rehearsal room display: `koe.live/app` — full screen, no sleep

### Sessions archive
- [ ] `https://koe.live/sessions/hawaii-2026-07` loads with password `KOE2026`
- [ ] Band manager has confirmed they can access it

### Backup
- [ ] Extra USB-C cable accessible in a drawer (in case of cable failure)
- [ ] Oki knows the factory reset procedure: hold button 5 seconds (LED goes red then reboot)
- [ ] Oki has contact for remote support (see Phase 8)

---

## Phase 8 — Emergency Contacts & Recovery

### Device offline (no heartbeat for > 2 minutes)

1. Check WiFi — reconnect if router was restarted
2. Power-cycle device: unplug USB-C, wait 10 seconds, replug
3. If still offline: factory reset (hold button 5 seconds — LED flashes red)
   - Device will reboot and reconnect using stored NVS WiFi credentials
   - NVS credentials are NOT erased by normal reboot — only by factory reset
4. If factory reset needed, NVS must be reflashed with WiFi + device_id (contact Yuki)

### OTA firmware hung (device restarting loop)

- The OTA system writes to `ota_0`/`ota_1` partitions only — NVS is never erased
- If boot loop: hold button during power-on to stay in factory partition (contact Yuki for recovery)

### Session data not appearing on koe.live

```bash
# Check server status:
curl https://koe.live/health
# If down: fly status -a koe-live (run from any machine with fly CLI)
# Restart if needed: fly restart -a koe-live
```

### Contacts

| Role | Contact | Method |
|------|---------|--------|
| Remote support (firmware/server) | 濱田祐樹 (Yuki) | mail@yukihamada.jp / iMessage |
| On-site host | 濱田優貴 (Oki) | local |
| koe.live server | fly status -a koe-live | CLI |

**Yuki's availability during ONE OK ROCK stay (July 1–15)**:
Available via iMessage for remote debugging. For urgent issues (server down),
Yuki can SSH into Fly.io within minutes from anywhere.
