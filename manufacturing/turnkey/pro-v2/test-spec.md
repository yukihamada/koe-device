# Pro v2 — Functional Test Specification

## Test Equipment
- USB-C cable
- Multimeter
- 3.5mm audio cable + headphones
- J-Link or nRF Connect app (BLE scan)

## Tests (all must PASS)

### TEST 1: Power Supply
1. Connect USB-C
2. Measure nPM1300 output: **PASS if 3.2V - 3.4V**

### TEST 2: Battery & Charging
1. Plug battery into BT1
2. Connect USB-C (charging)
3. nPM1300 CHRG indicator active
4. Battery voltage: **PASS if 3.0V - 4.2V**

### TEST 3: BLE Radio (nRF5340)
1. Power on device
2. Scan BLE with phone (nRF Connect app)
3. Device advertises as "Koe-Pro-XXXX"
4. **PASS if device appears in BLE scan**

### TEST 4: Audio Input (3.5mm → ADC)
1. Connect audio source to J2 (3.5mm)
2. Play 1kHz test tone
3. Verify AK5720 receives signal (LED pattern changes or audio loops back)
4. **PASS if audio signal detected**

### TEST 5: Audio Output (Speaker)
1. Play audio through I2S → MAX98357A → Speaker
2. Listen for clear audio from speaker
3. **PASS if audio audible, no distortion**

### TEST 6: UWB Radio
1. Verify DW3000 initializes (LED indicates UWB ready)
2. **PASS if no error LED pattern**

### TEST 7: Button & LED
1. Press SW1
2. LED D1/D2 respond
3. **PASS if LED changes state on button press**

### TEST 8: Enclosure
1. All ports accessible (USB-C, 3.5mm, button, SMA)
2. No rattling when shaken
3. Snap-fit secure
4. **PASS if mechanical integrity OK**

## Reject Criteria
- Any test FAIL → rework or reject
- nRF5340 not responding → check crystal Y1/Y2 solder joints
- No BLE → check antenna trace and nRF5340 orientation
