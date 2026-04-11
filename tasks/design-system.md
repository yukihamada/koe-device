# Koe Design System — v1.0
*Locked: 2026-04-11*
*Owner: 濱田祐樹*

---

## 0. Design Philosophy

### Core Tenet
**"The absence of things."**

Koe is designed by removing, not by adding. Every element must justify its existence against silence, blankness, and stillness. If a feature, button, word, label, color, or gesture cannot earn its place, it is cut.

### Inspirations
- **Dieter Rams** — "Less, but better"
- **Naoto Fukasawa** — "Super-normal"
- **Jony Ive** — Aluminum unibody, the inevitable form
- **Teenage Engineering** — Material-first, toy-as-instrument
- **Leica M** — Haptic weight, serial numbers as ritual
- **Japanese stonecraft** — River-worn pebbles, worry stones, 数寄

### Anti-patterns
- ❌ Feature lists
- ❌ "AI-powered" messaging
- ❌ Gradients on brand surfaces
- ❌ Stock photography
- ❌ App icons with drop shadows
- ❌ Exclamation marks
- ❌ Emoji in product UI
- ❌ Corporate blue (#007AFF, #1DA1F2, etc.)
- ❌ "Made in China" aesthetics
- ❌ Glossy plastics

---

## 1. Brand Mark

### Logotype: `K O E`
- Single word. Three letters. All uppercase.
- Rendered in **Inter**, weight 100 (Thin), letter-spacing **0.35em**.
- Never abbreviated to "K", never extended to "KOE STONE" or "Koe™".
- Trademark symbol: banned on product surfaces. Allowed only in legal fine print.

### Icon Mark (for NFC, Qi pad, favicon)
- Single character **`K`** set in Inter Thin (weight 100).
- Minimum size: **8mm** (below this, omit the mark).
- Always rendered in a single color (no fills, no outlines, no drop shadows).

### Wordmark examples
| Context | Form |
|---------|------|
| Website header | `K O E` (thin, 0.35em tracking) |
| Product engraving | `K O E` + serial on a single line, e.g. `K O E · 001 · 100` |
| Packaging label | `K O E` centered on card |
| Press signature | `Koe, by Enabler Inc., Tokyo` |

**Never use:** bold, italic, underline, outline, emoji, reversed-out dropshadow, metallic effects.

---

## 2. Color System

### Primary palette — only 3 colors exist
| Name | Hex | Use |
|------|-----|-----|
| **Void** | `#0a0a0a` | Backgrounds, product body absence, infinite space |
| **Breath** | `#e8e8e8` | Text, product anodize hairline highlight |
| **Pulse** | `#8B5CF6` | Accent — used sparingly, only for moments of action |

That's it. No secondary palette. No semantic colors (success/warning/error). No light theme.

### Accent usage rules
- **Pulse (#8B5CF6)** is used only for:
  - LED pulse on device wake
  - Limited-edition badge on website
  - Keynote final frame text
  - CTA primary hover state
- Never used for body text, borders, backgrounds, or logos.
- **If in doubt, don't use Pulse.**

### Product finish (physical CMF)
- **Space Gray hard anodize** (closest Pantone: 432C, hex equivalent `#2a2a2e`)
- **One color only.** No black, silver, gold, titanium, rose. Never.
- Hairline brush direction: radial, centered on top face.
- Laser engraving: clean (0.1mm line width), no fill, no shadows.

---

## 3. Typography

### Only 1 typeface: **Inter**
- Weights allowed: **100 (Thin)**, **200 (ExtraLight)**, **300 (Light)**, **400 (Regular)**, **500 (Medium)**
- Weights banned: 600, 700, 800, 900 (bold)
- Italic: **banned**
- Source: Google Fonts (or self-host for production)

### Type scale
| Level | Size | Weight | Tracking | Usage |
|-------|------|--------|----------|-------|
| Display | clamp(3rem, 9vw, 8rem) | 100 | -0.05em | Hero "Koe" |
| H1 | clamp(2rem, 5vw, 3.5rem) | 100 | -0.03em | Page titles |
| H2 | clamp(1.4rem, 3vw, 2.4rem) | 200 | -0.02em | Section headers |
| H3 | 1.5rem | 200 | -0.02em | Spec card values |
| Body | 1rem | 300 | 0 | Paragraphs |
| Small | 0.82rem | 300 | 0 | Spec card subs |
| Label | 0.62rem | 500 | 0.3em (uppercase) | Eyebrows, badges |
| Mono | N/A | banned | N/A | We don't use code fonts |

### Japanese typography
- Primary: **Hiragino Sans** (default on Mac/iOS)
- Fallback: System default
- Weights match Latin rules (100-500 only)
- Kerning: trust the font (no manual adjustment)

### Copy rules
- **1 sentence, 1 idea.** If a sentence needs a comma, it probably should be 2 sentences.
- **Max 14 words per headline.**
- **Max 3 lines per body paragraph** on web.
- **No exclamation marks.** Ever.
- **No emoji** in product-facing surfaces.

---

## 4. Motion

### Principle
Motion should feel like **physical objects at rest**, not UI animation.

### Easings
- Default: `cubic-bezier(0.22, 1, 0.36, 1)` — out-expo, feels like a heavy object settling
- Fast interaction: `cubic-bezier(0.34, 1.56, 0.64, 1)` — slight overshoot for touch
- Never: linear, ease-in-out, spring, bounce

### Durations
| Context | ms |
|---------|-----|
| Hover | 150 |
| Click/tap response | 200 |
| Page transitions | 400 |
| Hero fade-ins | 600 |
| LED device pulse | 1500 (2 cycles/sec) |
| Breathing/idle animations | 6000 |

### Banned motion
- ❌ Bounce on landing
- ❌ Auto-rotating 3D models (OK for product viewer, NOT for hero)
- ❌ Parallax backgrounds
- ❌ Scroll-triggered letter reveals
- ❌ Cursor trails
- ❌ Auto-play video with sound

---

## 5. Iconography

### Rule: **We don't use icons.**

Icons are a shortcut for when words fail. Koe does not use icons in UI, marketing, or product. We use either:
- **Actual language** (one or two words)
- **Photography** (a single hand, a single object)
- **Nothing**

The only exceptions are:
- Platform-required favicons (use `K` glyph)
- Accessibility labels (invisible to users)

---

## 6. Product ID Specification

### Silhouette
- Superellipse profile, **n = 3.5**
- Diagonal: **Ø80mm**
- Height: **25mm** body + **2mm** dome
- Top: subtle lenticular dome (catenary curve preferred for production)
- Bottom: flat with recessed features only
- Edge fillet: **1mm** at both top and bottom meeting of wall and faces
- Wall: perpendicular, hairline-brushed radially

### Engravings (laser, 0.1mm line width)
- Top face (dead center): `K` — 8mm × 8mm, 0.3mm deep recess
- Bottom face (perimeter arc, 5mm from edge):
  `KOE · 001 · TOKYO · MMXXVI` (roman numeral year)

### Interface (zero visible)
- No buttons
- No ports (Qi wireless charging only)
- No LEDs visible when off
- Single capacitive sense on top face (invisible, full top is touch)
- LED array: 5× WS2812 inside top face, visible only through 0.2mm laser-drilled pinhole array in the K recess

### Material
- **6061-T6 aluminum**, CNC unibody
- Finish: **Hairline + Hard anodize**, Pantone 432C
- No painting, no coatings, no rubber feet

### Weight
- **380g ± 20g** — heavy enough to feel intentional, light enough to pick up with one hand
- Internal weight distribution: center of gravity exactly at geometric centroid

---

## 7. Packaging

### Philosophy: **the box is part of the product**.
The first 10 seconds of ownership — hand to box, box opens, reveals weight — must be as considered as the device itself.

### Primary box: **Hacoa wooden box**
- Material: Walnut solid wood, oil finish
- Interior: Closed-cell foam, die-cut for exact Stone shape
- Dimensions: 120 × 120 × 50mm
- Weight of empty box: ~180g
- Cost: ¥3,500-¥5,000/unit at 100 quantity
- Supplier: **Hacoa** (Sabae, Fukui) — they ship worldwide

### Alternative: **福永紙工 thick-cardboard slide box**
- Material: Hirano-Shiko double-layered black board
- Finish: Foil-stamped `K O E` on lid center
- Dimensions: 100 × 100 × 40mm
- Cost: ¥800-¥1,200/unit
- Use for: bulk shipments, touring demo kit

### Contents (in order of reveal)
1. Outer box (lid off = 2 seconds)
2. Thin foam layer — print: `K O E` (revealed after lid)
3. Removable foam layer lifts to reveal:
4. Stone itself, sitting in die-cut
5. Under Stone: single leather business card (see §10)
6. Under card: Qi wireless charging pad (thin, single cable USB-C, Qi coil in leather-wrapped circle) — 1 pad per shipment, not per Stone
7. No manual. No warranty card. No stickers. No leaflets.

### Tactile rules
- Box opening must require **intention** (not fall open)
- All materials must have clearly different textures: wood / foam / leather / metal
- Zero plastic visible anywhere in packaging
- **Silent unpack** — no crackling, no tape-rip sounds

---

## 8. Business Card / Info Card

### Form
- 91 × 55mm (Japanese business card standard)
- 600 gsm thick cardboard (approximate feel of a hotel room key)
- Material: Matte black cardstock, foil-stamped gold `K O E` (or uncoated brown kraft with blind-embossed K)
- Back side: serial number handwritten or laser-engraved

### Front
```
          K O E

      Stone  ·  001 / 100

     hello@koe.live
```

### Back
```
             K

          ¥300,000
           Tokyo
           MMXXVI

       business@koe.live
```

Zero other copy. No QR code visible (embedded NFC tag instead, NTAG213, ¥50/each).

---

## 9. Web Design

### Layout
- Single column, centered
- Max width: **1100px** for specs grid
- Max width: **720px** for manifesto/prose
- Vertical rhythm: **8rem** between sections
- Side padding: clamp(1.5rem, 5vw, 2.5rem)

### Backgrounds
- Pure **#0a0a0a** (Void)
- Hero section adds a subtle radial gradient to `#1a1a2e` at top
- No decorative shapes, no SVG patterns, no blurred blobs

### Components (only 4 exist)
1. **Nav** — fixed top, logo left, 3-4 links right
2. **Hero** — full-viewport, centered, single product image floating
3. **Spec card** — grid item with label + value + sub
4. **CTA** — pill button, 2 variants (primary white, secondary ghost)

That's it. No sliders, no carousels, no accordions, no modals, no tooltips, no dropdowns.

### Responsive
- Breakpoints: 480px, 640px, 768px, 1024px
- Mobile-first, but default styles assume desktop (because the product is about physical objects, viewed at rest)
- Touch targets: 44px minimum (WCAG)

### Performance budget
- First Contentful Paint: **< 1.0s**
- Largest Contentful Paint: **< 1.8s**
- Page weight (excluding hero image): **< 150KB**
- No external JS except Three.js on `/3d`
- No analytics libraries (privacy + speed)
- No cookies

---

## 10. Photography & Imagery

### Only 5 allowed subjects
1. **The Stone** — isolated on black, single 3-point light
2. **A single hand** holding or touching the Stone
3. **A guitar** (acoustic or electric) in context
4. **Natural environments** — ocean, wooden surfaces, stone textures
5. **Human activity from behind** — no faces visible

### Banned imagery
- ❌ Smiling people looking at camera
- ❌ Group shots
- ❌ "Lifestyle" stock (coffee cups, laptops, plants)
- ❌ Any device except the Stone in frame
- ❌ Bright sunlight or harsh shadows
- ❌ Colored backgrounds

### Lighting
- Always moody: side light + rim light + soft fill
- No flat lighting, no softbox diffusion
- Shot on: full-frame camera, fixed 50mm or 85mm lens, f/2.8-4

---

## 11. Sound Design

### Device sounds
- **Startup chime**: single low-frequency sine wave, 200Hz, 300ms, fade in+out
  - Only plays on first-ever power-up, never again
- **Touch response**: subsonic tactile pulse via BMR, no audible click
- **Error**: three quiet 1kHz beeps (only if something is genuinely broken)
- **Voice prompt**: 1 phrase, English male voice, British accent
  - "Hi. Touch me to play music."
  - Triggered only by 5-second top press

### Marketing sound
- Keynote audio: **original composition**, fingerpicked acoustic guitar, 30 seconds, commissioned from a single musician
- Ocean sounds: recorded on-site in Hawaii, not stock
- Silence is a valid choice: 10+ seconds of ambient silence is acceptable

---

## 12. Voice & Tone

### When Koe speaks
- First person: **never** (Koe is not alive)
- Second person: **rarely** (not "you will love it")
- Imperative voice: **preferred** ("Touch the top. Music plays.")
- Declarative: **for specs** ("80mm. 380g. Aluminum.")

### Tone adjectives
- Calm (never excited)
- Confident (never defensive)
- Understated (never hyperbolic)
- Literal (never metaphorical in copy, except in the manifesto)

### Banned words
- Amazing, incredible, revolutionary, game-changer, best-in-class, award-winning, leading, innovative, cutting-edge, next-gen, seamless, premium (we show it, we don't say it), elevated, curated, artisan, crafted (unless literally by hand)

### Preferred words
- Touch, hold, listen, place, carry, breathe, rest, weight, metal, quiet, still, one

---

## 13. File & Asset Structure

```
koe-device/
├── docs/                  (deployed static site)
│   ├── index.html         (hero / Stone landing)
│   ├── 3d.html            (Stone 3D viewer)
│   ├── start.html         (onboarding / how it works)
│   ├── business.html      (press + specs)
│   ├── archive.html       (internal 31-model explorer)
│   └── stl/               (3D model files + thumbs)
├── brand/                 (to be created)
│   ├── logo/              (K mark SVGs)
│   ├── type/              (Inter font files if self-hosted)
│   ├── colors.json        (design tokens)
│   ├── photography/       (approved hero images)
│   └── sounds/            (startup chime, voice prompt WAVs)
└── tasks/                 (planning docs)
    ├── prd-koe.md         (product spec)
    ├── keynote.md         (30-sec film script)
    ├── oki-brief.md       (first-user brief)
    ├── koe-launch.md      (timeline)
    ├── design-system.md   (this document)
    ├── personas.md
    └── master-plan.md
```

---

## 14. Version & Evolution

- **v1.0 is locked through Hawaii prototype (2026-07-15).**
- Post-Hawaii, any changes require formal revision with dated diff.
- Design system is not a living document during launch — it is frozen, executed, evaluated, and revised only between launches.
- All design decisions not covered above default to: **"remove it."**
