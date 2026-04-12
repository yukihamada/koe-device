# Koe Device — Prototype BOM (Hawaii Deployment)

**Deadline**: Must arrive in Hawaii before **July 1, 2026** (ONE OK ROCK arrival)
**Order by**: June 1, 2026 at the latest (allow 2–4 weeks domestic shipping, 3–5 weeks AliExpress)
**Today**: April 12, 2026 → ~80 days remaining

---

## A. Amp Prototype (ESP32-S3, firmware v0.3.1 ready)

Firmware already compiles and runs on ESP32-S3. These are breadboard/DevKit units
for initial deployment at Oki's house before custom PCBs ship.

| # | Part | Qty | Unit USD | Subtotal | Source | Part # / Search |
|---|------|-----|----------|----------|--------|-----------------|
| 1 | ESP32-S3-DevKitC-1-N8R8 (8MB flash, 8MB PSRAM) | 4 | $14.00 | $56.00 | Mouser | [919-ESP32-S3-DEVKITC1N](https://www.mouser.com/ProductDetail/Espressif-Systems/ESP32-S3-DevKitC-1-N8R8) |
| 2 | INMP441 I2S MEMS microphone module (breakout) | 8 | $2.50 | $20.00 | AliExpress | search: "INMP441 I2S microphone module" |
| 3 | MAX98357A I2S DAC + Class-D amp breakout | 4 | $4.95 | $19.80 | Adafruit | [Adafruit #3006](https://www.adafruit.com/product/3006) |
| 4 | WS2812B addressable RGB LED (5mm through-hole or module) | 8 | $0.50 | $4.00 | AliExpress | search: "WS2812B LED module 5mm" |
| 5 | USB-C power supply 5V 2A (wall adapter) | 4 | $6.00 | $24.00 | Amazon | search: "5V 2A USB-C power adapter" |
| 6 | USB-C cable 1m | 4 | $2.00 | $8.00 | Amazon | search: "USB-C cable 1m" |
| 7 | Breadboard 830-tie-point | 4 | $3.00 | $12.00 | Amazon | search: "830 breadboard" |
| 8 | Dupont jumper wire set M-M/M-F 20cm | 2 | $4.00 | $8.00 | Amazon | search: "jumper wire 40pcs dupont" |
| 9 | Project enclosure ~65×58×35mm (ABS) | 4 | $4.00 | $16.00 | Amazon | search: "ABS project box 65x58mm" |

**Amp Subtotal: $167.80**

### Wiring notes (DevKit → breakouts)
```
INMP441 (mic, x2 per unit):
  VDD → 3.3V    GND → GND
  BCLK → GPIO14   WS → GPIO15
  SD   → GPIO32   L/R → GND (left ch) / 3.3V (right ch)

MAX98357A (speaker amp):
  VIN → 5V      GND → GND
  BCLK → GPIO26  LRC → GPIO27  DIN → GPIO25
  SD (shutdown) → GPIO21 (active HIGH = on)

WS2812B:
  DIN → GPIO2    VCC → 5V    GND → GND
```

---

## B. Stone Prototype (nRF5340-DK, Auracast BLE Audio testing)

The Stone firmware targets nRF5340 running Zephyr RTOS with LC3 BLE Audio LE broadcast (Auracast).
DevKit is needed for firmware development/testing before CNC aluminium units are built.

| # | Part | Qty | Unit USD | Subtotal | Source | Part # |
|---|------|-----|----------|----------|--------|--------|
| 1 | nRF5340-DK (Nordic official dev kit) | 2 | $65.00 | $130.00 | Mouser | [949-NRF5340DK](https://www.mouser.com/ProductDetail/Nordic-Semiconductor/nRF5340-DK) |
| 2 | 3W full-range speaker driver 4ohm (50mm) | 2 | $4.00 | $8.00 | AliExpress | search: "3W 4ohm 50mm full range speaker" |
| 3 | PAM8403 5V stereo Class-D amp module | 2 | $2.00 | $4.00 | AliExpress | search: "PAM8403 module 5V" |
| 4 | USB-A to Micro-B cable (nRF5340-DK power) | 2 | $3.00 | $6.00 | Amazon | search: "USB micro-B cable" |

**Stone Subtotal: $148.00**

---

## C. Pick Prototype (Guitar onset detection)

Pick attaches to guitar body. Piezo detects string onset → BLE event to Amp unit → session trigger.

| # | Part | Qty | Unit USD | Subtotal | Source | Part # / Search |
|---|------|-----|----------|----------|--------|-----------------|
| 1 | ESP32-C3 SuperMini (BLE 5.0, USB-C, 4MB flash) | 4 | $3.50 | $14.00 | AliExpress | search: "ESP32-C3 SuperMini" |
| 2 | Piezoelectric transducer disk 27mm | 8 | $0.40 | $3.20 | AliExpress | search: "piezo disk 27mm buzzer transducer" |
| 3 | 1MΩ resistor 0.25W (piezo load) | 20 | $0.02 | $0.40 | AliExpress | search: "1M ohm resistor pack" |
| 4 | 100nF ceramic capacitor (ADC filter) | 20 | $0.02 | $0.40 | AliExpress | search: "100nF 0.1uF ceramic capacitor pack" |
| 5 | Black silicone strap 20mm wide × 300mm | 4 | $2.00 | $8.00 | AliExpress | search: "black silicone strap 20mm watch band" |
| 6 | LiPo battery 301230 3.7V 80mAh | 4 | $3.00 | $12.00 | AliExpress | search: "lipo 301230 80mah 3.7v" |
| 7 | TP4056 USB-C LiPo charger module | 4 | $1.00 | $4.00 | AliExpress | search: "TP4056 USB-C charger module" |
| 8 | Double-sided foam tape 3M 1mm | 1 roll | $5.00 | $5.00 | Amazon | search: "3M 9088 foam tape" |

**Pick Subtotal: $47.00**

---

## D. Shared Consumables & Tools

| # | Part | Qty | Unit USD | Subtotal | Source |
|---|------|-----|----------|----------|--------|
| 1 | USB-C UART programmer (CP2102) | 2 | $5.00 | $10.00 | Amazon |
| 2 | Anti-static mat + wrist strap | 1 | $12.00 | $12.00 | Amazon |
| 3 | Soldering iron (if not available on-site) | 1 | $25.00 | $25.00 | Amazon |
| 4 | 60/40 solder wire 0.8mm | 1 | $8.00 | $8.00 | Amazon |

**Consumables Subtotal: $55.00**

---

## Total BOM Summary

| Category | Subtotal |
|----------|----------|
| A. Amp prototype (×4 units) | $167.80 |
| B. Stone prototype (×2 units) | $148.00 |
| C. Pick prototype (×4 units) | $47.00 |
| D. Shared consumables/tools | $55.00 |
| **Grand Total** | **$417.80** |

Shipping estimate (AliExpress standard to Hawaii): +$30–50
**Total with shipping: ~$450–470**

---

## Recommended Order Sequence

### Week 1 (order by April 19, 2026) — Long-lead items first

1. **nRF5340-DK × 2** from Mouser (949-NRF5340DK)
   - Lead time: in-stock at Mouser, 3–5 business days US domestic
   - Hawaii delivery via UPS/FedEx: ~1 week total
   - Cost: $130.00

2. **ESP32-S3-DevKitC-1-N8R8 × 4** from Mouser
   - In-stock, 3–5 business days
   - Cost: $56.00

3. **AliExpress bundle order** (combine to minimize shipping):
   - INMP441 modules × 8
   - WS2812B LED modules × 8
   - ESP32-C3 SuperMini × 4
   - Piezo disks × 8
   - Resistors, capacitors, silicone straps, LiPo batteries, TP4056 chargers
   - Expected delivery: 3–5 weeks (arrive ~mid-May)

### Week 2 (order by April 26, 2026) — US domestic

4. **Adafruit MAX98357A × 4** (Adafruit #3006)
   - Adafruit domestic ship: 3–5 business days
   - Cost: $19.80

5. **Amazon bundle**:
   - USB-C power supplies, cables, breadboards, jumper wires, project boxes
   - Soldering supplies, programmer dongles
   - Prime delivery: 1–2 days

### Buffer
- All parts should be in hand by **June 1, 2026** at the latest
- Allows 4 weeks for assembly, firmware flashing, and testing before June 28 deployment deadline

---

## Notes

- **N8R8 vs N8R2**: Use N8R8 (8MB PSRAM) for DevKit units — firmware audio ring buffer benefits from PSRAM
- **INMP441 orientation**: Order mic L/R as separate channels. One unit per side → set L/R pin accordingly (GND = left, 3.3V = right)
- **Pick BLE**: ESP32-C3 SuperMini firmware not yet written; use threshold-based ADC onset detection → BLE GATT notify to Amp unit
- **Stone Auracast**: nRF5340-DK requires Zephyr SDK + nRF Connect SDK. Build with `west build -b nrf5340dk/nrf5340/cpuapp`
