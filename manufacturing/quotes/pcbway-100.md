# Koe Seed — PCBWay Manufacturing Quote (2026-04-10)

## PCB Quote (28mm x 28mm round, 2-layer FR-4, ENIG, green)

| Qty  | PCB Cost  | Per Board | Build Time |
|------|-----------|-----------|------------|
| 100  | $140.45   | $1.40     | 6-7 days   |
| 500  | $189.35   | $0.38     | 6-7 days   |
| 1000 | $283.09   | $0.28     | 6-7 days   |

Source: PCBWay Partner API, queried 2026-04-10.

## Full Cost Breakdown — 100 Units

| Item                        | Per Unit | x100     | Notes                              |
|-----------------------------|----------|----------|------------------------------------|
| PCB (PCBWay)                | $1.40    | $140     | 28mm round, 2L, ENIG, green       |
| Components (LCSC/DigiKey)   | $10.00   | $1,000   | ESP32-S3-MINI, codec, passives     |
| SMT Assembly                | $3.00    | $300     | PCBWay turnkey or JLCPCB           |
| 3D Print Enclosure          | $2.00    | $200     | SLA resin or injection mold amortized |
| Box Build / QC Labor        | $3.00    | $300     | Final assembly, flash, test        |
| Shipping (CN -> JP)         | $1.50    | $150     | DHL/FedEx estimated                |
| **Total**                   | **$20.90** | **$2,090** |                                |

## Full Cost Breakdown — 500 Units

| Item                        | Per Unit | x500     | Notes                              |
|-----------------------------|----------|----------|------------------------------------|
| PCB (PCBWay)                | $0.38    | $189     | Volume discount                    |
| Components (LCSC/DigiKey)   | $8.00    | $4,000   | Reel pricing at 500+               |
| SMT Assembly                | $2.00    | $1,000   | Setup cost amortized               |
| 3D Print / Injection Mold   | $1.50    | $750     | Mold amortization kicks in         |
| Box Build / QC Labor        | $2.50    | $1,250   |                                    |
| Shipping (CN -> JP)         | $1.00    | $500     |                                    |
| **Total**                   | **$15.38** | **$7,689** |                                |

## Full Cost Breakdown — 1000 Units

| Item                        | Per Unit | x1000    | Notes                              |
|-----------------------------|----------|----------|------------------------------------|
| PCB (PCBWay)                | $0.28    | $283     | Best volume price                  |
| Components (LCSC/DigiKey)   | $7.00    | $7,000   | Full reel pricing                  |
| SMT Assembly                | $1.50    | $1,500   | Fully amortized                    |
| Injection Mold Enclosure    | $1.00    | $1,000   | Mold cost ~$2K spread over 1000    |
| Box Build / QC Labor        | $2.00    | $2,000   |                                    |
| Shipping (CN -> JP)         | $0.80    | $800     |                                    |
| **Total**                   | **$12.58** | **$12,583** |                              |

## Summary

| Qty  | Total Cost | Per Unit | Target Retail ($65) Margin |
|------|------------|----------|---------------------------|
| 100  | $2,090     | $20.90   | 68%                       |
| 500  | $7,689     | $15.38   | 76%                       |
| 1000 | $12,583    | $12.58   | 81%                       |

## API Details

- Endpoint: `https://api-partner.pcbway.com/api/Pcb/PcbQuotation`
- API Key: `W1046165A 74D7895DE56D134C8063A54138502164`
- Raw response saved to `pcbway-raw.json`
