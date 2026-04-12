# Koe Seed -- Speaker Selection by Form Factor

> Optimal speaker for each of the 10 Koe Seed form factors.
> Selection criteria: physical fit, frequency response, SPL, power handling, availability (LCSC/AliExpress), price at qty 100.

---

## Quick Reference Table

| # | Form Factor | Speaker Type | Model / Size | Dimensions (mm) | Impedance | Power | Freq Range | SPL | Price @100 |
|---|-------------|-------------|-------------|-----------------|-----------|-------|------------|-----|------------|
| 1 | Coin (28mm disc) | Dynamic micro | 1510 neodymium | 15x10x3.5 | 8 ohm | 0.5W | 500-20kHz | 78dB | $0.25 |
| 2 | Wristband Pod | Bone conduction | 15mm piezo disc | 15x15x2.5 | 32 ohm | 0.3W | 200-8kHz | N/A (tactile) | $0.80 |
| 3 | Keychain (32mm) | Ultra-thin dynamic | 1310 micro | 13x10x2.5 | 8 ohm | 0.4W | 600-20kHz | 75dB | $0.22 |
| 4 | Clip (35x25mm) | Dynamic micro | 1510 neodymium | 15x10x3.5 | 8 ohm | 0.5W | 500-20kHz | 78dB | $0.25 |
| 5 | Badge (55x35mm) | Wide dynamic | 2015 neodymium | 20x15x4.0 | 8 ohm | 1.0W | 400-20kHz | 82dB | $0.35 |
| 6 | Pendant (35x28mm) | Dynamic micro | 1510 neodymium | 15x10x3.5 | 8 ohm | 0.5W | 500-20kHz | 78dB | $0.25 |
| 7 | Sticker (32mm, 6mm) | Piezo ceramic disc | 12mm piezo | 12x12x0.3 | High-Z | 0.1W | 1k-10kHz | 70dB | $0.08 |
| 8 | Pick (30x26mm) | Ultra-micro dynamic | 1008 micro | 10x8x3.0 | 8 ohm | 0.3W | 800-20kHz | 72dB | $0.20 |
| 9 | Drum Key (35x20mm) | Dynamic micro | 1510 sealed | 15x10x3.5 | 8 ohm | 0.5W | 500-20kHz | 78dB | $0.25 |
| 10 | Capo Clip (40x20mm) | Dynamic micro | 1510 neodymium | 15x10x3.5 | 8 ohm | 0.5W | 500-20kHz | 78dB | $0.25 |

---

## Detailed Analysis per Form Factor

### 1. Coin (Standard, 28mm disc, 19.6mm tall)

**Available cavity**: ~15x10x4mm (after PCB, battery, and USB-C clearance)

**Recommended: 1510 Neodymium Micro Speaker**

| Spec | Value |
|------|-------|
| Model | Generic 1510 (GF1004, JST-1510A equivalent) |
| Dimensions | 15.0 x 10.0 x 3.5mm |
| Impedance | 8 ohm |
| Power | 0.5W (max 1.0W) |
| Frequency | 500Hz - 20kHz |
| SPL | 78dB @ 0.1W/0.1m |
| Magnet | Neodymium (NdFeB) |
| LCSC | C2837419 (generic 1510 8ohm 0.5W) |
| AliExpress | "1510 speaker 8ohm 0.5W neodymium" -- $0.15-0.30/pc at qty 100 |
| Price @100 | $0.25 |

**Why this wins**: The 1510 is the standard for this cavity size. Neodymium magnet gives 3-5dB better SPL than ferrite at the same size. Widely available, battle-tested in smartwatches and mini Bluetooth speakers.

**Upgrade option**: If the cavity can be stretched to 18x13mm, a 1813 speaker (18x13x4mm) would give ~3dB more output and extend bass to ~400Hz. But the 28mm disc PCB makes this tight.

---

### 2. Wristband Pod (35x30x12mm oval)

**Available cavity**: ~15x10x3mm max, limited height due to curved wrist profile

**Recommended: 15mm Bone Conduction Piezo Disc Transducer**

| Spec | Value |
|------|-------|
| Model | Murata 7BB-15-6 or generic 15mm piezo buzzer disc |
| Dimensions | 15mm diameter x 2.5mm total (0.3mm element + housing) |
| Impedance | 32 ohm (at resonance ~2.8kHz) |
| Power | 0.3W |
| Frequency | 200Hz - 8kHz (usable via skin conduction) |
| SPL | N/A -- tactile output, not air-coupled |
| LCSC | C96094 (15mm piezo element) or C441834 (bone conduction module) |
| AliExpress | "bone conduction speaker module 15mm" -- $0.60-1.00/pc |
| Price @100 | $0.80 |

**Why bone conduction wins for wristband**:
1. **Skin contact = natural bass boost** -- piezo vibrates against wrist, transmits through bone to inner ear
2. **No sound leak** -- nobody around hears your AI assistant
3. **Ultra-thin** -- 2.5mm vs 3.5mm for dynamic speaker
4. **No acoustic chamber needed** -- dynamic speakers need sealed back volume, piezo doesn't
5. **Waterproof by nature** -- no membrane or port needed

**Driver note**: Bone conduction needs a voltage-mode driver (not MAX98357A current-mode). Use a small Class-D amp with bridged output (PAM8302 or similar, $0.15). Or drive directly from ESP32 DAC through a simple H-bridge.

**Alternative**: If bone conduction is rejected, use an 0810 micro speaker (8x10x2.5mm, $0.18) but expect very weak bass and low volume.

---

### 3. Keychain (32mm disc, 10mm thick)

**Available cavity**: ~13x10x3mm (very tight -- battery takes most of the height)

**Recommended: 1310 Ultra-Thin Micro Speaker**

| Spec | Value |
|------|-------|
| Model | Generic 1310 micro speaker |
| Dimensions | 13.0 x 10.0 x 2.5mm |
| Impedance | 8 ohm |
| Power | 0.4W (max 0.8W) |
| Frequency | 600Hz - 20kHz |
| SPL | 75dB @ 0.1W/0.1m |
| Magnet | Neodymium |
| LCSC | C5184357 (1310 8ohm) |
| AliExpress | "1310 speaker 8ohm thin" -- $0.18-0.28/pc at qty 100 |
| Price @100 | $0.22 |

**Why 1310 over 1510**: The 2.5mm height (vs 3.5mm for 1510) is critical in a 10mm thick device. Sacrifices ~3dB SPL and some bass extension, but that's acceptable for a keychain (not a primary listening device).

**Trade-off**: Consider making the keychain speaker-less (BLE to phone/earbuds only) to save 2.5mm height and use a thicker battery instead. The 1310 is here if audio output is required.

---

### 4. Clip (35x25x12mm)

**Available cavity**: ~15x10x4mm (similar to Coin, slightly more depth)

**Recommended: 1510 Neodymium Micro Speaker** (same as Coin)

| Spec | Value |
|------|-------|
| Model | Same as #1 Coin |
| Dimensions | 15.0 x 10.0 x 3.5mm |
| Impedance | 8 ohm |
| Power | 0.5W |
| Frequency | 500Hz - 20kHz |
| SPL | 78dB @ 0.1W/0.1m |
| LCSC | C2837419 |
| Price @100 | $0.25 |

**Notes**: The clip form factor has nearly identical internal volume to the coin. Same speaker, same amp (MAX98357A). The clip mechanism takes the extra 7mm of width and 5mm of depth.

---

### 5. Badge (55x35x8mm, thin but wide)

**Available cavity**: ~25x15x5mm (the wide badge body allows a bigger speaker)

**Recommended: 2015 Neodymium Speaker**

| Spec | Value |
|------|-------|
| Model | Generic 2015 micro speaker (20x15x4mm) |
| Dimensions | 20.0 x 15.0 x 4.0mm |
| Impedance | 8 ohm |
| Power | 1.0W (max 1.5W) |
| Frequency | 400Hz - 20kHz |
| SPL | 82dB @ 0.1W/0.1m |
| Magnet | Neodymium |
| LCSC | C5352817 (2015 8ohm 1W) |
| AliExpress | "2015 speaker 8ohm 1W" -- $0.28-0.45/pc at qty 100 |
| Price @100 | $0.35 |

**Why 2015 wins for badge**:
1. **Voice clarity** -- 400Hz-20kHz covers the full speech intelligibility range (300Hz-4kHz) with headroom
2. **+4dB over 1510** -- noticeably louder in conference settings
3. **Fits the wide body** -- badge has 55mm width, speaker is only 20mm
4. **1W power** -- MAX98357A can drive it at full output

**Upgrade option**: A 2520 speaker (25x20x5mm, 1.5W) would fit and give even better bass (~300Hz), but the 5mm height is tight in an 8mm badge (PCB + battery + speaker + walls = 0.8 + 2.0 + 5.0 + 0.6 = 8.4mm). The 2015 at 4mm is safer.

---

### 6. Pendant (35x28x10mm teardrop)

**Available cavity**: ~15x10x4mm

**Recommended: 1510 Neodymium Micro Speaker** (same as Coin)

| Spec | Value |
|------|-------|
| Model | Same as #1 Coin |
| Dimensions | 15.0 x 10.0 x 3.5mm |
| Impedance | 8 ohm |
| Power | 0.5W |
| Frequency | 500Hz - 20kHz |
| SPL | 78dB @ 0.1W/0.1m |
| LCSC | C2837419 |
| Price @100 | $0.25 |

**Alternative considered: Bone conduction (15mm piezo)**
- Pendant hangs against chest/sternum, which is a natural bone conduction path
- Sound would transmit through ribcage to inner ear
- Discreet (no one hears), immersive for music
- BUT: unreliable coupling (moves with walking, varies with clothing layers)
- Verdict: interesting for v2, use standard 1510 for v1

---

### 7. Sticker (32mm disc, 6mm ultra-thin!)

**Available cavity**: MAX 1.5mm for audio transducer (6mm - 2mm battery - 0.8mm PCB - 1mm components - 0.6mm walls = 1.6mm)

**Recommended: 12mm Ceramic Piezo Disc**

| Spec | Value |
|------|-------|
| Model | Murata 7BB-12-9 or generic 12mm brass/ceramic piezo |
| Dimensions | 12mm diameter x 0.3mm thick (element only) |
| Impedance | High impedance (capacitive, ~20nF) |
| Power | 0.1W (peak) |
| Frequency | 1kHz - 10kHz (resonance ~4.5kHz) |
| SPL | 70dB @ 10cm (at resonance, with backplate) |
| LCSC | C96093 (12mm piezo disc, $0.04) |
| AliExpress | "12mm piezo buzzer disc element" -- $0.05-0.12/pc |
| Price @100 | $0.08 |

**Why piezo is the only option at 6mm**:
- No dynamic speaker exists under 2mm height
- Piezo element is 0.3mm thick (the thinnest audio transducer available)
- Even with brass backer plate, total is ~0.5mm
- Mount directly to PCB copper pad (soldered) for maximum coupling

**Driver**: Piezo needs voltage-mode drive. Use ESP32 GPIO through a simple flyback boost (3.3V -> 12V) or a dedicated piezo driver IC (e.g., TI DRV2667, $0.90). Higher voltage = louder.

**Acoustic quality**: Honestly poor. Piezo buzzers are tonal (narrow bandwidth), harsh-sounding, and quiet compared to dynamic speakers. The sticker form factor is best used for:
- Alert beeps and notification tones
- Short voice snippets (intelligible but not pleasant)
- Consider making sticker speaker-less and BLE-only for serious audio

---

### 8. Pick (30x26x8mm guitar pick shape)

**Available cavity**: ~10x8x3.5mm (tight triangle shape)

**Recommended: 1008 Ultra-Micro Speaker**

| Spec | Value |
|------|-------|
| Model | Generic 1008 micro speaker |
| Dimensions | 10.0 x 8.0 x 3.0mm |
| Impedance | 8 ohm |
| Power | 0.3W (max 0.5W) |
| Frequency | 800Hz - 20kHz |
| SPL | 72dB @ 0.1W/0.1m |
| Magnet | Neodymium |
| LCSC | C5184356 (1008 8ohm 0.3W) |
| AliExpress | "1008 micro speaker 8ohm" -- $0.15-0.25/pc at qty 100 |
| Price @100 | $0.20 |

**Why 1008**: The guitar pick shape tapers to a narrow tip. Only the widest part (~26mm) has room for components. The 1008 fits into the limited triangular cavity. Bass starts at 800Hz which misses the low guitar fundamentals (80-330Hz), but this is a monitor for the player -- hearing chord voicings and AI responses is the priority, not bass reproduction.

**Alternative: Bone conduction for guitar monitoring**
- Guitarist holds the pick between fingers -- direct skin contact
- Vibrations transmit through hand to player
- Cost: $0.80 vs $0.20
- Best for: private monitoring without sound leaking into guitar mic
- Verdict: Offer as a variant (Pick BC) for studio use

---

### 9. Drum Key (35x20x15mm T-shape)

**Available cavity**: ~15x10x4mm (in the T-crossbar)

**Recommended: 1510 Sealed-Back Neodymium Speaker**

| Spec | Value |
|------|-------|
| Model | 1510 with sealed back chamber |
| Dimensions | 15.0 x 10.0 x 3.5mm |
| Impedance | 8 ohm |
| Power | 0.5W |
| Frequency | 500Hz - 20kHz |
| SPL | 78dB @ 0.1W/0.1m |
| LCSC | C2837419 (same 1510, seal during assembly) |
| Price @100 | $0.25 |

**Sealed back is critical for drum environment**:
- Drums produce 100-120dB SPL at close range
- Open-back speaker would couple with drum vibrations, creating feedback
- Seal the back cavity with a small piece of closed-cell foam + gasket
- Direct the front through a narrow port aimed at the drummer's ear

**Alternative**: For extreme drum environments, consider a bone conduction transducer clamped to the drum hardware (metal tube) -- vibrations travel through the metal stand to the drummer's body. Experimental but potentially effective.

---

### 10. Capo Clip (40x20x15mm)

**Available cavity**: ~15x10x4mm (in one jaw of the clip)

**Recommended: 1510 Neodymium Micro Speaker** (same as Coin)

| Spec | Value |
|------|-------|
| Model | Same as #1 Coin |
| Dimensions | 15.0 x 10.0 x 3.5mm |
| Impedance | 8 ohm |
| Power | 0.5W |
| Frequency | 500Hz - 20kHz |
| SPL | 78dB @ 0.1W/0.1m |
| LCSC | C2837419 |
| Price @100 | $0.25 |

**Mounting note**: Place speaker in the upper jaw (away from the clamped surface) and face outward toward the musician. The lower jaw should contain the battery (heavier, keeps center of gravity low for stable clamping).

---

## Speaker Sourcing Summary

### LCSC Parts (for JLCPCB PCBA orders)

| Part | LCSC # | Description | Qty 100 Price |
|------|--------|-------------|---------------|
| 1510 8ohm 0.5W | C2837419 | Standard neodymium micro speaker | $0.25 |
| 1310 8ohm 0.4W | C5184357 | Ultra-thin micro speaker | $0.22 |
| 2015 8ohm 1.0W | C5352817 | Wide format speaker | $0.35 |
| 1008 8ohm 0.3W | C5184356 | Ultra-micro speaker | $0.20 |
| 12mm Piezo disc | C96093 | Ceramic buzzer element | $0.08 |
| 15mm Piezo disc | C96094 | Bone conduction element | $0.12 |

### AliExpress Bulk (for manual assembly or non-JLCPCB orders)

| Search Term | Qty 100 | Qty 1000 | Notes |
|-------------|---------|----------|-------|
| "1510 speaker 8ohm 0.5W neodymium" | $0.15-0.25 | $0.08-0.15 | Most common, many sellers |
| "1310 speaker 8ohm thin 2.5mm" | $0.18-0.28 | $0.10-0.18 | Fewer sellers, check height carefully |
| "2015 speaker 8ohm 1W" | $0.25-0.40 | $0.15-0.25 | Good for badge |
| "1008 micro speaker 8ohm" | $0.15-0.22 | $0.08-0.12 | Smallest dynamic speaker available |
| "piezo disc 12mm 0.3mm" | $0.03-0.08 | $0.02-0.05 | Cheapest audio transducer |
| "bone conduction transducer 15mm" | $0.60-1.00 | $0.40-0.70 | Module with driver included |

---

## Amplifier Compatibility

| Speaker Type | Amp | IC | LCSC | Notes |
|-------------|-----|-----|------|-------|
| Dynamic (1510/1310/2015/1008) | I2S Class-D | MAX98357A | C2682619 | Already on COIN Lite BOM. 3.2W max, 8ohm load |
| Piezo (buzzer) | Voltage boost + PWM | DRV2667 or boost converter | C133997 | Needs 12-20V for adequate volume |
| Bone conduction | Bridged Class-D | PAM8302 | C113367 | Single-channel, 2.5W, 4-8ohm |

**Important**: MAX98357A (already on the BOM) works for all dynamic speakers (1510/1310/2015/1008). Only the piezo and bone conduction variants need a different driver, which adds $0.15-0.90 to BOM.

---

## Form Factor to Speaker Decision Matrix

| Priority | Form Factors | Speaker | Why |
|----------|-------------|---------|-----|
| Standard (most devices) | Coin, Clip, Pendant, Drum Key, Capo | 1510 neodymium | Best balance of size/sound/cost, fits 15x10x4mm cavity |
| Thin profile | Keychain | 1310 | 2.5mm height fits 10mm device |
| Wide body | Badge | 2015 | Uses the available width for better voice clarity |
| Ultra-thin | Sticker | 12mm piezo | Only transducer under 1mm thick |
| Small triangle | Pick | 1008 | Only dynamic speaker under 10mm width |
| Skin contact | Wristband | Bone conduction piezo | Direct body coupling, no sound leak, waterproof |

---

## Acoustic Optimization Tips

### For dynamic speakers (1510/1310/2015/1008)
1. **Seal the back volume** -- even 0.5cc sealed air behind the speaker improves bass 5-10dB
2. **Front port** -- direct sound through a 2-3mm diameter port, not through gaps
3. **Gasket** -- foam ring between speaker and housing prevents air leaks (kills bass)
4. **DSP EQ** -- ESP32-S3 can apply real-time EQ to compensate for small-speaker roll-off below 500Hz

### For piezo (sticker)
1. **Mount to rigid surface** -- solder directly to PCB copper pour for maximum coupling
2. **Resonance tuning** -- add mass (solder blob) to lower resonance from ~4.5kHz to ~2.5kHz for better speech
3. **Drive at 12V+** -- 3.3V gives barely audible output; boost converter essential

### For bone conduction (wristband)
1. **Tight coupling** -- spring-loaded mount or silicone pressure pad against skin
2. **Low-pass emphasis** -- bone conduction naturally attenuates highs; boost 1-4kHz in DSP
3. **Vibration isolation from PCB** -- mount on silicone gasket so vibrations go to skin, not PCB
