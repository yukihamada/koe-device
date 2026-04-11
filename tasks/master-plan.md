# Koe — Master Plan (Hawaii 2026-07-01)
*Locked 2026-04-11 · Enabler Inc. · 濱田祐樹*

---

## North Star
Place **19 objects** (16 Koe + 3 existing comparison speakers) in 濱田優貴's Hawaii house by **2026-06-25**. When ONE OK ROCK + manager arrive **2026-07-01** and stay **15 days**, every object is naturally touchable, each creating a different moment of discovery. After 15 days, at least **3 of 6 first users** trigger their success condition (§see personas.md).

## Budget
**$250,000 USD** upfront (revised 2026-04-11 to include Koe Sessions feature). Expected return: intangible brand value, peer-level design review from 濱田優貴 (ex-Mercari US CEO), potential unsolicited endorsement from ONE OK ROCK, business inquiry from manager, **and potentially a private Hawaii recording session captured on the devices themselves**.

## Major scope addition: Koe Sessions (Auto Record)
Based on the insight that ONE OK ROCK members will bring instruments and may naturally jam, Koe Amps and Picks add a **passive multi-track recording** feature:
- Amps have stereo MEMS mic arrays + 64GB NAND storage
- Picks have contact piezo for guitar body vibration capture
- On-device ML classifier distinguishes instrument from conversation (5-class)
- 6-track synchronized multi-track recording (<2ms inter-track)
- Local storage only, 30-day retention, private access via `koe.live/sessions/hawaii-2026-07`
- Artist owns all recordings, Koe claims zero rights
- See `tasks/sessions-consent-form.md` for legal framework
- Adds +1 week to Nordic Design House contract (+$15K), +$800 BOM

---

## The 19 Objects

### Koe originals (16 units, 5 SKUs)
| # | SKU | Count | Price equivalent | Serial range |
|---|-----|-------|------------------|--------------|
| 1 | **Stone** (Ø80×25) | 6 | $1,995 | ST-001 — ST-006 |
| 2 | **Stone Mini** (Ø50×15) | 4 | $895 | MN-001 — MN-004 |
| 3 | **Pick** (Reuleaux 40mm) | 2 | $595 | PK-001 — PK-002 |
| 4 | **Pendant** (Ø35 teardrop) | 2 | $795 | PD-001 — PD-002 |
| 5 | **Amp** (60×60×55) | 2 | $2,995 | AM-001 — AM-002 |

**Koe total value at retail:** $24,770

### Comparison shelf (3 existing speakers, ~$1,200)
- **Beoplay A1** ($250) — puck form direct comparison
- **Sonos Roam** ($180) — portable/outdoor comparison
- **Marshall Willen** ($120) — rugged casual comparison
- **+ TE Field Speaker** ($650) — design comparison

These exist alongside Koe in the shelf to communicate: "we know what the category looks like. We built something different."

### Accessories (for context/use diversity)
- 8× leather cord loops (for Stone Mini lanyard carry)
- 6× walnut wood stands (Hacoa) for shelf display
- 3× Qi wireless charging pads (kitchen/living/master bedroom)
- 2× waterproof neoprene pouches (for beach Pendant carry)
- 2× silicone guitar-body strap wrappers (for Pick attachment)
- 1× leather pouch per Stone (12 total) for travel carry

---

## Place Map — 濱田優貴's Hawaii House, 19 Object Placement

```
╔════════════════════════════════════════════════════╗
║  BEACH                                              ║
║  [Stone Mini #04] deck table                        ║
║  [Pendant #02]    beach sand pouch (nearby towel)  ║
║  [Marshall Willen] comparison, outdoor              ║
╠════════════════════════════════════════════════════╣
║  BEACHFRONT BEDROOM                                 ║
║  [Stone #05]  nightstand, wake/sleep                ║
║  [Pendant #01] dresser, for beach pickup           ║
╠════════════════════════════════════════════════════╣
║  LIVING ROOM (center of gravity)                    ║
║  [Stone #01]  coffee table — most touched          ║
║  [Stone #02]  bookshelf — art object                ║
║  [Stone #03]  side table by sofa                    ║
║  [Amp #01]    credenza — primary BGM                ║
║  [Beoplay A1] shelf — comparison                    ║
║  [Sonos Roam] shelf — comparison                    ║
╠════════════════════════════════════════════════════╣
║  KITCHEN / DINING                                   ║
║  [Stone #04]     counter — 濱田優貴's daily driver  ║
║  [Stone Mini #01] window — morning sun             ║
║  [TE Field]      comparison shelf                   ║
╠════════════════════════════════════════════════════╣
║  BACK BEDROOM (Ryota's room, assigned)              ║
║  [Stone #06]     nightstand — reading               ║
║  [Stone Mini #02] shelf — portable                  ║
╠════════════════════════════════════════════════════╣
║  THIRD BEDROOM (flex space)                         ║
║  [Stone Mini #03] dresser — visitor                 ║
╠════════════════════════════════════════════════════╣
║  HANARE (guest house / jam room)                    ║
║  [Pick #01]      clipped to guitar body             ║
║  [Pick #02]      spare                              ║
║  [Stone #07-08]  ceiling shelf — sync demo         ║
║  [Amp #02]       main listening position            ║
╚════════════════════════════════════════════════════╝

Total: 19 objects
 ├─ Koe originals: 16 (Stone×6, Mini×4, Pick×2, Pendant×2, Amp×2)
 └─ Comparison: 3 (Beoplay A1, Sonos Roam, Marshall Willen) + TE Field
```

---

## Shared Platform — Koe Board v1

**Critical decision:** All 5 Koe SKUs share the same electronics. Only enclosure and driver differ.

### Platform spec
| Component | Value |
|-----------|-------|
| SoC | nRF5340 (Nordic) |
| Wireless | BLE Audio LE + mesh 802.15.4 |
| Charging | Qi 5W wireless (every SKU) |
| NFC | NTAG216 passive tag (every SKU) |
| LiPo | varies per SKU (200-5000mAh) |
| Audio amp | TAS2563 smart amp + DSP |
| Driver | varies per SKU (see below) |
| Sensor | 3-axis accelerometer + capacitive top |
| FW | Single firmware, runtime profile selection |

### Driver per SKU
| SKU | Driver | Reason |
|-----|--------|--------|
| Stone | Tectonic BMR 40mm | Full range in small enclosure |
| Stone Mini | TangBand W1-1943S 28mm | Size-constrained |
| Pick | Piezo contact transducer | Contact mic, no audio-out |
| Pendant | Knowles SR-32453 20mm | Personal/ambient |
| Amp | Dayton RS100-4 + 2× Tectonic BMR | 3-way, higher power |

### Why this works
- **1 PCB design** = 1 Nordic Design House contract ($80K), not 5
- **1 firmware** = no per-SKU FW development
- **1 BOM core** = parts procurement lock
- **5 enclosure CAD files** = manageable for 11 weeks
- **5 driver subsystems** = more work but the rest is frozen

---

## Critical Path — 11 Weeks

### W1 (2026-04-13 — 2026-04-18) · Commits
**Deliverables:**
- [ ] Decision: 5-SKU platform approach locked ✅ (this document)
- [ ] Nordic Design House 1 selected ($80K, 6-week sprint)
- [ ] CNC vendor selected (山形小松 or Fictiv + Xometry parallel)
- [ ] FW engineer contracted (6 weeks, $25K)
- [ ] ID freelance contracted (2-week sprint, $15K)
- [ ] Stone Mini / Pick / Pendant / Amp CAD polished ← running in background as of 2026-04-11

**Blockers:**
- 濱田優貴's actual Hawaii address
- 濱田優貴's availability for day -2 briefing (2026-06-23)
- Budget $235K approved

### W2-3 (2026-04-20 — 2026-05-03) · Parallel kickoff
- PCB v1 schematic + layout (Nordic team, 1 week)
- All 5 CAD → CNC 試作 G-code generation (parallel 5 workflows)
- FW boot strap on nRF5340 Audio DK (pre-pilot hardware)
- ID renders + CMF specification (Space Gray anodize variants)
- Amazon US → Hawaii shipment of 3 comparison speakers (early deposit)

### W4-5 (2026-05-04 — 2026-05-17) · First hardware
- PCB v1 fabricated (JLCPCB, 30 boards)
- CNC v1 prototypes arrive (5 units, 1 per SKU)
- First touch test, first impression review
- FW drop on real hardware
- Initial latency measurements

### W6-7 (2026-05-18 — 2026-05-31) · Iteration
- CAD v2 based on v1 feedback (minor revisions)
- PCB v2 if needed (bugs from v1)
- FW integration: BLE Audio LE + mesh + OTA + dashboard
- Audio tuning per SKU (Dayton RS100 in Amp, BMR coupling in Stone)
- Fatigue / drop / salt fog tests

### W8-9 (2026-06-01 — 2026-06-14) · Production
- CNC 20 units fabrication (16 Koe + 4 spares)
- PCB assembly 20 boards
- Hand assembly (Tokyo workshop)
- 100h soak test per unit
- Final QA: each unit plays audio + charges + pairs + OTA
- Engraving: K + serial + "TOKYO · MMXXVI"
- Packaging: Hacoa wooden boxes, leather accessories
- **Ship deadline: 2026-06-13**

### W10 (2026-06-15 — 2026-06-21) · Transit
- DHL Tokyo → Hawaii, 5-7 days
- Customs clearance
- Koe admin dashboard live at `koe.live/admin/hawaii`
- Remote monitoring system tested
- 濱田優貴 pre-briefed (Signal/LINE call, 5 min)

### W11 (2026-06-22 — 2026-06-28) · On-site setup
- 濱田優貴 receives shipment
- Yuki (remote) monitors setup
- Each Stone placed per map
- Each unit tested on arrival (ping dashboard)
- Leather/wood accessories in place
- **Setup deadline: 2026-06-25**

### W12 (2026-06-29 — 2026-07-15) · The trial
- **2026-07-01: ONE OK ROCK + manager arrive**
- Daily dashboard check (remote)
- Silent period — no intervention unless broken
- Capture: any touches, any feedback 濱田優貴 reports
- **2026-07-15: guests depart**
- Post-mortem with 濱田優貴 (recorded call)

---

## Decision Gates

Each gate must pass before proceeding. If blocked, escalate to Yuki immediately.

| Gate | Date | Must pass |
|------|------|----------|
| **G0** | W1 end | 5-SKU CAD locked, Nordic DH signed, budget approved |
| **G1** | W3 end | PCB v1 ordered, FW boot works, CNC v1 ordered |
| **G2** | W5 end | First 5 prototype units functional, latency measured |
| **G3** | W7 end | FW integration complete (BLE + mesh + OTA + dashboard) |
| **G4** | W9 end | All 16 units assembled, 100h soak passed, QA 16/16 |
| **G5** | W10 end | Shipment arrived Hawaii, customs cleared |
| **G6** | W11 end | 16 units placed, all pinging dashboard, 濱田優貴 briefed |

If G1 fails (e.g., PCB broken), fall back to **"DK Edition version"**: use nRF5340 Audio DK boards inside each Koe enclosure, wired to driver. Uglier, works. Ships 1 week later.

If G4 fails (assembly blocked), reduce to 10 units (2×Stone, 2×Mini, 1×Pick, 1×Pendant, 2×Amp), ship partial set.

---

## Budget Breakdown ($235K)

| Category | $ | Notes |
|----------|---|-------|
| Nordic Design House (HW+FW incl. Sessions classifier) | 95,000 | 1 PCB, 1 FW, 7-week sprint (+1 week for Sessions) |
| ID freelance (5 SKUs) | 15,000 | 2-week sprint, Dribbble top or Takram Jr. |
| CNC prototyping (5 vendors × 5 units each) | 18,000 | Parallel risk reduction |
| FW engineer contract | 25,000 | 6 weeks embedded |
| PCBA 20 boards | 6,000 | JLCPCB SMT |
| Drivers (Tectonic, TangBand, Knowles, Dayton, Piezo) | 1,500 | 16 units worth |
| nRF5340 + LiPo + Qi + NFC modules | 1,200 | per BOM |
| **Sessions add-on**: 64GB NAND (×2 Amps) + Knowles MEMS mics (×2 Amps × 2) | 800 | Recording hardware |
| Legal: Tokyo IP law firm, consent form review | 2,000 | Recording rights framework |
| Packaging (Hacoa wood boxes, leather, cards) | 1,500 | 16 sets |
| Tokyo workshop assembly labor | 4,000 | 2 days × 2 people |
| Acoustic DSP tuning contractor | 8,000 | 5 SKUs, 1 week |
| Shipping Tokyo → Hawaii (DHL) | 500 | 1 box |
| Comparison shelf speakers | 1,200 | Beoplay A1 + Sonos Roam + Marshall + TE |
| Admin dashboard development | 3,000 | koe.live/admin/hawaii |
| Keynote 30-sec video production | 30,000 | Professional or crowd-sourced |
| 業務委託 (Legal, contracts, NDAs) | 5,000 | Basic IP cover |
| **Hawaii setup trip buffer** | 5,000 | Yuki may need to fly if things go wrong |
| **Contingency 15%** | 32,745 | Slack for fire-fighting |
| **TOTAL** | **251,045** | Revised 2026-04-11 with Sessions scope |

---

## Risk Register (Top 10)

| # | Risk | Prob | Impact | Mitigation |
|---|------|------|--------|-----------|
| 1 | 11 weeks too short for 5-SKU CAD | Med | Critical | Parallel vendors, reduce to 3 SKUs if needed |
| 2 | PCB v1 DOA | Low | High | Nordic DH has pre-certification, 2nd vendor on standby |
| 3 | FW BLE Audio LE not ready | Med | High | Use Nordic sample, skip UWB, plain BLE Audio as fallback |
| 4 | CNC delay | Med | Med | 3 vendors, buffer 1 week |
| 5 | 濱田優貴 unavailable during setup | Low | Critical | Backup: Yuki flies to Hawaii for 3 days W11 |
| 6 | ONE OK ROCK ignores all 16 units | Med | Med | Oki-san demonstrates at day 2, still delivers personas 5-6 |
| 7 | Manager rejects as "amateur" | Med | Med | Hacoa wooden box + serial + business card signals |
| 8 | Ship customs hold in Hawaii | Low | High | File 2 weeks early, formal invoice as "research prototypes" |
| 9 | Device dies in salt/humidity | Med | Med | Pendant IPX7 proven, others IPX4, conformal PCB coating |
| 10 | Budget overrun | Med | Med | 15% contingency + G4 fallback to 10 units |

---

## Success Criteria (Hard)

- [ ] 16/16 units functional at 2026-06-25
- [ ] All placed per map by 2026-06-25
- [ ] Zero device failures during 15-day stay
- [ ] Dashboard shows all 16 heartbeat every 5 min
- [ ] Remote OTA capability verified

## Success Criteria (Soft - per persona)

From `tasks/personas.md`:
- [ ] Taka touches at least 1 Stone for >10 min
- [ ] Toru asks about guitar/stage use
- [ ] Ryota orders one after Hawaii
- [ ] Tomoya notes sync accuracy to another member
- [ ] 濱田優貴 asks to keep his daily-driver Stone
- [ ] Manager emails business@koe.live within 30 days

**Target:** 3 of 6.
**Floor:** 濱田優貴 validates the product at peer level (=1 of 6 minimum).

---

## Post-Hawaii (what comes next)

### Aug 2026
- Debrief interviews with 濱田優貴 (1 hour call)
- Gather any captured ONE OK ROCK feedback
- Mass production decision: **proceed to 100 units** or **iterate more**
- Cost-down exercise (target production cost $350/unit → $250/unit)

### Sep 2026
- 100-unit commercial launch announcement
- Preorder page live at koe.live (already exists in skeleton)
- Press embargoed reach-out: Monocle, Wallpaper*, The Verge, Gadget Lab

### Nov 2026
- First 100 customer shipments
- Price: $1,995 USD / ¥300,000 JPY (Stone)
- SKU mix: 80 Stone, 10 Mini, 5 Pick, 3 Pendant, 2 Amp
- Distribution: koe.live direct + Reverb.com + Ikebe Gakki

### Q1 2027
- SKU-specific refinements based on 100-unit feedback
- Launch v2 of underperforming SKUs
- Soluna festival integration (leverage existing SOLUNA fest position)

---

## Open questions for 濱田祐樹

1. **濱田優貴's Hawaii address** (exact) — needed for DHL shipping manifest
2. **濱田優貴's LINE/Signal** — needed for direct comms
3. **Budget approval** ($235K) — timing of capital deployment
4. **Can Yuki fly to Hawaii W11** as backup setup hands? — contingency flag
5. **Manager identity** — who specifically is ONE OK ROCK's person?
6. **Does Toru bring a guitar** on vacation? — confirms Pick use case viability
7. **Legal: export clearance for prototype electronics** — any export control concerns?

---

## Files
- `tasks/prd-koe.md` — PRD, spec locked
- `tasks/design-system.md` — Design language v1.0 locked
- `tasks/personas.md` — First 6 user personas deep dive
- `tasks/master-plan.md` — THIS FILE
- `tasks/keynote.md` — 30-sec film script
- `tasks/oki-brief.md` — 濱田優貴 briefing document
- `tasks/koe-launch.md` — Timeline (older version, superseded by this)
