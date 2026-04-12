# Koe Seed Outdoor Extreme Edition — -30°C Rated Design

## Target Use Cases
- Ski resorts & snowboard parks
- Arctic festivals (Igloofest, Polar Sound)
- Winter sports events
- Outdoor concerts in cold climates (Scandinavia, Canada, Hokkaido)
- Military/expedition communications

## Operating Specification
- **Operating temperature**: -30°C to +60°C
- **Storage temperature**: -40°C to +70°C
- **Ingress protection**: IP67 (1m submersion, 30 min)
- **Humidity**: 5-95% RH non-condensing (conformal coated)

---

## 1. Component Temperature Audit (vs Standard BOM)

| Component | Part | Standard Rating | -30°C Status | Action |
|-----------|------|----------------|--------------|--------|
| MCU | nRF5340-QKAA-R7 | -40°C to +105°C | OK | Keep |
| PA/LNA | nRF21540-QFAA-R | -40°C to +105°C | OK | Keep |
| Audio Amp | MAX98357AETE+T | -40°C to +85°C | OK | Keep |
| LDO | AP2112K-3.3TRG1 | -40°C to +85°C | OK | Keep |
| **Charger** | **TP4054** | **0°C to +85°C** | **FAIL** | **Replace** |
| **LED** | **WS2812B-2020** | **-20°C to +80°C** | **FAIL** | **Replace** |
| Crystal 32MHz | 2012 package | Typically -40°C to +85°C | OK (verify datasheet) | Keep |
| Crystal 32.768kHz | 1610 package | Typically -40°C to +85°C | OK (verify datasheet) | Keep |
| Capacitors 100nF (X5R) | 0402 | -55°C to +85°C | **Derating**: X5R loses ~40% capacitance at -30°C | **Upgrade to C0G/NP0 for critical paths** |
| Capacitors 10uF (X5R) | 0402/0603 | -55°C to +85°C | **Derating**: significant at -30°C | **Upgrade to X7R or increase value** |
| USB-C Connector | 16P | -30°C to +80°C (typical) | Marginal | Keep (metal, OK) |
| Tact Switch | 3x4mm | -20°C to +70°C (typical) | **FAIL** | **Replace with rated part** |
| Antenna | 2450AT18B100 | -40°C to +85°C | OK | Keep |

### Critical Replacements

#### 1. Charger IC: TP4054 -> BQ25185 (TI)
- **Problem**: TP4054 rated 0°C min, cannot charge LiPo below 0°C (also dangerous to charge Li-ion below 0°C)
- **Solution**: TI BQ25185 (or BQ25180)
  - Operating range: -40°C to +85°C
  - **Built-in JEITA temperature-compliant charging**: automatically reduces charge current at low temps
  - Prevents charging below 0°C (critical safety feature for Li-ion)
  - QFN-12 package, ~$1.20 @ 1k qty
  - LCSC: C2759451 (BQ25180)
- **Alternative**: MCP73831-2ACI with external NTC thermistor circuit (cheaper, $0.50, but requires external components)

#### 2. LED: WS2812B-2020 -> APA102C-2020 or SK6812MINI-E
- **Problem**: WS2812B rated -20°C minimum
- **Solution Options**:
  - **APA102C-2020**: rated -40°C to +85°C, SPI interface (needs 2 extra GPIOs but more reliable timing in cold)
    - ~$0.08 @ 1k, LCSC: C2921604
  - **SK6812MINI-E 2020**: rated -25°C to +80°C (still marginal at -30°C)
  - **Recommendation**: APA102C-2020 for guaranteed -40°C operation
  - Note: APA102C uses SPI (CLK+DATA) instead of single-wire, firmware change required

#### 3. Tact Switch: Standard -> Panasonic EVQ-P7L01P
- IP67-rated tact switch, -40°C to +85°C
- Through-hole mount, requires board modification
- ~$0.40 @ 1k
- **Alternative**: C&K PTS645SM43SMTR92 LFS (-40°C rated, SMD 6x6mm)

#### 4. Capacitors: Upgrade critical paths
- **Decoupling (C1-C4, C7-C8)**: Keep X5R 100nF but add parallel 100nF C0G/NP0 on nRF5340 VDD pins
- **Bulk caps (C5, C10-C12)**: Upgrade from X5R 10uF to **X7R 10uF 0805** (better temp stability)
  - X7R retains ~85% capacitance at -30°C vs X5R's ~60%
- **Crystal load caps (C14, C15)**: Upgrade to C0G/NP0 12pF (critical for oscillator stability)
  - C0G has <0.1% variation over temperature vs X5R's 20%+

---

## 2. Battery Solution

### Primary Recommendation: Low-Temperature LiPo + Self-Heating

#### Battery: Grepow Low-Temperature LiPo
- **Model**: Grepow GRP3048050 (or equivalent custom)
- **Chemistry**: Modified LiCoO2 with low-temperature electrolyte
- **Specs**:
  - Nominal: 3.7V, 600mAh
  - Size: 3.0 x 48 x 50mm (fits 38mm diameter case with folding)
  - **Discharge**: -40°C to +60°C (0.5C at -40°C, delivers ~70% capacity)
  - **Charge**: 0°C to +45°C (industry standard, never charge below 0°C)
  - Cycle life: 500+ cycles
  - Cost: ~$4.50 @ 1k qty (vs $1.50 for standard LiPo)
- **Alternative**: EnergyPower EP-LT series, similar specs, $4-5 range
- **Alternative 2**: Ultralife UBBL39 thin-cell (-40°C rated, MIL-spec, $8)

#### Self-Heating Circuit (for charging in cold)
- **PTC heater element**: 1W PTC thermistor (Murata PRG18BB471) on battery surface
- **NTC temperature sensor**: 10k NTC on battery (TDK NTCG164BH103JT1)
- **Logic**: BQ25185 monitors NTC, enables PTC heater when T < 5°C before allowing charge
- Heater draws ~300mA @ 3.7V = 1.1W, warms cell from -30°C to 0°C in ~3 minutes
- **Cost**: +$0.80 for PTC + NTC + MOSFET

#### Why NOT LiFePO4:
- 3.2V nominal requires different LDO chain (AP2112K-3.3 needs >3.5V input)
- Much lower energy density (cell would be 2x larger for same capacity)
- Better cycle life but we don't need 2000+ cycles for a consumer device
- Would require complete power supply redesign

#### Why NOT Supercapacitor Hybrid:
- Adds complexity and cost (~$2 for supercap + charge balancing)
- Low-temp LiPo already handles burst current adequately at -30°C
- Would be justified for -50°C+ applications but overkill for -30°C target

---

## 3. Enclosure Design

### Dimensions
- **Diameter**: 38mm (vs 31.6mm standard) — extra room for insulation + larger battery
- **Height**: 15mm (vs 19.6mm standard) — wider but flatter profile for jacket attachment
- **Wall thickness**: 2.5mm (vs 1.5mm) — thermal insulation + impact resistance

### Material
- **PA12 Nylon (SLS/MJF printing)**: NOT resin
  - PA12 retains ductility at -40°C (resin becomes brittle below -10°C)
  - Impact strength: 4.5 kJ/m2 at -30°C (vs resin: shatters)
  - Glass transition: ~170°C
  - Color: Matte black (dyed)
  - MJF printing at JLCPCB: ~$3.50/unit @ 100 qty

### IP67 Sealing
- **Gasket groove**: 1.2mm wide x 0.8mm deep groove around case seam
- **Gasket material**: Silicone O-ring (shore 50A), rated -60°C to +200°C
  - Parker 2-014 size or custom cut
  - Silicone remains flexible at -40°C (EPDM also acceptable)
  - ~$0.15/unit @ 1k qty
- **USB-C port**: Recessed 3mm with silicone rubber flap (attached via living hinge)
  - Flap material: LSR (Liquid Silicone Rubber) overmolded or separate insert
- **Speaker grille**: Acoustic membrane (Gore-Tex ePTFE) behind grille holes
  - IP67 waterproof, acoustically transparent
  - Gore Part: GAW300 or equivalent
  - ~$0.30/unit @ 1k qty
- **Button**: Silicone dome cap over tact switch (IP67 seal, tactile feedback through cap)

### Water-Shedding Speaker Grille
- Grille holes angled outward at 15° (cone shape)
- Water runs off, snow doesn't pack into holes
- Acoustic membrane as secondary barrier

### Features
- **Carabiner loop**: Integrated PA12 loop at top, 8mm opening, 15kg rated
- **Recessed button**: 1.5mm recess, 5mm diameter — prevents accidental press with gloves, but large enough to press with gloved finger
- **Anti-slip texture**: 0.3mm knurl pattern on side walls for grip with gloves
- **Lanyard point**: Secondary attachment point opposite carabiner

---

## 4. Conformal Coating

### Specification: Parylene C
- **Why Parylene C**: Best all-around protection for temperature cycling + moisture
  - Pinhole-free at 5um thickness (spray coatings have pinholes)
  - -200°C to +80°C operating range
  - Excellent dielectric properties (won't affect RF)
  - MIL-I-46058C qualified
- **Thickness**: 8-12um (0.008-0.012mm)
- **Coverage**: Entire PCB both sides, excluding:
  - USB-C connector mating surface (masked during coating)
  - Speaker connector pads (masked)
  - Battery connector pads (masked)
  - Test points (masked)
- **Application**: Vacuum deposition (applied at board house or specialty shop)
- **Cost**: ~$1.50/board @ 100 qty, ~$0.60/board @ 1k qty

### Alternative: Silicone Conformal Coating (Dow Corning 1-2577)
- Cheaper ($0.20/board), brush/spray applied
- -65°C to +200°C
- Reworkable (Parylene is not)
- Less reliable moisture barrier (pinholes possible)
- Acceptable for initial production runs

### Condensation Prevention
The conformal coating is critical because:
- Device moves from -30°C outdoor to +20°C indoor
- Condensation forms on cold PCB surfaces
- Without coating: short circuits, corrosion, failure
- Parylene C prevents all moisture-related failures during thermal cycling

---

## 5. Full BOM Delta (Standard -> Outdoor Extreme)

| Change | Standard Part | Outdoor Part | Delta Cost |
|--------|-------------|-------------|------------|
| Charger IC | TP4054 ($0.15) | BQ25185 ($1.20) | +$1.05 |
| LED | WS2812B ($0.06) | APA102C-2020 ($0.08) | +$0.02 |
| Tact Switch | 3x4mm ($0.05) | IP67 rated ($0.40) | +$0.35 |
| Battery | Standard LiPo 400mAh ($1.50) | Grepow LT LiPo 600mAh ($4.50) | +$3.00 |
| PTC Heater | N/A | PTC + NTC + MOSFET ($0.80) | +$0.80 |
| Cap upgrades | X5R all ($0.20) | C0G/NP0 + X7R mix ($0.60) | +$0.40 |
| Conformal coating | N/A | Parylene C ($0.60) | +$0.60 |
| Case | SLA Resin ($1.50) | PA12 Nylon MJF ($3.50) | +$2.00 |
| Gasket | N/A | Silicone O-ring ($0.15) | +$0.15 |
| Acoustic membrane | N/A | Gore ePTFE ($0.30) | +$0.30 |
| USB flap | N/A | LSR silicone ($0.20) | +$0.20 |
| Button dome | N/A | Silicone cap ($0.10) | +$0.10 |
| **Total delta** | | | **+$8.97** |

### Cost Summary
| Item | Standard Seed | Outdoor Extreme |
|------|--------------|----------------|
| PCB + components | ~$12 | ~$14.42 |
| Battery | $1.50 | $5.30 (incl. heater) |
| Case + sealing | $1.50 | $4.15 |
| Conformal coating | $0 | $0.60 |
| Assembly | $3 | $4 (extra sealing steps) |
| **Total BOM** | **~$18** | **~$28.47** |
| **Target retail** | **$35 (¥5,000)** | **$65 (¥9,500)** |
| **Margin** | ~49% | ~56% |

---

## 6. Firmware Changes Required

1. **APA102C LED driver**: Replace WS2812B single-wire with SPI-based driver
   - CLK on GPIO_X, DATA on GPIO_Y (2 pins instead of 1)
   - SPI clock: 1MHz (APA102C supports up to 20MHz)
2. **Battery temperature monitoring**: Read NTC via ADC
   - Disable charge enable pin when T < 0°C
   - Trigger PTC heater when T < 5°C and USB connected
3. **Low-temperature power management**:
   - Reduce BLE TX power in extreme cold (battery capacity reduced)
   - Increase sleep current budget (DCDC less efficient at low temp)
4. **Self-test on boot**: Check battery temperature, warn user if too cold to charge

---

## 7. Testing & Certification

### Environmental Testing
- **MIL-STD-810H Method 502.7**: High Temperature (+60°C, 4hr)
- **MIL-STD-810H Method 501.7**: Low Temperature (-30°C, 4hr)
- **MIL-STD-810H Method 503.7**: Temperature Shock (-30°C to +60°C, 5 cycles)
- **IEC 60529 IP67**: Immersion test (1m, 30min)
- **Drop test**: 1.5m onto concrete at -20°C (PA12 brittleness check)

### Regulatory
- All standard certifications apply (CE, FCC, MIC/Giteki)
- Additional: IP67 test report for marketing claims
- Battery: UN38.3 transport test (required for LiPo regardless)

---

## 8. Product Label Specification

```
Koe Seed Outdoor
Model: KOE-SEED-OD
Operating: -30°C to +60°C
IP67
Auracast / BLE 5.3
[CE] [FCC] [技適]
```
