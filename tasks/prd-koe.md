# Koe Stone — PRD (Product Requirements Document)
**Version:** v0.1 (2026-04-11)
**Status:** LOCKED for Hawaii prototype batch
**Owner:** 濱田祐樹

---

## 1. Positioning
**One line:** 「22ms。ギターから1000人の耳まで。」
**One line (EN):** "A home that becomes a single speaker."

---

## 2. Target User (First 6)
| Persona | Role | Expectation |
|---------|------|------------|
| ONE OK ROCK (Taka, Toru, Ryota, Tomoya) | Global rock musicians | Must pass their tactile & sonic judgment within 10 seconds |
| Oki-san (host, tech-savvy) | Friend hosting house | Daily user, remote debug proxy, demo partner |
| ONE OK ROCK manager | Amuse Inc. | Must read as "real product" in 30 seconds, not a prototype |

---

## 3. Hard Requirements

### 3.1 Physical
| Spec | Value |
|------|-------|
| Form | Stone (worry stone / pebble) |
| Diameter | 80mm |
| Height | 25mm |
| Weight | 380g ± 20g |
| Material | **CNC 6061-T6 aluminum unibody** (single block) |
| Finish | Hairline + Hard anodize, Space Gray (#2a2a2e) |
| Marking | Laser engrave: "KOE / TOKYO / 001-012" + K-logo only |
| Colors available | 1 (Space Gray only) |

### 3.2 Audio
| Spec | Value |
|------|-------|
| Driver | **Tectonic BMR 40mm (TEBM46C20N-4B)** |
| Passive radiator | 50×30mm elliptical, bottom face |
| Amp | TAS2563 smart amp w/ DSP |
| Freq response | 100Hz–20kHz (±3dB) |
| SPL (single) | 82dB @ 1m @ 1W |
| SPL (8-unit mesh) | 91dB @ 1m |
| Codec | **LDAC + aptX Adaptive + LC3 (BLE Audio LE)** |
| Latency (Bluetooth) | <40ms |
| Latency (mesh sync) | <2ms inter-device |
| SNR | ≥90dB |
| THD @ 1W | <0.5% |

### 3.3 Electronics
| Spec | Value |
|------|-------|
| SoC | **nRF5340** (Nordic, dual-core, BLE Audio LE certified) |
| RAM/Flash | 512KB / 1MB internal + 8GB external NAND for audio cache |
| Wireless | Bluetooth 5.4 + BLE Audio LE + 802.15.4 mesh |
| Wi-Fi | **Not included** (BLE mesh only, AirPlay via iPhone bridge) |
| UWB | **Not in Stone** (reserved for Koe Pro v2 later) |
| NFC | **NTAG216** passive tag on bottom face |
| Sensor | 3-axis accelerometer (wake on pickup), capacitive touch top surface |
| Battery | LiPo 3000mAh 3.7V (18650 pouch equivalent) |
| Battery life | **8h playback / 30d deep sleep** |
| Charging | **Qi 5W wireless** (bottom face, no cable needed) |
| Charge time | 0–100% in 2.5h |

### 3.4 UX (Zero-button Interface)
| Action | Response |
|--------|----------|
| Pickup (accelerometer wake) | LED pulse once, device ready |
| Touch top surface (cap sense) | Music plays (1 sec to sound) |
| 2-finger touch | Volume cycle: low / mid / high |
| Flip upside down | Mute (hard stop) |
| Touch another Stone in range | Playback handoff (follow user) |
| Put down | Keep playing, no state change |
| Hold top 5 sec | Voice prompt: "Hi. Touch me to play music." (EN only) |
| No interaction 30 min | Fade out, sleep |
| Tap NFC with phone | `koe.live/start` auto-opens |
| QR scan bottom | `koe.live/start` fallback |

### 3.5 Firmware
- nRF Connect SDK v2.5+ / Zephyr
- BLE Audio LE + Auracast receiver
- OTA via `koe.live/api/v1/device/firmware` (existing Fly.io endpoint)
- Mesh pairing: factory pre-paired, mesh auto-join on power, no user setup
- Audio source priority: AirPlay 2 (iPhone) > BLE Audio LE broadcast > Preloaded playlist (10 Hawaii vibe tracks, 48kHz/24bit WAV, ~3.5GB)
- Remote monitoring: heartbeat every 5 min to `koe.live/api/v1/device/heartbeat`
- Factory reset: touch top + flip upside down + hold 10 sec

### 3.6 Mechanical
- Unibody CNC aluminum, **no parting line visible**
- Bottom: hollowed chamber for Qi coil + passive radiator + LiPo
- Top face: capacitive touch surface with engraved K-logo center
- Internal PCB floating on 4× M2 standoffs
- Gasket-sealed for water resistance (IPX4, splash-proof not submersible)
- Drop rating: 1m onto hardwood, 6 faces, 3x pass

---

## 4. NOT included in v1 (Strict scope cut)
- ❌ Microphone (no input, speaker only)
- ❌ App (phone not required beyond AirPlay source)
- ❌ Wi-Fi (BLE only)
- ❌ Color options (Space Gray only)
- ❌ Customization/user accounts
- ❌ Cloud dependency (works offline)
- ❌ Voice assistant integration
- ❌ Multi-room group naming (mesh auto-groups)
- ❌ EQ settings (fixed tuning)

---

## 5. Quantities & Timeline
| Item | Qty |
|------|-----|
| Hawaii prototype batch | 12 units (serials 001-012) |
| Placement in house | 8 (001-008) |
| Presentable spares | 4 (009-012) |
| Ship date | 2026-06-13 Tokyo → Hawaii |
| Arrival | 2026-06-20 |
| Configuration | 2026-06-25 |
| ONE OK ROCK arrival | 2026-07-01 |

---

## 6. Budget (Hawaii batch only)
| Item | Cost |
|------|------|
| HW/FW design (Nordic Design House) | $80,000 |
| ID freelance | $10,000 |
| CNC 12 units | $3,600 ($300/unit) |
| PCBA 12 units | $4,800 ($400/unit) |
| Tectonic drivers + passive radiators | $720 ($60/unit × 12) |
| nRF5340 modules | $180 ($15 × 12) |
| Qi modules + batteries | $240 ($20 × 12) |
| NFC tags + misc | $120 |
| Packaging (leather pouches + cards) | $600 |
| Shipping TY→HNL | $500 |
| FW engineer (6 weeks contract) | $25,000 |
| Acoustic DSP tuning | $8,000 |
| ID freelance round 2 (Hawaii refinement) | $5,000 |
| **Contingency 20%** | $27,592 |
| **Total** | **$165,552** |

---

## 7. Success Criteria

### Hard
- [ ] 12 units assembled and pass QA by 2026-06-06
- [ ] Shipped to Hawaii by 2026-06-13
- [ ] Placed in house by 2026-06-25
- [ ] Survive 15 days unattended without intervention
- [ ] Zero unit failures during 15-day period

### Soft (Marketing value)
- [ ] At least 1 ONE OK ROCK member uses a Stone for >10 minutes
- [ ] At least 1 spontaneous positive comment captured (text/photo/video with permission)
- [ ] Manager requests business contact
- [ ] Any member asks to keep one (→ give from spares)

### Stretch
- [ ] Social media post from any member (organic)
- [ ] Request for tour usage discussion
- [ ] Collaboration interest expressed

---

## 8. Risk Register

| Risk | Mitigation |
|------|------------|
| 11 weeks too short for custom FW | Use Nordic BLE Audio sample + minimal mod, no UWB in v1 |
| CNC delivery slip | 3 parallel vendors (山形/Protolabs/Xometry) |
| Acoustic tuning subpar | External contractor (Knowles / Goertek / ex-Bose engineer) |
| 8 units mesh instability | Factory pre-pairing, tested 100h soak before ship |
| Salt/humidity damage in Hawaii | IPX4 + conformal coat on PCB |
| Oki-san can't troubleshoot | Remote admin dashboard at `koe.live/admin`, OTA recovery |
| Members don't touch any Stone in 15 days | Strategic placement + Oki demonstration + beach picnic scenario |
| Manager dismisses as "proto" | Business card + packaging + spare supply signals "real product" |

---

## 9. Post-Hawaii (Commercial Launch)
- 2026-09-01: Kickstarter or direct preorder launch, 100 units
- 2026-11-01: First 100 customer shipment
- Price: $1,995 USD / ¥300,000 JPY
- Channels: koe.live direct, Reverb.com, 1-2 boutique audio retailers
