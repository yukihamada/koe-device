# Koe Seed — PCBWay Order Summary (2026-04-10)

## PCB Order — 100 Units

| Item | Cost |
|------|------|
| PCBWay PCB (28mm round, 2-layer, ENIG, green, 100pcs) | $140.45 |

## Full BOM Cost Estimate — 100 Units

| Item | Per Unit | x100 | Notes |
|------|----------|------|-------|
| PCB (PCBWay) | $1.40 | $140.45 | 28mm round, 2L FR-4, ENIG, green |
| Components (LCSC/DigiKey) | $10.00 | $1,000.00 | ESP32-S3-MINI, codec, passives |
| SMT Assembly | $3.00 | $300.00 | PCBWay turnkey |
| 3D Print Enclosure | $2.00 | $200.00 | SLA resin black |
| Box Build / QC Labor | $3.00 | $300.00 | Final assembly, flash, test |
| Shipping (CN -> JP, DHL) | $1.50 | $150.00 | |

## Total Order Cost

| | |
|---|---|
| **Total (100 units)** | **$2,090.45** |
| **Per unit** | **$20.90** |
| **Target retail ($65)** | **68% margin** |

## Timeline

| Phase | Duration | Date (est.) |
|-------|----------|-------------|
| PCB fabrication | 6-7 days | Apr 10-17 |
| Component sourcing | 3-5 days | Apr 10-15 |
| SMT assembly | 5-7 days | Apr 17-24 |
| Box build + QC | 3-5 days | Apr 24-29 |
| Shipping (DHL CN->JP) | 3-5 days | Apr 29 - May 4 |
| **Total lead time** | **~3.5 weeks** | **~May 4, 2026** |

## Place Order

```bash
python3 manufacturing/order.py --order
```

This will:
1. Validate all Gerber/BOM/CPL files
2. Get a live quote from PCBWay API (if `PCBWAY_API_KEY` is set)
3. Confirm and submit the order
4. If no API key, opens PCBWay in browser for manual order

## Quote Source

- PCBWay Partner API, queried 2026-04-10
- Raw response: `manufacturing/quotes/pcbway-raw.json`
- Detailed breakdown: `manufacturing/quotes/pcbway-100.md`
