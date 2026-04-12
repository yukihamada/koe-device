# Pro v2 — Firmware Flash Instructions

## Chip: nRF5340-QKAA-R7 (Nordic Semiconductor)
## Interface: USB-C (USB DFU) or SWD (J-Link)

## Option A: USB DFU (no special hardware needed)

### Setup
```bash
pip install nrfutil
# Or download nRF Connect for Desktop
```

### Flash
1. Connect USB-C
2. Enter DFU mode: hold button while connecting USB, or double-tap reset
3. Flash:
```bash
nrfutil dfu usb-serial -pkg firmware.zip -p /dev/ttyACM0
```

## Option B: SWD via J-Link (faster, more reliable)

### Setup
- J-Link programmer (any model)
- Connect SWD pins: SWDIO, SWDCLK, GND, VCC (test pads on PCB)

### Flash
```bash
nrfjprog --program firmware.hex --chiperase --verify
nrfjprog --reset
```

## Option C: Pre-built binary with nRF Connect
1. Open nRF Connect for Desktop → Programmer
2. Select J-Link device
3. Load firmware.hex
4. Click "Write"

## Post-Flash Verification
1. Device boots: LED D1 flashes green 3x then breathes blue
2. BLE advertises as "Koe-Pro-XXXX"
3. Audio loopback test passes

## Firmware Files
- `firmware.hex` — nRF5340 application core hex (in this directory)
- `firmware.zip` — DFU package for USB update
- If not present, build from source:
  ```bash
  cd koe-device/firmware/pro-v2
  west build -b koe_pro_v2
  # Output: build/zephyr/zephyr.hex
  ```
