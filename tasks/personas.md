# Koe — First User Personas
*Version 1.0 · 2026-04-11*
*For: Hawaii prototype deployment, July 1-15, 2026*

---

## Why personas matter here

Koe Stone will be experienced by 6 people in a Hawaii beach house over 15 days. Each person has different tolerance for friction, different aesthetic reflexes, different context for evaluation. A product decision that makes Taka smile might bore Tomoya; a gesture that delights Oki might confuse the manager. This document maps each user's interior world so we can design for each moment.

**The goal is not that all 6 love Koe. The goal is that at least 2 love it without being asked, and the others don't hate it.**

---

## Persona 01 — Taka (Takahiro Moriuchi)
### Vocalist, ONE OK ROCK

**Age:** ~38
**Home:** Tokyo, LA, international
**Daily media:** Spotify Premium, Apple Music, Instagram, Tumblr
**Drives:** A modified Porsche, collects Rimowa luggage
**Watch:** Vintage Rolex, sometimes Apple Watch Ultra
**Style:** Raf Simons / Rick Owens / vintage tees
**Tech stack:** iPhone, MacBook Pro, Logic Pro, Apple TV

### Aesthetic reflex
Taka is a designer at heart. He has opinions about paper weight, typography, and how a microphone looks in his hand. He notices if a button travel is wrong. He has rejected merch designs over single-pixel alignment issues. He travels with a coffee setup that cost $4,000.

### What he cares about
- **Weight.** Things that feel cheap are invisible to him. He picks up a phone charger and decides in 2 seconds.
- **Silence.** His hotel room is always dark and quiet. He doesn't play music unless he means it.
- **Language.** He reads English fluently, thinks in Japanese, writes lyrics in both. He notices bad copy.
- **Authorship.** He respects makers. If Koe is "made by one guy in Tokyo", that's a story.

### What he rejects instantly
- Plastic
- Blinking blue LEDs
- Fake woodgrain
- The word "premium"
- Apps that want signups
- Anything that smells like a startup

### Ideal moment with Koe
Day 2, morning. Taka is alone in the kitchen with coffee. He sees the Stone on the counter near the French press. Picks it up. Feels the weight — "heavier than an iPhone." Turns it in his hand. Notices the K engraving. Places it back down. Doesn't even try to turn it on. It's already earned shelf space because **it looks like a thing he would buy.**

Later that day, he touches it accidentally while reaching for salt. Music starts. He laughs. Tries the other Stones.

### Demo scenario (Taka-specific)
- No demo. Never demo Taka anything. He finds things himself.
- Success = Taka posts it on his Instagram story 6 months later, unprompted.

### Risk
Taka is design-rejection-risk-#1. If even one element feels corporate or generic, he'll ignore the whole thing.

### Mitigation
- Packaging is a wooden Hacoa box, not a cardboard sleeve
- Weight is 380g (heavy)
- Engraving is laser, not printed
- Zero branding noise inside the box

---

## Persona 02 — Toru (Toru Yamashita)
### Lead Guitar, ONE OK ROCK

**Age:** ~38
**Home:** Tokyo, LA (tour base)
**Gear:** Kiesel 7-string, Mayones Regius, Fractal Audio Axe-FX III, Shure GLXD16+ wireless
**Daily tools:** iPhone, MacBook Pro, Cubase, Reaper, IK Multimedia
**Style:** Functional — tour-tested clothes, sneakers, minimal

### Aesthetic reflex
Toru is a gear pragmatist. He doesn't care how something looks — he cares whether it actually works on stage. He owns expensive gear, but only because it solves a real problem. He has returned $3000 pedals that had weird latency. He reads manuals.

### What he cares about
- **Latency.** He can *feel* 20ms of latency on a monitor setup. If Koe has latency, he'll notice in 5 seconds.
- **Reliability.** If something needs "re-pairing" more than once, it's dead to him.
- **Clean signal chain.** He doesn't want more boxes, more cables, more things to plug in.
- **Tour survival.** He thinks about drop tests, airport X-ray, hotel WiFi.

### What he rejects instantly
- Things labeled "audiophile" without measurements
- Wireless systems that "just work" (he knows they don't)
- Gear that needs firmware updates to basic features
- Consumer-grade materials on pro-use products

### Ideal moment with Koe
Day 4, evening. Toru brought his Axe-FX and a small rig to jam in the hanare. He plugs in, fires up the amp sim, plays a riff. He notices a small aluminum puck on the amp case. Picks it up.

Touches it. Music starts — but it's his own riff, coming from the Stone.

He stops playing. Picks up another Stone from the coffee table. Plays again. Both Stones play. He walks into the main house. The 3 Stones in the living room are also playing his riff, in perfect sync.

He says one sentence: "Yuki friend?"

### Demo scenario (Toru-specific)
- He might be the one person who asks how it works.
- Oki: "No idea, it just does that."
- That's enough.

### Risk
Toru's bar is **latency**. If the Bluetooth Audio LE mesh adds more than ~40ms of total latency, his reaction is "nice idea but unusable" and he's done.

### Mitigation
- Use BLE Audio LE with LC3 at 48kHz (~20ms theoretical)
- Mesh inter-device sync <2ms
- Stream-to-Stone via AirPlay 2 as fallback (slightly higher latency but rock-solid)
- Pre-test in the Hawaii house before arrival using a guitar rig similar to Toru's

---

## Persona 03 — Ryota (Ryota Kohama)
### Bass, ONE OK ROCK

**Age:** ~37
**Home:** Tokyo
**Daily rhythm:** Quiet, methodical, early riser
**Instrument:** Music Man Stingray, Sadowsky custom
**Style:** Muji / Beams Plus / understated

### Aesthetic reflex
Ryota is the quietest of the four. He notices things others miss. He's the one who reads the liner notes and researches the studio. He also happens to be a design thinker — he follows Monocle, reads Brutus magazine, likes Japanese craftsmanship.

### What he cares about
- **Craftsmanship.** Knows the difference between CNC and injection molding by touch.
- **Story.** Wants to know *where* and *who*.
- **Calmness.** Avoids flashy things. Appreciates quietness in product design.
- **Japanese identity.** Proud of Japanese makers. Would love a story like "guy in Tokyo making 100 speakers."

### What he rejects
- Marketing speak
- Flashy lighting effects
- Products that shout
- Anything that feels Western-minimal-startup (we're trying to avoid this — tricky)

### Ideal moment with Koe
Day 3, late afternoon. Ryota is reading in the second bedroom (the back one, quieter). He's finishing a book. On the nightstand is a Stone. He's glanced at it before but hasn't touched it.

He finishes his book. Reaches for coffee. Accidentally touches the Stone. Silence, then a Bach Cello Suite begins quietly. He doesn't move. He stays in the chair for 20 more minutes, listening.

He asks Oki that evening: "How is it made?"

Oki: "One guy in Tokyo. Aluminum. 100 of them."

Ryota: "Where can I buy one?"

### Demo scenario
- Passive. Don't show him. Let him find it in the quietest room.
- The back bedroom Stone is assigned to Ryota.

### Risk
Ryota is the highest-conversion-probability persona. If Koe disappoints him on *craftsmanship*, we lose the one person most likely to actually order.

### Mitigation
- CNC unibody aluminum (no seam visible)
- Weight distribution centered
- Subtle lenticular top dome (requires 5-axis CNC, visible in low-angle light)
- Hacoa wooden box
- Handwritten serial number (not just laser)

---

## Persona 04 — Tomoya (Tomoya Kanki)
### Drums, ONE OK ROCK

**Age:** ~37
**Home:** Tokyo
**Instrument:** Pearl Reference, custom snare collection
**Daily:** Gym, protein, sleep discipline
**Tech:** Modest — iPhone, headphones, that's it

### Aesthetic reflex
Tomoya is the rhythm engine. He feels time in ms. His ears are calibrated. But he's also the least gadget-y of the four — he doesn't buy cameras, he doesn't fuss over hi-fi. He appreciates things that work cleanly.

### What he cares about
- **Timing.** If the mesh is out of sync by >10ms, he'll notice — and it'll bother him physically.
- **Durability.** Drummers break things. He likes things that can survive a dropped drumstick.
- **Simplicity.** He'll put it down and walk away if it requires thinking.

### What he rejects
- Delicate things
- "Setup modes"
- Things that require holding his phone
- Anything that feels fragile

### Ideal moment with Koe
Day 7, mid-afternoon. Tomoya and Toru are in the hanare. Toru is noodling on guitar. Tomoya is drumming on his knees. The Stones in the room play Toru's guitar live.

Tomoya notices that the beat is perfectly in time across the Stones in both rooms.

He picks up a Stone, walks to the kitchen, and the music follows him — still in perfect time. He tests it: puts the Stone on the kitchen counter, walks back to the hanare. The main song continues, and the kitchen Stone is still perfectly locked.

He doesn't say anything. He puts both hands up in a small "nice" gesture toward Yuki's laptop on the shelf (thinking Yuki can see).

### Demo scenario
- The mesh sync accuracy is Tomoya's entire experience. If it fails, he's out.
- The 8-device sync demo is basically designed for Tomoya.

### Risk
Technical. If FW fails to maintain sub-10ms inter-device sync under real conditions (walls, humidity, interference), Tomoya's experience breaks and he tells the band "it's not quite there."

### Mitigation
- Factory-pair all units, test sync over 100h soak
- Use PTP-style mesh timing protocol
- Have a fallback: if any unit drops sync >10ms, it auto-mutes for 200ms and rejoins (smooth recovery)

---

## Persona 05 — Oki-san
### Host, tech-savvy friend

**Age:** ~40s (estimated)
**Location:** Lives in or near Hawaii house
**Relationship to Yuki:** Close friend, trusted
**Tech level:** Fluent — can troubleshoot, can install updates, understands OTA, BLE, mesh
**Role during Hawaii stay:** Host, day-to-day user, remote debug proxy, occasional demonstrator

### Aesthetic reflex
Unknown — to be learned. But if he's a tech-savvy friend of Yuki (Mercari CPO, infrastructure builder), he's likely:
- Appreciative of good engineering
- Not easily impressed by marketing
- Enjoys having "insider" access to prototypes
- Probably his own gear hobbyist (camera? audio? coding?)

### What he cares about
- **Being trusted** with something pre-release
- **Not breaking anything**
- **Being able to explain it** if asked
- **Helping his friend Yuki** succeed
- **Quiet presence** — not wanting to feel like a salesman to the guests

### What he rejects
- Having to perform / pitch to guests
- Too many instructions
- Things that embarrass him in front of guests (e.g., needing reboots)

### Ideal moment with Koe
Day 0 (before guests arrive). Oki sets up the 8 Stones per the map. He tests each one, listens, nods. He keeps Stone #3 (kitchen) for himself — plays music while cooking. By day -2 he's already a daily user.

When guests arrive Day 1, Oki is cooking dinner with Stone #3 playing quietly. Taka walks into the kitchen. "Yo Oki, what is this?" Oki: "Ah — Yuki's friend is testing these. Touch it." Hands over the Stone. Taka touches it. Music moves to Taka's hand. Oki keeps cooking.

Perfect.

### Demo scenario
- Oki is the demo vehicle. His job is to be natural. He has the brief (`tasks/oki-brief.md`) and understands enough to troubleshoot remotely.
- We give Oki dashboard access at `koe.live/admin/hawaii` so he can monitor.
- We let Oki keep Stone #3 after the trip as a thank-you.

### Risk
- Oki travels out of the house during guest stay → nobody demonstrates → guests never touch.
- Oki has a language barrier with English-speaking members → handoff conversation breaks.
- Oki feels pressured and over-demos → guests get suspicious.

### Mitigation
- Oki's brief explicitly says: "Just use them yourself. Don't sell."
- Pre-flight call between Yuki and Oki to align on tone (5 min, max)
- Remote Yuki backup: if guests arrive and nothing has been touched by day 3, Yuki calls Oki and asks him to play music from Stone #3 loudly during breakfast

---

## Persona 06 — The Manager
### Amuse Inc. or tour manager
*To be profiled further when we learn who specifically*

**Age:** 35-50, likely male, Japanese, possibly English-fluent
**Role:** Logistics, band welfare, merch/endorsement gatekeeper
**Daily:** Hundreds of decisions about what enters/exits band's world
**Tech:** Professional level — iPhone, MacBook, tour software, spreadsheets
**Business sense:** Sharp — sees 50+ products per year pitched for endorsements

### Aesthetic reflex
Managers think in terms of: cost, risk, brand fit, press value, scalability. They don't care about materials unless materials become a talking point. They care about **whether the product works reliably** because failures reflect on the band.

### What he cares about
- **Is it a real product?** Managers smell "one-guy-in-garage" from a mile away. Koe needs to read as **intentional**, not improvised.
- **Does it scale?** If it's 100 units this year, 1000 next year, that's a story. If it's always 100 forever, that's a collector item (still interesting, different deal).
- **Who else is endorsing it?** They want social proof. "Koe is in pilot with..." matters.
- **Liability.** If it breaks, who handles it?
- **Authorship attribution.** What does the band get credit for if they use it?

### What he rejects
- Amateur packaging
- Handwritten notes in the box (unless carefully calculated)
- Direct pitches from the maker ("Hi, I'm Yuki, I want your band to try this")
- Ambiguous business terms
- Gifts without clarity on obligations

### Ideal moment with Koe
Day 8. The manager has seen Taka and Toru touching the Stones. He's curious but professionally reserved. He picks one up when the room is empty. Notices:
- The weight
- The engraving "K O E · 007 · 012" (he notices the low serial number)
- The business card under it
- The card's business email

He doesn't touch the top. He puts it back. Pockets the card.

Two weeks after the trip, he emails business@koe.live. Subject: "ONE OK ROCK / introduction".

### Demo scenario
- He is **never** directly pitched.
- His entire experience is: the product is in the environment, he investigates on his own, he finds a clean business contact channel, he chooses when to engage.
- Zero pressure.

### Risk
The manager is the hardest to win. He's designed to say no. If even one element reads "amateur" he'll file Koe as "nice hobby, not ready."

### Mitigation
- Packaging is Hacoa wooden box (signals: real manufacturing, Japan proud)
- Serial numbers are low 001-012 (signals: early, scarce)
- Business card exists (signals: professional infrastructure)
- `koe.live/business` is live and well-written (signals: real company)
- Email response time < 24h (we set up a dedicated inbox)
- When he emails, response is from "Yuki Hamada, Enabler Inc." with a clean signature — not a cold pitch.

---

## Cross-persona design decisions

Each design decision was made to satisfy a specific persona's requirement. This is the mapping:

| Design choice | Who drove it | Why |
|---------------|--------------|------|
| 380g aluminum unibody | Taka | Weight signals premium |
| <2ms mesh sync | Tomoya | Rhythm calibration |
| BLE Audio LE LC3 | Toru | Low latency for jamming |
| Hacoa wooden box | Ryota | Japanese craftsmanship story |
| Zero buttons | Oki | Simple enough to leave around |
| Serial numbers 001-012 + business card | Manager | Real product signals |
| No app / no account | All 6 | Nobody wants setup |
| Matte Space Gray only | Taka | Design discipline |
| English voice prompt only | Manager/members | Common language |
| `koe.live/business` page | Manager | Professional channel |

Every feature must be traceable to a persona. If it doesn't serve one, cut it.

---

## What we're NOT doing (and why)

### Not targeting "audiophiles"
Audiophiles are forum-hostile, spec-obsessed, and non-emotional buyers. Koe sells emotion-first. If an audiophile buys one, great, but we don't design for them.

### Not pitching "smart home" or "multi-room speaker"
Sonos owns that category. Koe is not a Sonos. Koe is a **worry stone that plays music**. Different category.

### Not catering to "casual listeners"
Casual listeners buy $50 Bluetooth speakers. They don't pay $1,995. Our floor is emotionally-committed aesthetes with disposable income.

### Not promising ecosystem
We are **100 units** for now. Period. Buyers know they're buying a closed edition. That's part of the appeal. We don't promise "more colors coming" or "app coming" because it'd break the finality.

---

## Success metrics by persona

| Persona | Success = |
|---------|-----------|
| Taka | Unprompted social post OR mentions Koe in an interview within 6 months |
| Toru | Asks about tour / stage use specifically |
| Ryota | Orders one from koe.live after Hawaii |
| Tomoya | Mentions the sync accuracy to any of the other 3 |
| Oki | Asks to keep his Stone + uses it monthly for 1 year |
| Manager | Emails business@koe.live within 30 days |

**Soft target:** 3 out of 6 trigger their success condition.
**Hard failure:** All 6 politely ignore Koe. (Mitigation: Yuki personally follows up via LINE/Signal with Oki 2 weeks after the trip.)
