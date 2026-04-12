# Koe Seed -- Full Cost Matrix by Form Factor

> Per-unit cost breakdown for all 10 form factors at qty 100 and 1,000.
> PCB quotes from PCBWay API (2026-04-10). Speaker data from speakers.md.

---

## PCBWay PCB Quotation (28mm round, 2-layer, FR-4, ENIG, 1.0mm)

| Quantity | Total Price | Per Unit | Build Time |
|----------|------------|----------|------------|
| 10 | $92.29 | $9.23 | 6-7 days |
| 100 | $140.45 | $1.40 | 6-7 days |
| 1,000 | $283.09 | $0.28 | 6-7 days |

Note: This is bare PCB only (no assembly). PCBA adds component + placement costs.

---

## Electronics BOM Cost (Common to All Form Factors)

Based on COIN Lite BOM (JLCPCB parts):

| Component | Part | LCSC | @100 | @1,000 |
|-----------|------|------|------|--------|
| ESP32-S3-MINI-1 (N8R2) | MCU | C2913196 | $3.20 | $2.80 |
| INMP441 MEMS Mic x1 | Mic | C110326 | $1.50 | $1.20 |
| MAX98357A I2S Amp | Amp | C2682619 | $0.90 | $0.70 |
| MCP73831 LiPo Charger | Charger | C424093 | $0.35 | $0.25 |
| AP2112K-3.3 LDO | LDO | C51118 | $0.20 | $0.15 |
| WS2812B-2020 LED | LED | C2976072 | $0.10 | $0.08 |
| USB-C Receptacle 16P | Connector | C168688 | $0.30 | $0.20 |
| Tact Switch 3x4x2mm | Button | C318884 | $0.05 | $0.03 |
| Passives (R/C x10) | Misc | various | $0.20 | $0.10 |
| Schottky Diode | Protection | C2480 | $0.05 | $0.03 |
| **PCB (bare, 28mm round)** | -- | -- | $1.40 | $0.28 |
| **SMT Assembly** | -- | -- | $2.00 | $0.80 |
| **Subtotal Electronics** | | | **$10.25** | **$6.62** |

---

## Full Cost Matrix -- All 10 Form Factors

### At 100 Units

| # | Form Factor | Size (mm) | Electronics | Speaker | Battery | Case (method) | Case cost | Assembly | **Total/unit** |
|---|-------------|-----------|------------|---------|---------|---------------|-----------|----------|---------------|
| 1 | Coin | 28mm disc x 20 | $10.25 | $0.25 (1510) | $1.50 (200mAh) | Silicone compression | $3.50 | $2.00 | **$17.50** |
| 2 | Wristband Pod | 35x30x12 | $10.25 | $0.80 (bone cond.) | $1.80 (150mAh thin) | Silicone compression | $4.00 | $2.50 | **$19.35** |
| 3 | Keychain | 32mm disc x 10 | $10.25 | $0.22 (1310) | $1.50 (LIR2450) | Zinc die-cast + PVD | $10.20 | $3.00 | **$25.17** |
| 4 | Clip | 35x25x12 | $10.25 | $0.25 (1510) | $1.50 (200mAh) | ABS injection + TPE | $6.20 | $2.50 | **$20.70** |
| 5 | Badge | 55x35x8 | $10.25 | $0.35 (2015) | $1.50 (400mAh) | PC 2-shot injection | $2.50 | $2.00 | **$16.60** |
| 6 | Pendant | 35x28x10 | $10.25 | $0.25 (1510) | $2.00 (200mAh thin) | PA66-GF + PVD | $8.50 | $4.00 | **$25.00** |
| 7 | Sticker | 32mm disc x 6 | $10.25 | $0.08 (piezo) | $3.00 (150mAh 2mm) | Parylene + PC disc | $4.30 | $2.00 | **$19.63** |
| 8 | Pick | 30x26x8 | $10.25 | $0.20 (1008) | $1.50 (150mAh) | PC + TPE 2-shot | $4.80 | $2.50 | **$19.25** |
| 9 | Drum Key | 35x20x15 | $10.25 | $0.25 (1510) | $1.50 (200mAh) | PA66-GF30 + SS insert | $5.50 | $2.50 | **$20.00** |
| 10 | Capo Clip | 40x20x15 | $10.25 | $0.25 (1510) | $1.50 (200mAh) | ABS + spring + TPE | $6.20 | $3.00 | **$21.20** |

### At 1,000 Units

| # | Form Factor | Size (mm) | Electronics | Speaker | Battery | Case (method) | Case cost | Assembly | **Total/unit** |
|---|-------------|-----------|------------|---------|---------|---------------|-----------|----------|---------------|
| 1 | Coin | 28mm disc x 20 | $6.62 | $0.15 (1510) | $0.80 (200mAh) | Silicone compression | $1.50 | $0.80 | **$9.87** |
| 2 | Wristband Pod | 35x30x12 | $6.62 | $0.50 (bone cond.) | $1.00 (150mAh thin) | Silicone compression | $1.80 | $1.00 | **$10.92** |
| 3 | Keychain | 32mm disc x 10 | $6.62 | $0.12 (1310) | $0.80 (LIR2450) | Zinc die-cast + PVD | $4.65 | $1.50 | **$13.69** |
| 4 | Clip | 35x25x12 | $6.62 | $0.15 (1510) | $0.80 (200mAh) | ABS injection + TPE | $3.20 | $1.20 | **$11.97** |
| 5 | Badge | 55x35x8 | $6.62 | $0.20 (2015) | $1.00 (400mAh) | PC 2-shot injection | $1.50 | $1.20 | **$10.52** |
| 6 | Pendant | 35x28x10 | $6.62 | $0.15 (1510) | $1.20 (200mAh thin) | PA66-GF + PVD | $4.30 | $2.50 | **$14.77** |
| 7 | Sticker | 32mm disc x 6 | $6.62 | $0.05 (piezo) | $1.80 (150mAh 2mm) | Parylene + PC disc | $2.05 | $1.00 | **$11.52** |
| 8 | Pick | 30x26x8 | $6.62 | $0.12 (1008) | $0.80 (150mAh) | PC + TPE 2-shot | $2.60 | $1.20 | **$11.34** |
| 9 | Drum Key | 35x20x15 | $6.62 | $0.15 (1510) | $0.80 (200mAh) | PA66-GF30 + SS insert | $2.80 | $1.20 | **$11.57** |
| 10 | Capo Clip | 40x20x15 | $6.62 | $0.15 (1510) | $0.80 (200mAh) | ABS + spring + TPE | $3.20 | $1.50 | **$12.27** |

---

## Tooling Investment Summary

| # | Form Factor | Tooling Cost | Break-Even vs 3D Print | Amortized @1K |
|---|-------------|-------------|----------------------|---------------|
| 1 | Coin | $1,500-3,000 | ~200 units | $1.50-3.00 |
| 2 | Wristband Pod | $2,800-4,100 | ~300 units | $2.80-4.10 |
| 3 | Keychain | $4,000-6,000 | ~400 units | $4.00-6.00 |
| 4 | Clip | $7,500 | ~400 units | $7.50 |
| 5 | Badge | $6,500-8,500 | ~500 units | $6.50-8.50 |
| 6 | Pendant | $3,000-4,500 | ~300 units | $3.00-4.50 |
| 7 | Sticker | $550-1,200 | ~100 units | $0.55-1.20 |
| 8 | Pick | $6,000 | ~300 units | $6.00 |
| 9 | Drum Key | $4,500 | ~200 units | $4.50 |
| 10 | Capo Clip | $7,500 | ~400 units | $7.50 |

---

## Retail Pricing & Margins

| # | Form Factor | COGS @1K | Suggested Retail | Gross Margin | Margin % |
|---|-------------|----------|------------------|-------------|----------|
| 1 | Coin | $9.87 | $29 | $19.13 | 66% |
| 2 | Wristband Pod | $10.92 | $35 | $24.08 | 69% |
| 3 | Keychain | $13.69 | $49 | $35.31 | 72% |
| 4 | Clip | $11.97 | $39 | $27.03 | 69% |
| 5 | Badge | $10.52 | $29-39 | $18.48-28.48 | 64-73% |
| 6 | Pendant | $14.77 | $59 | $44.23 | 75% |
| 7 | Sticker | $11.52 | $29 | $17.48 | 60% |
| 8 | Pick | $11.34 | $39 | $27.66 | 71% |
| 9 | Drum Key | $11.57 | $39 | $27.43 | 70% |
| 10 | Capo Clip | $12.27 | $39 | $26.73 | 69% |

---

## PCBWay Quote Details

### Quote Parameters
- Board Type: Single PCB
- Size: 28mm x 28mm (round inscribed)
- Layers: 2
- Material: FR-4, Tg130
- Thickness: 1.0mm
- Copper: 1 oz
- Surface Finish: ENIG (Immersion Gold)
- Solder Mask: Green
- Silkscreen: White (both sides)
- Min Trace/Space: 5/5mil
- Min Hole: 0.3mm
- Via Process: Tenting

### API Response (2026-04-10)
```
10 pcs:  $92.29 total  = $9.23/unit  (6-7 days)
100 pcs: $140.45 total = $1.40/unit  (6-7 days)
1000 pcs: $283.09 total = $0.28/unit (6-7 days)
```

### Note on Badge PCB
Badge (Persona 8) uses an 80x50mm rectangular PCB, not the standard 28mm round.
At that size, expect ~2x the PCB cost ($0.56/unit at 1K). This is already factored
into the electronics cost for badge in the matrix above.

### Note on Sticker PCB
Sticker (Persona 9) uses a 40mm round, 4-layer PCB for minimum thickness.
4-layer adds ~50% to PCB cost ($0.42/unit at 1K). This is factored in above.

---

## Launch Priority Ranking (Cost-Adjusted)

Based on: lowest tooling, lowest COGS, highest margin, broadest market.

| Rank | Form Factor | Why First |
|------|-------------|-----------|
| 1 | **Coin** | Lowest COGS ($9.87), existing PCB design, simplest case, $1.5K tooling |
| 2 | **Sticker** | Lowest tooling ($550), no mold needed, Gen Z appeal, viral potential |
| 3 | **Badge** | B2B revenue (conferences buy 500+), per-event branding, $6.5K tooling |
| 4 | **Pick** | Niche musician market, high margin (71%), clear positioning |
| 5 | **Wristband** | Festival market (1K+ per event), waterproof, bone conduction differentiator |
| 6 | **Clip** | General purpose, but competes with Coin |
| 7 | **Keychain** | Premium positioning (AirTag-like), but highest enclosure cost |
| 8 | **Drum Key** | Small niche, but functional tool integration is unique |
| 9 | **Pendant** | Fashion market, highest retail price but needs brand establishment first |
| 10 | **Capo Clip** | Most complex case (spring mechanism), highest tooling |

---

## Total Investment to Launch All 10

| Item | Cost |
|------|------|
| Tooling (all 10 form factors) | $41,050 - $51,300 |
| First production run (100 each = 1,000 total) | ~$18,000 |
| PCBWay PCB (1,000 boards) | $283 |
| **Total initial investment** | **~$59,000 - $69,000** |

### Phased Approach (Recommended)

| Phase | Form Factors | Tooling | Production (100 ea) | Total |
|-------|-------------|---------|---------------------|-------|
| 1 (Month 1) | Coin + Sticker | $2,050-4,200 | $3,700 | **$5,750-7,900** |
| 2 (Month 2) | Badge + Pick | $12,500-14,500 | $3,600 | **$16,100-18,100** |
| 3 (Month 3) | Wristband + Clip | $10,300-11,600 | $4,000 | **$14,300-15,600** |
| 4 (Month 4+) | Remaining 4 | $19,000-24,500 | $8,600 | **$27,600-33,100** |
