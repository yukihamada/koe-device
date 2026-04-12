# Koe Seed — Assembly Drawing

## Product: Koe Seed Wireless Auracast Audio Receiver
## SoC: nRF5340 + nRF21540 (BLE 5.3 Auracast)
## PCB: Circular 28mm, 2-layer, 1.0mm FR-4
## Enclosure: Cylindrical 32mm x 18.5mm, 2-piece snap-fit

---

## Assembly Order

### Step 1: SMT Assembly (machine)
All components in BOM marked "SMT" are placed by pick-and-place machine.
Use CPL.csv for placement coordinates.

**Critical components requiring careful inspection:**
- **U1 (nRF5340-QKAA-R7)**: QFN-94 7x7mm, 0.4mm pitch. GND pad underneath MUST have adequate solder paste. Check all 94 pads for bridging.
- **U2 (nRF21540-QFAA-R)**: QFN-16 3x3mm. Antenna TX/RX pins must not be bridged.
- **Y1 (32MHz crystal)**: Orientation-sensitive. Match pad 1 marking to PCB.
- **Y2 (32.768kHz crystal)**: Small 1610 package. Verify placement accuracy.

### Step 2: Visual Inspection
- Check all solder joints under 10x magnification
- **U1 (nRF5340)**: Inspect all 4 sides of QFN-94 for solder bridges. Use magnification or X-ray if available. This is the highest-risk component.
- **U2 (nRF21540)**: Check QFN-16 pads, especially antenna path pins (ANT, VDD_PA)
- Verify no solder bridges on USB-C (J1)
- Confirm LED1 (WS2812B) orientation: corner notch = pin 1
- Verify Y1 and Y2 crystal orientation markings

### Step 3: Antenna Matching Network Check
```
  nRF21540 ANT_OUT → L1 (3.9nH) + C16 (1.5pF) → ANT1 (chip antenna)

  CRITICAL: L1 and C16 must be placed correctly.
  ANT1 (Johanson 2450AT18B100) must be at board edge.
  Missing or misaligned → no RF performance.
```

### Step 4: Power Test (before manual assembly)
- Connect USB-C cable to J1
- Measure VCC on U4 (AP2112K) output: must read 3.3V +/- 0.1V
- If LED1 flashes, nRF5340 app core is alive (good)
- If no voltage: check U4, U5 solder joints
- Check nRF5340 DECN pins have proper voltage (1.0V internal DCDC)

### Step 5: Battery Wiring
```
  Battery (BT1): 301020 LiPo 3.7V 300mAh with JST-PH 2.0mm connector
  
  ┌──────────────┐
  │  BT1 header  │  ← JST-PH 2P on PCB
  │  [+]    [-]  │
  └──────────────┘
  
  Plug in battery JST connector. NO soldering required.
  CRITICAL: Verify polarity matches before plugging in!
  Wrong polarity = dead unit (TP4054/AP2112K damaged)
```

### Step 6: Speaker Wiring
```
  Speaker (SPK1): 15x10mm 8ohm 0.5W with JST-PH 2.0mm connector
  
  ┌──────────────┐
  │ SPK1 header  │  ← JST-PH 2P on PCB
  │  [+]    [-]  │
  └──────────────┘
  
  Plug in speaker JST connector. NO soldering required.
```

### Step 7: Firmware Flash
- Connect SWD debugger (J-Link or nRF DK) to SWD pads on PCB
- Flash firmware binary (see flash-instructions.md)
- Alternative: Use USB DFU if bootloader is pre-flashed
- Verify: LED should show brief color sequence, then breathe blue

### Step 8: Functional Test
- Run tests per test-spec.md
- All 7 tests must PASS

### Step 9: Final Mechanical Assembly
```
  Enclosure Cross-Section (32mm diameter):
  
  ┌─────────────────┐  ← Top case (snap-fit)
  │  ▓▓▓ Speaker ▓▓▓│  ← Speaker facing up (sound holes)
  │                  │
  │  ═══ PCB ═══════│  ← PCB on standoffs (components face UP)
  │  ████ Kapton ███│  ← Kapton tape insulation
  │  ░░░ Battery ░░░│  ← Battery in bottom cavity
  └─────────────────┘  ← Bottom case
  
  USB-C port aligns with bottom case cutout (Y=0 side)
  Button aligns with right side cutout
```

1. Place battery in bottom case (flat, connector wire routed to side)
2. Apply Kapton tape over PCB bottom (covers battery contact area)
3. Set PCB on standoff posts (4 posts, components facing UP)
4. Route speaker wire through to top compartment
5. Plug speaker JST connector into SPK1 header
6. Place speaker in top case cavity (face up toward grille holes)
7. Press top case onto bottom case until snap-fit clicks

### Step 10: Final Verification
- Press button: device powers on, LED lights up
- Press button again: device powers off
- Connect USB-C: charging LED behavior visible
- Shake test: no rattling (battery and speaker secure)

---

## Pin Assignment Reference (nRF5340)

| Function | nRF5340 Pin | Notes |
|----------|-------------|-------|
| I2S BCLK (to MAX98357) | P0.26 | Audio bit clock |
| I2S LRCK (to MAX98357) | P0.27 | Word select |
| I2S DOUT (to MAX98357) | P0.06 | Audio data out |
| MAX98357 SD_MODE | P0.25 | HIGH=enable, LOW=shutdown |
| WS2812B DIN | P0.13 | LED data (via 330R R3) |
| Button (SW1) | P0.08 | Active LOW, 10k pull-up R6 |
| nRF21540 TXEN | P0.19 | PA transmit enable |
| nRF21540 RXEN | P0.20 | LNA receive enable |
| nRF21540 MODE / ANT_SEL | P0.21 | Mode / antenna select |
| Battery voltage (ADC) | P0.04 | AIN2, voltage divider |
| NFC1 (GPIO) | P0.02 | Repurposed as GPIO (AIN0) |
| USB D+ | — | Built-in USB on nRF5340 |
| USB D- | — | Built-in USB on nRF5340 |
| 32MHz XTAL | XC1/XC2 | Y1 (required for RF) |
| 32.768kHz XTAL | P0.00/P0.01 | Y2 (RTC, low-power timing) |
| SWD IO | P0.18 | Debug/flash pad (TP1) |
| SWD CLK | SWDCLK | Debug/flash pad |
