# Koe — Industrial Design RFP
*Issued: 2026-04-13 · Response deadline: 2026-04-20 · Enabler Inc.*

---

## Overview

Enabler Inc. (Tokyo) is seeking an industrial design partner for **Koe**, a family of five CNC aluminum wireless audio objects. This RFP covers mechanical design development, surfacing, finish specification, and pre-production samples.

Vendor shortlist:
1. **Nordic Design House** (Stockholm)
2. **Makable** (Shenzhen / Tokyo)
3. **Tangent** (London / Hong Kong)

---

## Product Brief

Koe is a premium home speaker system built around one material (CNC 6061-T6 aluminum), one gesture (touch the top surface), and one design language (superellipse n=3.5, hairline + anodize finish, Space Gray).

**Design principle:** Every object should feel like it belongs in a museum — not as a technology exhibit, but as a sculpture.

---

## SKU Family (5 objects, one shared design language)

| SKU | Nickname | Form | Key constraint |
|-----|----------|------|----------------|
| Stone | The Anchor | Ø80×25mm disc | Touch sensor top face, Tectonic BMR 40mm below |
| Stone Mini | The Traveler | Ø50×15mm disc | Lanyard slot, no buttons |
| Pick | The Contact | Reuleaux 40mm×4mm tapered | Adheres to guitar body; piezo contact transducer |
| Pendant | The Talisman | Ø35mm teardrop×10mm | IPX7; bail for leather cord; Knowles 20mm driver |
| Amp | The Temple | 60×60×55mm trapezoidal | 5° tilt back; Fibonacci grille on top; Dayton RS100 |

---

## Design Language

See `tasks/design-system.md` for full spec. Summary:

- **Material:** CNC 6061-T6 aluminum unibody (no visible seams on Stone/Mini/Pendant)
- **Surface:** Hairline brushed, then hard anodize #0a0a0a (Void Black)
- **Mesh/grille:** Etched, not stamped. Pattern derived from superellipse grid.
- **Typography:** None. One laser-engraved serial number only (bottom face).
- **Color accent:** None on exterior. Violet (#8B5CF6) only visible through status LED on underside edge.
- **Profile language:** Every silhouette uses superellipse exponent n=3.5 (midpoint between circle and rectangle).

---

## Deliverables Requested

### Phase 1: Concept (4 weeks, due 2026-05-11)
- [ ] 3 × surfacing explorations per SKU (15 total renders)
- [ ] Material + finish sample coupon: 3 anodize shades (Space Gray target + 2 alternatives)
- [ ] Grille pattern alternatives: 3 options (Stone, Amp)
- [ ] Cross-section drawings showing driver placement, PCB stack, charging coil, battery
- [ ] DFM risk register (first pass)

### Phase 2: Engineering (4 weeks, due 2026-06-08)
- [ ] Final STEP files, all 5 SKUs
- [ ] GD&T drawings (critical tolerances: touch sensor fit, mesh acoustic aperture, IPX7 seal path)
- [ ] BOM review against our reference PCB (nRF5340 shared platform)
- [ ] Tooling vendor recommendation (Japan or Taiwan preferred)
- [ ] Pilot run quantity: 30 units (6 Stone + 4 Mini + 6 Pick + 6 Pendant + 2 Amp × 1.5 overage)

### Phase 3: Pre-production samples (2 weeks, due 2026-06-22)
- [ ] 2 × matched set samples (Stone + Amp) for venue placement by 2026-06-25
- [ ] Packaging: unbranded black cardboard + tissue for Hawaii delivery
- [ ] Final anodize sign-off on physical coupon

---

## Koe Sessions Integration (Amp + Pick)

The Amp includes microphone capability for passive multi-track recording (Koe Sessions feature). This adds two requirements not typical of passive speakers:

**Amp additions:**
- Stereo MEMS mic array (Knowles SPH0645LM4H × 2) on top face
- 64GB NAND storage (internal, inaccessible externally)
- Violet LED ring (1.5mm diffused through anodized edge slot, 0.2mm kerf)
- Status indicator must be visible from 3m at arm height

**Pick additions:**
- Piezo contact transducer (20mm × 3mm, mounted bottom face)
- Silicone over-mold strap receptacle (must accept 8mm wide strap)
- Charge port: USB-C (not Qi; too thin)

These requirements should be flagged in the DFM risk register Phase 1.

---

## Timeline

| Milestone | Date |
|-----------|------|
| RFP issued | 2026-04-13 |
| Vendor response deadline | 2026-04-20 |
| Vendor selection + contract | 2026-04-25 |
| Phase 1 kick-off | 2026-04-28 |
| Phase 1 delivery | 2026-05-11 |
| Phase 2 delivery | 2026-06-08 |
| Pre-production samples | 2026-06-22 |
| Hawaii delivery | 2026-06-25 |

---

## Budget Range

**$80,000–$120,000 USD** for full scope (Phase 1–3 inclusive of pilot run tooling and 30-unit production). Breakdown expected in response:
- Design fees (hourly or fixed per phase)
- Tooling estimate (5 SKU family)
- Pilot unit cost per SKU
- Shipping (to Tokyo, then Hawaii)

Note: This is a design-forward, not cost-optimized engagement. The budget reflects premium execution. Responses that compromise material or finish to reduce cost will be rejected.

---

## Selection Criteria

| Criterion | Weight |
|-----------|--------|
| Portfolio: precision CNC consumer products | 35% |
| Timeline confidence (June 22 samples) | 30% |
| DFM approach / Japan/Taiwan factory relationships | 20% |
| Communication quality of response | 15% |

---

## To Respond

Please send by **2026-04-20**:
1. Fixed-fee or T&M proposal for all 3 phases
2. Relevant portfolio (3–5 projects, precision metal consumer)
3. Factory relationships (Japan / Taiwan preferred)
4. Key contact / designer for this project

Send to: **yukihamada@enablerdao.com** with subject line: `Koe ID RFP — [Studio Name]`

Questions welcome before 2026-04-18.

---

*Enabler Inc. · Tokyo · koe.live*
