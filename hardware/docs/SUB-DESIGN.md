# Koe SUB — Technical Design Specification

## 1. Overview

Koe SUB is a GPS-synchronized subwoofer for the Koe Soluna Festival System. It delivers 30-80Hz sub-bass using a 15" driver and 1000W Class-D amplification, replacing L-Acoustics SB28 at 1/7 the cost.

| Parameter | Value |
|-----------|-------|
| Type | Powered subwoofer, bass reflex |
| Frequency range | 30-80Hz (-3dB) |
| Max SPL | 130dB (peak) / 127dB (continuous) |
| Amplifier | ICEpower 1000ASP, 1000W |
| Synchronization | GPS 1PPS (<30ns), WiFi control |
| Dimensions | 500 x 500 x 600mm (external) |
| Weight | ~35kg |
| BOM cost | ~$432 |

## 2. Driver Selection

### Primary: Dayton Audio RSS390HF-4

| Thiele-Small Parameter | Value |
|------------------------|-------|
| Nominal diameter | 15" (381mm) |
| Impedance | 4 ohm |
| fs (resonance) | 28Hz |
| Qts | 0.34 |
| Qes | 0.36 |
| Qms | 5.6 |
| Vas | 203L |
| Xmax | 17mm (one-way) |
| Sd (effective area) | 855 cm2 |
| Sensitivity | 97dB (1W/1m) |
| Power handling | 500W RMS / 1000W program |
| BL | 18.7 T*m |
| Mms | 145g |

### Alternative: B&C 15SW115-4

Similar T/S parameters, higher BL (21 T*m), slightly better transient response. $140 vs $120. Consider for premium version.

## 3. Enclosure Design

### 3.1 Bass Reflex Alignment

Using Thiele-Small analysis for vented alignment:

```
Given:
  fs  = 28 Hz
  Qts = 0.34
  Vas = 203 L

Target alignment: QB3 (quasi-Butterworth 3rd order)
  Optimal Vb  = Vas * 1.44 * Qts^2.87  (for QB3)
                ≈ 203 * 1.44 * 0.34^2.87
                ≈ 203 * 1.44 * 0.044
                ≈ 12.9 L  (too small for practical port)

Revised: SBB4 alignment (4th-order Super Boom Box)
  h  = 0.7 / Qts = 2.06
  Vb = Vas / (Qts^2 * h^2 * (2*pi*fs)^2 / (2*pi*fb)^2)

Practical target:
  Vb = 80L (balances extension, efficiency, and box size)
  fb = 35Hz (tuning frequency)
```

### 3.2 Port Design

```
Port type:    Circular, flared ends (reduces turbulence)
Port diameter: Dp = 100mm
Port area:     Ap = pi * (0.05)^2 = 78.5 cm2
Port velocity:  < 17 m/s at Xmax (safe limit < 25 m/s)

Port length calculation (Helmholtz resonator):
  Lp = (c^2 * Ap) / (4 * pi^2 * fb^2 * Vb) - 0.732 * Dp

  Where:
    c   = 343 m/s (speed of sound at 20C)
    Ap  = 78.5e-4 m2
    fb  = 35 Hz
    Vb  = 0.080 m3
    Dp  = 0.10 m

  Lp = (343^2 * 78.5e-4) / (4 * pi^2 * 35^2 * 0.080) - 0.732 * 0.10
     = (117649 * 0.00785) / (4 * 9.87 * 1225 * 0.080) - 0.0732
     = 923.5 / 3870.7 - 0.0732
     = 0.2386 - 0.0732
     = 0.165 m ≈ 165mm

Practical port length: 200mm (slightly over-tuned to ~33Hz for deeper extension)
```

### 3.3 Frequency Response Prediction

```
Modeled -3dB points:
  Low:  32Hz (bass reflex extension below fs)
  High: 80Hz (DSP low-pass filter)

Response shape:
  30Hz: -5dB (rolling off, 24dB/oct below fb)
  32Hz: -3dB
  35Hz: 0dB (port resonance, maximum output)
  40Hz: +1dB (slight hump typical of vented)
  50Hz: 0dB (reference)
  80Hz: -3dB (DSP LR4 low-pass begins)
  160Hz: -27dB (LR4 = 24dB/oct)
```

### 3.4 Maximum SPL Calculation

```
Sensitivity:           97 dB SPL (1W/1m)
Amplifier power:       1000W into 4 ohm
Power gain:            10 * log10(1000) = 30 dB

Continuous max SPL:    97 + 30 = 127 dB (1m, free field)
Peak SPL (+3dB crest): 130 dB

4x SUB array:
  Mutual coupling gain: 6 dB (coherent addition, half-space)
  System max SPL:       127 + 6 = 133 dB continuous
```

### 3.5 Physical Construction

```
                   500mm
         ┌─────────────────────┐
         │                     │
         │    ┌───────────┐    │
         │    │           │    │
         │    │  15" DVR  │    │  600mm (depth)
         │    │           │    │
         │    └───────────┘    │
  500mm  │                     │
         │      ○ PORT         │
         │     (100mm)         │
         │                     │
         └─────────────────────┘
              FRONT VIEW

Material:        18mm Baltic birch plywood
Internal volume: ~80L net (after driver, bracing, port displacement)
Panel dimensions:
  Front/Back:    500 x 500mm (internal: 464 x 464mm)
  Top/Bottom:    500 x 600mm (internal: 464 x 564mm)
  Sides:         500 x 600mm (internal: 464 x 564mm)

Bracing:
  - 1x horizontal shelf brace (18mm ply, 60% window) at mid-height
  - 2x vertical pillar braces connecting front to back
  - Purpose: eliminate panel resonance below 200Hz

Damping:
  - Rear panel: 2mm bitumen constrained-layer damping (CLD)
  - Side panels: 25mm polyester batting (50% fill)
  - DO NOT stuff port or front chamber

Joints:
  - Butt joints with wood glue (Titebond III) + wood screws
  - All internal seams sealed with silicone caulk
  - Gasket foam under driver mounting flange
```

## 4. Amplifier: ICEpower 1000ASP

| Parameter | Value |
|-----------|-------|
| Topology | Class-D with integrated SMPS |
| Output power | 1000W @ 4 ohm |
| THD+N | < 0.005% (1W) |
| SNR | > 113dB (A-weighted) |
| Input | Balanced XLR (differential) |
| Power supply | Universal AC 100-240V, 50/60Hz |
| Efficiency | > 90% at rated power |
| Protection | Over-temp, DC offset, short circuit, over-current |
| Standby power | < 0.5W |

### Mounting

The 1000ASP is a back-panel mount module. It replaces the traditional amplifier rack and includes:
- AC inlet (integrated in module, but we add separate IEC C14 for flexibility)
- Signal input (balanced, summed to mono internally)
- Speaker output (binding posts, wired to Speakon NL4 jacks)

## 5. DSP: miniDSP 2x4

### Signal Chain

```
XLR Input → miniDSP Input 1
                ↓
         [Input EQ]
         [Subsonic HPF: 25Hz, BW4 (24dB/oct)]
         [Parametric EQ: room correction slots x4]
         [Low-pass: 80Hz, LR4 (24dB/oct)]
         [Delay: 0-100ms (GPS-derived)]
         [Limiter: -3dBFS, 10ms attack, 200ms release]
                ↓
         miniDSP Output 1 → ICEpower 1000ASP Input
```

### DSP Configuration

| Filter | Type | Frequency | Slope | Purpose |
|--------|------|-----------|-------|---------|
| Subsonic HPF | Butterworth | 25Hz | 24dB/oct | Protect driver from infrasonic content |
| Low-pass | Linkwitz-Riley | 80Hz | 24dB/oct | Crossover to FILL speakers |
| PEQ 1 | Parametric | 45Hz | Q=2.0, -3dB | Tame vented alignment hump |
| PEQ 2 | Parametric | (reserved) | — | Room/venue correction |
| PEQ 3 | Parametric | (reserved) | — | Room/venue correction |
| PEQ 4 | Parametric | (reserved) | — | Room/venue correction |
| Limiter | Peak | -3dBFS | 10ms atk | Protect driver from over-excursion |
| Delay | Variable | 0-100ms | — | GPS-synchronized alignment |

### Alternative DSP: ADAU1701 Board

For cost-optimized production ($8 vs $25), an ADAU1701-based custom PCB can replace the miniDSP 2x4. The ADAU1701 provides:
- 2 ADC + 4 DAC (28-bit)
- 1024 instructions (sufficient for filters above)
- I2C control from ESP32
- SigmaDSP graphical programming via SigmaStudio

## 6. GPS Synchronization

### Hardware

| Component | Part | Purpose |
|-----------|------|---------|
| GNSS module | u-blox NEO-M9N | Multi-constellation, 1PPS output |
| TCXO | 26MHz 0.5ppm | Holdover clock when GPS unavailable |
| Antenna | 25x25mm active patch | Outdoor reception |

### 1PPS Timing Architecture

```
GPS Satellite
     ↓ (L1/L5 signals)
Active Antenna → NEO-M9N
                    ↓
              1PPS pulse (rising edge, <30ns jitter)
                    ↓
              ESP32-S3 GPIO interrupt
                    ↓
              Calculate sample-accurate delay offset
                    ↓
              Set miniDSP delay register via I2C/UART
                    ↓
              All SUBs play the same sample at the same time
```

### Phase Coherence

Multiple SUBs must be phase-coherent for constructive interference. At 50Hz (wavelength = 6.86m), a 1ms timing error = 6.86mm path difference = 0.18 degrees phase error. GPS 1PPS provides <30ns accuracy, which gives:
- Path error: < 0.01mm
- Phase error at 80Hz: < 0.009 degrees
- Result: **perfect coherent summation** across all SUBs

### GPS Holdover

When GPS signal is lost (indoor venues):
1. TCXO maintains timing with <0.5ppm drift
2. At 0.5ppm: 0.5us drift per second = 500us drift after 1000 seconds
3. At 80Hz: 500us = 14.4 degrees phase error after ~17 minutes
4. WiFi PTP fallback provides <1ms sync (acceptable for sub frequencies)

## 7. Control: ESP32-S3

### Functions

| Function | Interface | Details |
|----------|-----------|---------|
| GPS sync | UART to NEO-M9N | Parse NMEA, capture 1PPS interrupt |
| DSP control | I2C/UART to miniDSP | Set delay, EQ, limiter, gain |
| WiFi | Built-in 2.4GHz | Receives commands from Koe STAGE |
| LED control | GPIO to WS2812B | Status display, sync visualization |
| Temperature | ADC + NTC thermistor | Monitor amp heatsink, protect |
| Status reporting | WiFi to STAGE | Report GPS lock, temp, limiter activity |

### WiFi Protocol

ESP32 connects to Koe STAGE's WiFi network and receives OSC or MQTT commands:
- `/sub/N/delay` — set delay in samples
- `/sub/N/gain` — set gain in dB
- `/sub/N/eq/N` — set PEQ parameters
- `/sub/N/mute` — mute/unmute
- `/sub/N/led` — LED pattern + color

## 8. Protection Systems

| Protection | Sensor | Action | Recovery |
|------------|--------|--------|----------|
| Thermal (amp) | ICEpower internal | Auto power reduction at 80C, shutdown at 95C | Auto resume at 70C |
| Thermal (driver) | NTC on magnet | ESP32 reduces gain at 150C, mutes at 180C | Auto resume at 120C |
| Short circuit | ICEpower internal | Instant shutdown | Manual power cycle |
| DC offset | ICEpower internal | Relay disconnect | Auto after 3s |
| Over-excursion | DSP limiter | Peak limiter at -3dBFS | Instantaneous |
| Clip detection | ICEpower clip LED | ESP32 reads clip output, reduces gain 1dB | Auto after 2s |
| Subsonic | DSP HPF 25Hz | 24dB/oct filter prevents infrasonic | Always active |

## 9. Connector Panel (Rear)

```
┌─────────────────────────────────────┐
│                                     │
│  [IEC C14 + Switch]   [XLR In]     │
│                                     │
│  [Speakon NL4 In]  [Speakon NL4 Out]│
│                                     │
│  [GPS Antenna SMA]  [Status LED]    │
│                                     │
│  [ICEpower 1000ASP Module Panel]    │
│  (heatsink fins visible)            │
│                                     │
└─────────────────────────────────────┘
```

## 10. Mechanical

### Pole Mount

M20 threaded steel insert on top panel, centered. Accepts standard 35mm speaker pole via M20-to-35mm adapter. Allows stacking Koe FILL on top of Koe SUB.

### Handles

2x spring-loaded recessed handles on opposing sides (left/right). Positioned at center of gravity (approximately 250mm from bottom).

### Feet

4x M8 threaded rubber isolation feet, 50mm diameter. Decouples cabinet from floor to reduce structure-borne transmission. For hard coupling (cardioid arrays), replace with spikes.

### Rigging

No fly points on SUB (floor/ground stack only). For suspended applications, use a dedicated rigging frame (not included, designed separately).

## 11. Finish

- Exterior: Black Duratex textured coating (water-resistant, durable)
- Grille: Powder-coated perforated steel, acoustically transparent (>60% open area)
- Logo: Laser-engraved "Koe" on front grille frame
- LED ring: Visible through port tube opening (subtle sub-bass visualization)

## 12. Compliance Targets

| Standard | Scope |
|----------|-------|
| IEC 60065 / 62368-1 | Electrical safety |
| EN 55032 | EMC emissions |
| EN 55035 | EMC immunity |
| RoHS | Hazardous substances |
| IP20 | Indoor use (no weather rating) |

## 13. Test Plan

| Test | Method | Pass Criteria |
|------|--------|---------------|
| Frequency response | Swept sine, 1m on-axis, anechoic | 32-80Hz +/-3dB |
| Max SPL | Shaped pink noise, 1m | >= 127dB continuous |
| THD | Single tone at 50Hz, rated power | < 3% |
| GPS sync | 2x SUBs, measure phase at 50Hz | < 1 degree |
| Thermal | 2hr pink noise at 1/8 power | Amp temp < 80C |
| Drop test | 500mm onto concrete, padded corners | No structural damage |
| Port noise | Sine sweep 30-80Hz at rated power | No audible chuffing |
