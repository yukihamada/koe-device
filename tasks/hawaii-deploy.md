# Hawaii Deployment Checklist — Oki's House (June 28, 2026)

**Venue**: 濱田優貴 (Oki) residence, Hawaii
**Guests**: ONE OK ROCK band + crew, arrive July 1, 2026
**Hard deadline**: Everything verified and working by **June 28, 2026 18:00 HST**
**Devices**: 4× Amp (Raspberry Pi 5 + ReSpeaker USB), Stone = AirPlay 2 speakers (stand-in), Pick = skipped
**Session archive slug**: `hawaii-2026-07` | Password: `KOE2026`

---

## Phase 0 — Pre-arrival Prep (complete before flying to Hawaii)

Hardware approach: **plug-and-play Raspberry Pi 5 units** — no soldering, no firmware flashing on-site.
All SD cards are pre-flashed and bench-tested in Tokyo before shipping.
See `tasks/bom-pi5.md` for full parts list and order deadlines.

### 0-A: Hardware ordering (Tokyo, by June 23)
- [ ] Order 4× Pi 5 bundles via Amazon (see `tasks/bom-pi5.md` Section 1)
- [ ] Order Stone stand-ins if desired (Sonos Era 100 or IKEA SYMFONISK — see Section 2)
- [ ] Confirm all hardware arrives at Tokyo address

### 0-B: SD card flashing (Tokyo)
- [ ] Obtain Oki's WiFi SSID and password before flashing
- [ ] Flash SD card for each unit with unique device_id:
  ```bash
  cd /Users/yuki/workspace/koe-device/hub
  ./flash-sd.sh --device-id koe-amp-hawaii-01 --wifi-ssid <OKI_SSID> --wifi-pass <OKI_PASS>
  ./flash-sd.sh --device-id koe-amp-hawaii-02 --wifi-ssid <OKI_SSID> --wifi-pass <OKI_PASS>
  ./flash-sd.sh --device-id koe-amp-hawaii-03 --wifi-ssid <OKI_SSID> --wifi-pass <OKI_PASS>
  ./flash-sd.sh --device-id koe-amp-hawaii-04 --wifi-ssid <OKI_SSID> --wifi-pass <OKI_PASS>
  ```
- [ ] Insert flashed SD cards into Pi 5 units, attach ReSpeaker USB mic arrays

### 0-C: Bench verification (Tokyo)
- [ ] Verify 4× Pi 5 units boot and appear in `koe.live/api/v1/room/state`
  ```bash
  curl -s https://koe.live/api/v1/room/state | python3 -m json.tool
  # Expected: koe-amp-hawaii-01 through -04 listed with last_seen < 30s
  ```
- [ ] Verify ReSpeaker shows as audio device on each unit via SSH:
  ```bash
  ssh pi@<unit-ip> arecord -l
  # Expected: "ReSpeaker" or "UAC1.0 HID" listed as card
  ```
- [ ] Test onset detection: play guitar near Pi, verify session appears in `koe.live`
  - Clap or strum within 2m → session should appear in dashboard within 5 seconds

### 0-D: Server check
- [ ] Verify `koe.live` server is healthy: `curl https://koe.live/health`
- [ ] Confirm `KOE_ADMIN_TOKEN` is set: `fly ssh console -a koe-live --command "printenv KOE_ADMIN_TOKEN"`

### 0-E: Packing and shipping
- [ ] Box all 4 Pi 5 units (SD cards inserted, ReSpeaker attached, PSU + USB-A cable per unit)
- [ ] Ship to Oki's Hawaii address via FedEx International Priority by **June 22**
  - Transit: ~3–5 business days → arrive by June 27 (1-day buffer before setup day)
- [ ] Print this checklist

---

## Phase 1 — Hardware Setup

### 1-A: Room Assignments

| Room | Device | Device ID | Role |
|------|--------|-----------|------|
| Living room | Amp-1 (Pi 5) | `koe-amp-hawaii-01` | Primary session capture — main PA feed |
| Rehearsal room | Amp-2 (Pi 5) | `koe-amp-hawaii-02` | Guitar onset detection anchor (place within 2m of guitar) |
| Master bedroom | Amp-3 (Pi 5) | `koe-amp-hawaii-03` | Ambient |
| Lanai / outdoor | Amp-4 (Pi 5) | `koe-amp-hawaii-04` | Outdoor fill |
| Living room | Stone (Sonos/SYMFONISK) | — | AirPlay 2 playback (optional) |
| Rehearsal room | Stone (Sonos/SYMFONISK) | — | AirPlay 2 playback (optional) |

- [ ] Place Amp-1 in living room — near power outlet, ReSpeaker mic facing into room
- [ ] Place Amp-2 in rehearsal room — **within 2m of guitar playing position** (critical for onset detection)
- [ ] Place Amp-3 in master bedroom — on bedside shelf or dresser
- [ ] Place Amp-4 on lanai — keep out of direct rain/sun; Pi 5 is not weatherproof
- [ ] Place Stone speakers (if available) per room — pair with AirPlay 2 via Sonos app

### 1-B: WiFi Configuration

Oki's house WiFi credentials must be provisioned into NVS before deployment (see Phase 2).
Record actual credentials here (do NOT commit to git):

```
SSID: ___________________________
Pass: ___________________________
```

- [ ] Confirm WiFi band — Pi 5 supports both 2.4 GHz and 5 GHz (5 GHz preferred for lower latency)
- [ ] Confirm all device placement locations have signal ≥ -70 dBm (test with phone)
- [ ] Confirm internet reachability: `curl https://koe.live/health` from WiFi

### 1-C: Power

- [ ] Amp-1: Raspberry Pi 27W USB-C power supply → Pi 5 USB-C port
- [ ] Amp-2: Raspberry Pi 27W USB-C power supply
- [ ] Amp-3: Raspberry Pi 27W USB-C power supply
- [ ] Amp-4: Raspberry Pi 27W USB-C power supply (outdoor-rated extension cable if needed)
- [ ] Stone speakers (if Sonos/SYMFONISK): standard power brick per unit
- [ ] All cables are strain-relieved / taped down to avoid accidental disconnection
- [ ] No device is on an outlet controlled by a light switch

---

## Phase 2 — On-site Boot Verification

All SD cards are pre-flashed in Tokyo (see Phase 0-B). No firmware flashing or serial
cables required on-site. Just plug in power and verify connectivity.

### 2-A: Power on and wait

- [ ] Plug in Amp-1 (Pi 5 27W USB-C PSU) — wait 60 seconds for full boot
- [ ] Plug in Amp-2 — wait 60 seconds
- [ ] Plug in Amp-3 — wait 60 seconds
- [ ] Plug in Amp-4 — wait 60 seconds

### 2-B: Verify all units appear in koe.live

```bash
# Run from any laptop/phone on Oki's WiFi (or via mobile data):
curl -s https://koe.live/api/v1/room/state | python3 -m json.tool
# Expected: all 4 device IDs listed with last_seen < 30s
```

- [ ] `koe-amp-hawaii-01` appears in `koe.live/api/v1/room/state`
- [ ] `koe-amp-hawaii-02` appears in `koe.live/api/v1/room/state`
- [ ] `koe-amp-hawaii-03` appears in `koe.live/api/v1/room/state`
- [ ] `koe-amp-hawaii-04` appears in `koe.live/api/v1/room/state`

### 2-C: Verify ReSpeaker mic array on each unit

SSH into each unit (IPs shown in `koe.live/api/v1/room/state` or check router DHCP):

```bash
ssh pi@<unit-ip> arecord -l
# Expected output includes something like:
#   card N: ..., device 0: USB Audio [ReSpeaker Mic Array v2.0], ...
```

- [ ] Amp-1: ReSpeaker listed as audio device
- [ ] Amp-2: ReSpeaker listed as audio device
- [ ] Amp-3: ReSpeaker listed as audio device
- [ ] Amp-4: ReSpeaker listed as audio device

### 2-D: Onset detection smoke test

- [ ] Bring guitar near Amp-2 (rehearsal room, within 2m)
- [ ] Strum or clap loudly → verify a session appears in `koe.live` dashboard within 5s
- [ ] Gentle background noise → confirm no false session triggers

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

## Phase 6 — Pick (skipped for Hawaii July 1)

The Pick piezo sensor requires a custom PCB that is not yet manufactured.
For this deployment, Amp-2 captures guitar onset via room microphone.

**Action required**: Position Amp-2 within **2m of guitar playing position** in the
rehearsal room. The ReSpeaker array's beamforming gives reliable acoustic onset
detection without a contact piezo.

Verify onset detection works via Phase 2-D smoke test. Pick hardware will ship
in a later production revision after JLCPCB PCBs are back.

---

## Phase 7 — Day-of Checklist (June 28, 2026)

Run through this final list the morning of June 28 before guests arrive July 1.

### Hardware
- [ ] All 4 Amp units (Pi 5) powered on — green LED on board, active in `koe.live/api/v1/room/state`
- [ ] All 4 ReSpeaker mic arrays connected and listed in `arecord -l` (SSH spot-check one unit)
- [ ] Stone speakers (if Sonos/SYMFONISK) powered on and reachable from Oki's network
- [ ] Amp-2 placed within 2m of guitar playing position (room mic onset detection)
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
- [ ] Oki knows the recovery procedure: unplug USB-C, wait 10s, replug (Pi 5 reboots cleanly)
- [ ] Oki knows SSH access: `ssh pi@<unit-ip>` (password set during SD flash)
- [ ] Oki has contact for remote support (see Phase 8)

---

## Phase 8 — Emergency Contacts & Recovery

### Device offline (no heartbeat for > 2 minutes)

1. Check WiFi — reconnect router if it was restarted
2. Power-cycle Pi 5: unplug USB-C, wait 10 seconds, replug
   - Pi 5 boots in ~45 seconds; allow 60s before checking `koe.live/api/v1/room/state`
3. If still offline after reboot: SSH into unit and check logs:
   ```bash
   ssh pi@<unit-ip> journalctl -u koe-hub --since "5 min ago"
   ```
4. If unit won't boot or SD card is corrupt: contact Yuki — a replacement SD can be
   shipped overnight or re-flashed remotely via image download

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
