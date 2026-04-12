# Koe Seed — Premium & Everyday Form Factors

> Manufacturing analysis for Personas 6-9.
> PCB baseline: ESP32-S3-MINI-1, INMP441 mic, WS2812B LED, MCP73831 charger, USB-C.
> Reference PCB: COIN Lite (26mm diameter, 2-layer) or custom flex PCB where needed.

---

## Persona 6: Everyday Carry / Tech Enthusiast (日常使い・テック好き)

**Form: Keychain (AirTag style)**
- Target size: 32mm diameter x 8-9mm thick (AirTag = 31.9mm x 8mm)
- Weight: < 15g
- Quantity: 1,000 - 10,000

### What Apple Actually Uses for AirTag

Apple AirTag construction:
- **Body**: 304L stainless steel (CNC machined + mirror polish)
- **Back cap**: Injection-molded polycarbonate (white, removable for battery)
- **Front logo**: Chrome-plated stainless with laser-etched Apple logo
- **Sealing**: IPX4 (splash-proof), ultrasonic-welded internal gaskets
- **Apple's unit cost**: Estimated $5-8 at 100M+ volume (custom tooling fully amortized)
- **Retail**: $29

At 1K-10K volume, true stainless steel CNC + mirror polish = $8-15/unit for the shell alone.
Approximating the AirTag feel at $3-5/unit requires compromises.

### Recommended: Zinc Alloy Die-Cast + PVD Coating

This is how most "premium" consumer electronics accessories (watch cases, earphone housings, high-end keychains) achieve a metal feel at volume.

**Why zinc alloy over stainless steel:**
- Die-casting is 5-10x cheaper than CNC at 1K+ volumes
- Zamak 3 (zinc alloy) takes PVD coating beautifully — indistinguishable from stainless by touch
- Weight is similar to stainless (7.0 vs 7.9 g/cm3), giving a premium heft
- Complex geometries in a single shot (keyring loop, internal standoffs, snap features)

**Process flow:**
1. Zinc alloy die-cast (top shell + bottom shell)
2. CNC trim flash / parting lines (automated)
3. Vibratory tumble (deburr)
4. PVD sputtering: stainless-look silver, gunmetal, matte black, or gold
5. Laser-etch logo (through PVD layer = contrasting reveal)
6. Polycarbonate light-pipe insert (press-fit, for LED)
7. Silicone gasket (IP54)

**Alternative considered: Machined aluminum + anodize**
- Pro: Lighter (2.7 g/cm3), easier to machine, mature anodizing supply chain
- Con: Feels less premium than zinc-PVD at same price; anodize scratches more easily
- Best for: Multi-color lineup where anodize colors (space gray, midnight, starlight) matter
- Cost: $4-6/unit at 1K (slightly more than zinc die-cast due to CNC time)

**Rejected: Injection-molded PC/ABS + chrome plating**
- Chrome plating on plastic peels under keychain abuse (pocket keys, drops)
- Fails the "premium feel" test — too light, hollow sound when tapped
- Only viable for $1-2 budget targets

### Cost Breakdown

| Item | @100 | @1,000 | @10,000 |
|------|------|--------|---------|
| Zinc die-cast shells (2-piece) | $6.00 | $2.80 | $1.50 |
| PVD coating (batch) | $3.00 | $1.20 | $0.60 |
| Laser logo engraving | $0.50 | $0.30 | $0.15 |
| PC light-pipe insert | $0.30 | $0.15 | $0.08 |
| Silicone gasket + screws | $0.40 | $0.20 | $0.12 |
| **Enclosure total** | **$10.20** | **$4.65** | **$2.45** |
| PCB + components (COIN Lite) | $12.00 | $9.50 | $7.00 |
| Battery (LIR2450 or 200mAh LiPo) | $1.50 | $0.80 | $0.50 |
| Assembly labor | $3.00 | $1.50 | $0.80 |
| **Total per unit** | **$26.70** | **$16.45** | **$10.75** |

### Tooling Costs

| Tooling | Cost | Amortization |
|---------|------|--------------|
| Die-cast mold (2 cavities) | $3,000 - $5,000 | 50K+ shots |
| PVD jig/fixtures | $500 | Reusable |
| Laser engraving program | $200 | One-time |
| Assembly jig | $300 | Reusable |
| **Total tooling** | **$4,000 - $6,000** | |

### Lead Time

| Phase | Duration |
|-------|----------|
| Mold design + fabrication | 3-4 weeks |
| Die-cast sampling (T1) | 1 week |
| PVD coating setup | 1 week |
| First article inspection | 3 days |
| Production run (1K) | 1-2 weeks |
| **Total to first delivery** | **6-8 weeks** |

### MOQ
- Die-casting: 500 pcs (per color/finish)
- PVD: 200 pcs per batch
- Practical MOQ: **500 units**

### Factory / Service

| Service | Provider | Location |
|---------|----------|----------|
| Zinc die-casting | Shenzhen (Alibaba: search "zinc alloy die casting small parts") | Dongguan/Shenzhen |
| PVD coating | Foxin Vacuum / local PVD shop | Shenzhen |
| PCB + PCBA | JLCPCB / PCBWay | Shenzhen |
| Laser engraving | Same factory or local CNC shop | Shenzhen |
| Final assembly | Manual or semi-automated | Shenzhen |
| For prototyping | PCBWay (CNC + die-cast + coating, one-stop) | Shenzhen |

### Surface Finish Options

| Finish | PVD Target | Look |
|--------|------------|------|
| Polished Silver | Stainless steel (SUS304) | AirTag-like mirror |
| Gunmetal | TiAlN | Dark metallic, fingerprint-resistant |
| Matte Black | TiN + DLC | Stealth, scratch-resistant |
| Rose Gold | TiN (tuned) | Fashion-forward |
| Champagne Gold | ZrN | Classic luxury |

### Customization Options
- Laser engraving: Logo, serial number, custom text ($0.15-0.30/unit)
- Color: Any PVD finish, MOQ 200/color
- Keyring attachment: Integrated loop (die-cast) or separate stainless ring

### Packaging Recommendation
- **Box**: Rigid 2-piece box (like AirTag packaging), 60x60x25mm
- Magnetic lid closure, foam insert with device cutout
- Unboxing feel matters for this persona
- Include: USB-C cable (15cm short), keyring, quick-start card
- Cost: $1.50-2.50/unit at 1K
- Alternative (budget): Kraft paper tuck box with foam insert, $0.50/unit

---

## Persona 7: Fashion / Jewelry (ファッション・ジュエリー)

**Form: Pendant (pebble/teardrop)**
- Target size: 25-30mm x 35-40mm x 8-10mm (river pebble shape)
- Weight: < 15g (must not pull on chain)
- Quantity: 200 - 1,000

### Analysis of Manufacturing Methods

| Method | Finish Quality | Feel | Cost @500 | Minimum | Verdict |
|--------|---------------|------|-----------|---------|---------|
| Ceramic injection molding (CIM) | Excellent — real ceramic | Warm, smooth, stone-like | $15-25 | 500 | Best for "not electronics" feel, but expensive tooling |
| Lost-wax cast brass + plating | Excellent — real metal | Heavy, cold, luxurious | $8-15 | 100 | Best for metal jewelry look |
| CNC titanium | Exceptional | Light, premium | $30-60 | 25 | Ultra-premium only |
| Injection molded + PVD/ceramic coat | Good — coated plastic | Lightweight, warm | $4-8 | 300 | Best cost/quality ratio |
| Resin casting + mineral fill | Good — stone-like texture | Medium weight, organic | $5-10 | 50 | Good for artisan/small batch |

### Recommended: Two-Tier Approach

**Tier A (Standard Line): Injection-Molded Shell + Ceramic-Look PVD**

For the 200-1000 volume sweet spot, injection molding with advanced coating delivers 80% of the ceramic feel at 30% of the cost.

- Shell: Glass-filled nylon (PA66-GF15) or liquid crystal polymer (LCP)
  - These feel "warm" like ceramic, unlike ABS which feels cheap
- Coating: Magnetron sputtering with ceramic (Al2O3 or ZrO2) target layer
  - Creates a real ceramic surface at molecular level (1-3 microns)
  - Scratch hardness: 8-9 Mohs (vs 2-3 for anodize, 6-7 for PVD metal)
- Weight: 8-12g (comfortable as pendant)
- Colors: Matte white (ceramic look), matte black, rose gold metallic, sage green

**Tier B (Limited Edition): Lost-Wax Cast Brass + Plating**

For 100-300 unit "capsule collections" with jewelry-grade finish.

- Process: 3D print wax master, invest, cast in brass/bronze, hand-finish
- Plating: 18K gold flash (0.5 micron), rhodium (white gold look), or raw patina
- Each piece slightly unique (artisan appeal)
- Weight: 20-25g (heavier, but acceptable for statement jewelry)
- Best sold at premium price point ($80-150 retail vs $40-60 for Tier A)

### Cost Breakdown — Tier A (Injection + Ceramic Coat)

| Item | @100 | @500 | @1,000 |
|------|------|------|--------|
| Injection-molded shell (2-piece, PA66-GF) | $4.00 | $2.00 | $1.20 |
| Ceramic PVD coating | $4.00 | $2.00 | $1.20 |
| Pendant bail / chain loop (stainless insert) | $0.50 | $0.30 | $0.20 |
| **Enclosure total** | **$8.50** | **$4.30** | **$2.60** |
| PCB + components (custom round/oval) | $13.00 | $10.00 | $8.00 |
| Battery (ultra-thin 200mAh) | $2.00 | $1.20 | $0.80 |
| Chain/cord (45cm adjustable) | $1.50 | $0.80 | $0.50 |
| Assembly + QC | $4.00 | $2.50 | $1.50 |
| **Total per unit** | **$29.00** | **$18.80** | **$13.40** |

### Cost Breakdown — Tier B (Lost-Wax Brass)

| Item | @50 | @200 | @500 |
|------|-----|------|------|
| Lost-wax cast brass shell | $12.00 | $8.00 | $6.00 |
| Hand finishing + plating | $8.00 | $5.00 | $3.50 |
| Assembly | $5.00 | $3.00 | $2.00 |
| PCB + battery | $15.00 | $11.00 | $9.00 |
| **Total per unit** | **$40.00** | **$27.00** | **$20.50** |

### Tooling Costs

| Tooling | Cost | Notes |
|---------|------|-------|
| Injection mold (Tier A) | $2,500 - $4,000 | Teardrop shape, 2 cavities |
| PVD jig (Tier A) | $400 | Batch fixture |
| Wax master 3D print (Tier B) | $50-100 | Per design iteration |
| Investment casting flask setup (Tier B) | $200-500 | Reusable |
| **Tier A total** | **$3,000 - $4,500** | |
| **Tier B total** | **$300 - $600** | Very low tooling — ideal for limited runs |

### Lead Time

| Phase | Tier A | Tier B |
|-------|--------|--------|
| Mold / master | 3-4 weeks | 1 week |
| Sampling | 1 week | 1 week |
| Production (500 pcs) | 2 weeks | 3-4 weeks |
| **Total** | **6-7 weeks** | **5-6 weeks** |

### MOQ
- Tier A (injection): 300 units
- Tier B (lost-wax): 50 units (ideal for testing market)

### Factory / Service

| Service | Provider | Notes |
|---------|----------|-------|
| Injection + PVD (Tier A) | PCBWay (injection molding service) | One-stop quote |
| Lost-wax casting (Tier B) | Shenzhen jewelry casting houses (Alibaba: "lost wax casting small batch") | Many specialize in tech-jewelry |
| Casting (Tier B, Japan) | dmm.make 3D print + local casting | Higher cost, faster iteration |
| Chain/cord | Alibaba: "925 silver chain 45cm adjustable" or "waxed cord necklace" | $0.30-1.50 |

### Surface Finish Options

| Finish | Method | Aesthetic |
|--------|--------|-----------|
| Matte White Ceramic | PVD Al2O3 on PA66 | Like a polished pebble |
| Brushed Brass | Raw cast + Scotch-Brite | Warm, develops patina |
| Rose Gold | PVD TiN on PA66 or electroplate on brass | Unisex fashion |
| Matte Black | PVD DLC on PA66 | Monochrome minimalist |
| Sage Green | Ceramic PVD with pigment | Nature-inspired |

### Customization
- Engraving (initial, name): Laser on metal or coating
- Chain options: Silver chain, leather cord, waxed cotton, gold-filled chain
- Limited edition numbering: Laser-etched "XXX/500" on back

### Packaging Recommendation
- **Box**: Jewelry box (clamshell, velvet-lined), 60x80x30mm
- Branded sleeve or belly band
- Include: Chain/cord, polishing cloth, care card
- Unboxing must feel like opening jewelry, not electronics
- Cost: $2.50-4.00/unit at 500
- Consider: Reusable pouch (drawstring microfiber) as alternative, $1.00/unit

---

## Persona 8: Corporate / Conference (ビジネス・会議)

**Form: Badge (name tag style)**
- Target size: 85 x 55 x 5-8mm (credit card footprint)
- Weight: < 30g
- Quantity: 500 - 5,000

### Key Requirement: On-Demand Logo Customization

Conference badges MUST support per-event branding. This eliminates approaches where the brand is molded into the shell.

**Solution: Printed insert system**
- Transparent front window (shows printed card underneath)
- Each conference prints their own inserts (standard inkjet/laser on card stock)
- Template provided as PDF/Figma — conference organizer adds logo + attendee name

### Recommended: 2-Shot Injection (Clear Front + Opaque Back)

**Why 2-shot over separate pieces:**
- Single molded unit = no rattling, better feel, IP43 with gasket
- Clear polycarbonate front transmits LED light diffusely
- Opaque back (PC/ABS) gives rigidity and hides PCB

**Process flow:**
1. 2-shot injection: Shot 1 = black PC/ABS back, Shot 2 = clear/frosted PC front
2. PCB drops into back shell (snap-fit standoffs)
3. Printed card insert slides into channel between PCB and clear front
4. Ultrasonic weld or snap-fit closure
5. Lanyard slot molded into top edge

**Alternative: Simple approach for first run**

If 2-shot tooling ($6K-8K) is too much for v1, use a simpler approach:
- Single-shot injection: White PC/ABS shell (back + frame)
- Separate clear PC window (0.5mm, laser-cut or punched), glued with optically clear adhesive
- Same insert card system
- Tooling: $2,000-3,000

### Card-Style Variant (Ultra-Thin)

For maximum portability, consider a credit-card thickness design:
- Flex PCB (0.2mm) + ultra-thin LiPo (2mm, 150mAh) + ESP32-C3 (smaller than S3)
- Total: 4-5mm thick, 25g
- Trade-off: Shorter battery life (3-4 hours), no speaker (BLE to phone only)
- Better for 1-day conference use where charging overnight is acceptable

### Cost Breakdown — Standard Badge (2-Shot)

| Item | @500 | @1,000 | @5,000 |
|------|------|--------|--------|
| 2-shot injection shell | $2.50 | $1.50 | $0.80 |
| PCB + components (rectangular layout) | $11.00 | $9.00 | $6.50 |
| Battery (502535, 400mAh, 5x25x35mm) | $1.50 | $1.00 | $0.60 |
| Lanyard clip (alligator + safety pin) | $0.30 | $0.20 | $0.10 |
| Assembly + QC | $2.00 | $1.20 | $0.60 |
| **Total per unit** | **$17.30** | **$12.90** | **$8.60** |

### Cost Breakdown — Budget Badge (Single-Shot + Window)

| Item | @500 | @1,000 | @5,000 |
|------|------|--------|--------|
| Single-shot shell + clear window | $1.80 | $1.00 | $0.50 |
| PCB + components | $11.00 | $9.00 | $6.50 |
| Battery | $1.50 | $1.00 | $0.60 |
| Lanyard + clip | $0.30 | $0.20 | $0.10 |
| Assembly | $2.00 | $1.20 | $0.60 |
| **Total per unit** | **$16.60** | **$12.40** | **$8.30** |

### Tooling Costs

| Tooling | Cost | Notes |
|---------|------|-------|
| 2-shot injection mold | $6,000 - $8,000 | 2 materials, badge shape |
| Single-shot mold (budget) | $2,000 - $3,000 | Simpler, 1 cavity |
| Clear window die (budget option) | $300 | For punching PC sheet |
| Assembly jig | $200 | Holds badge during insertion |
| Insert card template (Figma/PDF) | $0 | Digital, self-service |
| **Total (2-shot)** | **$6,500 - $8,500** | |
| **Total (budget)** | **$2,500 - $3,500** | |

### Lead Time

| Phase | Duration |
|-------|----------|
| Mold design + fabrication | 4-5 weeks (2-shot) / 3 weeks (single) |
| T1 samples | 1 week |
| Production (1K) | 1-2 weeks |
| **Total** | **6-8 weeks (2-shot) / 5-6 weeks (single)** |

### MOQ
- 2-shot injection: 500 units
- Single-shot: 300 units
- Insert cards: 1 (print on demand)

### Factory / Service

| Service | Provider | Notes |
|---------|----------|-------|
| 2-shot injection | PCBWay injection / Protolabs (faster) | Protolabs = 2-3 week molds |
| Single-shot injection | JLCPCB 3D print (proto) → Shenzhen mold shop (prod) | |
| Insert card printing | Any commercial printer / conference's own printer | Standard 86x54mm card stock |
| Lanyard + clips | Alibaba: "badge lanyard custom print" | Custom print MOQ 100 |

### Surface Finish Options

| Finish | Method | Target Aesthetic |
|--------|--------|------------------|
| Matte White + Clear | Standard (2-shot) | Clean, Apple-like |
| Matte Black + Frosted | 2-shot with frosted PC | Stealth corporate |
| Wood grain texture | In-mold texture (VDI 3400 / Mold-Tech) | Warm, sustainable feel |
| Soft-touch | Overmold with TPE or soft-touch paint | Comfortable to hold |

### Customization Options
- **Per-conference branding**: Insert card system (self-service, zero cost per event)
- **Custom lanyard**: Printed nylon lanyard with event logo, MOQ 100, $0.50/pc
- **Shell color**: Custom color per MOQ 500 (or paint for smaller runs)
- **Engraving**: Laser on back shell (company name, serial number)
- **NFC**: Add NFC sticker inside ($0.30/unit) for digital business card / vCard exchange

### Packaging Recommendation
- **Individual**: Kraft paper envelope with foam insert (conference swag bag style)
- **Bulk**: 50 units per tray in a master carton (shipped to event venue)
- Include: Pre-printed insert card with event branding, USB-C cable, lanyard
- Cost: $0.30-0.50/unit (envelope) or $0.10/unit (bulk tray)
- Conference organizers want easy distribution — individually bagged is ideal

---

## Persona 9: Ultra-Minimalist / Gen Z (ミニマリスト)

**Form: Sticker (ultra-thin)**
- Target size: 40-50mm diameter x 3-4mm thick (the dream) or 5-6mm (realistic)
- Weight: < 10g
- Quantity: 1,000 - 10,000

### Thickness Analysis: What's Physically Possible?

| Component | Minimum Thickness |
|-----------|-------------------|
| ESP32-C3 (QFN, smaller than S3) | 0.75mm |
| INMP441 MEMS mic | 1.0mm |
| PCB (2-layer flex or rigid-flex) | 0.4-0.8mm |
| Battery (ultra-thin LiPo) | 1.5-2.5mm |
| Enclosure walls (top + bottom) | 0.3mm x 2 = 0.6mm |
| **Theoretical minimum** | **~4.5mm** |

A true "sticker" (< 2mm) is not feasible with current ESP32 + LiPo technology.
The realistic target is **5-6mm thick** — thin enough to not create a noticeable bump on a phone/laptop.

### Recommended: Conformal-Coated PCB + Ultra-Thin Adhesive Shell

**The sticker approach: no traditional "case" at all.**

**Process flow:**
1. Custom PCB: Round, 40mm diameter, 0.6mm 4-layer rigid (or 2-layer with 0.8mm)
2. ESP32-C3 (not S3 — smaller die, fewer pins, sufficient for mic + LED + WiFi)
3. Components on top side only
4. Conformal coating: Parylene C (vapor deposition, 10-25 microns)
   - Fully waterproof at molecular level (better than any gasket)
   - Transparent, does not interfere with RF
   - Protects all components without adding bulk
5. Top cover: 0.3mm polycarbonate disc (screen-printed with design)
   - Adhesive-bonded to PCB perimeter
   - Serves as aesthetic surface and scratch protection
6. Bottom: 3M VHB adhesive pad (removable/replaceable)
   - Or magnetic mount (embedded 8mm x 1mm neodymium disc)

**Total stack:**
- Battery: 2.0mm (ultra-thin 150-200mAh, e.g., GMB 303030)
- PCB + components: 1.8mm (0.6mm PCB + 1.2mm tallest component)
- Top cover: 0.3mm
- Bottom adhesive: 0.5mm
- **Total: ~4.6-5.5mm**

### Alternative: Flexible PCB Version (Future)

For a truly thin "smart sticker" (< 3mm):
- Requires flex PCB + flex battery (printed battery, 0.5mm, ~50mAh)
- Battery life: 1-2 hours max (limits usefulness)
- More R&D needed, not production-ready for 2026
- Viable when thin-film batteries improve (2027-2028 timeline)

### Cost Breakdown

| Item | @100 | @1,000 | @10,000 |
|------|------|--------|---------|
| Custom round PCB + SMT (4-layer, 40mm) | $14.00 | $8.00 | $4.50 |
| Parylene C conformal coating (batch) | $3.00 | $1.50 | $0.80 |
| PC top disc (screen-printed) | $1.00 | $0.40 | $0.20 |
| Ultra-thin LiPo (2mm, 150mAh) | $3.00 | $1.80 | $1.00 |
| 3M VHB adhesive pad | $0.30 | $0.15 | $0.08 |
| Assembly + QC | $2.00 | $1.00 | $0.50 |
| **Total per unit** | **$23.30** | **$12.85** | **$7.08** |

### Tooling Costs

| Tooling | Cost | Notes |
|---------|------|-------|
| PCB panel layout + stencil | $50-100 | Standard PCBA setup |
| Parylene coating jig | $200-500 | Holds PCBs during deposition |
| Screen print screen (top disc) | $100-200 | Per design |
| Die-cut tool (top disc + adhesive) | $200-400 | For punching circles |
| **Total tooling** | **$550 - $1,200** | Very low — no molds needed |

### Lead Time

| Phase | Duration |
|-------|----------|
| PCB fabrication + assembly | 1-2 weeks (JLCPCB) |
| Parylene coating | 1 week (batch) |
| Top disc print + die cut | 1 week |
| Assembly + QC | 1 week |
| **Total** | **4-5 weeks** |

### MOQ
- PCBs: 5 (JLCPCB minimum), practical: 100+
- Parylene coating: 50 pcs per batch
- Screen print: 100 pcs per design
- **Practical MOQ: 100 units**

### Factory / Service

| Service | Provider | Notes |
|---------|----------|-------|
| PCB + PCBA | JLCPCB / PCBWay | 4-layer round board, panelized |
| Parylene coating | Specialty Coating Systems (US) / Shenzhen conformal coating shops | Vapor deposition |
| Top disc printing | Any screen print / digital print shop | Die-cut polycarbonate |
| Ultra-thin batteries | GMB (Shenzhen), Grepow, Enepaq | Search "ultra thin lipo 2mm" |
| 3M VHB adhesive | 3M distributor or die-cut shop | Pre-cut circles |

### Surface Finish Options

| Finish | Method | Look |
|--------|--------|------|
| Matte Black | Screen print + matte laminate on PC disc | Stealth, minimal |
| Holographic | Holographic film laminate on PC disc | Gen Z eye-catch |
| Custom print (any design) | Digital UV print on PC disc | Infinite designs |
| Transparent / smoke | Tinted PC disc, components visible | Cyberpunk / tech-forward |
| Mirror chrome | Vacuum metallization on PC disc | Statement piece |

### Customization Options
- **Top disc print**: Any design, photo quality (UV digital print, MOQ 1)
- **Holographic effects**: Film laminate overlay, MOQ 100
- **QR code**: Printed on disc, links to user's profile / device setup
- **Shape**: Circle (default), rounded rectangle (phone-like), custom die-cut
- **Collaboration**: Co-branded with phone case / laptop skin brands

### Packaging Recommendation
- **Peel-and-reveal card**: Device mounted on a card (like a phone PopSocket package)
- Card stock with UV print, device peels off from backing
- Include: Spare adhesive pad (x2), micro USB-C cable (flat), setup QR code
- Aesthetic: Streetwear / sneaker brand vibes (bold typography, limited edition numbering)
- Cost: $0.30-0.60/unit at 1K
- Alternative: Resealable mylar pouch (holographic), $0.15/unit

---

## Summary Comparison Table

| Persona | Form | Material | Process | Unit Cost @1K | Tooling | Lead Time | IP Rating | Weight |
|---------|------|----------|---------|---------------|---------|-----------|-----------|--------|
| 6. EDC / Keychain | 32mm disc | Zinc alloy + PVD | Die-cast | **$16.45** | $4K-6K | 6-8 weeks | IP54 | 15g |
| 7A. Fashion (Standard) | Teardrop pendant | PA66-GF + ceramic PVD | Injection + PVD | **$18.80** | $3K-4.5K | 6-7 weeks | IP43 | 12g |
| 7B. Fashion (Limited) | Teardrop pendant | Brass, lost-wax | Investment casting | **$27.00** | $300-600 | 5-6 weeks | IP42 | 22g |
| 8A. Corporate Badge (2-shot) | 85x55mm card | PC + PC/ABS | 2-shot injection | **$12.90** | $6.5K-8.5K | 6-8 weeks | IP43 | 28g |
| 8B. Corporate Badge (budget) | 85x55mm card | PC/ABS + clear window | Single injection | **$12.40** | $2.5K-3.5K | 5-6 weeks | IP42 | 28g |
| 9. Sticker / Ultra-thin | 40mm disc, 5mm | PCB + Parylene + PC disc | Conformal coat | **$12.85** | $550-1.2K | 4-5 weeks | IP67* | 8g |

*Parylene C provides excellent moisture protection, though not formally IP-rated without a sealed enclosure.

### Cost vs Volume Curves

```
Unit cost ($)
  30 |  *
     |   *  7B (brass)
  25 |    *
     |      *
  20 |  *     *  ............
     |   * 7A     *
  15 |    *  *6      * 7B
     |  *  8A  *
  10 |   8B  *  *6  *9  *7A
     |    *9    *8A   *8B
   5 |              *9
     +------+------+-------→
          100    1K     10K  Quantity
```

### Recommended Priority Order (for Koe Seed launch)

1. **Persona 9 (Sticker)** — Lowest tooling, fastest lead time, broadest appeal for Gen Z. Start here.
2. **Persona 6 (Keychain)** — Strong EDC market, moderate tooling, AirTag positioning.
3. **Persona 8B (Badge, budget)** — Conference/B2B revenue. Low tooling. Customization is the killer feature.
4. **Persona 7A (Fashion pendant)** — After market validation. Higher ASP offsets lower volume.
5. **Persona 7B (Brass limited)** — Capsule drops for brand building. Tiny tooling investment.

---

## Bill of Materials Comparison (Electronics Only)

All personas share the same core electronics with minor variations:

| Component | Persona 6 | Persona 7 | Persona 8 | Persona 9 |
|-----------|-----------|-----------|-----------|-----------|
| MCU | ESP32-S3-MINI-1 | ESP32-S3-MINI-1 | ESP32-S3-MINI-1 | ESP32-C3-MINI-1 |
| Mic | INMP441 x1 | INMP441 x1 | INMP441 x1 | INMP441 x1 |
| LED | WS2812B-2020 | WS2812B-2020 | WS2812B-2020 x3 (status bar) | WS2812B-2020 |
| Charger | MCP73831 | MCP73831 | MCP73831 | MCP73831 |
| LDO | AP2112K-3.3 | AP2112K-3.3 | AP2112K-3.3 | AP2112K-3.3 |
| Speaker | None (BLE) | None (BLE) | Optional (10mm) | None (BLE) |
| Battery | LIR2450 or 200mAh | 200mAh ultra-thin | 400mAh (502535) | 150mAh ultra-thin |
| PCB | 26mm round | Custom oval | 80x50mm rect | 40mm round |
| Connectivity | WiFi + BLE | WiFi + BLE | WiFi + BLE + NFC | WiFi + BLE |

Note: Persona 9 uses ESP32-C3 instead of S3 to save height and cost (single core, but sufficient for mic + WiFi + LED).
