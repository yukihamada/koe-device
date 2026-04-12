# Koe Orchestra — Market Analysis

## Total Addressable Market (TAM)

### Core: Orchestras & Ensembles
- ~10,000 professional/semi-professional orchestras worldwide
- Average system spend: $10,000 (100-piece Orchestra Pack)
- **Core TAM: $100M**

### Adjacent Segments
| Segment | Global Count | Avg. System Size | Avg. Spend | TAM |
|---------|-------------|------------------|-----------|-----|
| Professional orchestras | 2,000 | Orchestra (100) | $9,500 | $19M |
| Semi-pro / regional orchestras | 8,000 | Chamber (20) | $2,200 | $18M |
| Bands (rock, jazz, pop) | 500,000+ | Band (5) | $650 | $325M |
| Houses of worship | 300,000+ | Band (5) | $650 | $50M* |
| Music schools & conservatories | 25,000 | Chamber (20) | $2,200 | $55M |
| Theater (Broadway, West End, touring) | 5,000 | Chamber (20) | $2,200 | $11M |
| Corporate AV / conferences | 50,000 | Band (5) | $650 | $32M |

*Houses of worship: conservative 25% adoption estimate

**Total expanded TAM: ~$500M**

## Current Solutions & Pricing

### Wired Systems
| Solution | Per-musician cost (100 ppl) | Total cost | Setup time | Limitations |
|----------|---------------------------|-----------|------------|------------|
| Dante network | $800-1,500 | $80K-150K | 4-8 hours | Cat6 cabling everywhere, network switches, stage boxes |
| Aviom personal monitor | $200-500 | $20K-50K | 2-4 hours | Proprietary, limited to 16-64 channels, wired |
| Allen & Heath ME-1 | $300-600 | $30K-60K | 3-6 hours | Wired Cat5 daisy chain |
| Behringer P16 | $100-200 | $10K-20K | 2-4 hours | 16 channels max, wired |

### Wireless Systems (Rx Only)
| Solution | Per-musician cost | Total cost | Latency | Limitations |
|----------|------------------|-----------|---------|------------|
| Shure PSM 1000 | $2,000+ | $200K+ | 3-5ms Rx | **No wireless Tx** — still need wired stage box |
| Sennheiser EW IEM G4 | $1,200 | $120K | 5-8ms Rx | No Tx, limited frequencies |
| Shure PSM 900 | $1,000 | $100K | 5ms Rx | No Tx, 20 ch max per freq band |

### Key Insight
**No existing wireless system does bidirectional (Tx + Rx).** Every "wireless IEM" system only handles the return path (mix to musician). The instrument-to-mixer path still requires XLR cables, stage boxes, and snake cables. Koe Orchestra eliminates both.

## Koe Disruption Vector

### Price Disruption: 10-20x cheaper
- Koe Orchestra (100 musicians, Tx+Rx): **$9,500**
- Nearest wireless competitor Rx-only (Shure PSM): $200,000+
- Nearest wired Tx+Rx (Dante): $80,000-150,000
- Price/performance ratio is unprecedented

### Setup Disruption: Zero to 60 seconds
| System | Setup for 100 musicians |
|--------|------------------------|
| Dante | 4-8 hours (cabling, network config, stage plots) |
| Aviom | 2-4 hours (Cat5 runs, rack mounting) |
| Shure PSM | 1-2 hours (frequency coordination, bodypack pairing) |
| **Koe Orchestra** | **< 1 minute** (power on Hubs, musicians clip on Pro) |

### Feature Disruption: Bidirectional wireless
- Only system that wirelessly captures instrument audio AND delivers monitor mix
- Built-in per-instrument DSP profiles (no external processing needed)
- Spatial awareness via UWB (Hub knows musician positions)
- Personal monitor mixes via Hub dashboard

## Go-to-Market Strategy

### Phase 1: Beachhead (Months 1-6)
**Target: Music schools and community orchestras**
- Price-sensitive: operating on limited budgets
- Tech-curious: younger conductors and music directors
- High volume: 25,000 music schools globally
- Forgiving: students and community players tolerate imperfections
- Word of mouth: music educators are tightly networked
- Entry product: Chamber Pack (20) at $2,200

### Phase 2: Expand (Months 6-18)
**Target: Houses of worship and small venues**
- 300,000+ churches/temples with live music programs
- Budget: typically $500-5,000 for audio equipment
- Decision maker: single worship leader or tech volunteer
- Entry product: Band Pack (5) at $650

### Phase 3: Professional (Months 12-24)
**Target: Professional orchestras, Broadway/West End, touring acts**
- Requires proven reliability track record from Phase 1-2
- Higher support expectations
- Larger deal sizes: Orchestra Pack at $9,500
- Potential for multi-system purchases (touring + rehearsal)

### Phase 4: Adjacent Markets (Months 18+)
- Corporate AV (wireless presenter + audience Q&A)
- Film/TV production (wireless talent monitoring)
- Sports coaching (real-time audio to players)
- Military/tactical (secure UWB comms)

## Competitive Moat

1. **UWB + BLE hybrid architecture** — No competitor combines UWB for Tx with Auracast for Rx. Patent-worthy topology.
2. **Open source hardware** — Community contributions, rapid iteration, trust (musicians can inspect the signal chain).
3. **Per-instrument DSP profiles** — Pre-tuned EQ/compression/gate per instrument type. Competitors require external processing.
4. **10x price advantage** — Even if a major competitor (Shure, Sennheiser) builds a similar system, their cost structure prevents matching Koe's price.
5. **Network effects** — More Pros in a venue = more value. Hub dashboard becomes the mixing surface.

## Financial Projections (Conservative)

| Year | Units (Pro) | Revenue | Key milestone |
|------|-----------|---------|---------------|
| Y1 | 2,000 | $200K | 100 music schools, 50 bands |
| Y2 | 15,000 | $1.5M | Church market entry, first professional orchestra |
| Y3 | 60,000 | $6M | International expansion, touring acts |
| Y5 | 250,000 | $25M | Market leader in wireless monitor systems |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| UWB regulatory differences by country | Medium | DW3000 is already certified in US/EU/JP; focus on certified markets first |
| BLE Auracast adoption is early | Low | nRF5340 supports Auracast natively; standard is ratified |
| Shure/Sennheiser launches competing product | Medium | 2-3 year head start; open source community; 10x price gap is hard to close |
| Audio quality concerns from professionals | High | AK5720 (24-bit) + PCM5102A (32-bit) are studio-grade; publish THD/SNR benchmarks |
| Battery life insufficient for long performances | Medium | 800mAh = 8+ hours; offer USB-C power bank clip accessory |
