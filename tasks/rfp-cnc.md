# Koe — CNC Manufacturing RFP
*Issued: 2026-04-13 · Enabler Inc.*

Vendor shortlist:
1. **山形小松精機** (Yamagata Komatsu Seiki, Japan)
2. **Protolabs** (Minneapolis / online)
3. **Fictiv** (San Francisco / China network)

---

## Part Summary (5 SKUs, ~30 pilot units)

| Part | Material | Finish | Qty |
|------|----------|--------|-----|
| Stone body | 6061-T6 billet | Hairline + hard anodize #0a0a0a | 9 |
| Stone Mini body | 6061-T6 billet | Same | 6 |
| Pick body | 6061-T6 billet tapered | Same | 9 |
| Pendant body | 6061-T6 billet teardrop | Same | 9 |
| Amp body | 6061-T6 billet trapezoidal | Same | 3 |

**Total: ~36 billeted parts (with 20% overage)**

---

## Critical Tolerances

### Stone (Ø80×25mm)
- Top face flatness: ≤0.05mm (touch sensor contact)
- Acoustic mesh aperture: Ø0.8mm through-holes, ±0.05mm (etched preferred over drilled)
- Qi coil recess depth: 3.0mm ±0.1mm
- Bottom snap-fit groove: 0.5mm ±0.05mm
- Serial number laser engrave depth: 0.08mm ±0.02mm (bottom face)

### Stone Mini (Ø50×15mm)
- Lanyard slot: 4.0×2.0mm, break-free from body contour
- All other tolerances as Stone proportionally scaled

### Pick (Reuleaux 40×35×4mm tapered)
- Taper: 4mm at thick end → 1.5mm at apex
- Bottom piezo recess: 21.5×21.5mm, depth 3.0mm ±0.1mm
- Silicone strap receptacle: 8.5mm slot, through-body

### Pendant (Ø35mm teardrop × 10mm)
- IPX7 seal groove: 0.8mm wide × 0.8mm deep, continuous
- Bail (top): Ø3.5mm through-hole, tangent to body curve (no sharp transitions)
- Driver recess: Ø21mm × 4mm depth ±0.1mm

### Amp (60×60×55mm trapezoidal)
- 5° back tilt machined into bottom face (not shimmed externally)
- Fibonacci grille top face: ≥24 apertures, Ø2.5–3.5mm each, ±0.08mm
- MEMS mic slot: 2× 1.5mm circular apertures on top face (not through)
- LED edge slot: 1.5mm wide kerf, 0.2mm window, full perimeter

---

## Surface Specification

1. **Machine:** CNC 3-axis or 5-axis as needed (5-axis preferred for Pendant bail + teardrop)
2. **Brush:** Hairline 80-grit radial (Stone/Mini: circumferential; Amp: parallel to long axis)
3. **Clean:** Ultrasonic bath
4. **Anodize:** Hard anodize (Type III), 25μm, dye #0a0a0a
5. **Seal:** Teflon PTFE seal preferred (not nickel acetate — nickel may affect touch sensor calibration)
6. **Laser:** Serial number, bottom face only. Font: Inter Bold 6pt. Depth: 0.08mm.

---

## Deliverables + Timeline

| Milestone | Date | Notes |
|-----------|------|-------|
| RFQ submission | 2026-04-20 | Quote per SKU per unit at qty 10/30/100 |
| DFM feedback | 2026-04-25 | Identify any tolerance conflicts with our STEP files |
| First article (Stone only) | 2026-05-20 | Single machined + anodized Stone for approval |
| Pilot run delivery (all 5 SKUs) | 2026-06-22 | Packed for international shipping (Tokyo delivery) |

---

## Questions for RFQ Response

1. Confirm 5-axis capability for Pendant teardrop profile
2. Confirm Type III anodize in-house or sub-contract (need sub name)
3. Quote at unit level: qty 10 / 30 / 100 per SKU
4. Lead time from STEP file approval to first article (Stone)
5. Lead time from first article approval to pilot run (all 5 SKUs)
6. Japan domestic delivery or international shipping capability?
7. Experience with acoustic mesh apertures ≤1mm via etching vs. micro-drilling?

---

## Contact

Send to: **yukihamada@enablerdao.com** by **2026-04-20**
Subject: `Koe CNC RFQ — [Company Name]`

STEP files available upon NDA signing (request below).

---

*Enabler Inc. · Tokyo · koe.live*
