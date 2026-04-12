# Koe Amp — balena.io Fleet

Zero-touch provisioning for Koe Amp devices (Raspberry Pi 5).  
Burn one SD card image, plug in power, device auto-connects and runs.

## Deploy

```bash
# 1. Log in to balenaCloud
balena login

# 2. Create the fleet (one-time)
balena fleet create koe-amp --type raspberrypi5

# 3. Push the application code
balena push koe-amp
```

## Provision SD Cards

1. Open the balena dashboard → fleet **koe-amp** → *Add device*.
2. Select **Production** image, choose your WiFi SSID/password (or leave blank for captive portal).
3. Download the `.img.zip`.
4. Burn with [balena Etcher](https://etcher.balena.io/) — select image, select SD card, Flash.
5. Insert SD card into Pi 5, apply power.
6. Device appears in the dashboard within ~90 seconds and automatically pulls the `koe-amp` container.

## Per-Device Configuration

Set room name and other variables per device after it registers:

```bash
balena env add KOE_ROOM living_room --device <uuid>
balena env add KOE_ROOM bedroom     --device <uuid>
```

Fleet-wide defaults are in `docker-compose.yml` under `environment:`.

## WiFi Captive Portal (fallback)

If the device cannot find a known network, the `wifi-connect` service broadcasts a hotspot:

- **SSID**: `Koe Setup`
- **Password**: `koedevice`

Connect from any phone/laptop, a captive portal opens automatically.  
Enter the target WiFi credentials and the device reboots onto that network.

## Useful Commands

```bash
balena devices --fleet koe-amp          # list all devices
balena logs <uuid>                      # tail logs
balena ssh <uuid>                       # open shell on device
balena env add KEY value --fleet koe-amp  # set fleet-wide var
balena push koe-amp                     # redeploy after code change
```
