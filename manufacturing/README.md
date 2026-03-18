# Koe Device -- JLCPCB PCBA Ordering Guide

## Overview

This guide walks through ordering assembled PCBs for the Koe Device from JLCPCB.
The board is a 2-layer 30x40mm design with all surface-mount components assembled
by JLCPCB. A few through-hole/off-board parts (battery, speaker) are sourced
separately and attached during final assembly.

## Prerequisites

Before ordering you need three files exported from KiCad:

| File | Format | Source |
|------|--------|--------|
| Gerber + drill files | ZIP | KiCad: File > Fabrication Outputs > Gerbers |
| BOM | CSV | `jlcpcb/BOM-JLCPCB.csv` (this repo) |
| CPL (pick & place) | CSV | `jlcpcb/CPL-JLCPCB.csv` (this repo, update coords from KiCad) |

### Generating Gerbers from KiCad

1. Open the PCB in KiCad PCB Editor.
2. File > Fabrication Outputs > Gerbers (.gbr).
3. Settings:
   - Layers: F.Cu, B.Cu, F.SilkS, B.SilkS, F.Mask, B.Mask, Edge.Cuts
   - Format: 4.6, unit mm
   - Check "Use Protel filename extensions"
   - Check "Subtract soldermask from silkscreen"
4. Click "Plot", then "Generate Drill Files...":
   - Drill units: mm
   - Format: Excellon
   - Check "PTH and NPTH in single file"
5. ZIP all generated files into one archive.

### Generating CPL (Component Placement) from KiCad

1. File > Fabrication Outputs > Component Placement (.pos).
2. Format: CSV, Units: mm, Coordinate origin: Auxiliary axis origin.
3. The output needs column renaming to match JLCPCB format:
   - `Ref` -> `Designator`
   - `PosX` -> `Mid X`
   - `PosY` -> `Mid Y`
   - `Rot` -> `Rotation`
   - `Side` -> `Layer`
4. Replace the placeholder values in `jlcpcb/CPL-JLCPCB.csv` with the real
   coordinates.

**Important:** The `CPL-JLCPCB.csv` in this repo contains placeholder coordinates.
You MUST regenerate it from the actual KiCad PCB layout before ordering.

## Step-by-Step Ordering on JLCPCB

### Step 1: Upload Gerbers

1. Go to https://www.jlcpcb.com/ and click "Order Now".
2. Upload the Gerber ZIP file.
3. Wait for the board preview to render and verify it looks correct.

### Step 2: Set PCB Parameters

Configure these settings (see `jlcpcb/PCB-SPEC.md` for full details):

| Parameter | Value |
|-----------|-------|
| Layers | 2 |
| Dimensions | 30 x 40 mm |
| PCB Thickness | 1.0 mm |
| PCB Color | Green |
| Silkscreen | White |
| Surface Finish | ENIG |
| Material | FR-4 TG155 |
| Impedance Control | Yes (JLC04161H-7628) |
| Min Trace/Space | 0.15mm / 0.15mm |
| Quantity | 5 (minimum) |

### Step 3: Enable SMT Assembly

1. Scroll down to "SMT Assembly" and toggle it ON.
2. Settings:
   - Assembly Side: **Top Side**
   - Tooling Holes: **Added by JLCPCB**
   - Confirm Parts Placement: **Yes**
3. Click "Next".

### Step 4: Upload BOM and CPL

1. Upload `jlcpcb/BOM-JLCPCB.csv` as the BOM file.
2. Upload `jlcpcb/CPL-JLCPCB.csv` as the CPL file.
3. Click "Process BOM & CPL".

### Step 5: Verify Part Matching

1. JLCPCB will match LCSC part numbers from the BOM.
2. Verify every part is matched and in stock.
3. If a part is out of stock, check for compatible alternatives:
   - Use JLCPCB's part search or https://www.lcsc.com/
   - Ensure footprint and electrical specs match
4. Parts NOT available at JLCPCB (battery, speaker) are omitted from the BOM
   and will be installed manually. See `manual-parts.md`.

### Step 6: Review Placement

1. JLCPCB shows a 2D/3D preview of component placement.
2. Check that:
   - All ICs (U1-U6) have correct orientation (pin 1 dot alignment)
   - Polarized components (D1, C1, C3, C4, C5, C6, C7) are correct
   - USB connector (J1) faces the board edge
3. Adjust rotation offsets if any part looks wrong.

### Step 7: Order

1. Review the final quote. Expected pricing for 5 boards:
   - PCB fabrication: ~$10 ($2/board)
   - SMT assembly setup: ~$8
   - Component cost: ~$9/board
   - Total: **~$60-70 for 5 assembled boards**
2. Select shipping (DHL/FedEx for speed, standard mail for cost).
3. Place order and pay.

## Timeline

| Stage | Duration |
|-------|----------|
| PCB fabrication + assembly | 5-7 business days |
| Shipping (DHL Express) | 3-5 days |
| Shipping (standard) | 10-20 days |
| **Total (express)** | **~10-12 days** |

## After Receiving Boards

See `assembly-guide.md` for instructions on:
- Soldering the battery connector wires
- Attaching the speaker
- Installing the board into the case
- First power-on and firmware flashing

## File Inventory

```
manufacturing/
  README.md                  -- This file
  assembly-guide.md          -- Final assembly instructions
  manual-parts.md            -- Parts to source separately
  jlcpcb/
    BOM-JLCPCB.csv           -- Bill of Materials (JLCPCB format)
    CPL-JLCPCB.csv           -- Component Placement List (JLCPCB format)
    PCB-SPEC.md              -- PCB fabrication specifications
```

## Cost Summary (Per Unit, 5-board run)

| Item | Cost |
|------|------|
| PCB + PCBA (JLCPCB) | ~$11.50 |
| JLCPCB components | ~$9.00 |
| Battery (AliExpress) | ~$2.50 |
| Speaker (AliExpress) | ~$0.50 |
| **Total per unit** | **~$23.50** |

Costs decrease significantly at higher quantities (50+ units).
