# Koe FILL — Technical Design Specification

## 1. Overview

Koe FILL is a bi-amplified, GPS-synchronized 2-way fill speaker for the Koe Soluna Festival System. It handles 65Hz-20kHz using an 8" woofer and 1" compression driver on a constant-directivity horn. The onboard Raspberry Pi 5 with WiFi 7 also serves as a wireless access point for up to 500 Koe CROWD devices.

| Parameter | Value |
|-----------|-------|
| Type | Powered 2-way, bi-amplified, sealed enclosure |
| Frequency range | 65Hz-20kHz (-3dB) |
| Max SPL | 118dB (peak) / 112dB (continuous) |
| Amplifier | ICEpower 125ASX2, 125W x 2ch |
| DAC | ES9038Q2M, -120dB SNR |
| DSP | Raspberry Pi 5 (FIR crossover, EQ, limiter) |
| Synchronization | GPS 1PPS + PTP master clock |
| WiFi | WiFi 7 (Intel BE200), AP mode for 500+ CROWD |
| Cellular | Quectel EC25-J 4G LTE (backup) |
| Dimensions | 280 x 280 x 400mm (external) |
| Weight | ~12kg |
| BOM cost | ~$497 |

## 2. Driver Selection

### 2.1 Woofer: SB Acoustics SB20FRPC30-8

| Thiele-Small Parameter | Value |
|------------------------|-------|
| Nominal diameter | 8" (200mm) |
| Cone material | Paper cone, rubber surround |
| Impedance | 8 ohm |
| fs (resonance) | 42Hz |
| Qts | 0.38 |
| Qes | 0.42 |
| Qms | 5.2 |
| Vas | 17L |
| Xmax | 6mm (one-way, linear) |
| Sd (effective area) | 220 cm2 |
| Sensitivity | 91dB (1W/1m) |
| Power handling | 80W RMS / 150W program |
| BL | 8.4 T*m |
| Mms | 18g |

### Alternative: Peerless 830860

Similar specifications, slightly higher Qts (0.42), paper cone. $30. Good budget alternative.

### 2.2 HF Driver: Celestion CDX1-1730

| Parameter | Value |
|-----------|-------|
| Exit diameter | 1" (25.4mm) |
| Diaphragm | Polyimide |
| Impedance | 8 ohm |
| Sensitivity | 109dB (1W/1m) |
| Frequency range | 1.5kHz-20kHz |
| Power handling | 30W RMS |
| Weight | 0.9kg |

### 2.3 Horn: 90x50 Constant Directivity

| Parameter | Value |
|-----------|-------|
| Horizontal coverage | 90 degrees (-6dB) |
| Vertical coverage | 50 degrees (-6dB) |
| Throat diameter | 1" (25.4mm) |
| Material | ABS injection molded (or 3D printed for prototype) |
| Depth | ~120mm |

The CD horn provides uniform coverage across the listening area. Unlike simple conical horns, the coverage angle remains constant across frequency, which is critical for consistent SPL distribution in festival environments.

## 3. Enclosure Design

### 3.1 Sealed Alignment

```
Given:
  fs  = 42 Hz
  Qts = 0.38
  Vas = 17 L

Sealed box (airtight, no port):
  Target Qtc = 0.707 (Butterworth, maximally flat)

  Qtc = Qts * sqrt(Vas/Vb + 1)
  0.707 = 0.38 * sqrt(17/Vb + 1)
  1.861 = sqrt(17/Vb + 1)
  3.463 = 17/Vb + 1
  Vb = 17 / 2.463
  Vb = 6.9L

  With Qtc = 0.707 and Vb = 6.9L:
    fc = fs * sqrt(Vas/Vb + 1) = 42 * 1.861 = 78Hz

Practical design:
  Vb = 15L (larger box for lower fc and gentler rolloff)

  Actual Qtc = 0.38 * sqrt(17/15 + 1) = 0.38 * 1.461 = 0.555
  Actual fc  = 42 * sqrt(17/15 + 1) = 42 * 1.461 = 61.4Hz

  With Qtc = 0.555 (underdamped side):
    Response is slightly underdamped — smooth rolloff
    -3dB point ≈ 65Hz
    -6dB point ≈ 52Hz
    12dB/oct rolloff below fc

Why sealed (not ported):
  - Phase accuracy: sealed has 12dB/oct rolloff (2nd order) vs 24dB/oct (4th order)
  - Group delay: < 10ms at 65Hz (ported would be 15-20ms)
  - Time alignment: critical for FIR crossover coherence
  - Transient response: superior for music playback
  - SUBs handle everything below 80Hz anyway
```

### 3.2 Frequency Response Prediction

```
Woofer in 15L sealed:
  65Hz:   -3dB
  80Hz:    0dB (reference, crossover region)
  100Hz:  +0.5dB
  200Hz:   0dB
  500Hz:   0dB
  1kHz:   -1dB (natural rolloff beginning)
  1.8kHz: -6dB (crossover point, DSP takes over)

HF driver on CD horn:
  1.8kHz: -6dB (crossover point, DSP brings up)
  2kHz:    0dB
  5kHz:    0dB
  10kHz:  -1dB
  16kHz:  -3dB
  20kHz:  -6dB

Combined system with FIR crossover:
  65Hz-20kHz: +/- 3dB (before room EQ)
  65Hz-16kHz: +/- 1.5dB (with system EQ applied)
```

### 3.3 Maximum SPL Calculation

```
Woofer:
  Sensitivity:        91 dB SPL (1W/1m)
  Amplifier power:    125W into 8 ohm
  Power gain:         10 * log10(125) = 21 dB
  Continuous max:     91 + 21 = 112 dB (1m)
  Peak (+6dB crest):  118 dB

HF Driver:
  Sensitivity:        109 dB SPL (1W/1m)
  Amplifier power:    125W (but limited to 30W by driver)
  Usable power gain:  10 * log10(30) = 14.8 dB
  Continuous max:     109 + 14.8 = 123.8 dB
  (HF is padded down -12dB in DSP to match woofer level)

System:
  Woofer-limited:     112 dB continuous / 118 dB peak
  8x FILL array:      112 + 9 = 121 dB continuous (coherent, half-space)
```

### 3.4 Physical Construction

```
         280mm
    ┌──────────────┐
    │  ┌────────┐  │
    │  │ 8" WFR │  │
    │  └────────┘  │
    │              │ 280mm
    │  ┌──┐        │
    │  │CD│ horn   │
    │  └──┘        │
    └──────────────┘
       FRONT VIEW

         280mm
    ┌──────────────┐
    │  Woofer      │
    │  chamber     │
    │  (sealed)    │
    │══════════════│ ← internal shelf brace
    │  Electronics │ 400mm (depth)
    │  Pi5 + DAC   │
    │  ICEpower    │
    │  GPS + 4G    │
    └──────────────┘
       SIDE SECTION

Material:        15mm Baltic birch plywood
Internal volume: ~15L net (woofer chamber only)
Panel dimensions:
  Front/Back:    280 x 280mm (internal: 250 x 250mm)
  Top/Bottom:    280 x 400mm (internal: 250 x 370mm)
  Sides:         280 x 400mm (internal: 250 x 370mm)

Internal layout:
  Upper 60%:  Woofer chamber (sealed, damped)
  Lower 40%:  Electronics chamber (ventilated via rear mesh)
  Divider:    15mm plywood shelf, sealed with gasket

Bracing:
  - 1x shelf brace (doubles as electronics/acoustic chamber divider)
  - 2x corner blocks in woofer chamber
  - Front baffle: 22mm (15mm + 7mm reinforcement ring around woofer cutout)

Damping (woofer chamber only):
  - Rear panel: 2mm bitumen CLD
  - Side panels: 15mm polyester batting
  - 30% fill by volume
```

## 4. Crossover: FIR DSP

### 4.1 Why FIR (not IIR)

| Property | IIR | FIR |
|----------|-----|-----|
| Phase | Non-linear (frequency-dependent delay) | **Linear phase** (constant group delay) |
| Latency | Low (~1ms) | Higher (~15ms for 512 taps) |
| Driver alignment | Requires physical offset or all-pass | **Perfect time alignment** |
| Transient response | Pre-ringing: none, post-ringing: yes | Pre-ringing: symmetric, post-ringing: symmetric |
| CPU load | Low | Moderate (Pi 5 handles easily) |

For a festival PA system, **linear phase** is essential. It ensures that the woofer and compression driver sum perfectly at the crossover point with zero phase shift, creating a seamless transition. The 15ms latency is imperceptible and compensated by GPS sync.

### 4.2 Crossover Design

```
Crossover frequency: 1.8kHz
Filter type:         FIR linear phase
Tap count:           512 taps (at 48kHz = 10.67ms latency)
Window:              Kaiser (beta=8)

Woofer channel:
  FIR low-pass:  1.8kHz, -60dB stopband rejection
  Slope:         ~48dB/oct equivalent (brick-wall FIR)
  Baffle step:   +3dB shelf at 500Hz (compensated in FIR)

HF channel:
  FIR high-pass: 1.8kHz, -60dB stopband rejection
  Slope:         ~48dB/oct equivalent
  Level pad:     -12dB (match sensitivity to woofer)
  HF shelf:      +2dB above 10kHz (air loss compensation)
```

### 4.3 System EQ

| Band | Type | Frequency | Gain | Q | Purpose |
|------|------|-----------|------|---|---------|
| 1 | High-pass | 55Hz | — | — | Subsonic protection (BW2) |
| 2 | PEQ | 120Hz | -2dB | 1.5 | Reduce upper bass bloom |
| 3 | PEQ | 500Hz | +1.5dB | 0.8 | Baffle step compensation |
| 4 | PEQ | 2kHz | -1dB | 2.0 | Smooth crossover region |
| 5 | PEQ | 8kHz | +1dB | 1.0 | Presence lift |
| 6 | Shelf | 12kHz | +2dB | — | Air/sparkle |
| 7 | Low-pass | 20kHz | — | — | Anti-alias (BW2) |

### 4.4 FIR Phase Correction

In addition to crossover filtering, the FIR engine applies phase correction measured from each driver's impulse response:

1. Measure woofer impulse response (at 1m, on-axis)
2. Measure HF driver impulse response (same position)
3. Calculate minimum-phase inverse for each driver
4. Convolve with crossover FIR to create final filter set
5. Store as coefficient file on Pi 5 SD card

This corrects for driver-specific phase anomalies and ensures flat phase through the crossover region.

## 5. Amplifier: ICEpower 125ASX2

| Parameter | Value |
|-----------|-------|
| Topology | Class-D with integrated SMPS |
| Channels | 2 (bi-amp: ch1=woofer, ch2=HF) |
| Output power | 125W + 125W @ 8 ohm |
| THD+N | < 0.003% (1W) |
| SNR | > 117dB (A-weighted) |
| Input | Single-ended or balanced |
| Power supply | Universal AC 100-240V, 50/60Hz |
| Efficiency | > 90% at rated power |
| Dimensions | 170 x 83 x 34mm |
| Protection | Over-temp, DC offset, short circuit |

### Bi-amp Routing

```
Pi 5 I2S → ES9038Q2M DAC
              ├── L output → ICEpower Ch1 → Woofer (125W)
              └── R output → ICEpower Ch2 → HF Driver (125W, limited to 30W by DSP)
```

## 6. DAC: ES9038Q2M

| Parameter | Value |
|-----------|-------|
| Chip | ESS Sabre ES9038Q2M |
| Architecture | Dual-mono HyperStream II |
| SNR | -120dB (A-weighted) |
| THD+N | -112dB |
| Dynamic range | 120dB |
| Interface | I2S (from Pi 5 GPIO) |
| Sample rate | Up to 384kHz / 32-bit |
| Output | Balanced analog (differential) |

### Why ES9038Q2M over HiFiBerry DAC+

| | HiFiBerry DAC+ Pro | ES9038Q2M Board |
|---|---|---|
| Chip | PCM5122 | ES9038Q2M |
| SNR | -112dB | **-120dB** |
| Price | $35 | **$15** |
| Dynamic range | 112dB | **120dB** |
| Interface | HAT (occupies GPIO) | **I2S (3 GPIO pins)** |

The ES9038Q2M provides 8dB better SNR at less than half the cost, and doesn't consume the Pi's HAT slot (needed for WiFi 7 M.2 adapter).

## 7. Compute: Raspberry Pi 5

### Audio Processing Pipeline

```
Audio Input (AES67/Dante over Ethernet, or WiFi stream, or XLR via ADC)
     ↓
Pi 5 receives audio samples (48kHz/24-bit)
     ↓
[GPS 1PPS sync → adjust sample clock]
     ↓
[FIR Crossover Engine - 512 taps per channel]
  ├── Woofer path: FIR LP 1.8kHz + System EQ + Phase correction
  └── HF path:     FIR HP 1.8kHz + System EQ + Phase correction + Level pad
     ↓
[Peak Limiter - per channel]
  ├── Woofer: threshold = +18dBu, attack 1ms, release 100ms
  └── HF:     threshold = +6dBu, attack 0.5ms, release 50ms
     ↓
[I2S output to ES9038Q2M DAC]
     ↓
[ICEpower 125ASX2]
  ├── Ch1 → 8" Woofer
  └── Ch2 → 1" CD Horn
```

### CPU Budget (Pi 5 Cortex-A76 @ 2.4GHz)

| Task | CPU Core | Load |
|------|----------|------|
| FIR crossover (512 taps x 2ch) | Core 0 | ~15% |
| System EQ + limiter | Core 0 | ~5% |
| GPS sync + PTP | Core 1 | ~2% |
| WiFi AP (500 CROWD devices) | Core 2 | ~20% |
| 4G backhaul + control | Core 3 | ~5% |
| OS overhead | Shared | ~10% |
| **Total** | | **~57%** |

Headroom is sufficient. NEON SIMD acceleration reduces FIR load further.

### WiFi 7 Access Point

The Intel BE200 operates in AP mode, serving as the local wireless hub:

| Parameter | Value |
|-----------|-------|
| Band | 6GHz (WiFi 7 primary) + 2.4GHz (fallback for CROWD v1) |
| Bandwidth | 160MHz channel on 6GHz |
| Max throughput | 2.4Gbps aggregate |
| Client capacity | 500+ (MU-MIMO + OFDMA) |
| MLO | Multi-Link Operation for low latency |
| Range | ~50m outdoor (sufficient for FILL coverage zone) |

Each FILL acts as a WiFi AP for its coverage zone. CROWD devices auto-connect to the nearest FILL.

## 8. GPS Synchronization

### 1PPS + PTP Architecture

```
GPS Satellite
     ↓
Active Antenna → NEO-M9N
                    ↓
              1PPS pulse (rising edge, <30ns jitter)
                    ↓
              Pi 5 GPIO interrupt → gpsd + chrony
                    ↓
              PTP master clock (IEEE 1588)
                    ↓
              Audio sample clock disciplined to GPS
                    ↓
              All FILLs play the same sample at the same instant
```

### PTP Master Clock

Each FILL runs as a PTP grandmaster (when GPS-locked) or PTP slave (when daisy-chained via Ethernet). This provides:
- <1us sync between all speakers on the same Ethernet segment
- <100ns sync when GPS-locked
- Seamless failover: GPS → PTP → WiFi NTP (degraded)

### Delay Towers

For delay tower applications, GPS sync automatically handles the time-of-flight compensation:

```
STAGE                        DELAY TOWER
[FILL] ←── 50m ──→ Listener ←── 0m ──→ [FILL]

Speed of sound: 343 m/s
50m delay: 50/343 = 145.8ms

Delay tower FILL adds 145.8ms delay (calculated from GPS positions).
Result: Sound from both sources arrives at listener simultaneously.
GPS positions are auto-detected — no manual measurement needed.
```

## 9. Cellular: Quectel EC25-J

| Parameter | Value |
|-----------|-------|
| Standard | 4G LTE Cat-4 |
| Bands (Japan) | B1/3/8/18/19/26/28/41 |
| DL speed | 150Mbps |
| Interface | USB 2.0 to Pi 5 |
| Purpose | Backup internet, remote monitoring, OTA updates |

The 4G module provides internet connectivity when venue WiFi is unavailable. It is NOT used for audio transport (latency too high). Uses:
- Remote control from Koe cloud dashboard
- OTA firmware updates
- Telemetry upload (GPS position, temperature, limiter events)
- Emergency alerting

## 10. Protection Systems

| Protection | Sensor | Action | Recovery |
|------------|--------|--------|----------|
| Thermal (amp) | ICEpower internal | Auto power reduction at 75C | Auto at 65C |
| Thermal (woofer) | NTC on voice coil | Pi reduces woofer gain at 140C, mutes at 160C | Auto at 110C |
| Thermal (HF) | NTC on diaphragm | Pi reduces HF gain at 120C, mutes at 150C | Auto at 100C |
| Short circuit | ICEpower internal | Instant shutdown | Auto retry after 3s |
| DC offset | ICEpower internal | Relay disconnect | Auto after 3s |
| Woofer excursion | DSP limiter | Peak limiter at +18dBu | Instantaneous |
| HF excursion | DSP limiter | Peak limiter at +6dBu | Instantaneous |
| Clip detection | ICEpower clip out | Pi reduces input gain 1dB | Auto after 2s |
| Power brownout | Pi voltage monitor | Graceful shutdown at 4.5V | Manual restart |

## 11. Application Modes

Koe FILL is versatile. The DSP preset changes based on deployment:

| Mode | Position | Preset Changes |
|------|----------|----------------|
| **Main PA** | On stage, aimed at audience | Full range 65Hz-20kHz, no delay |
| **Delay Tower** | Mid-field on pole | GPS-calculated delay, reduced LF below 100Hz |
| **Front Fill** | Stage lip, aimed at front rows | Reduced level, -6dB LF shelf, narrow V coverage |
| **Stage Monitor** | On stage floor, aimed at performer | -10dB LF, +3dB 2-5kHz presence, wedge EQ |
| **Side Fill** | Stage wings | Full range, mono sum, delay matched to mains |

Mode is selected via Koe STAGE control interface or auto-detected from GPS position relative to stage coordinates.

## 12. Connector Panel (Rear)

```
┌────────────────────────────────────────┐
│                                        │
│  [IEC C14]  [XLR In]  [Speakon Out]   │
│                                        │
│  [RJ45 Ethernet]  [USB-C]             │
│                                        │
│  [GPS Ant SMA]  [4G Ant SMA]          │
│                                        │
│  [Power LED]  [Status LED x5 WS2812B] │
│                                        │
│  (ventilation mesh for electronics)    │
│                                        │
└────────────────────────────────────────┘
```

## 13. Mechanical

### Rigging Point

Single M10 threaded insert on top panel, flush mount, rated for 50kg (4x safety factor for 12kg unit). Accepts standard clamp or safety cable.

### Pole Mount

35mm speaker stand adapter on bottom panel. Steel flange with M20 thread insert. Compatible with standard K&M / Ultimate Support speaker poles.

### Handle

Single top-mounted powder-coated steel strap handle. Position: centered on top panel, recessed 5mm.

### Orientation

| Mounting | Orientation | Notes |
|----------|-------------|-------|
| Speaker pole | Vertical, horn on top | Default |
| Floor monitor | 45-degree wedge bracket (optional) | Stage monitor mode |
| Rigging | Inverted or horizontal | Via M10 rigging point |
| Wall mount | U-bracket (optional accessory) | Permanent install |

## 14. Finish

- Exterior: Black Duratex textured coating
- Grille: Powder-coated perforated steel, acoustically transparent (>60% open area)
- Logo: Laser-engraved "Koe" on front grille frame
- LED strip: Visible through grille gap between woofer and horn (status + sync visualization)

## 15. Compliance Targets

| Standard | Scope |
|----------|-------|
| IEC 62368-1 | Electrical safety |
| EN 55032 Class B | EMC emissions |
| EN 55035 | EMC immunity |
| EN 301 489 | Radio equipment EMC |
| EN 300 328 / 303 687 | WiFi 7 radio |
| JATE / TELEC | Japan radio certification |
| RoHS | Hazardous substances |
| IP20 | Indoor use |

## 16. Test Plan

| Test | Method | Pass Criteria |
|------|--------|---------------|
| Frequency response | Swept sine, 1m on-axis, anechoic | 65Hz-20kHz +/-3dB |
| Max SPL (woofer) | Shaped pink noise, 1m | >= 112dB continuous |
| Max SPL (HF) | Shaped pink noise, 1m | >= 118dB continuous |
| THD (80Hz) | Single tone at rated power | < 3% |
| THD (1kHz) | Single tone at rated power | < 0.5% |
| THD (10kHz) | Single tone at rated power | < 1% |
| Crossover sum | Transfer function measurement | +/-1dB through 1.8kHz |
| Phase linearity | Group delay measurement | < 2ms variation 200Hz-16kHz |
| GPS sync | 2x FILLs, measure phase at 1kHz | < 5 degrees |
| WiFi capacity | 500 ESP32 clients, 100byte/s each | All connected, <50ms latency |
| 4G connectivity | Remote SSH via cellular | Stable connection |
| Thermal | 2hr pink noise at 1/4 power | All components < rated temp |
| Drop test | 300mm onto concrete, padded corners | No structural damage |
| Horizontal coverage | Polar plot at 2kHz, 4kHz, 8kHz | 90deg +/-10deg |
| Vertical coverage | Polar plot at 2kHz, 4kHz, 8kHz | 50deg +/-10deg |
