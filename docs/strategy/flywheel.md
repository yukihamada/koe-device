# Koe Seed Flywheel (Bezos Method)

## The Flywheel

```
More festivals use Seed
        ↓
More attendees experience personal audio
        ↓
Attendees demand it at OTHER festivals ("Why don't you have Koe?")
        ↓
More festivals adopt Seed (social pressure / FOMO)
        ↓
Unit cost drops (volume manufacturing)
        ↓
Lower price → even smaller events can afford it
        ↓
More festivals use Seed ← (loop)
```

## Accelerators (what spins the flywheel faster)

### 1. Seed Rental Marketplace
Festivals happen on different weekends. A 1000-Seed pack sits idle 340 days/year.
→ Build a marketplace where festivals rent Seed packs from each other.
→ Pack owner earns passive revenue. Renter pays $2/Seed/event instead of buying.
→ **This turns every customer into a supply-side participant.**

### 2. Data as a Service
Every Seed is a data point: location (via BLE RSSI triangulation), usage time, popular zones.
→ Sell anonymized crowd analytics to festival organizers.
→ "75% of your crowd was in Zone B during the headliner. Move the food trucks there next year."
→ **Data revenue subsidizes hardware cost.**

### 3. Sponsorship Layer
Each Seed plays audio. Between sets, play a 5-second sponsor message.
→ "This Koe Seed experience is brought to you by Red Bull."
→ Sponsor pays $0.50/Seed/event. 5000 Seeds = $2,500/event in sponsor revenue.
→ **Sponsors subsidize the Seed cost for festivals. Festival gets Seeds for free.**

## The Bezos Long Game

### Year 1: Product-Market Fit
- Deploy at SOLUNA FEST 2026 (own festival, controlled environment)
- Deploy at 2-3 partner festivals (offered free/discounted for testimonials)
- Collect data: attendee satisfaction, loss rate, battery real-world performance
- 10,000 Seeds manufactured

### Year 2: Marketplace + Scale
- Launch Seed Rental Marketplace (SaaS, 15% take rate)
- 10 festivals using Koe. 50,000 Seeds in circulation.
- Unit cost drops to $12 (10K volume from JLCPCB)
- Introduce subscription: $500/month for 1000 Seeds + management dashboard

### Year 3: Platform
- Koe is the "AWS of venue audio"
- API: third-party apps can push audio to Seeds (translator apps, accessibility, emergency alerts)
- Government contracts: emergency broadcast to every person in a building/stadium
- 500,000 Seeds in circulation. Revenue: $5M ARR (mix of hardware + SaaS + data)

## Key Metrics (Bezos would track these)

| Metric | Definition | Target Y1 |
|--------|-----------|-----------|
| Seeds Deployed | Total active Seeds at events | 10,000 |
| Attendee NPS | "Would you want Koe at every festival?" | >70 |
| Reuse Rate | Events per Seed per year | >5 |
| Loss Rate | % Seeds not returned per event | <5% |
| Audio Uptime | % of event duration with uninterrupted audio | >99% |
| Unit Cost | Fully loaded manufacturing cost | <$20 |
| CAC | Customer acquisition cost per festival | <$500 |
| LTV | Revenue per festival customer over 3 years | >$15,000 |

## The Empty Chair (Customer Voice)

Before every product decision, ask:

**Festival organizer**: "Does this save me money or make my attendees happier?"
**Attendee**: "Does this make the music sound better without me doing anything?"
**Sponsor**: "Does this give me a guaranteed touchpoint with every attendee?"

If the answer to all three is yes → build it.
If any is no → don't build it.
