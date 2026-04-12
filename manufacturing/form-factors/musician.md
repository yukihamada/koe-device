# Koe Seed — Musician Form Factors: Manufacturing Guide

> PCB: ESP32-S3-MINI-1 + INMP441 + MAX98357A, 26mm round / 25x30mm rectangular
> Reference: existing pick-case.scad (38x42x13mm), COIN Lite BOM ~$17/unit

---

## Persona 3: Guitarist (ギタリスト) — Guitar Pick Shape

### Design Constraints
- Dimensions: ~40 x 35 x 10mm (oversized pick, Dunlop Big Stubby scale)
- Must feel natural between thumb and index finger
- Rounded tip (not sharp — houses PCB, not for strumming)
- Grip zone on both faces (thumb pad + finger pad)
- Weight target: 20-30g (heavier than a pick, lighter than a phone)

### Recommended: Injection Molded Polycarbonate + Overmold TPE Grip

**Why this wins:**
- Polycarbonate (PC) is what premium picks (Dunlop Stubby) use — familiar feel to guitarists
- Translucent options available (amber, smoke, clear) — shows PCB/LED glow through
- Overmolded TPE (thermoplastic elastomer) grip zones prevent slipping during sweaty performances
- Excellent impact resistance — survives drops onto stage floors

**Process:** 2-shot injection molding (PC body + TPE grip pads)

| Volume | Tooling | Unit Cost | Total | Lead Time |
|--------|---------|-----------|-------|-----------|
| 100 | $6,000 (2 molds) | $4.80 | $6,480 | 6-8 weeks |
| 500 | $6,000 | $3.20 | $7,600 | 6-8 weeks |
| 1,000 | $6,000 | $2.60 | $8,600 | 6-8 weeks |
| 5,000 | $6,000 | $1.90 | $15,500 | 8-10 weeks |

**MOQ:** 500 (most Chinese injection molders, 2-shot)

### Alternative Options Evaluated

| Method | Pros | Cons | Unit @ 1K |
|--------|------|------|-----------|
| **CNC Delrin/Acetal** | Ultra-smooth, premium, no tooling | Expensive per-unit, no translucency | $12-18 |
| **Injection ABS + soft-touch paint** | Cheaper tooling ($3K single mold) | Paint wears off with heavy use, 2 processes | $2.80 |
| **CNC Polycarbonate** | No tooling, translucent | Expensive, tool marks need polish | $15-25 |
| **Overmold (rigid + full rubber)** | Maximum grip | Hides LED, looks rubbery not premium | $3.50 |

### 3D Print Comparison (Break-Even Analysis)

| Method | Unit Cost | Break-Even vs Injection |
|--------|-----------|------------------------|
| **SLA Resin (JLCPCB)** | $3.50 | Injection wins at ~300 units |
| **MJF Nylon (PA12)** | $5.00 | Injection wins at ~200 units |
| **SLS Nylon + dye** | $6.50 | Injection wins at ~150 units |

**Verdict:** At 500+ units, injection molding is clearly cheaper. Below 200, use SLA/MJF for prototyping and early adopter batches.

### Surface Finish Specification
- **Body:** SPI-A2 polish (mirror-like for translucent areas) or SPI-B1 semi-gloss
- **Grip zones:** MT-11010 texture (fine sandblast, similar to Dunlop Max Grip)
- **Colors:** Amber translucent, Smoke translucent, Matte black opaque, Pearl white
- **Logo:** Laser-etched "Koe" on grip face, 2mm depth relief

### Special Considerations
- **LED light pipe:** Translucent PC body acts as its own light pipe — LED visible through shell
- **Non-slip:** TPE durometer Shore 50A-60A (soft enough for grip, firm enough for durability)
- **Sweat resistance:** TPE is inherently hydrophobic; PC doesn't absorb moisture
- **Pick holder integration:** Consider a small slot/groove on the edge to hold an actual guitar pick (marketing hook: "your pick holds your picks")
- **Lanyard hole:** 2mm hole at the wide end for clip attachment to strap

### Factory Recommendations
1. **JLCPCB 3D Printing** — Prototypes and <200 units (SLA 8001 Resin)
2. **Protolabs (protolabs.com)** — Low-volume injection (100-1000), fast turnaround, US/EU
3. **Star Rapid (starrapid.com)** — 2-shot overmolding specialty, Zhongshan China
4. **ICOMold (icomold.com)** — Budget injection, $2-5K tooling, Shenzhen
5. **HLH Prototypes (hlhprototypes.com)** — PC + TPE overmold experience, Shenzhen

---

## Persona 4: Drummer (ドラマー) — Drum Key / T-Shape

### Design Constraints
- Dimensions: T-shape, ~70mm tall x 40mm wide x 15mm thick (handle section)
- Must survive constant vibration (mounted on drum hardware)
- Integrated drum key socket (standard 1/4" square) at top of T — functional tool
- Clip or threaded mount to attach to hi-hat stand, floor tom leg, or cymbal stand tube (22-28mm diameter)
- Weight: 40-60g acceptable (drummers don't hold this — it's mounted)

### Recommended: Glass-Filled Nylon (PA66-GF30) Injection Molding + Stainless Steel Insert

**Why this wins:**
- PA66-GF30 has excellent vibration damping (better than aluminum for electronics)
- Metal-like appearance and rigidity without metal weight or conductivity issues
- Stainless steel threaded insert for the drum key socket (press-fit during molding)
- 10x cheaper than CNC aluminum at volume
- Impact resistance: survives being knocked by drumsticks

**Process:** Single-shot injection molding + ultrasonic insert (M6 threaded + 1/4" square socket)

| Volume | Tooling | Unit Cost | Total | Lead Time |
|--------|---------|-----------|-------|-----------|
| 100 | $4,500 (1 mold) | $5.50 | $5,050 | 5-7 weeks |
| 200 | $4,500 | $4.80 | $5,460 | 5-7 weeks |
| 500 | $4,500 | $3.50 | $6,250 | 5-7 weeks |
| 1,000 | $4,500 | $2.80 | $7,300 | 6-8 weeks |

**MOQ:** 200 (single-shot mold, simpler than 2-shot)

### Alternative Options Evaluated

| Method | Pros | Cons | Unit @ 500 |
|--------|------|------|------------|
| **CNC Aluminum + hard anodize** | Premium metal feel, heat dissipation | $25-40/unit, resonates vibration to PCB | $30 |
| **Zinc die-cast + chrome** | Heavy/premium, complex shapes | Tooling $8-15K, MOQ 1000+, heavy (80g+) | $4.50 |
| **Metal Injection Molding (MIM)** | Complex metal geometry | Tooling $15-25K, MOQ 5000+, overkill | $3.00 |
| **CNC Delrin + metal insert** | Vibration-dampening, no tooling | $18-25/unit, not "industrial" looking | $22 |

### 3D Print Comparison (Break-Even Analysis)

| Method | Unit Cost | Break-Even vs Injection |
|--------|-----------|------------------------|
| **MJF PA12 (HP)** | $7.00 | Injection wins at ~250 units |
| **MJF PA12-GF (glass-filled)** | $9.00 | Injection wins at ~180 units |
| **SLA Tough Resin** | $6.00 | Injection wins at ~300 units |
| **SLS PA11** | $8.00 | Injection wins at ~200 units |

**Verdict:** At 200+ units, injection is cost-effective. For initial 50-100 drummer beta testers, MJF PA12-GF is the best 3D print option (closest mechanical properties to PA66-GF30).

### Surface Finish Specification
- **Body:** VDI 27 texture (fine stipple, industrial/tool-like appearance)
- **Grip area (handle):** VDI 33 texture (medium stipple, non-slip even with sweaty hands)
- **Color:** Matte black (RAL 9005) — default stage gear color, doesn't reflect stage lights
- **Optional:** Gunmetal grey (RAL 7024) for "metal look" without actual metal
- **Logo:** Debossed "Koe" on handle face, filled with white paint

### Special Considerations
- **Vibration isolation:** Add 1mm silicone gasket between PCB mounting and case walls. PA66-GF30 dampens significantly better than aluminum
- **Drum key functionality:** Standard 1/4" (6.35mm) square socket at T-top. Stainless steel 304 insert, press-fit. This makes the device a functional drum key — drummers will carry it because it's useful
- **Mounting clamp:** Integrated spring clamp for 22-28mm tubes (standard drum hardware). Use a separate stainless steel C-clamp insert, attached via M3 screw
- **Cable routing:** If wired USB-C charging is needed, route the port away from the clamp side. Consider wireless Qi charging to eliminate ports entirely (vibration can loosen USB-C)
- **Stage lighting:** Matte finish prevents reflections. LED should be visible but not blinding — use a 1mm translucent window, not full transparency
- **Resonance testing:** Verify at 80-500Hz range (kick drum fundamental frequencies). PA66-GF30's loss factor is ~0.04, adequate but add internal foam if needed

### Factory Recommendations
1. **JLCPCB 3D Printing** — Prototypes (MJF PA12 available on JLCPCB)
2. **Xometry (xometry.com)** — Instant quote, MJF and injection, good for 100-500 range
3. **Firstpart (firstpart.com)** — PA66-GF injection specialty, Shenzhen, good with inserts
4. **Fictiv (fictiv.com)** — Managed manufacturing, quality inspection included, US-managed China production
5. **RapidDirect (rapiddirect.com)** — Budget injection + insert molding, Shenzhen

---

## Persona 5: General Musician (汎用) — Capo/Universal Clip

### Design Constraints
- Dimensions: ~80mm x 30mm x 20mm (closed), opens to ~50mm jaw
- Spring-loaded jaw clamps onto: mic stands (20-25mm), music stands (2-10mm), guitar necks (40-50mm), cymbal stands, keyboard edges
- One-hand operation: squeeze to open, release to clamp (like a capo or spring clamp)
- Must not scratch instruments — rubber/silicone jaw pads
- Weight target: 35-50g

### Recommended: Injection Molded ABS Body + Spring Steel Clip + Overmolded TPE Jaw Pads

**Why this wins:**
- Same proven construction as guitar capos (Kyser, Shubb spring-style)
- ABS body is light, rigid, and takes matte finishes well
- Spring steel torsion spring provides consistent clamping force (~2-3 lbs)
- TPE overmold on jaw faces protects instruments from scratching
- Tooling cost is moderate because the mechanism is well-understood

**Process:** ABS injection molding (2 halves) + spring steel insert + TPE overmold on jaw faces

| Volume | Tooling | Unit Cost | Total | Lead Time |
|--------|---------|-----------|-------|-----------|
| 100 | $7,500 (2 molds + spring tooling) | $6.20 | $8,120 | 7-9 weeks |
| 500 | $7,500 | $4.00 | $9,500 | 7-9 weeks |
| 1,000 | $7,500 | $3.20 | $10,700 | 7-9 weeks |
| 2,000 | $7,500 | $2.60 | $12,700 | 8-10 weeks |
| 5,000 | $7,500 | $2.10 | $18,000 | 10-12 weeks |

**MOQ:** 500 (multi-component assembly requires minimum run)

### Alternative Options Evaluated

| Method | Pros | Cons | Unit @ 1K |
|--------|------|------|-----------|
| **All-metal CNC + laser engrave** | Ultra-premium, durable | Heavy (100g+), expensive, cold to touch | $25-35 |
| **2K injection (rigid + spring)** | Single molding step | Plastic spring fatigues over time, limited force | $3.80 |
| **Die-cast zinc + rubber pads** | Heavy/premium feel | Tooling $12K+, heavy, overkill | $4.00 |
| **CNC aluminum + spring** | Premium, light | $20+ per unit, no texture options | $22 |

### 3D Print Comparison (Break-Even Analysis)

| Method | Unit Cost | Break-Even vs Injection |
|--------|-----------|------------------------|
| **MJF PA12** | $8.50 | Injection wins at ~400 units |
| **SLA Tough Resin** | $7.00 | Injection wins at ~500 units (resin is brittle for springs) |
| **SLS PA11** | $9.00 | Injection wins at ~350 units |
| **FDM PETG (DIY)** | $3.00 | Injection wins at ~600 units (but FDM quality is poor) |

**Note:** 3D printed clips have a durability problem — the hinge/spring area fatigues. For prototyping, use a metal torsion spring with 3D printed jaws. Never 3D print the spring mechanism.

**Verdict:** At 500+ units, injection is clearly superior. Below 300, use MJF PA12 bodies + off-the-shelf torsion springs + silicone pads (manual assembly).

### Surface Finish Specification
- **Body:** SPI-C1 matte (industry standard for pro audio/stage gear)
- **Jaw pads:** TPE Shore 40A, micro-ridged texture (grips without marring)
- **Color:** Matte black (primary), with optional accent ring in brand color
- **Logo:** Pad-printed "Koe" on body side, white on black
- **Spring:** Black oxide coating on spring steel (prevents rust, matches aesthetic)

### Special Considerations
- **Jaw range:** Design for 2mm (music stand edge) to 50mm (guitar neck). Use asymmetric jaws — one flat (for thin edges), one curved (for round tubes). This is how high-end capos work
- **Instrument protection:** TPE durometer Shore 40A maximum. Too hard = scratches finishes. Too soft = slips. Test on nitrocellulose lacquer (most scratch-prone guitar finish)
- **Stage lighting:** Matte black ABS absorbs light — no reflections on stage. LED window should face the musician, not the audience
- **Quick-release:** Spring tension should allow one-hand clamp/release. Target: 2 lbs clamping force (enough to hold 50g device, not enough to damage guitar necks)
- **Cable management:** Consider an integrated USB-C cable clip/channel on the body to route charging cable cleanly along a mic stand
- **Rotation:** Allow the device body to rotate on the clamp jaw (ball joint or friction hinge) so the mic/speaker always faces the right direction regardless of mount orientation
- **Compatibility testing:** Verify on Shure SM58 (23mm), K&M music stand (8mm flat), Fender guitar neck (43mm at nut), Pearl cymbal stand (22mm), Roland keyboard edge (15mm)

### Factory Recommendations
1. **JLCPCB 3D Printing** — Prototype bodies only (springs must be metal)
2. **Protolabs** — Best for 100-500 units, handles multi-component assembly
3. **ICOMold** — Budget ABS injection, good for 500+ runs, Shenzhen
4. **Star Rapid** — Overmolding + insert molding in one factory, Zhongshan
5. **Fictiv** — Managed production, handles sourcing torsion springs + assembly
6. **AliExpress spring suppliers** — Source standard torsion springs (wire dia 0.8-1.0mm, 180-degree, 15mm leg) for prototypes: ~$0.10/pc

---

## Cross-Persona Comparison

### Cost Summary (Enclosure Only, Excluding PCB/Electronics)

| Persona | Method | Tooling | Unit @100 | Unit @500 | Unit @1K | Unit @5K |
|---------|--------|---------|-----------|-----------|----------|----------|
| **3: Guitarist** | PC + TPE overmold | $6,000 | $4.80 | $3.20 | $2.60 | $1.90 |
| **4: Drummer** | PA66-GF30 + SS insert | $4,500 | $5.50 | $3.50 | $2.80 | — |
| **5: Clip** | ABS + spring + TPE | $7,500 | $6.20 | $4.00 | $3.20 | $2.10 |

### Total Device Cost (Enclosure + COIN Lite PCB Assembly)

Using COIN Lite electronics at ~$10/unit (BOM at 1K volume):

| Persona | Unit @500 | Unit @1K | Retail Price (3x margin) |
|---------|-----------|----------|--------------------------|
| **3: Guitarist** | $13.20 | $12.60 | $39 / 4,900 |
| **4: Drummer** | $13.50 | $12.80 | $39 / 4,900 |
| **5: Clip** | $14.00 | $13.20 | $39 / 4,900 |

### Phased Manufacturing Strategy

#### Phase 1: Prototype (Month 1-2) — 50 units each
- **All personas:** 3D print enclosures (JLCPCB SLA/MJF)
- **Guitarist:** SLA Resin translucent, $3.50/unit
- **Drummer:** MJF PA12-GF black, $9.00/unit + off-shelf SS drum key insert
- **Clip:** MJF PA12 black, $8.50/unit + off-shelf torsion spring + silicone pads
- **Total enclosure cost:** ~$1,050 for 150 units
- **Purpose:** Beta tester feedback, ergonomic validation

#### Phase 2: Pilot (Month 3-4) — 200-500 units
- **Guitarist:** Soft-tool injection (aluminum mold, 1000-shot life), $2,500 tooling
- **Drummer:** Soft-tool injection, $2,000 tooling
- **Clip:** Soft-tool injection + purchased springs, $3,000 tooling
- **Total tooling:** ~$7,500
- **Purpose:** Early sales, crowdfunding fulfillment

#### Phase 3: Production (Month 5+) — 1,000+ units
- **All personas:** Steel molds (50K+ shot life), full overmolding
- **Total tooling:** ~$18,000
- **Purpose:** Retail/distribution scale

### Shared Tooling Opportunities
- **TPE grip compound:** Same TPE (Shore 50A, black) across Guitarist and Clip personas — buy in bulk
- **PCB:** Single COIN Lite PCB design fits all three enclosures (26mm round)
- **USB-C gasket:** Same silicone port gasket across all three
- **Packaging:** Unified box design with persona-specific inserts

---

## Material Quick Reference

| Material | Density | Tensile | Impact | Translucent | Cost/kg | Best For |
|----------|---------|---------|--------|-------------|---------|----------|
| PC (Polycarbonate) | 1.20 | 65 MPa | Excellent | Yes | $3.50 | Guitarist |
| PA66-GF30 | 1.37 | 130 MPa | Good | No | $4.00 | Drummer |
| ABS | 1.04 | 45 MPa | Good | No | $2.00 | Clip body |
| TPE Shore 50A | 1.15 | 8 MPa | Excellent | No | $5.00 | Grip pads |
| Delrin/Acetal | 1.41 | 70 MPa | Good | No | $6.00 | CNC alt |
| Spring Steel (301) | 7.90 | 1000 MPa | N/A | No | $2.50 | Clip spring |
| SUS304 Insert | 8.00 | 515 MPa | N/A | No | $8.00 | Drum key socket |

---

## Risk Mitigation

| Risk | Persona | Mitigation |
|------|---------|------------|
| TPE delamination from PC | Guitarist | Use PC/TPE chemically compatible grades (Covestro Makrolon + Kraiburg TPE) |
| Vibration loosens PCB | Drummer | Conformal coating on solder joints + silicone potting on connectors |
| Spring fatigue | Clip | Specify 50K cycle minimum; use music wire (ASTM A228), not cheap carbon steel |
| Instrument scratching | Clip | Shore 40A maximum on jaw pads; test on nitrocellulose before production |
| Drop damage | All | 1.5m drop test onto concrete, 6 faces, 3 samples each |
| Sweat corrosion | Guitarist | No exposed metal; conformal coat PCB; TPE is inherently resistant |
| USB-C port stress | Drummer (vibration) | Consider magnetic pogo-pin charging or Qi wireless to eliminate port |
