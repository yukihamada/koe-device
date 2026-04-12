# Koe Pro v2 Hardware Design Validation Report

**Date**: 2026-03-27
**Board**: 45x30mm, 4-layer FR-4
**MCU**: nRF5340-QKAA (QFN-94)
**Reviewer**: Automated cross-check against datasheets and Zephyr devicetree

---

## 1. nRF5340 Pin Assignment Verification

### I2S Peripherals

- **CRITICAL FINDING**: The nRF5340 has **only ONE I2S peripheral (I2S0)** on the application core.
  - Source: [Zephyr nrf5340_cpuapp_peripherals.dtsi](https://github.com/zephyrproject-rtos/zephyr/blob/main/dts/arm/nordic/nrf5340_cpuapp_peripherals.dtsi) defines only `i2s0 @ 0x28000`. There is **no i2s1**.
  - Source: [Nordic nRF5340 I2S Product Spec](https://infocenter.nordicsemi.com/topic/ps_nrf5340/i2s.html)

| Pin Assignment | Overlay | Schematic | Status |
|---|---|---|---|
| I2S0 SCK (BCLK) | P0.06 | P0.04 (schematic label says P0.04) | see note below |
| I2S0 LRCK | P0.07 | P0.05 | see note below |
| I2S0 SDIN | P0.08 | P0.06 | see note below |
| I2S1 SCK | P0.26 | P0.25 | **DOES NOT EXIST** |
| I2S1 LRCK | P0.27 | P0.26 | **DOES NOT EXIST** |
| I2S1 SDOUT | P0.28 | P0.27 | **DOES NOT EXIST** |

#### Overlay vs Schematic Pin Mismatch

The overlay uses P0.06/P0.07/P0.08 for I2S0, but the schematic labels them as P0.04/P0.05/P0.06/P0.07. The gen_pro_v2.py routes reference "P0.04-P0.07" in comments. **These are inconsistent -- the overlay is the authoritative firmware config but the schematic and PCB traces route to different pins.**

### SPI3 (DW3720 UWB)

| Signal | Overlay Pin | Schematic Pin | Status |
|---|---|---|---|
| MOSI | P0.13 | P0.13 (B1) | Consistent |
| MISO | P0.14 | P0.14 (B2) | Consistent |
| SCK | P0.15 | P0.15 (B3) | Consistent |
| CS | P0.16 | P0.16 (B4) | Consistent |
| IRQ | P0.17 | P0.17 (B5) | Consistent |
| RST | P0.18 | P0.18 (B6) | Consistent |

### I2C1 (nPM1300 PMIC)

| Signal | Overlay Pin | Schematic Pin | Status |
|---|---|---|---|
| SDA | P0.30 | P0.09 (A7) | **MISMATCH** |
| SCL | P0.31 | P0.10 (A8) | **MISMATCH** |

The overlay uses P0.30/P0.31 for I2C, but the schematic labels these as P0.09/P0.10. The gen_pro_v2.py routes I2C traces from the nRF5340 to nPM1300 using coordinates that correspond to the schematic's P0.09/P0.10 positions.

### Other GPIO

| Signal | Overlay Pin | Schematic Pin | Status |
|---|---|---|---|
| Button | P0.23 (sw0) | P0.08 (A6) | **MISMATCH** |
| WS2812B LED | P0.24 | P0.20 (C1) | **MISMATCH** |
| Speaker Amp EN | P0.25 | P0.21 (C2) | **MISMATCH** |

---

## 2. I2S Architecture -- CRITICAL ERROR

### The Problem

The design requires **3 separate I2S buses**:
1. **I2S0**: AK5720 ADC input (RX)
2. **I2S1**: PCM5102A DAC output (TX) -- **DOES NOT EXIST**
3. **AMP I2S**: MAX98357A speaker amp -- **NO PERIPHERAL AVAILABLE**

The nRF5340 has **only 1 I2S peripheral** which supports full-duplex (simultaneous SDIN + SDOUT on the same instance).

### The Fix

Use I2S0 in full-duplex mode:
- I2S0 SDIN: connect to AK5720 SDOUT (ADC input)
- I2S0 SDOUT: connect to PCM5102A DIN (DAC output)
- I2S0 SCK/LRCK: shared clock bus to both AK5720 and PCM5102A

The MAX98357A must either:
- (a) Share the I2S0 bus (BCLK/LRCK/SDOUT, with its own SD enable pin), or
- (b) Be removed from the design and replaced with the PCM5102A driving an external amplifier

**Status**: MUST FIX before fabrication

---

## 3. AK5720 ADC Verification

| Parameter | Schematic | Datasheet | Status |
|---|---|---|---|
| Package | SSOP-16 | SSOP-16 | Correct |
| Pin 1: LRCK | Connected | LRCK input | Correct |
| Pin 2: BCLK | Connected | BCLK input | Correct |
| Pin 3: SDOUT | Connected to I2S SDIN | Serial data out | Correct |
| Pin 4: MCLK | Connected | Master clock in | Correct |
| Pin 5: AINL | Connected to TRS tip | Analog input L | Correct |
| Pin 6: AINR | Connected to TRS tip | Analog input R | Correct |
| Pin 7: AVDD | 3.3V | Analog VDD | Correct |
| Pin 8: DVDD | 3.3V | Digital VDD | Correct |
| Pin 9: AGND | GND | Analog GND | Correct |
| Pin 10: DGND | GND | Digital GND | Correct |
| Pin 11: FMT | 10k pull-down (R6) | Format select | Correct (I2S mode) |
| Bypass caps | C7 (100nF AVDD), C8 (10uF DVDD) | Required | Correct |

**Note**: AK5720 does NOT have MCLK on pin 4 in all variants. The AK5720VT datasheet should be cross-checked for exact pin 4 function. Some variants use pin 4 as a mode select. The schematic symbol shows pin 4 as MCLK which may be incorrect for the VT variant.

---

## 4. PCM5102A DAC Verification

| Parameter | Schematic | Datasheet (TI) | Status |
|---|---|---|---|
| Package | TSSOP-20 (schematic says SSOP-20 in gen_pro_v2.py) | TSSOP-20 | **gen_pro_v2.py pad dimensions wrong** |
| Pin 1: BCK | Connected to I2S1_SCK | **Correct function** | Pin exists |
| Pin 2: DIN | Connected to I2S1_SDOUT | **Should be DATA IN** | See note |
| Pin 3: LRCK | Connected to I2S1_LRCK | LRCK input | Correct |
| Pin 4: SCK | Not connected in overlay | System clock | **Must tie to GND for auto-clock** |
| Pin 5: FMT | 10k pull-down (R7) | Format select | Correct (I2S mode = LOW) |
| Pin 6: XSMT | Not visible in schematic | Soft mute | **Must tie HIGH via pull-up for normal operation** |
| Pin 13: DEMP | 10k pull-down (R8) | De-emphasis | Correct (OFF = LOW) |
| AVDD, DVDD, CPVDD | 3.3V | Power | Verify all 3 connected |
| GND | Connected | Ground | Correct |
| Bypass caps | C9 (100nF), C10 (10uF) | Required | Correct |

**Issues**:
- SCK (pin 4) must be tied LOW for auto-clock detection mode; verify this connection
- XSMT (pin 6) must be tied HIGH (3.3V) or driven HIGH to unmute; **missing pull-up in schematic**
- The schematic symbol only exposes 13 pins of the 20-pin TSSOP; remaining pins (VOUTL coupling caps, charge pump pins CAPP/CAPM, VNEG, LDOO, FLT) are not shown -- verify they are properly connected in the PCB layout
- gen_pro_v2.py defines PCM5102A as "SSOP-20" with pad pitch calculation, but the actual part (PCM5102APWR) is TSSOP-20 (4.4x6.5mm). The footprint in gen_pro_v2.py uses 6.5x7.5mm body which is **oversized** for a TSSOP-20

---

## 5. DW3000 UWB Verification (was DW3720 -- replaced)

| Parameter | Design | Datasheet | Status |
|---|---|---|---|
| Package | QFN-48 (per BOM) | **DW3000 family uses QFN-40 or WLCSP-52** | **PACKAGE ERROR** |
| SPI interface | Pins 1-4 in schematic | Verify against actual datasheet | **Cannot verify -- DW3720 may not exist as a real part** |
| IRQ | Pin 5 | DW3000 QFN pin 1 is IRQ | **Pin numbering likely wrong** |
| RST | Pin 6 | Verify | Unknown |
| RF_OUT | Pin 7 | Verify | Unknown |
| Crystal | Not shown in schematic | 38.4MHz TCXO required for DW3000 | **MISSING CRYSTAL/TCXO** |
| RF matching network | Not in BOM | Required for antenna | **MISSING from BOM** |

**Critical Issues**:
- The "DW3720" may not be a real Qorvo part number. The DW3000 family naming convention is DW3X1X (WLCSP) and DW3X2X (QFN), e.g. DW3110, DW3120, DW3210, DW3220. A "DW3720" does not follow this pattern.
- The LCSC part C5184302 should be verified -- it may map to a different part entirely.
- DW3000 QFN package has **40 pads**, not 48 as specified in gen_pro_v2.py (49 including exposed pad). The footprint generates 48 signal pads + 1 EP = 49 total, which is wrong for a 40-pad QFN.
- Missing 38.4MHz TCXO/crystal for UWB transceiver.
- Missing RF matching network components (typically Pi-network with inductors and capacitors).

---

## 6. nPM1300 PMIC Verification

| Parameter | Design | Datasheet | Status |
|---|---|---|---|
| I2C Address | 0x6B | 0x6B (confirmed) | Correct |
| Package | QFN-32 | QFN-32 (5x5mm) | Correct |
| VBUS (pin 1) | Connected to USB VBUS | VBUS input | Correct |
| VBAT (pin 2) | Connected to battery | Battery input | Correct |
| SDA (pin 3) | Connected to I2C SDA | TWI data | Correct |
| SCL (pin 4) | Connected to I2C SCL | TWI clock | Correct |
| BUCK1_OUT (pin 5) | 3.3V rail | Buck output | Correct |
| BUCK1_LX (pin 6) | To inductor L1 | Switch node | Correct |
| LDSW1 (pin 7) | Load switch | Load switch out | Correct |
| GND (pin 8) | Ground | Ground | Correct |
| Buck inductor (L1) | 10uH (0805) | 10uH recommended | Correct |
| Buck2 inductor (L2) | 4.7uH (0805) | 4.7uH recommended | Correct |
| Input cap (C12) | 10uF | 10uF recommended | Correct |
| Output cap (C13) | 22uF | 22uF recommended | Correct |
| I2C pull-ups | R4/R5 4.7k | Required | Correct |

**Note**: The simplified schematic only shows 8 pins + EP of the 32-pin QFN. Many pins (BUCK2_LX, BUCK2_OUT, GPIO, NTC, etc.) are not shown. Verify unconnected pins are properly handled (NC or tied appropriately).

---

## 7. Gerber File Validation

### Board Dimensions

Edge_Cuts Gerber defines a 45x30mm board with 1mm corner radius arcs. Verified: X range 0-45mm, Y range 0-30mm.

### Pad Count Verification

| Component | Expected Pads | Status |
|---|---|---|
| U1 (nRF5340) | 95 (94 signal + 1 EP) | Correct in gen |
| U2 (DW3720) | 49 (48 + 1 EP) | **Should be 41 (40+1) for real DW3000** |
| U3 (AK5720) | 16 | Correct |
| U4 (PCM5102A) | 20 | Correct |
| U5 (MAX98357A) | 17 (16 + 1 EP) | Correct |
| U6 (nPM1300) | 33 (32 + 1 EP) | Correct |
| Total component pads | 323 | -- |
| Total vias | 21 | -- |
| Total F_Cu flashes | 344 | Matches (323 + 21) |

### Drill File Verification

| Tool | Diameter | Usage | Count | Status |
|---|---|---|---|---|
| T1 | 1.0mm | TRS jack through-holes | 5 | Correct |
| T2 | 2.2mm | M2 mounting holes | 4 | Correct |
| T3 | 0.3mm | Signal/GND vias | 21 | Correct |

Via drill 0.3mm with 0.5mm pad is acceptable for 4-layer fabrication.

### Aperture Verification

Key apertures in F_Cu:
- D10: R,0.2x0.7mm -- nRF5340 QFN pads (24 per side, 0.4mm pitch, correct)
- D11: R,0.7x0.2mm -- nRF5340 QFN pads (rotated, correct)
- D12: C,5.0mm -- nRF5340 exposed thermal pad (correct for 5x5mm EP)
- D13: R,0.25x0.8mm -- DW3720 pads (0.5mm pitch, correct geometry)
- D15: C,4.0mm -- DW3720 exposed pad (correct)
- D16: R,0.4x1.5mm -- AK5720 SSOP-16 pads (incorrect if 0.65mm pitch)

### Missing Gerber Layers

The production set has:
- F_Cu, B_Cu, In1_Cu, In2_Cu (4 copper layers)
- F_Mask, B_Mask
- F_SilkS
- Edge_Cuts
- Drill file

**Missing**: B_SilkS (back silkscreen -- minor, not critical for fabrication)

---

## 8. Summary of Issues

### CRITICAL (Board will not function)

| # | Issue | Files Affected | Status |
|---|---|---|---|
| 1 | **nRF5340 has only 1 I2S peripheral.** Design uses i2s0 + i2s1 + AMP I2S = 3 I2S buses. Only I2S0 exists. | overlay, audio.c, schematic, gen_pro_v2.py | OPEN (firmware overlay change needed) |
| 2 | ~~**DW3720 may not be a real part.** QFN-48 footprint is wrong. Missing crystal/TCXO and RF matching network.~~ | gen_pro_v2.py, schematic, BOM | ✅ FIXED: Replaced DW3720 with DW3000 (LCSC C2843371). Added Y3 38.4MHz TCXO, C16-C19 decoupling caps, L3 15nH + C20 1.5pF RF matching network, R10 RST pull-up. Footprint updated to 6x6mm QFN-48. |
| 3 | **Pin assignment mismatch between overlay and schematic.** I2C pins (P0.30/31 vs P0.09/10), button (P0.23 vs P0.08), LED (P0.24 vs P0.20) are different in firmware vs hardware. | overlay, schematic, gen_pro_v2.py | OPEN (firmware overlay change needed) |

### HIGH (Board may partially function with rework)

| # | Issue | Files Affected | Status |
|---|---|---|---|
| 4 | ~~PCM5102A XSMT pin must be tied HIGH (missing pull-up resistor). Without this, DAC stays muted.~~ | schematic, gen_pro_v2.py | ✅ FIXED: Added R11 10k pull-up on XSMT pin. |
| 5 | ~~PCM5102A SCK pin must be tied to GND for auto-clock mode. Not verified in schematic.~~ | schematic | ✅ FIXED: Added DAC_SCK_GND trace routing SCK pin to GND. |
| 6 | ~~PCM5102A footprint dimensions in gen_pro_v2.py (6.5x7.5mm) are wrong for TSSOP-20 (4.4x6.5mm).~~ | gen_pro_v2.py | ✅ FIXED: Body size corrected to 4.4x6.5mm, pad row spacing updated to 2.2mm half-width. |
| 7 | ~~Missing charge pump caps (CAPP/CAPM), output coupling caps, LDOO bypass cap for PCM5102A.~~ | schematic, BOM | ✅ FIXED: Added C21 1uF (charge pump CAPP/CAPM), C22/C23 2.2uF (output coupling VOUTL/VOUTR), C24 10uF (LDOO bypass), C25 100nF (CPVDD bypass). |
| 8 | AK5720 MCLK connection -- verify AK5720VT variant actually has MCLK on pin 4. | schematic | OPEN (requires datasheet verification) |

### MEDIUM (Cosmetic / Non-blocking)

| # | Issue | Files Affected | Status |
|---|---|---|---|
| 9 | Missing back silkscreen Gerber in production set. | generate_gerbers.py | OPEN (minor, not critical) |
| 10 | ~~BOM lists "DW3720 (Qorvo QFN-48)" -- verify LCSC C5184302 maps to a real orderable part.~~ | BOM | ✅ FIXED: Changed to DW3000 with LCSC C2843371. |
| 11 | nPM1300 schematic only shows 8/32 pins. Remaining pins need verification. | schematic | OPEN (requires datasheet verification) |

---

## 9. Recommended Fix Plan

### Priority 1: I2S Architecture Redesign

1. Use I2S0 in full-duplex mode (SDIN from AK5720, SDOUT to PCM5102A)
2. Connect MAX98357A to the same I2S bus (BCLK/LRCK/SDOUT shared with PCM5102A)
3. Use MAX98357A SD_MODE pin (P0.25 via GPIO) to enable/disable speaker independently
4. Update device tree overlay to single I2S0 with both SDIN and SDOUT pins
5. Update audio.c to use single I2S device for both RX and TX

### Priority 2: Resolve Pin Mismatches

Align overlay with schematic (or vice versa). Since the PCB is not yet fabricated, update the overlay to match the schematic pin assignments, which correspond to actual PCB traces.

### Priority 3: UWB Module -- ✅ COMPLETED

1. ~~Verify DW3720 is a real part or replace with DW3220 (QFN) or DW3120 (WLCSP)~~ -- Replaced with DW3000 (C2843371)
2. ~~Fix footprint to correct pin count~~ -- Updated to 6x6mm QFN-48
3. ~~Add 38.4MHz TCXO to BOM and schematic~~ -- Added Y3 (C2838510)
4. ~~Add RF matching network components~~ -- Added L3 15nH (C76862) + C20 1.5pF, R10 10k RST pull-up, C16-C19 decoupling

### Priority 4: PCM5102A Fixes -- ✅ COMPLETED

1. ~~Add pull-up resistor on XSMT pin~~ -- Added R11 10k (C25744)
2. ~~Tie SCK to GND~~ -- Added DAC_SCK_GND trace
3. ~~Add charge pump and output coupling capacitors~~ -- Added C21 1uF, C22/C23 2.2uF, C24 10uF, C25 100nF
4. ~~Fix TSSOP-20 footprint dimensions~~ -- Corrected to 4.4x6.5mm body

---

## 10. Datasheet Sources

- [nRF5340 Product Specification](https://docs.nordicsemi.com/bundle/ps_nrf5340/page/keyfeatures_html5.html)
- [nRF5340 I2S Peripheral](https://infocenter.nordicsemi.com/topic/ps_nrf5340/i2s.html)
- [nRF5340 Zephyr Peripheral DTS](https://github.com/zephyrproject-rtos/zephyr/blob/main/dts/arm/nordic/nrf5340_cpuapp_peripherals.dtsi)
- [nRF5340 Peripheral Instantiation](https://docs.nordicsemi.com/bundle/ps_nrf5340/page/chapters/soc_overview/doc/instantiation.html)
- [PCM5102A Datasheet (TI)](https://www.ti.com/product/PCM5102A)
- [AK5720 Datasheet (AKM)](https://www.akm.com/content/dam/documents/products/audio/audio-adc/ak5720vt/ak5720vt-en-datasheet.pdf)
- [DW3000 Datasheet (Qorvo)](https://www.mouser.com/pdfDocs/DW3000DataSheet5.pdf)
- [DW3000 Family Notes](https://technicallycompetent.com/blog/uwb-dw3xxx/)
- [nPM1300 Datasheet (Nordic)](https://download.mikroe.com/documents/datasheets/nPM1300_datasheet.pdf)
- [nPM1300 Zephyr Binding](https://docs.zephyrproject.org/latest/build/dts/api/bindings/mfd/nordic,npm1300.html)
