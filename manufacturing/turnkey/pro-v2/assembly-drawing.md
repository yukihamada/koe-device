# Pro v2 — Assembly Drawing

## Product: Koe Pro v2 Wireless Audio Transmitter
## PCB: 45x30mm rounded rectangle, 4-layer, 1.6mm FR-4
## Enclosure: 49.4x34.4x20.7mm pill shape, 2-piece snap-fit

---

## Assembly Order

### Step 1: SMT Assembly (machine)
All components in BOM marked "SMT" placed by pick-and-place.
Use CPL.csv for placement coordinates. Note: 4-layer board.

### Step 2: Visual Inspection
- nRF5340 (U1) QFN: check all pads soldered, no bridges
- DW3000 (U2) QFN-48: check pin alignment
- USB-C (J1): no bridges on fine-pitch pins
- PCM5102A (U4) TSSOP-20: verify orientation (pin 1 dot)
- AK5720 (U3): verify orientation

### Step 3: Power Test
- Connect USB-C to J1
- nPM1300 (U6) should regulate: measure 3.3V on output
- LED D1 should flash if firmware present
- **PASS: VCC = 3.3V ±0.1V**

### Step 4: Battery Connection
```
  Battery: 802535 LiPo 3.7V 800mAh with JST-PH 2.0mm connector
  
  Simply plug JST-PH connector into BT1 socket.
  
  ┌─ BT1 (JST-PH) ─┐
  │  +          -    │  ← Verify: Red=+, Black=-
  └──────────────────┘
  
  If battery has bare wires (no JST):
  Solder red → BT1 pin 1 (+)
  Solder black → BT1 pin 2 (-)
```

### Step 5: Speaker Connection
```
  Speaker: 20mm round, 8ohm 1W
  
  Connect via SPK1 2-pin connector pad:
  - Solder 40mm 30AWG wires to PCB SPK+/SPK- pads
  - Connect to speaker terminals
  
  Speaker position in case: top cavity, facing up
```

### Step 6: UWB Antenna
- Screw UWB antenna onto J3 (SMA connector, right edge of PCB)
- Finger-tight only, do not over-torque

### Step 7: Firmware Flash
- Connect USB-C to computer
- nRF5340 uses J-Link or USB DFU (see flash-instructions.md)
- Verify: LED sequence on boot

### Step 8: Functional Test
- Run all tests per test-spec.md

### Step 9: Final Mechanical Assembly
```
  Enclosure Cross-Section (side view):
  
  ┌───────────────────────────┐  ← Top case
  │  ▓▓ Speaker ▓▓  (grille) │  ← Speaker facing up
  │  ○ LED window             │
  │                           │
  │  ═══════ PCB ════════════│  ← PCB on 4 standoffs
  │  ████ Kapton █████████████│
  │  ░░░░ Battery ░░░░░░░░░░░│  ← 802535 in bottom cavity
  └───────────────────────────┘  ← Bottom case
  
  Cutouts (side view):
  ├─ USB-C (bottom edge, center) ─┤
  ├─ 3.5mm jack (left edge) ──────┤
  ├─ Button hole (left, lower) ───┤
  ├─ SMA antenna (right edge) ────┤
```

1. Place battery in bottom case cavity (flat, wires toward connector)
2. Plug battery JST into BT1 (or route bare wires)
3. Apply Kapton tape over PCB underside
4. Set PCB on standoff posts (components UP)
5. Route speaker wires through top opening
6. Place speaker in top cavity (cone facing up toward grille)
7. Screw UWB antenna through case hole into J3
8. Press top case onto bottom until snap-fit clicks
9. Verify all ports accessible: USB-C, 3.5mm, button, antenna
