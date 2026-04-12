# Koe Seed — Firmware Flash Instructions

## Chip: nRF5340-QKAA-R7 (dual-core: App + Net)
## Interface: SWD (primary) or USB DFU (if bootloader pre-flashed)

## Option A: Using nrfjprog + J-Link (recommended for manufacturing)

### Setup (once)
1. Install nRF Command Line Tools: https://www.nordicsemi.com/Products/Development-tools/nRF-Command-Line-Tools
2. Connect J-Link debugger (or nRF5340 DK used as debugger)

### SWD Pad Location on PCB
```
  PCB bottom side (near edge):

  ┌───────────┐
  │ SWDIO  ○  │  ← Pad with label
  │ SWDCLK ○  │
  │ GND    ○  │
  │ VCC    ○  │  ← 3.3V (optional, for powering via debugger)
  └───────────┘

  Connect pogo-pin jig or solder temporary wires.
```

### Flash each unit (both cores)

The nRF5340 has two cores. Flash the **network core** first, then the **application core**.

```bash
# 1. Erase chip
nrfjprog --eraseall --coprocessor CP_NETWORK
nrfjprog --eraseall --coprocessor CP_APPLICATION

# 2. Flash network core (BLE controller / Auracast stack)
nrfjprog --program net_core_firmware.hex --coprocessor CP_NETWORK --verify

# 3. Flash application core (main application)
nrfjprog --program app_core_firmware.hex --coprocessor CP_APPLICATION --verify

# 4. Reset to start
nrfjprog --reset
```

### Verify
```bash
nrfjprog --readcode --coprocessor CP_APPLICATION --codefile readback_app.hex
nrfjprog --readcode --coprocessor CP_NETWORK --codefile readback_net.hex
# Compare readback against originals
```

## Option B: Using USB DFU (if MCUboot bootloader is pre-flashed)

### Prerequisites
- MCUboot bootloader already flashed via SWD (Option A, first unit or pre-programmed)
- nRF Connect for Desktop with Programmer app, or `nrfutil`

### DFU steps
```bash
# 1. Put device in DFU mode:
#    Hold button while connecting USB-C (device enumerates as USB DFU)

# 2. Flash via nrfutil
nrfutil device program --firmware dfu_package.zip --traits nordicDfu

# 3. Device reboots automatically after flash
```

### Creating DFU package (build step)
```bash
nrfutil pkg generate --application app_core_firmware.hex \
  --application-version 1 --hw-version 52 \
  --sd-req 0x00 --key-file private.pem \
  dfu_package.zip
```

## Option C: Using west + nRF Connect SDK (developer workflow)
```bash
cd koe-device/firmware/coin-lite-v2
west build -b koe_coin_lite_v2
west flash --recover
```

## Post-Flash Verification
1. Disconnect debugger / USB
2. Power on device (button press or USB-C)
3. Device should boot: LED flashes briefly then breathes blue
4. Device appears as BLE peripheral named "Koe-Seed-XXXX"
5. In nRF Connect app: device should be scannable and show Auracast sink capability

## Batch Flashing (manufacturing)
For multiple units, use a pogo-pin SWD jig:
```bash
#!/bin/bash
# batch_flash.sh — flash one unit, wait for operator to swap
while true; do
  echo "Place unit on jig and press Enter..."
  read
  
  echo "Erasing..."
  nrfjprog --eraseall --coprocessor CP_NETWORK
  nrfjprog --eraseall --coprocessor CP_APPLICATION
  
  echo "Flashing network core..."
  nrfjprog --program net_core_firmware.hex --coprocessor CP_NETWORK --verify
  
  echo "Flashing app core..."
  nrfjprog --program app_core_firmware.hex --coprocessor CP_APPLICATION --verify
  
  echo "Resetting..."
  nrfjprog --reset
  
  echo "=== DONE — verify LED breathes blue, then remove unit ==="
  echo ""
done
```

## Firmware Binaries
- `app_core_firmware.hex` — nRF5340 application core (main logic, audio, LED, button)
- `net_core_firmware.hex` — nRF5340 network core (BLE 5.3, Auracast BAP sink, nRF21540 control)
- `dfu_package.zip` — (optional) signed DFU package for USB update

If not present, build from source:
```bash
cd koe-device/firmware/coin-lite-v2
west build -b koe_coin_lite_v2
# Outputs in build/zephyr/zephyr.hex (app core)
# and build/hci_ipc/zephyr/zephyr.hex (net core)
```

## Important Notes
- **Do NOT use esptool** — this is NOT an ESP32 device
- nRF5340 requires SWD (Serial Wire Debug), not UART boot mode
- The network core MUST be flashed for BLE/Auracast to work
- If device does not appear in BLE scan after flash: check Y1 (32MHz crystal) solder joints
