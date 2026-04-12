# Koe Seed — Functional Test Specification

## Test Equipment Required
- USB-C cable
- Multimeter
- Smartphone with nRF Connect app (iOS or Android)
- Auracast broadcast source (optional, for TEST 5)
- SWD debugger with nRF Connect for Desktop (for reflash if needed)

## Tests (all must PASS)

### TEST 1: Power Supply
1. Connect USB-C cable
2. Measure voltage at U4 (AP2112K) output pad: **PASS if 3.2V - 3.4V**
3. Measure nRF5340 DECN pin (internal DCDC output): **PASS if 0.95V - 1.05V**
4. Disconnect USB-C

### TEST 2: Battery Charge
1. Connect USB-C with battery plugged into BT1
2. TP4054 CHRG pin should go LOW (charging)
3. Measure battery voltage: **PASS if 3.0V - 4.2V**

### TEST 3: BLE Scan (nRF5340 alive)
1. Power on device (press button or connect USB-C)
2. Open nRF Connect app on smartphone
3. Scan for BLE devices
4. **PASS if device appears as "Koe-Seed-XXXX"** (XXXX = last 4 hex of MAC)
5. If not found within 10 seconds: check SWD flash, Y1 crystal solder

### TEST 4: Audio Output
1. Power on device
2. Trigger built-in test tone (hold button 3 seconds, or via nRF Connect UART service)
3. Listen for audio from speaker
4. **PASS if audio is audible and clear (no distortion at moderate volume)**

### TEST 5: Auracast Receive (if broadcast source available)
1. Start an Auracast broadcast from a source device (phone, another nRF5340 DK, etc.)
2. Power on Koe Seed — it should auto-scan for Auracast broadcasts
3. Device LED turns green when synced to broadcast
4. **PASS if audio from broadcast is played through speaker**
5. If no broadcast source: mark as SKIP (not FAIL)

### TEST 6: LED + Button
1. Short-press button (SW1)
2. LED1 should light up (any color)
3. Short-press again: LED changes color or pattern
4. **PASS if LED responds to button presses**

### TEST 7: Enclosure Integrity
1. Shake device gently — no rattling
2. USB-C port accessible through case cutout
3. Button accessible through case cutout
4. LED visible through top window
5. **PASS if all access points functional and no loose parts**

### TEST 8 (Optional): Range Test with nRF21540 PA
1. Place Koe Seed in open area
2. Move BLE-connected smartphone away from device
3. Monitor RSSI in nRF Connect app
4. **PASS if BLE connection maintained at 30m+ line-of-sight**
5. Expected: ~50-80m with nRF21540 PA/LNA active
6. If range < 10m: check nRF21540 solder joints, R5/R6 antenna matching resistors

## Reject Criteria
- Any test (1-4, 6-7) FAIL -> unit is rejected
- TEST 5 SKIP is acceptable if no broadcast source available
- TEST 8 SKIP is acceptable (optional range verification)
- Solder bridges visible -> rework required
- Battery polarity reversed -> unit scrapped (do not rework)
- Cracked enclosure -> replace case only
- nRF5340 QFN-94 bridge -> reflow rework under microscope

## Label
Apply small label (if provided) with:
- Model: KOE-SEED
- Serial: SEED-NNNN (sequential)
- Date: YYYY-MM-DD
