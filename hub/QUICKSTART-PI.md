# Koe Amp — Pi 5 Quick-Start (Tokyo Prep → Hawaii Ship)

Step-by-step guide for preparing 4 SD cards in Tokyo before shipping to Hawaii  
(濱田優貴 ハワイ試作ホスト宅、ONE OK ROCK 2026-07-01〜15 滞在期間に間に合わせる)

---

## What you need

| Item | Notes |
|------|-------|
| Raspberry Pi 5 (×4) | 4 GB RAM or 8 GB |
| MicroSD cards (×4) | 32 GB+ Class A2 recommended |
| balena Etcher | https://etcher.balena.io/ |
| MacBook (this machine) | For flashing + verifying |
| USB-C power supply | 5V 5A per Pi |

---

## Option A — balenaCloud (recommended, zero-touch)

This is the easiest path. All 4 devices get OTA updates forever.

### 1. Push the fleet once

```bash
cd /Users/yuki/workspace/koe-device/hub/balena
balena login                                          # opens browser
balena fleet create koe-amp --type raspberrypi5       # one-time
balena push koe-amp                                   # uploads container image
```

### 2. Download 4 OS images

1. Go to https://dashboard.balena-cloud.com → fleet **koe-amp** → *Add device*.
2. Set **WiFi credentials** = Hawaii home WiFi (ask 濱田優貴 for SSID/password).
3. Image type: **Production**.
4. Download → you get `balena-koe-amp-raspberrypi5-<hash>.img.zip`.
5. Repeat 4 times (each image pre-embeds the device certificate, so they are different).

> Tip: generate all 4 in one browser session. Each download is ~700 MB.

### 3. Flash each SD card

```bash
# With balena CLI (scripted):
balena os flash balena-koe-amp-raspberrypi5-<hash>.img.zip \
  --drive /dev/diskN   # check with: diskutil list
```

Or use the GUI Etcher app — Select Image → Select Drive → Flash.

### 4. Set per-device room names

After all 4 devices power on and appear in the dashboard (takes ~90 s each),
set individual room variables:

```bash
balena env add KOE_ROOM living_room  --device <uuid-1>
balena env add KOE_ROOM bedroom      --device <uuid-2>
balena env add KOE_ROOM studio       --device <uuid-3>
balena env add KOE_ROOM stage        --device <uuid-4>
```

UUIDs are shown in the balena dashboard device list.

### 5. Verify each unit before boxing

```bash
balena logs <uuid> --tail 20
# Expected output:
# [koe-amp] Listening on 239.42.42.1:4242 (room=living_room)
```

Also check the dashboard status dot is green (online).

---

## Option B — Raspberry Pi OS (manual, no cloud dependency)

Use this if balenaCloud is not available or you prefer self-hosted.

### 1. Download image

- **Raspberry Pi OS Lite (64-bit)** — Debian Bookworm  
  https://www.raspberrypi.com/software/operating-systems/  
  (No desktop needed — saves ~1 GB and boots faster)

### 2. Flash with Raspberry Pi Imager

Use the official Raspberry Pi Imager (https://www.raspberrypi.com/software/):

1. Choose OS → *Use custom* → select the `.img.xz`.
2. Click the gear icon (Advanced options) **before** flashing:
   - Enable SSH (use password auth, set `pi` / `koedevice`)
   - Set hostname: `koe-amp-1` … `koe-amp-4`
   - Configure WiFi: enter Hawaii home SSID + password (ask 濱田優貴)
3. Write to SD card.

### 3. Pre-configure WiFi (manual method, boot partition)

If you prefer to edit the SD card directly after flashing:

```bash
# Mount the boot partition (shows as "bootfs" on Mac)
# Create wpa_supplicant.conf on that partition:
cat > /Volumes/bootfs/wpa_supplicant.conf <<'EOF'
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="HawaiiHomeSSID"
    psk="HawaiiHomePassword"
    key_mgmt=WPA-PSK
}
EOF

# Enable SSH
touch /Volumes/bootfs/ssh
```

### 4. Set device_id and room

Create `/boot/koe-config.env` on the SD card before shipping:

```bash
cat > /Volumes/bootfs/koe-config.env <<'EOF'
KOE_DEVICE_ID=koe-hawaii-01
KOE_ROOM=living_room
KOE_API_URL=https://koe.live
EOF
```

Repeat for each card with incrementing device IDs:
- `koe-hawaii-01` / `living_room`
- `koe-hawaii-02` / `bedroom`
- `koe-hawaii-03` / `studio`
- `koe-hawaii-04` / `stage`

### 5. Install koe-amp service (first boot)

On first boot, SSH in and run:

```bash
ssh pi@koe-amp-1.local
curl -sSL https://koe.live/setup-pi.sh | bash
sudo systemctl enable koe-hub koe-amp
sudo systemctl start koe-hub koe-amp
```

### 6. Verify

```bash
systemctl status koe-amp
journalctl -u koe-amp -f
# Expected: [koe-amp] Listening on 239.42.42.1:4242 (room=living_room)
```

---

## Pre-Ship Checklist (both options)

Run this for each of the 4 units before boxing:

- [ ] Device boots and gets IP address
- [ ] `koe-amp` service is running (green in dashboard or `systemctl status`)
- [ ] Correct `KOE_ROOM` set per unit
- [ ] Log line shows expected room name
- [ ] Power-cycle test: unplug → replug → service auto-restarts within 60 s
- [ ] SD card label written with device ID (e.g., `KOE-HI-01`)

---

## Shipping to Hawaii

### Carrier
**FedEx International Priority** — Tokyo → Honolulu  
- Transit time: 1–2 business days
- Track online: fedex.com

### Customs Declaration

| Field | Value |
|-------|-------|
| Description | Electronic Development Kit |
| Contents | Raspberry Pi 5 single-board computer with SD card |
| HS Code | 8471.50 (processing units) |
| Declared value | USD 150 per unit (×4 = USD 600 total) |
| Country of origin | UK (Raspberry Pi) |

Pack each Pi individually in anti-static bag + bubble wrap.  
Mark outer box: **"Fragile — Electronic Equipment"**.

### Insurance

Declare full replacement value ($150/unit). FedEx International Priority includes  
up to $100 coverage by default — purchase additional declared value for the difference.

### Contact at destination

濱田優貴 (ex-Mercari US CEO, Hawaii)  
Confirm delivery address before shipping.

---

## After Devices Arrive in Hawaii

The remote user just needs to:

1. Insert SD card, plug in power.
2. (balena) Device appears in dashboard automatically.
3. (manual) Connect to `koe-amp-N.local` via SSH if any tweaks needed.
4. Report back via Telegram/Slack if any unit shows errors.

You can push fixes remotely with `balena push koe-amp` (balena option)  
or `ssh + git pull + systemctl restart` (manual option) without touching the hardware.
