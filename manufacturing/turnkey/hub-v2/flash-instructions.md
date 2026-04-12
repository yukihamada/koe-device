# Hub v2 — Firmware & OS Flash Instructions

## Two components need firmware:
1. **nRF5340** (BLE/UWB MCU on main PCB)
2. **Raspberry Pi CM5** (Linux OS on microSD)

---

## 1. nRF5340 Firmware

### Option A: SWD via J-Link
```bash
nrfjprog --program firmware.hex --chiperase --verify
nrfjprog --reset
```

### Option B: USB DFU
```bash
nrfutil dfu usb-serial -pkg firmware.zip -p /dev/ttyACM0
```

### Verification
- LED1-LED6 show rainbow sequence on boot
- BLE advertises "Koe-Hub-XXXX"

---

## 2. Raspberry Pi CM5 OS

### Flash microSD
```bash
# Download Hub OS image (provided separately)
# Flash to 32GB microSD:
sudo dd if=koe-hub-os.img of=/dev/sdX bs=4M status=progress
sync
```

### Or use Raspberry Pi Imager
1. Select "Use custom" → koe-hub-os.img
2. Select 32GB microSD
3. Write

### Insert microSD into J19 slot on PCB

### Verification
- CM5 green LED blinks during boot
- Ethernet link LED lights up
- SSH accessible at koe-hub.local (if on same network)

---

## Firmware Files
- `firmware.hex` — nRF5340 hex file
- `firmware.zip` — DFU package
- `koe-hub-os.img` — Pi CM5 OS image (provided separately, ~2GB)

## If files not present, build from source:
```bash
# nRF5340
cd koe-device/firmware/pro-v2
west build -b koe_hub_v2
# Output: build/zephyr/zephyr.hex

# Pi CM5 OS
cd koe-device/hub
./build-image.sh
# Output: koe-hub-os.img
```
