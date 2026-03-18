# Koe Device -- Final Assembly Guide

## What You Receive

### From JLCPCB (assembled PCB)
A fully assembled PCB (30x40mm) with ALL surface-mount components soldered:
- ESP32-S3-MINI-1 (U1)
- INMP441 microphones x2 (U2, U3)
- MAX98357A amplifier (U4)
- MCP73831 charger (U5)
- AP2112K LDO (U6)
- SS14 Schottky diode (D1)
- WS2812B RGB LED (LED1)
- USB-C connector (J1)
- Tact switch (SW1)
- All resistors (R1-R6) and capacitors (C1-C8)

### Purchased Separately
- 802535 LiPo battery 800mAh (BT1)
- 1510 micro speaker 8ohm 0.5W (SPK1)
- 3D-printed case (top + bottom)

## Tools Needed

| Tool | Purpose | Notes |
|------|---------|-------|
| Soldering iron | Battery & speaker wires | Temperature-controlled, 300-350C |
| Solder wire | Connections | 0.5-0.8mm diameter, lead-free recommended |
| Flux pen | Clean solder joints | No-clean flux |
| Wire strippers | Prepare wires | For 28-30 AWG |
| Tweezers | Handling small parts | ESD-safe |
| Multimeter | Verify connections | Continuity and voltage check |
| Side cutters | Trim wire ends | Flush cut |
| Magnifier/loupe | Inspect solder joints | 5x-10x magnification |
| Hot glue gun | Secure battery and speaker | Low-temp recommended |
| Kapton tape | Insulation | Prevent shorts under battery |

## Pre-Assembly Inspection

Before soldering anything, inspect the JLCPCB board:

1. Visual check under magnification:
   - All ICs present and properly oriented
   - No solder bridges (especially on ESP32-S3 and USB-C)
   - No missing components
2. Check USB-C connector alignment -- should be flush with board edge
3. Press the tact switch (SW1) -- should click

## Assembly Steps

### Step 1: Prepare Speaker Wires

Cut two pieces of 30AWG silicone wire, ~40mm each (red and black).
Strip 2mm of insulation from each end.

```
  Speaker (bottom side)       Wire (~40mm)        PCB pads
  ┌─────────────┐                                 ┌─────┐
  │  (+) ●──────── red  ──────────────────────── ● SPK+ │
  │  (-) ●──────── black ─────────────────────── ● SPK- │
  │   1510       │                                 │     │
  └─────────────┘                                 └─────┘
```

### Step 2: Solder Speaker Wires to PCB

1. Apply a small amount of solder to the SPK+ and SPK- pads on the PCB.
2. Hold the red wire to SPK+ and reflow the solder.
3. Hold the black wire to SPK- and reflow the solder.
4. Tug gently to verify the joints are solid.
5. Do NOT attach wires to the speaker yet.

```
     PCB (top view, component side up)
  ┌──────────────────────────────────────┐
  │  [U2]              [U3]        [LED1]│
  │                                      │
  │           ┌──────────────┐           │
  │           │              │           │
  │           │    ESP32     │      [SW1]│
  │           │     (U1)     │           │
  │           │              │           │
  │           └──────────────┘           │
  │                                      │
  │  [U5][U6]  [D1]    [U4]  SPK+ SPK-  │
  │                           (o)  (o) <── solder wires here
  │  ═══════════[USB-C J1]═══════════    │
  └──────────────────────────────────────┘
```

### Step 3: Solder Battery Wires to PCB

**CRITICAL: Verify battery polarity with a multimeter before soldering.**

If the battery has a JST connector and the PCB has a matching header, simply
plug it in. Otherwise, solder directly:

1. Apply solder to the BT+ and BT- pads on the PCB.
2. Red wire from battery -> BT+ pad.
3. Black wire from battery -> BT- pad.

```
  Battery (802535)
  ┌─────────────────────┐
  │                     │
  │  3.7V  800mAh       │
  │                     │
  │  RED(+)  BLACK(-)   │
  └───●────────●────────┘
      │        │
      │        │   (wires ~30mm)
      │        │
  ────●────────●────  PCB pads: BT+  BT-
```

**WARNING:** Reversing battery polarity will destroy the MCP73831 charger IC
and possibly the ESP32. Triple-check before soldering.

### Step 4: Test Power-On (Before Final Assembly)

1. Do NOT install in the case yet.
2. Connect the battery (or plug in USB-C).
3. Expected behavior:
   - LED1 should briefly flash or stay off (depends on firmware)
   - If USB connected: MCP73831 charges the battery (STAT pin behavior)
   - ESP32 should be detectable via USB (if firmware is flashed)
4. Measure voltages with multimeter:
   - VBAT pad: 3.7-4.2V (battery voltage)
   - VCC test point: 3.3V (+/- 0.1V)
   - If VCC is 0V, check LDO (U6) and input voltage
5. If everything checks out, proceed to final assembly.

### Step 5: Attach Speaker Wires to Speaker

1. Solder the free ends of the speaker wires to the speaker terminals.
2. Red wire to speaker (+), black wire to speaker (-).
3. Polarity is not critical for audio quality, but keep it consistent.

```
  Completed speaker wiring:

      PCB                    Speaker
  ┌─────────┐            ┌──────────┐
  │ SPK+ (o)├── red  ────┤(+)       │
  │ SPK- (o)├── black ───┤(-)       │
  └─────────┘            └──────────┘
```

### Step 6: Insulate and Position Battery

1. Place a strip of Kapton tape over the back of the PCB where the battery
   will sit. This prevents the battery from shorting against solder joints.

```
  Side view of assembly:

          Battery
  ┌─────────────────────┐
  │  802535  800mAh      │  8mm thick
  └─────────────────────┘
  ========================  Kapton tape
  ┌─────────────────────┐
  │  PCB (component side │  1mm thick
  │  faces DOWN in case) │
  └─────────────────────┘
```

2. Position the battery on the back of the PCB (opposite side from components).
3. Secure with a small dab of hot glue at each end.
4. Route battery wires so they do not cross over the USB-C port.

### Step 7: Install in Case

```
  Case cross-section:

  ┌─────────────── Top Shell ────────────────┐
  │  ┌─speaker cavity──┐                     │
  │  │  [speaker]       │   ← speaker faces up
  │  └─────────────────┘                     │
  │                                           │
  │  ┌───────battery────────────────────┐     │
  │  │  [802535 LiPo]                   │     │
  │  └──────────────────────────────────┘     │
  │  ┌───────PCB────────────────────────┐     │
  │  │  components face down            │     │
  │  └──────────────────────────────────┘     │
  │    ↕ button post    ↕ LED light pipe      │
  └───────────── Bottom Shell ───────────────┘
                    ↕ USB-C opening
```

1. Place the speaker into the speaker cavity in the top shell.
   Apply a thin bead of hot glue around the speaker edge to seal it
   acoustically and hold it in place.
2. Fold the battery over the back of the PCB (Kapton tape between them).
3. Slide the PCB+battery assembly into the bottom shell:
   - USB-C port aligns with the slot in the case wall
   - Button (SW1) aligns with the button post on the bottom shell
   - LED (LED1) aligns with the light pipe / translucent window
4. Connect the speaker wires (already soldered in Step 5).
5. Tuck all wires neatly so they do not pinch when closing.
6. Snap the top and bottom shells together.

### Step 8: Final Test

1. Press and hold the button for 3 seconds -- device should power on.
2. Connect USB-C cable:
   - Charging LED behavior should be visible
   - Device should appear as USB serial port on computer
3. Flash firmware via USB (see firmware documentation).
4. Test audio:
   - Speak near the microphones -- recording should work
   - Play audio through the speaker -- amplifier should output sound
5. Test WiFi connectivity.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| No power at all | Battery disconnected or reversed | Check battery wiring polarity |
| 3.3V rail is 0V | LDO (U6) dead or no input | Check VBUS/VBAT reaching U6 input |
| USB not detected | Solder bridge on USB-C | Inspect J1 under magnification |
| No audio recording | INMP441 orientation wrong | Check pin 1 alignment on U2/U3 |
| No speaker output | Speaker wires disconnected | Check SPK+/SPK- continuity |
| LED not lighting | WS2812B orientation | Check data pin direction (DIN not DOUT) |
| Battery not charging | MCP73831 PROG resistor | Check R6 (2K) is present |
| Overheating | Short circuit | Disconnect battery immediately, inspect board |

## Safety Notes

- LiPo batteries are flammable. Do not puncture, crush, or short-circuit.
- Always disconnect the battery before soldering or reworking the PCB.
- If a LiPo battery puffs (swells), stop using it immediately and dispose
  of it safely at a battery recycling center.
- Do not leave charging unattended for the first few charge cycles.
- The MCP73831 has thermal regulation, but ensure adequate ventilation
  during charging.
