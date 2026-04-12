# Koe Seed -- Festival & Outdoor Form Factor Manufacturing Guide

## Device Internals Reference

Based on the existing Koe COIN/Pick design:
- **PCB**: 30 x 40 mm, 1.0 mm thick (2-layer FR-4)
- **Battery**: 802535 LiPo, 8 x 25 x 35 mm, ~15g
- **Speaker**: 1510 micro speaker, 15 x 10 x 3 mm
- **Total internal stack height**: ~12-14 mm (PCB + battery + speaker + clearance)
- **Internal volume needed**: ~40 x 32 x 14 mm minimum cavity
- **Electronics BOM**: ~$23.50/unit at qty 5 (drops to ~$12-15 at qty 1,000+)

---

## Persona 1: Festival Attendee (Wristband Pod)

### Use Case
Worn on wrist at music festivals. Must survive sweat, rain, dancing, being
dropped, and stepped on. Distributed to 1,000-10,000 attendees per event.
Must be cheap enough to be semi-disposable but ideally collected and reused.

### Recommended: Silicone Compression Molding + Insert Molding

**Why not the alternatives:**

| Method | Verdict | Reason |
|--------|---------|--------|
| 3D printing (FDM/SLA) | Rejected | $3-8/unit at volume, poor waterproofing, slow, not scalable past 100 units |
| 2-shot injection molding | Overkill | Tooling $15K-25K for two molds, justified only at 50K+ units |
| TPU injection molding | Runner-up | Good flexibility but harder to achieve IP67 seal without gaskets |
| LSR (Liquid Silicone Rubber) | Too expensive | Tooling $8K-15K, per-unit cost lower than compression but MOQ higher |
| Hard plastic injection + rubber gasket | Fragile | Rigid case cracks when stepped on, gasket adds assembly step |

**Why silicone compression molding wins:**

1. **Waterproof by design** -- silicone encapsulates the PCB assembly with no seams
2. **Survives impact** -- Shore 40A-60A silicone absorbs drops and foot strikes
3. **Cheap tooling** -- compression molds cost $1,500-3,000 (vs $5K-15K for injection)
4. **Colors & glow** -- silicone takes pigment easily; phosphorescent powder for glow-in-dark
5. **Soft/comfortable on wrist** -- no hard edges, skin-safe (medical grade available)

### Design Approach

```
Cross-section (wristband pod):

  ┌────── Silicone overmold (2-3mm wall) ──────┐
  │  ┌─────────────────────────────────────┐   │
  │  │  Speaker (facing outward)           │   │
  │  ├─────────────────────────────────────┤   │
  │  │  Battery (Kapton insulated)         │   │
  │  ├─────────────────────────────────────┤   │
  │  │  PCB (30x40mm)                      │   │
  │  └─────────────────────────────────────┘   │
  │                                             │
  │   [button membrane]    [LED window]         │
  │                [USB-C port w/ silicone flap] │
  └─────────────────────────────────────────────┘
       │                                   │
       └──── wristband strap slots ────────┘
```

- Silicone body molded as one piece with strap loop slots
- USB-C port covered by integral silicone flap (IP67 when closed)
- Button actuated through thin silicone membrane (0.5mm, Shore 30A locally)
- LED visible through translucent silicone window (clear/white silicone insert)
- Speaker sound exits through molded acoustic channels (narrow slits, not holes)

### Strap Options

| Type | Cost | Pros | Cons |
|------|------|------|------|
| **Tyvek wristband** (adhesive) | $0.03-0.05 | Cheapest, fastest distribution, event branding | Single-use, not reusable |
| Silicone strap (integral) | $0.00 (molded in) | No extra part, comfortable | Adds mold complexity (+$500) |
| Velcro nylon strap | $0.15-0.30 | Adjustable, reusable | Extra assembly step |
| Snap-on silicone band | $0.10-0.20 | Easy on/off for collection | Slightly more complex mold |

**Recommendation**: Tyvek adhesive band for disposable events; integral silicone
strap for reusable/rental fleets.

### Material Specification

| Property | Value |
|----------|-------|
| Material | Silicone rubber (VMQ), Shore A 50 |
| Temperature range | -40 to +200 C (far exceeds requirement) |
| UV resistance | Excellent (inherent, no degradation) |
| Water absorption | <0.1% |
| Color options | Any Pantone, translucent, glow-in-dark (SrAl2O4 pigment) |
| Skin safety | FDA/LFGB compliant (food/skin contact grade) |
| Flammability | UL94 V-0 (self-extinguishing) |

### Tooling & Cost Breakdown

#### Tooling (One-Time)

| Item | Cost | Notes |
|------|------|-------|
| Compression mold (steel P20) | $2,000-3,000 | 2-cavity mold, ~3 week lead time |
| Mold for glow-in-dark variant | +$500 | Separate color = separate mold run (same mold) |
| Fixture for PCB positioning | $200-400 | Ensures PCB sits correctly in mold cavity |
| USB-C port plug (reusable) | $100-200 | Silicone plugs to keep port clear during molding |
| **Total tooling** | **$2,800-4,100** | |

#### Per-Unit Cost (Enclosure Only, Not Electronics)

| Volume | Silicone body | Strap | Assembly labor | Total enclosure |
|--------|--------------|-------|----------------|-----------------|
| 100 | $3.50-4.50 | $0.05 | $1.50 | **$5.00-6.00** |
| 1,000 | $1.20-1.80 | $0.04 | $0.80 | **$2.00-2.60** |
| 5,000 | $0.80-1.20 | $0.03 | $0.50 | **$1.30-1.70** |
| 10,000 | $0.60-0.90 | $0.03 | $0.35 | **$1.00-1.30** |

Notes:
- Silicone material cost is ~$8-12/kg; each pod uses ~15-20g = $0.12-0.24 material
- Main cost driver at low volume is cycle time (compression molding: 2-5 min/shot)
- At 10K, amortized tooling adds only $0.28-0.41/unit
- Glow-in-dark pigment adds $0.05-0.10/unit

#### Total Unit Cost (Electronics + Enclosure)

| Volume | Electronics | Enclosure | Total |
|--------|------------|-----------|-------|
| 100 | $18-20 | $5.50 | **$23-26** |
| 1,000 | $13-15 | $2.30 | **$15-17** |
| 5,000 | $11-13 | $1.50 | **$12-15** |
| 10,000 | $10-12 | $1.15 | **$11-13** |

### Lead Time

| Phase | Duration |
|-------|----------|
| Mold design & review | 3-5 days |
| Mold fabrication (steel P20) | 15-20 days |
| T1 samples (first shots) | 3-5 days |
| Sample approval & adjustment | 5-7 days |
| Production run (1,000 units) | 5-7 days |
| Production run (10,000 units) | 15-20 days |
| Shipping (sea, China to Japan) | 10-15 days |
| Shipping (air, China to Japan) | 3-5 days |
| **Total (first order, 1K, air)** | **~5-6 weeks** |
| **Total (reorder, 1K, air)** | **~2-3 weeks** |

### IP Rating

| Rating | Achievable? | How |
|--------|------------|-----|
| IP54 (splash-proof) | Easy | Silicone overmold alone |
| IP67 (submersible 1m/30min) | Yes, with care | Silicone overmold + USB flap + acoustic membrane over speaker |
| IP68 | Difficult | Requires potting or sealed acoustic membrane; speaker output degrades |

**Recommendation**: Target IP67. Use a thin acoustic membrane (Gore-Tex ePTFE vent,
~$0.10/unit) over the speaker port to allow sound while blocking water.

### Surface Finish & Aesthetics

| Option | Method | Added Cost |
|--------|--------|------------|
| Matte texture | Mold surface EDM texture (VDI 27-33) | $200-400 one-time |
| Glossy | Polished mold cavity | Included |
| Logo debossed | Engraved in mold | $100-200 one-time |
| Logo printed | Pad printing or screen printing | $0.03-0.08/unit |
| Glow-in-dark | SrAl2O4 pigment mixed in silicone | $0.05-0.10/unit |
| Multi-color (2-tone) | Two-shot compression or painted | $0.15-0.30/unit |

### Color Options

Silicone accepts virtually any color. Recommended festival palette:
- Neon green, hot pink, electric blue, orange, purple (high visibility)
- Translucent frost (shows LED clearly)
- Glow-in-dark green/blue (contains phosphorescent pigment)
- Custom Pantone match: $0 extra (just pigment change between runs)
- Minimum color batch: ~200 units (time to purge previous color from mold)

### Recommended Factories

| Factory/Service | Location | Specialty | MOQ | Notes |
|----------------|----------|-----------|-----|-------|
| **Shenzhen/Dongguan silicone shops** (Alibaba) | Guangdong, CN | Silicone compression/overmolding | 500 | Search "silicone overmold electronics enclosure", many factories, $2K-3K tooling |
| **Xiamen Niceone-tech** | Xiamen, CN | Silicone keypads + overmolding | 500 | Specializes in silicone over PCB, good quality |
| **Shin-Etsu / Momentive distributors** | Japan | Medical-grade silicone supply | -- | Material only, use local molder |
| **PCBWay** (injection molding service) | Shenzhen, CN | Injection + overmold | 100 | Offers silicone overmolding, integrated with PCB orders |
| **Protolabs** | US/EU/JP | Rapid silicone molding (LSR) | 25 | 3x more expensive but 1-2 week turnaround |

**Best value**: Dongguan/Shenzhen silicone mold shops via Alibaba (search
"silicone compression molding custom"). Get 3 quotes, share 3D CAD, expect
$2K-3K tooling, $1-2/unit at 1K qty. Many of these shops also do wristband
products (fitness trackers, Apple Watch bands) so they understand wearable
enclosures.

### Pros vs 3D Printing

| Metric | Silicone compression molding | 3D printing (SLA/MJF) |
|--------|-----------------------------|-----------------------|
| Unit cost at 1K | $1.50-2.50 | $5-10 |
| Unit cost at 10K | $0.80-1.30 | $4-8 (no economy of scale) |
| Waterproof | Inherent (IP67) | Requires post-processing, unreliable |
| Impact resistance | Excellent (silicone absorbs) | Poor (brittle SLA) or fair (MJF nylon) |
| Color variety | Unlimited, mixed into material | Limited, painted or dyed |
| Glow-in-dark | Easy (pigment mix) | Specialty resin, expensive |
| Lead time (first order) | 5-6 weeks | 1-2 weeks |
| Lead time (reorder) | 2-3 weeks | 1-2 weeks |
| Tooling investment | $2.8K-4.1K | $0 |
| Break-even vs 3D print | ~300-500 units | -- |

**Verdict**: 3D printing is only viable for prototyping (under 50 units) or
proof-of-concept. At festival scale (1K+), silicone compression molding is
the only sensible choice.

---

## Persona 2: Outdoor / Adventure (Carabiner Clip)

### Use Case
Clipped to backpack, belt loop, or tent guy-line by hikers, campers, climbers.
Must survive being dropped on rock, submerged in rain puddles, extreme
temperatures (-20 to +60 C), and prolonged UV exposure.

### Recommended: Glass-Filled Nylon Injection Molding + TPE Overmold

**Why not the alternatives:**

| Method | Verdict | Reason |
|--------|---------|--------|
| CNC machined aluminum | Rejected at volume | $15-30/unit even at 1K, overkill for electronics enclosure |
| Die-cast zinc alloy | Too heavy | Zinc is 7.1 g/cm3 vs nylon 1.4 g/cm3; hikers care about weight |
| Standard ABS/PC injection | Runner-up | Works but lacks impact resistance and premium feel of GF nylon |
| 3D printing (MJF nylon) | Prototype only | $8-15/unit, inconsistent surface, no overmold possible |
| Full aluminum + gasket | Premium option | See "Premium Variant" section below |

**Why glass-filled nylon + TPE overmold wins:**

1. **Strength-to-weight ratio** -- GF nylon (PA66-GF30) has tensile strength >150 MPa,
   comparable to die-cast aluminum, at 1/5 the weight
2. **Drop/impact** -- GF nylon does not shatter on rock impact (unlike ABS or PC)
3. **Temperature** -- PA66-GF30 handles -40 to +120 C continuously
4. **UV resistance** -- Carbon black or UV stabilizer added; used in automotive exteriors
5. **TPE overmold** -- Soft-touch grip zones, vibration damping, seal for IP67
6. **Cost** -- Injection molding tooling is higher than silicone but per-unit cost is low
7. **Carabiner gate** -- GF nylon is stiff enough for a spring-loaded wire gate

### Design Approach

```
Carabiner clip form factor:

         ┌─── wire gate (spring steel) ───┐
         │                                 │
    ┌────┴───────────────────────────┐     │
    │  ┌───── GF nylon body ──────┐ │     │
    │  │ Speaker (w/ ePTFE vent)  │ │     │
    │  │ Battery                  │ │     │
    │  │ PCB 30x40mm              │ │     ▼
    │  └──────────────────────────┘ │   gate
    │  [TPE grip pad] [TPE grip pad]│   hinge
    │         [LED window]          │     │
    │    [button]    [USB-C w/cap]  │     │
    └───────────────────────────────┘─────┘
              carabiner spine
```

- **Body**: 2-part clamshell, GF nylon (PA66-GF30), ultrasonic welded
- **Grip zones**: TPE (Shore A 70) overmolded on two sides
- **Carabiner spine**: Integral to body, 5mm thick GF nylon (gate load: ~5 kg working)
- **Wire gate**: 1.5mm spring steel wire, press-fit into body
- **Sealing**: Ultrasonic weld line + O-ring groove (1mm Buna-N cord)
- **USB-C**: Threaded rubber cap on tether (like Garmin/Suunto GPS units)
- **Speaker**: ePTFE acoustic vent (Gore-Tex membrane) flush-mounted
- **LED**: Polycarbonate window, ultrasonic welded or press-fit

### Material Specification

| Component | Material | Properties |
|-----------|----------|------------|
| Body shell | PA66-GF30 (e.g., DuPont Zytel 70G30) | Tensile 185 MPa, HDT 250 C, UL94 V-2 |
| Grip overmold | TPE (Santoprene 101-64 or equiv) | Shore A 65-70, chemical bonds to PA66 |
| O-ring | Buna-N (NBR) 70A, 1mm cross-section | -40 to +120 C, standard AS568 |
| Wire gate | Spring steel (AISI 302), 1.5mm dia | Fatigue-resistant, ~10K cycles |
| USB cap | Silicone rubber, Shore A 50 | Tethered to body via integral silicone cord |
| Acoustic vent | ePTFE membrane (Gore, Donaldson, or Nitto) | IP67, sound transmission >80% |
| LED window | Polycarbonate (Makrolon), 1mm thick | UV-stabilized, optically clear |
| Fasteners | 4x M2 stainless steel screws (or ultrasonic weld) | Torx T6 for field serviceability |

### Tooling & Cost Breakdown

#### Tooling (One-Time)

| Item | Cost | Notes |
|------|------|-------|
| Injection mold -- body top (GF nylon) | $3,000-4,500 | Single-cavity steel mold (P20/718H) |
| Injection mold -- body bottom (GF nylon) | $3,000-4,500 | Single-cavity steel mold |
| Overmold tool (TPE grip) | $2,000-3,000 | Insert mold, runs after body is shot |
| USB cap mold (silicone) | $500-800 | Small single-cavity |
| Wire gate bending fixture | $200-400 | Simple wire form jig |
| Assembly fixture | $300-500 | Aligns PCB + battery + speaker |
| **Total tooling** | **$9,000-13,700** | |

Note: Multi-cavity molds (2x or 4x) add 40-60% to tooling cost but halve cycle time.
Worthwhile above 5,000 units.

#### Per-Unit Cost (Enclosure Only)

| Volume | GF nylon body | TPE overmold | O-ring + gate + cap | Assembly | Total enclosure |
|--------|--------------|-------------|---------------------|----------|-----------------|
| 100 | $4.50-6.00 | $1.50-2.00 | $0.60 | $2.00 | **$8.60-10.60** |
| 500 | $2.50-3.50 | $0.80-1.20 | $0.40 | $1.20 | **$4.90-6.30** |
| 1,000 | $1.80-2.50 | $0.60-0.90 | $0.35 | $0.80 | **$3.55-4.55** |
| 2,000 | $1.40-2.00 | $0.50-0.70 | $0.30 | $0.60 | **$2.80-3.60** |
| 5,000 | $1.00-1.50 | $0.40-0.55 | $0.25 | $0.45 | **$2.10-2.75** |

Notes:
- GF nylon (PA66-GF30) pellets: ~$4-6/kg; each body half uses ~8-12g = $0.06-0.12 material
- Main cost driver: injection cycle time (~30-45 sec/shot) and assembly labor
- Ultrasonic welding (vs screws): saves $0.10-0.20/unit in fastener cost, adds $500-1K to fixture cost

#### Total Unit Cost (Electronics + Enclosure)

| Volume | Electronics | Enclosure | Total |
|--------|------------|-----------|-------|
| 100 | $18-20 | $9.50 | **$28-30** |
| 500 | $14-16 | $5.60 | **$20-22** |
| 1,000 | $13-15 | $4.00 | **$17-19** |
| 2,000 | $12-14 | $3.20 | **$15-17** |
| 5,000 | $11-13 | $2.40 | **$13-15** |

### Lead Time

| Phase | Duration |
|-------|----------|
| DFM review + mold design | 5-7 days |
| Mold fabrication (steel) | 20-30 days |
| T1 samples | 5-7 days |
| Sample approval + T2 adjustment | 7-10 days |
| Overmold tooling (can parallel) | 15-20 days |
| Production run (500 units) | 5-7 days |
| Production run (2,000 units) | 10-14 days |
| Shipping (air, China to Japan) | 3-5 days |
| **Total (first order, 1K, air)** | **~7-9 weeks** |
| **Total (reorder, 1K, air)** | **~2-3 weeks** |

### IP Rating

| Rating | Achievable? | How |
|--------|------------|-----|
| IP54 | Easy | Body clamshell with simple gasket |
| IP67 (1m/30min) | Standard target | O-ring seal + ultrasonic weld + ePTFE vent + USB cap |
| IP68 (3m/1hr) | Possible | Requires controlled ultrasonic weld + premium O-ring + torque spec on screws |

**Recommendation**: Target IP67. This matches Garmin/Suunto GPS devices and
GoPro housings -- the benchmarks for outdoor electronics.

### Surface Finish & Aesthetics

| Option | Method | Added Cost |
|--------|--------|------------|
| Fine matte texture | Mold EDM texture (VDI 24-30) | $300-500 one-time |
| Coarse "grippy" texture | Mold EDM or chemical etch (MT-11020 to MT-11040) | $300-500 one-time |
| Smooth gloss | Polished mold (SPI A-2 to A-3) | $200-400 one-time |
| Soft-touch paint | Rubber-feel coating over nylon | $0.15-0.25/unit (not recommended, wears off) |
| Laser engraving (logo) | Post-mold laser marking | $0.05-0.10/unit |
| In-mold label (IML) | Printed film insert | $0.08-0.15/unit + $500-800 tooling |

**Recommendation**: VDI 27 matte texture on nylon body (hides mold marks, premium
rugged feel). Laser-engraved logo. No paint -- it chips outdoors.

### Color Options

| Color | Method | Notes |
|-------|--------|-------|
| Black | Carbon black in PA66 compound | Best UV resistance, industry standard |
| Dark olive / forest green | Masterbatch pigment | Popular for outdoor gear |
| Slate grey | Masterbatch pigment | Neutral, hides dirt |
| Safety orange | Masterbatch pigment | High visibility for rescue/signaling |
| Earth brown (coyote) | Masterbatch pigment | Tactical/camping aesthetic |
| Custom Pantone | Custom masterbatch | $200-400 setup + 25 kg minimum (enough for 2K+ units) |

Note: GF nylon with glass fiber visible on surface -- dark colors hide fiber
streaks better than light colors. Light colors possible but may need higher
mold polish or paint.

### Premium Variant: CNC Aluminum + Anodizing

For a premium "Garmin inReach" tier product at $80-120 retail:

| Spec | Value |
|------|-------|
| Material | 6061-T6 aluminum |
| Process | CNC milling (3-axis) + anodizing Type II |
| Wall thickness | 2.0 mm |
| Finish | Bead-blasted + hard anodize (Type III, 25um) |
| Colors | Black, gunmetal, OD green (anodize dye) |
| IP67 seal | Machined O-ring groove + silicone gasket |
| Weight | ~45-55g (body only) |

| Volume | CNC body | Anodize | Assembly | Total enclosure |
|--------|---------|---------|----------|-----------------|
| 100 | $18-25 | $3-5 | $3 | **$24-33** |
| 500 | $12-18 | $2-3 | $2 | **$16-23** |
| 1,000 | $10-15 | $1.50-2.50 | $1.50 | **$13-19** |

CNC aluminum is only recommended if positioning as a premium product (>$100 retail)
or for prototyping the carabiner form before committing to injection mold tooling.

**Recommended CNC services**: PCBWay CNC, Xometry, RapidDirect, Shenzhen Kaiao

### Recommended Factories

| Factory/Service | Location | Specialty | MOQ | Notes |
|----------------|----------|-----------|-----|-------|
| **Shenzhen/Dongguan mold shops** (Alibaba) | Guangdong, CN | GF nylon injection + overmold | 500 | Search "PA66 GF30 injection molding custom", expect $3K-5K/mold |
| **PCBWay Injection Molding** | Shenzhen, CN | Integrated PCB + enclosure orders | 100 | Lower quality than dedicated mold shops but convenient one-stop |
| **RapidDirect** | Shenzhen, CN | Injection + CNC + overmold | 200 | Good DFM feedback, competitive pricing |
| **Xometry** | US/EU/JP | CNC aluminum, MJF nylon (prototypes) | 1 | 2-3x China price but fast (5-10 day) turnaround |
| **Protolabs** | US/EU/JP | Rapid injection molding | 25 | Aluminum tooling, fast (2-3 weeks) but 2-3x cost |
| **First Mold (firstmold.com)** | Dongguan, CN | Complex overmolding, consumer electronics | 500 | Known for rugged device enclosures |
| **HLH Prototypes** | Shenzhen, CN | Low-volume injection + overmold | 100 | Good English communication, established with Western startups |

**Best value (1K-5K units)**: RapidDirect or HLH Prototypes for initial run (good
DFM support, reasonable pricing). Move to a Dongguan mold shop via Alibaba for
5K+ runs to reduce per-unit cost.

### Pros vs 3D Printing

| Metric | GF Nylon injection + TPE overmold | 3D printing (MJF/SLS nylon) |
|--------|-----------------------------------|-----------------------------|
| Unit cost at 500 | $4-6 enclosure | $10-15 enclosure |
| Unit cost at 2K | $3-4 enclosure | $8-12 (no economy of scale) |
| Impact strength | Excellent (GF nylon + TPE) | Fair (MJF nylon is brittle at -20 C) |
| IP67 waterproof | Standard (O-ring + weld) | Very difficult (porous material) |
| Overmold grip | Yes (TPE chemically bonds) | No (must glue rubber separately) |
| Temperature range | -40 to +120 C | -40 to +80 C (MJF PA12) |
| UV resistance | Excellent (with UV stabilizer) | Poor (PA12 yellows, degrades) |
| Surface finish | Mold texture, consistent | Grainy, requires post-process |
| Lead time (first) | 7-9 weeks | 1-2 weeks |
| Tooling | $9K-14K | $0 |
| Break-even vs 3D | ~200-300 units | -- |
| Carabiner function | Wire gate, proper spring | Weak, snaps under load |

**Verdict**: 3D print 10-20 units for design validation and user testing. Once
the form factor is locked, invest in injection mold tooling. Break-even at
~250 units, after which injection is cheaper, stronger, and waterproof.

---

## Manufacturing Decision Matrix

| Factor | Festival (Wristband) | Outdoor (Carabiner) |
|--------|---------------------|---------------------|
| **Process** | Silicone compression molding | GF nylon injection + TPE overmold |
| **Material** | Silicone VMQ Shore 50A | PA66-GF30 + TPE Shore 70A |
| **Tooling** | $2.8K-4.1K | $9K-14K |
| **Unit cost @ 1K** | $2.00-2.60 | $3.55-4.55 |
| **Lead time (first)** | 5-6 weeks | 7-9 weeks |
| **MOQ** | 500 | 200-500 |
| **IP rating** | IP67 | IP67 |
| **Break-even vs 3D print** | ~300-500 units | ~200-300 units |
| **Key advantage** | Cheap, waterproof, soft, colorful | Rugged, premium, functional clip |

## Prototyping Strategy (Before Tooling Investment)

### Phase 1: Form Factor Validation (2-4 weeks, $200-500)

1. **3D print** 5-10 enclosures (SLA resin for wristband, MJF nylon for carabiner)
2. Hand-assemble with real PCBs and batteries
3. User test at a small event (100 people) or with hiking group
4. Iterate on dimensions, button placement, LED visibility, strap attachment

### Phase 2: Material Validation (2-3 weeks, $500-1,000)

1. **Wristband**: Order silicone rubber samples from 2-3 Alibaba suppliers.
   Have them make simple test blocks in target Shore hardness + colors.
2. **Carabiner**: Order GF nylon test bars. Drop test, UV exposure test (1 week
   outdoor), temperature cycling.
3. Test IP67: submerge 3D printed prototypes with silicone sealant applied.

### Phase 3: Soft Tooling (4-6 weeks, $1K-3K)

1. **Wristband**: Aluminum compression mold (soft tool, 500-shot life).
   Run 50-100 units. Full event trial.
2. **Carabiner**: Aluminum injection mold via Protolabs or PCBWay.
   Run 25-50 units. Field testing with 10 hikers for 1 month.

### Phase 4: Production Tooling (see lead times above)

Commit to steel molds only after Phase 3 validation. Steel molds last
50K-100K+ shots.

---

## Appendix: Key Suppliers & Contact Points

### Silicone (Festival Wristband)
- **Material**: Shin-Etsu KE-951-U (general purpose), Dow Corning QP1-40 (medical grade)
- **Glow pigment**: Honeywell Lumilux SN-F50 (strontium aluminate, 8+ hr glow)
- **ePTFE vent**: Donaldson Tetratex, Nitto NTF-1122 (acoustic grade)
- **Alibaba search**: "custom silicone overmold electronics" + "silicone wristband manufacturer"

### GF Nylon (Outdoor Carabiner)
- **Material**: DuPont Zytel 70G30HSL (heat-stabilized, lubricated), BASF Ultramid A3WG6
- **TPE**: Kraiburg TPE TF5AAZ (bonds to PA66 without primer)
- **O-ring**: Parker 2-010 N70 (standard, 0.239" ID x 0.070" CS) or metric equivalent
- **Wire gate**: Sandvik 302 stainless spring wire, 1.5mm, order from Misumi or RS Components
- **Alibaba search**: "PA66 GF30 injection molding rugged enclosure" + "2K overmold TPE nylon"
