# Hub v2 — Assembly Drawing

## Product: Koe Hub v2 Professional Audio Mixer
## PCB: 140x120mm, 2-layer, 1.6mm FR-4
## Enclosure: 147x127x29mm box + screw-down lid, MJF Nylon

---

## Assembly Order

### Step 1: SMT Assembly (machine)
All "SMT" BOM items placed by pick-and-place per CPL.csv.

### Step 2: Through-Hole Soldering (manual)
Hand-solder these connectors to the PCB:
- **J14, J15**: Neutrik NCJ6FA-V XLR/TRS Combo (2 units)
  - Insert from top side, solder pins on bottom
- **J16, J17**: Neutrik NL4MP Speakon (2 units)
  - Insert from top side, solder pins on bottom

### Step 3: Visual Inspection
- nRF5340 (U2) QFN pads
- ES9038Q2M (U4) fine-pitch
- TPA3116D2 (U8) thermal pad
- All through-hole joints (XLR, Speakon)
- LM2596S (U9) TO-263 thermal

### Step 4: Power Test
- Connect 12V via USB-C PD adapter to J3
- Measure: 5.0V at U9 output, 3.3V at U10 output
- LEDs should show power-on sequence
- **PASS: 5.0V ±0.2V and 3.3V ±0.1V**

### Step 5: Raspberry Pi CM5 Installation
```
  CM5 Module → press onto J1+J2 (DF40 100-pin connectors)
  
  ┌─────────────────────────────┐
  │         PCB (top view)       │
  │                              │
  │  [J1]════[CM5]════[J2]      │  ← Press-fit, no soldering
  │                              │
  └─────────────────────────────┘
  
  Align CM5 carefully with both connectors.
  Press firmly until fully seated (click).
  Do NOT force at an angle.
```

### Step 6: microSD Card
- Flash Hub OS image onto 32GB microSD
- Insert into J19 (Micro-SD slot)

### Step 7: Firmware Flash
- nRF5340 firmware via SWD or USB DFU (see flash-instructions.md)
- Pi CM5 boots from microSD (no flash needed)

### Step 8: Functional Test
- Run all tests per test-spec.md

### Step 9: Final Mechanical Assembly
```
  Enclosure (exploded view):
  
  ┌─── Lid (M4 screws x4) ───────────────────┐
  │  [ventilation slots]                       │
  └────────────────────────────────────────────┘
                    ↓ screws
  ┌────────────────────────────────────────────┐
  │  Front: [HP][TRS][TRS][TRS][TRS][XLR][XLR]│
  │                                            │
  │         ═══════ PCB ═══════════            │
  │         [CM5 module on top]                │
  │                                            │
  │  Rear: [SPK][SPK][TOSLINK][BNC][HDMI][USB] │
  │  Right: [SMA antenna]                      │
  └────────────────────────────────────────────┘
  │  [rubber feet x4]                          │
  └────────────────────────────────────────────┘
```

1. Place PCB in case body on M4 standoffs
2. Screw PCB down with M4x8mm screws (4 corners)
3. Verify all connectors align with case cutouts
4. Screw UWB antenna onto J20 SMA through case hole
5. Place lid on top, align with screw holes
6. Screw lid down with M4 screws (4 corners)
7. Apply 4x rubber feet to bottom corners
8. Attach USB-C PD power supply (ships with unit)
