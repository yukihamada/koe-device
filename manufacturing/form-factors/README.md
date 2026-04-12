# Koe Seed — Form Factor Manufacturing Matrix

> Complete guide to all 9 personas across festival, musician, premium, and everyday categories.
> Each persona document contains detailed material specs, tooling costs, per-unit pricing at multiple volumes, factory recommendations, and packaging guidance.

## Documents

| File | Personas | Category |
|------|----------|----------|
| [`festival-outdoor.md`](festival-outdoor.md) | 1, 2 | Festival & Outdoor |
| [`musician.md`](musician.md) | 3, 4, 5 | Musician instruments |
| [`premium-everyday.md`](premium-everyday.md) | 6, 7, 8, 9 | Premium & Everyday |

---

## Full Persona Matrix

| # | Persona | Form Factor | Size (mm) | Weight | Material | Process | IP |
|---|---------|-------------|-----------|--------|----------|---------|-----|
| 1 | Festival Attendee | Wristband pod | 44x36x18 | 30g | Silicone (Shore 50A) | Compression molding | IP67 |
| 2 | Outdoor / Adventure | Carabiner clip | 90x45x18 | 40g | PA66-GF30 + TPE overmold | Injection + overmold | IP67 |
| 3 | Guitarist | Guitar pick shape | 40x35x10 | 25g | Polycarbonate + TPE grip | 2-shot injection | IP43 |
| 4 | Drummer | Drum key / T-shape | 70x40x15 | 35g | PA66-GF30 + SS insert | Insert injection | IP43 |
| 5 | General Musician | Capo / universal clip | 65x30x15 | 30g | ABS + spring + TPE pads | Multi-part injection | IP43 |
| 6 | EDC / Tech Enthusiast | Keychain (AirTag style) | 32mm dia x 9 | 15g | Zinc alloy + PVD coating | Die-cast | IP54 |
| 7A | Fashion (Standard) | Pendant (pebble) | 30x38x9 | 12g | PA66-GF + ceramic PVD | Injection + PVD | IP43 |
| 7B | Fashion (Limited) | Pendant (pebble) | 30x38x9 | 22g | Brass, lost-wax cast | Investment casting | IP42 |
| 8 | Corporate / Conference | Badge (name tag) | 85x55x7 | 28g | PC + PC/ABS | 2-shot injection | IP43 |
| 9 | Ultra-Minimalist / Gen Z | Sticker (ultra-thin) | 40mm dia x 5 | 8g | PCB + Parylene C + PC disc | Conformal coating | IP67* |

*Parylene C provides molecular-level moisture barrier, though not formally IP-rated in the traditional enclosure sense.

---

## Cost Comparison (All Personas @ 1,000 Units)

| # | Persona | Enclosure Cost | Electronics Cost | Total Unit Cost | Tooling Investment |
|---|---------|----------------|------------------|-----------------|-------------------|
| 1 | Festival Wristband | $1.50-2.50 | $13-15 | **$15-18** | $1,500-3,000 |
| 2 | Outdoor Carabiner | $3.55-4.55 | $13-15 | **$17-19** | $9,000-13,700 |
| 3 | Guitar Pick | $2.60 | $10 | **$12.60** | $6,000 |
| 4 | Drum Key | $2.80 | $10 | **$12.80** | $4,500 |
| 5 | Universal Clip | $3.20 | $10 | **$13.20** | $7,500 |
| 6 | EDC Keychain | $4.65 | $10.30 | **$16.45** | $4,000-6,000 |
| 7A | Fashion Pendant | $4.30 | $11.20 | **$18.80** | $3,000-4,500 |
| 7B | Fashion Brass | $13.00 | $11.00 | **$27.00** | $300-600 |
| 8 | Corporate Badge | $1.50 | $10.20 | **$12.90** | $6,500-8,500 |
| 9 | Ultra-thin Sticker | $2.05 | $9.80 | **$12.85** | $550-1,200 |

---

## Tooling Investment vs Volume Break-Even

| Persona | Tooling | Break-Even vs 3D Print |
|---------|---------|----------------------|
| 1. Festival | $1.5K-3K | ~200-300 units |
| 2. Outdoor | $9K-14K | ~500-800 units |
| 3. Guitar Pick | $6K | ~300 units |
| 4. Drum Key | $4.5K | ~200 units |
| 5. Universal Clip | $7.5K | ~300 units |
| 6. EDC Keychain | $4K-6K | ~400 units |
| 7A. Fashion | $3K-4.5K | ~300 units |
| 7B. Fashion Brass | $300-600 | 50 units (minimal tooling) |
| 8. Corporate Badge | $6.5K-8.5K | ~500 units |
| 9. Sticker | $550-1.2K | ~100 units (minimal tooling) |

---

## Lead Time Summary

| Persona | First Order | Reorder |
|---------|-------------|---------|
| 1. Festival | 5-6 weeks | 2-3 weeks |
| 2. Outdoor | 7-9 weeks | 2-3 weeks |
| 3. Guitar Pick | 6-8 weeks | 2-3 weeks |
| 4. Drum Key | 5-7 weeks | 2-3 weeks |
| 5. Universal Clip | 6-8 weeks | 2-3 weeks |
| 6. EDC Keychain | 6-8 weeks | 2-3 weeks |
| 7A. Fashion | 6-7 weeks | 2-3 weeks |
| 7B. Fashion Brass | 5-6 weeks | 3-4 weeks |
| 8. Corporate Badge | 6-8 weeks | 2-3 weeks |
| 9. Sticker | 4-5 weeks | 2-3 weeks |

---

## Shared Electronics Platform

All personas share the same core electronics with minor variations:

| Component | Personas 1-7A, 8 | Persona 7B | Persona 9 |
|-----------|-------------------|------------|-----------|
| MCU | ESP32-S3-MINI-1 (N8R2) | ESP32-S3-MINI-1 | ESP32-C3-MINI-1 (smaller) |
| Mic | INMP441 x1-2 | INMP441 x1 | INMP441 x1 |
| Amp | MAX98357A | None | None |
| LED | WS2812B-2020 | WS2812B-2020 | WS2812B-2020 |
| Charger | MCP73831 | MCP73831 | MCP73831 |
| LDO | AP2112K-3.3 | AP2112K-3.3 | AP2112K-3.3 |
| PCB base | COIN Lite (26mm round) | Custom oval | Custom 40mm round |

### PCB Variants Needed

| PCB | Diameter/Size | Layers | Used By |
|-----|---------------|--------|---------|
| COIN Lite (existing) | 26mm round | 2 | Personas 1, 2, 3, 4, 5, 6 |
| Pendant (new) | 25x35mm oval | 2 | Persona 7 |
| Badge (new) | 80x50mm rect | 2 | Persona 8 |
| Sticker (new) | 40mm round | 4 | Persona 9 |

---

## Recommended Launch Sequence

### Phase 1: Lowest Risk (Month 1-2)
**Persona 9 (Sticker) + Persona 7B (Brass Pendant)**
- Combined tooling: < $2,000
- MOQ: 100 stickers + 50 pendants
- Purpose: Market test, build brand, social media content
- Revenue target: $5K-10K (direct sales)

### Phase 2: Core Products (Month 3-4)
**Persona 6 (EDC Keychain) + Persona 3 (Guitar Pick)**
- Combined tooling: $10K-12K
- MOQ: 500 each
- Purpose: Main consumer product line
- Revenue target: $30K-50K

### Phase 3: B2B + Events (Month 5-6)
**Persona 8 (Corporate Badge) + Persona 1 (Festival Wristband)**
- Combined tooling: $8K-12K
- MOQ: 500 badges, 1000 wristbands
- Purpose: B2B sales (conference organizers, festival promoters)
- Revenue target: $50K-100K per event

### Phase 4: Full Lineup (Month 7+)
**Remaining personas (2, 4, 5, 7A)**
- Purpose: Complete the product line after market validation
- Only invest in tooling for personas with proven demand

---

## Factory Consolidation Strategy

For cost efficiency, source multiple personas from the same factory cluster:

| Factory Type | Personas | Location |
|--------------|----------|----------|
| JLCPCB / PCBWay (PCB + PCBA) | All | Shenzhen |
| Injection molder (multi-material) | 1, 2, 3, 5, 6, 8 | Dongguan/Shenzhen |
| Die-cast + PVD shop | 6 | Shenzhen |
| Jewelry caster | 7B | Shenzhen / Panyu (jewelry district) |
| Conformal coating (Parylene) | 9 | Shenzhen |
| Silicone compression molder | 1 | Shenzhen |

Consolidating injection molding work to a single factory (e.g., Star Rapid, ICOMold, or HLH Prototypes) enables volume discounts on tooling and shared material purchases.

---

## Retail Pricing Strategy

| Persona | COGS @1K | Suggested Retail | Margin | Channel |
|---------|----------|------------------|--------|---------|
| 1. Festival | $17 | $35-45 | 2-2.5x | B2B (event organizer buys in bulk) |
| 2. Outdoor | $18 | $49-59 | 2.7-3.3x | Amazon, outdoor retailers |
| 3. Guitar Pick | $13 | $39 | 3x | Music stores, direct |
| 4. Drum Key | $13 | $39 | 3x | Music stores, direct |
| 5. Universal Clip | $13 | $39 | 3x | Music stores, direct |
| 6. EDC Keychain | $16 | $49 | 3x | Direct, tech accessories |
| 7A. Fashion | $19 | $59-69 | 3-3.6x | Fashion boutiques, direct |
| 7B. Fashion Brass | $27 | $89-129 | 3.3-4.8x | Limited drops, direct |
| 8. Corporate Badge | $13 | $29-39 | 2.2-3x | B2B (conference organizers) |
| 9. Sticker | $13 | $29-35 | 2.2-2.7x | Direct, phone accessory market |
