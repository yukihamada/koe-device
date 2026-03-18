# Koe Device -- PCB Fabrication Specifications

## Board Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| **Layers** | 2 | Top copper + Bottom copper |
| **Board Size** | 30 x 40 mm | Pick model form factor |
| **Board Thickness** | 1.0 mm | Thin profile for wearable enclosure |
| **Material** | FR-4 TG155 | Higher Tg for lead-free reflow |
| **Surface Finish** | ENIG | Gold pads, required for fine-pitch ESP32-S3 module |
| **Copper Weight** | 1 oz (35um) outer | Standard |
| **Solder Mask Color** | Green | Default, lowest cost |
| **Silkscreen Color** | White | Default |
| **Min Track Width** | 0.15 mm | 6 mil |
| **Min Track Spacing** | 0.15 mm | 6 mil |
| **Min Via Drill** | 0.3 mm | |
| **Min Via Pad** | 0.6 mm | |
| **Castellated Holes** | No | |
| **Impedance Control** | Yes | USB differential pair |

## Impedance Requirements

| Signal | Type | Target | Stackup |
|--------|------|--------|---------|
| USB D+/D- | Differential pair | 90 ohm | JLC04161H-7628 |

When ordering on JLCPCB:
1. Select "Impedance Control: Yes"
2. Choose stackup: **JLC04161H-7628** (standard 2-layer 1.0mm impedance-controlled)
3. The trace width/spacing for 90 ohm differential on this stackup is approximately:
   - Trace width: 0.16 mm
   - Trace spacing: 0.18 mm
   - Reference: JLCPCB impedance calculator

## Layer Stackup (JLC04161H-7628)

```
  F.Cu      (signal + power)     35um copper
  Prepreg   7628                 ~0.9mm
  B.Cu      (GND plane + signal) 35um copper
```

## Design Rules Summary

| Rule | Value |
|------|-------|
| Min annular ring | 0.13 mm |
| Min hole size | 0.3 mm |
| Board edge to copper | 0.3 mm |
| Board edge to via | 0.3 mm |
| Pad to pad clearance | 0.15 mm |
| Solder mask expansion | 0.05 mm |
| Via tenting | Both sides (default) |

## Ground Planes

- Bottom layer: continuous ground pour covering entire board
- Top layer: ground pour fill in unused areas
- Multiple vias (0.3mm) stitching top and bottom ground planes
- Thermal relief on ground connections for hand-soldering pads (battery, speaker)

## Special Considerations

### USB-C Connector (J1)
- Located at board edge with pads extending to edge
- Requires accurate pad alignment for 16-pin SMD connector
- Shield tabs connected to GND

### ESP32-S3-MINI-1 (U1)
- Large ground pad under module requires adequate thermal relief vias
- Place 6-9 vias under the ground pad (0.3mm drill)
- Module is the tallest component at 2.4mm -- no components on bottom side
  directly underneath

### INMP441 Microphones (U2, U3)
- Acoustic port hole required in PCB (typically 0.5-1.0mm drill)
- Position at board edges for best audio pickup
- Keep analog traces short and away from switching power/digital signals

### Panelization
- JLCPCB can panelize if ordering larger quantities
- For 5-unit orders, individual boards are fine
- Add fiducial marks for automated assembly alignment

## JLCPCB Order Settings Quick Reference

```
Base Material:        FR-4
Layers:               2
Dimensions:           30 x 40 mm
PCB Qty:              5
Product Type:         Industrial/Consumer
PCB Thickness:        1.0
PCB Color:            Green
Silkscreen:           White
Surface Finish:       ENIG
Outer Copper Weight:  1 oz
Via Covering:         Tented
Board Outline Tolerance: +/- 0.2mm
Confirm Production File: Yes
Remove Order Number:  Specify a location (or Yes for extra cost)
Flying Probe Test:    Fully Test
Castellated Holes:    No
Impedance Control:    Yes (JLC04161H-7628)
```
