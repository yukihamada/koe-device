# Koe Device -- Manual Parts Sourcing Guide

Parts listed here are NOT included in the JLCPCB PCBA order and must be
purchased separately, then attached during final assembly.

## Parts List

### 1. LiPo Battery (BT1)

| Spec | Value |
|------|-------|
| Model | 802535 |
| Voltage | 3.7V nominal (4.2V full, 3.0V cutoff) |
| Capacity | 800mAh |
| Dimensions | 8 x 25 x 35 mm |
| Connector | JST PH 2.0mm 2-pin (or bare wires) |
| Weight | ~15g |

**Where to buy:**

| Source | Search Term | Est. Price | Min Qty | Link |
|--------|------------|------------|---------|------|
| AliExpress | "802535 lipo 800mah" | $2.00-3.00 | 1 | https://www.aliexpress.com/wholesale?SearchText=802535+lipo+800mah |
| AliExpress | "802535 3.7v battery JST" | $2.50-3.50 | 1 | https://www.aliexpress.com/wholesale?SearchText=802535+3.7v+battery+JST |
| Amazon JP | "802535 リポバッテリー" | 500-800 JPY | 1 | https://www.amazon.co.jp/s?k=802535+lipo |
| Adafruit | "Lithium Ion Polymer Battery 3.7v 800mAh" | $7.95 | 1 | https://www.adafruit.com/product/2011 |

**Important notes:**
- Verify polarity before connecting. There is no standard for JST PH polarity
  across battery manufacturers. Red = positive, black = negative.
- If the battery has a JST connector, verify it matches the PCB pad spacing.
  If using bare wires, solder directly to the BT1 pads.
- Buy batteries with built-in protection circuit (PCM/BMS) for safety.
  The protection circuit prevents over-discharge, over-charge, and short circuit.
- Shipping restrictions: LiPo batteries may have air freight restrictions.
  AliExpress sellers often ship by sea, adding 2-4 weeks to delivery.

**Estimated cost: $2.50/unit** (AliExpress, qty 10+)

---

### 2. Micro Speaker (SPK1)

| Spec | Value |
|------|-------|
| Type | Micro speaker |
| Dimensions | 15 x 10 x 3 mm (1510) |
| Impedance | 8 ohm |
| Power | 0.5W |
| Connection | Solder wires to PCB pads |

**Where to buy:**

| Source | Search Term | Est. Price | Min Qty | Link |
|--------|------------|------------|---------|------|
| AliExpress | "1510 speaker 8 ohm" | $0.30-0.60 | 5 | https://www.aliexpress.com/wholesale?SearchText=1510+speaker+8+ohm |
| AliExpress | "15x10mm speaker 0.5W" | $0.40-0.70 | 5 | https://www.aliexpress.com/wholesale?SearchText=15x10mm+speaker+0.5W+8ohm |
| Amazon JP | "小型スピーカー 1510 8ohm" | 300-500 JPY (5個) | 5 | https://www.amazon.co.jp/s?k=小型スピーカー+1510 |
| Taobao (1688) | "1510喇叭 8欧" | 0.15-0.30 RMB | 50 | https://s.1688.com/selloffer/offer_search.htm?keywords=1510喇叭8欧 |

**Important notes:**
- These are commodity parts with very little variation between sellers.
- Buy a few extras -- they are fragile and wires break easily.
- Speaker connects to MAX98357A output via two solder pads on the PCB.
  Polarity does not matter for single-frequency audio, but maintaining
  consistent polarity across units is good practice.

**Estimated cost: $0.50/unit** (AliExpress, qty 10+)

---

### 3. USB-C Connector (J1) -- Backup Source

The USB-C connector (LCSC C168688) is included in the JLCPCB BOM and should
be assembled by JLCPCB. However, this part occasionally goes out of stock.

**If out of stock at JLCPCB:**

| Source | Part Number | Est. Price | Link |
|--------|------------|------------|------|
| LCSC direct | C168688 | $0.25 | https://www.lcsc.com/product-detail/C168688.html |
| LCSC alt | C2765186 | $0.30 | https://www.lcsc.com/product-detail/C2765186.html |
| AliExpress | "USB C 16pin SMD connector" | $0.10-0.20 | https://www.aliexpress.com/wholesale?SearchText=USB+C+16pin+SMD |

**If hand-soldering:** USB-C connectors have very fine pitch pins. Use flux,
fine-tip iron (0.5mm or chisel), and magnification. Drag soldering recommended.

---

## Cost Summary (Manual Parts)

| Part | Unit Cost | Notes |
|------|-----------|-------|
| Battery (802535 800mAh) | $2.50 | AliExpress, qty 10+ |
| Speaker (1510 8ohm 0.5W) | $0.50 | AliExpress, qty 10+ |
| USB-C connector (backup) | $0.25 | Only if JLCPCB stock-out |
| **Total manual parts** | **$3.00** | Per unit |

## Recommended Order (for 10 units)

| Part | Qty | Source | Est. Total |
|------|-----|--------|------------|
| 802535 LiPo 800mAh w/ JST PH | 12 | AliExpress | $30 |
| 1510 Speaker 8ohm 0.5W | 15 | AliExpress | $7 |
| 30AWG silicone wire (red+black) | 1 roll each | AliExpress | $3 |
| **Total** | | | **~$40** |

Order extra batteries and speakers to account for damage during assembly
and testing.

## Lead Times

| Source | Shipping Method | Typical Delivery |
|--------|----------------|-----------------|
| AliExpress (China) | Standard | 15-30 days |
| AliExpress (China) | AliExpress Standard | 10-20 days |
| Amazon JP | Prime | 1-2 days |
| Adafruit (US) | Standard | 5-10 days |

**Recommendation:** Order manual parts at the same time as JLCPCB PCBs so
everything arrives together. JLCPCB express shipping (DHL) takes ~10 days,
while AliExpress standard takes ~15-20 days. Start the AliExpress order first.
