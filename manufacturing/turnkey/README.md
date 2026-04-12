# Koe Device — Turnkey (Box Build) Assembly Package

This directory contains everything needed to order **fully assembled, ready-to-use** Koe devices from a turnkey assembly service.

## What "Turnkey" means
You upload these files → manufacturer does everything → boxed products arrive at your door.
- PCB fabrication + SMT soldering
- Manual/through-hole component soldering (battery, speaker, connectors)
- 3D printed enclosure manufacturing
- Final assembly (PCB + battery + speaker into case)
- Firmware flashing via USB-C
- Functional testing per test spec
- Packaging

## Recommended Services

### 1. PCBWay Box Build Assembly (recommended)
- URL: https://www.pcbway.com/pcb-assembly.html
- "Turnkey" option → upload Gerber + Full BOM + Assembly Drawing
- They source all components (LCSC + Mouser/DigiKey fallback)
- 3D printing in-house
- Box build = final mechanical assembly
- Quote: email sales@pcbway.com with this package

### 2. Seeed Studio Fusion PCBA
- URL: https://www.seeedstudio.com/fusion_pcba.html
- Full turnkey + box build available
- Good for small batches (5-50 units)

### 3. JLCPCB PCBA + separate 3D print (partial turnkey)
- SMT assembly only (no manual soldering or box build)
- You'd still need to do final assembly yourself
- NOT recommended if you want zero manual work

## How to Order

1. Go to PCBWay → "PCB Assembly" → "Turnkey"
2. Upload files from this directory:
   - `coin-lite/` — COIN Lite complete package
   - `pro-v2/` — Pro v2 complete package
   - `hub-v2/` — Hub v2 complete package
3. Each subdirectory contains:
   - `gerbers.zip` — PCB fabrication files
   - `BOM-FULL.csv` — Complete BOM (SMT + manual parts)
   - `CPL.csv` — Component placement
   - `assembly-drawing.md` — Assembly instructions with diagrams
   - `test-spec.md` — Functional test requirements
   - `enclosure.stl` — 3D printed case file
   - `firmware.bin` — Pre-built firmware binary (if available)
   - `flash-instructions.md` — How to flash firmware
4. In the notes field, paste:
   ```
   Box Build Assembly requested.
   Please perform full mechanical assembly including:
   - SMT + through-hole soldering
   - Battery and speaker wire soldering per assembly drawing
   - 3D print enclosure (SLA Black Resin) and assemble PCB into case
   - Flash firmware via USB-C per flash instructions
   - Functional test per test spec
   - Package each unit individually
   ```
5. They will reply with a quote (typically 3-5 business days)

## Expected Cost (20 units total)

| Item | COIN Lite x10 | Pro v2 x5 | Hub v2 x5 |
|------|---------------|-----------|-----------|
| PCB + SMT | $98 | $203 | $155 |
| Manual parts (sourced by mfg) | $30 | $15 | $40 |
| 3D enclosure | $30 | $20 | $50 |
| Box build labor | $50 | $40 | $60 |
| Firmware flash + test | $20 | $15 | $20 |
| **Subtotal** | **$228** | **$293** | **$325** |

**Estimated total: ~$846 + shipping (~$50) = ~$900**

## Timeline
- Quote: 3-5 business days
- Production: 15-20 business days
- Shipping (DHL): 3-5 days
- **Total: ~4 weeks from order to delivery**
