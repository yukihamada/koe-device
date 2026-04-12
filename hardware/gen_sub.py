#!/usr/bin/env python3
"""
Koe SUB PCB — 120x80mm High-Power Subwoofer Board
===================================================
Raspberry Pi 5 (WiFi + DSP) + TPA3255 300W Class-D + PCM5102A DAC
48V DC input, LM2596 buck to 5V/3A, AMS1117-3.3V
Speaker out via Speakon NL4, Ethernet RJ45, USB-C config

Board: 120x80mm rectangle, 2-layer FR-4, 2oz copper
Power: 48V/10A DC barrel jack → TPA3255 mono 1x300W @4Ω
"""

import math
import zipfile
from pathlib import Path

# Board dimensions
BW, BH = 120.0, 80.0
TRACE, PWR, HPWR = 0.2, 0.5, 1.0
VIA_D, VIA_P = 0.3, 0.6

OUT = Path(__file__).parent / "kicad"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-sub"

# Mounting holes: M4 (4.2mm drill), 5mm from edges
MOUNTS = [
    (5.0, 5.0), (BW - 5.0, 5.0),
    (5.0, BH - 5.0), (BW - 5.0, BH - 5.0),
]
M4_DRILL = 4.2
M4_PAD = 7.0

def in_rect(x, y, m=0.5):
    return m <= x <= BW - m and m <= y <= BH - m

# ── Footprints ────────────────────────────────────────────────────────
FP = {}

# Raspberry Pi 5 — 40-pin GPIO header (2x20, 2.54mm pitch)
# Physical: 51.44mm x 5.08mm (20 pins x 2.54mm = 50.8mm long)
def _pi40():
    pads = []
    for row in range(2):
        for col in range(20):
            pin = row * 20 + col + 1
            px = (col - 9.5) * 2.54
            py = (row - 0.5) * 2.54
            pads.append((pin, px, py, 1.7, 1.7))
    return pads
FP["PI40"] = {"pads": _pi40(), "size": (52.0, 6.0)}

# TPA3255 — HTSSOP-36 (9.7x6.4mm body, 0.5mm pitch)
def _tpa3255():
    pads = []
    for i in range(18):
        pads.append((i + 1, -4.85, 2.875 - i * 0.5 + 4.25, 1.5, 0.3))
    for i in range(18):
        pads.append((19 + i, 4.85, -2.875 + i * 0.5 - 4.25 + 8.5, 1.5, 0.3))
    # Exposed thermal pad
    pads.append((37, 0, 0, 6.0, 4.2))
    return pads
FP["HTSSOP36"] = {"pads": _tpa3255(), "size": (11.0, 9.2)}

# PCM5102A — SSOP-20 (7.5x5.3mm body, 0.65mm pitch)
def _pcm5102():
    pads = []
    for i in range(10):
        pads.append((i + 1, -3.75, 2.925 - i * 0.65, 1.4, 0.35))
    for i in range(10):
        pads.append((11 + i, 3.75, -2.925 + i * 0.65, 1.4, 0.35))
    return pads
FP["SSOP20"] = {"pads": _pcm5102(), "size": (8.0, 6.5)}

# LM2596 — TO-263-5 (D2PAK)
def _lm2596():
    pads = []
    pins = [(-3.4, -6.0), (-1.7, -6.0), (0, -6.0), (1.7, -6.0), (3.4, -6.0)]
    for i, (px, py) in enumerate(pins):
        pads.append((i + 1, px, py, 1.2, 2.0))
    # Tab pad
    pads.append((6, 0, 2.0, 8.0, 6.0))
    return pads
FP["TO263"] = {"pads": _lm2596(), "size": (10.0, 10.0)}

# AMS1117-3.3 — SOT-223
FP["SOT223"] = {"pads": [
    (1, -2.3, 3.2, 1.0, 1.5),
    (2, 0.0, 3.2, 1.0, 1.5),
    (3, 2.3, 3.2, 1.0, 1.5),
    (4, 0.0, -3.2, 3.0, 1.5),  # Tab/heat
], "size": (6.5, 7.0)}

# Speakon NL4 — 4-pin panel mount (large, TH)
# Simplified as 4-pin rectangle footprint
FP["SPEAKON"] = {"pads": [
    (1, -5.0, -5.0, 3.0, 3.0),
    (2, 5.0, -5.0, 3.0, 3.0),
    (3, -5.0, 5.0, 3.0, 3.0),
    (4, 5.0, 5.0, 3.0, 3.0),
], "size": (18.0, 18.0)}

# RJ45 — standard TH jack
FP["RJ45"] = {"pads": [
    (1, -4.445, -5.0, 1.0, 1.6),
    (2, -3.175, -5.0, 1.0, 1.6),
    (3, -1.905, -5.0, 1.0, 1.6),
    (4, -0.635, -5.0, 1.0, 1.6),
    (5, 0.635, -5.0, 1.0, 1.6),
    (6, 1.905, -5.0, 1.0, 1.6),
    (7, 3.175, -5.0, 1.0, 1.6),
    (8, 4.445, -5.0, 1.0, 1.6),
    ("S1", -7.875, 0, 2.0, 2.0),
    ("S2", 7.875, 0, 2.0, 2.0),
], "size": (16.0, 14.0)}

# USB-C (16-pin, same as COIN)
FP["USBC"] = {"pads": [
    ("V1", -2.4, -1.0, 0.5, 1.0), ("V2", 2.4, -1.0, 0.5, 1.0),
    ("D-", -0.8, -1.0, 0.3, 1.0), ("D+", -0.4, -1.0, 0.3, 1.0),
    ("C1", -1.6, -1.0, 0.3, 1.0), ("C2", 1.6, -1.0, 0.3, 1.0),
    ("G1", -3.2, -1.0, 0.5, 1.0), ("G2", 3.2, -1.0, 0.5, 1.0),
    ("S1", -3.65, 0.0, 0.6, 1.2), ("S2", 3.65, 0.0, 0.6, 1.2),
], "size": (7.35, 3.2)}

# DC barrel jack (5.5x2.1mm, TH)
FP["BARREL"] = {"pads": [
    (1, 0.0, 0.0, 3.0, 3.0),  # center pin (+48V)
    (2, -6.0, 0.0, 3.0, 3.0),  # sleeve (GND)
    (3, 6.0, 0.0, 3.0, 3.0),  # switch
], "size": (14.0, 9.0)}

# WS2812B-5050
FP["LED5050"] = {"pads": [
    (1, -2.45, -1.6, 1.0, 1.0),  # VDD
    (2, -2.45, 1.6, 1.0, 1.0),   # DOUT
    (3, 2.45, 1.6, 1.0, 1.0),    # GND
    (4, 2.45, -1.6, 1.0, 1.0),   # DIN
], "size": (5.0, 5.0)}

# NTC thermistor (0805)
FP["0805"] = {"pads": [(1, -1.0, 0, 1.1, 1.4), (2, 1.0, 0, 1.1, 1.4)], "size": (2.8, 1.6)}
# Passives
FP["0603"] = {"pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)], "size": (2.2, 1.2)}
FP["0805_C"] = {"pads": [(1, -1.0, 0, 1.1, 1.4), (2, 1.0, 0, 1.1, 1.4)], "size": (2.8, 1.6)}

# Polyfuse (1812)
FP["1812"] = {"pads": [(1, -2.0, 0, 1.8, 2.5), (2, 2.0, 0, 1.8, 2.5)], "size": (5.6, 3.2)}

# TVS diode (SMA/DO-214AC)
FP["SMA"] = {"pads": [(1, -2.0, 0, 1.6, 2.4), (2, 2.0, 0, 1.6, 2.4)], "size": (5.2, 2.6)}

# Fan header (2-pin, 2.54mm)
FP["PIN2"] = {"pads": [(1, -1.27, 0, 1.7, 1.7), (2, 1.27, 0, 1.7, 1.7)], "size": (5.08, 3.0)}

# Inductor (12x12mm shielded, for LM2596)
FP["IND12"] = {"pads": [(1, -5.0, 0, 3.5, 4.0), (2, 5.0, 0, 3.5, 4.0)], "size": (12.0, 12.0)}

# Electrolytic cap (10x10mm, TH pads)
FP["ECAP10"] = {"pads": [(1, -2.0, 0, 2.5, 2.5), (2, 2.0, 0, 2.5, 2.5)], "size": (10.5, 10.5)}

# Schottky diode (SMA)
FP["SOD123"] = {"pads": [(1, -1.5, 0, 0.8, 1.0), (2, 1.5, 0, 0.8, 1.0)], "size": (3.6, 1.6)}


# ── Components ────────────────────────────────────────────────────────
PARTS = {
    # ── Pi 5 GPIO Header ──
    "J1": {"fp": "PI40", "x": 60.0, "y": 15.0, "rot": 0,
            "part": "2x20 Pin Header 2.54mm", "lcsc": "C2977589",
            "label": "Pi5\nGPIO", "color": "#1b5e20"},

    # ── TPA3255 Class-D Amp ──
    "U1": {"fp": "HTSSOP36", "x": 60.0, "y": 45.0, "rot": 0,
            "part": "TPA3255DKDR", "lcsc": "C131460",
            "label": "TPA3255\n300W", "color": "#b71c1c"},

    # ── PCM5102A DAC ──
    "U2": {"fp": "SSOP20", "x": 30.0, "y": 40.0, "rot": 0,
            "part": "PCM5102APWR", "lcsc": "C108765",
            "label": "PCM5102A\nDAC", "color": "#0d47a1"},

    # ── LM2596 5V Buck ──
    "U3": {"fp": "TO263", "x": 95.0, "y": 60.0, "rot": 0,
            "part": "LM2596S-5.0/NOPB", "lcsc": "C29781",
            "label": "LM2596\n5V/3A", "color": "#4a148c"},

    # ── AMS1117-3.3 LDO ──
    "U4": {"fp": "SOT223", "x": 30.0, "y": 60.0, "rot": 0,
            "part": "AMS1117-3.3", "lcsc": "C6186",
            "label": "AMS1117\n3.3V", "color": "#4e342e"},

    # ── Speakon NL4 output ──
    "J2": {"fp": "SPEAKON", "x": 105.0, "y": 15.0, "rot": 0,
            "part": "Neutrik NL4MP", "lcsc": "",
            "label": "Speakon\nNL4", "color": "#263238"},

    # ── RJ45 Ethernet ──
    "J3": {"fp": "RJ45", "x": 15.0, "y": 15.0, "rot": 0,
            "part": "HR911105A", "lcsc": "C12084",
            "label": "RJ45\nEthernet", "color": "#37474f"},

    # ── USB-C config ──
    "J4": {"fp": "USBC", "x": 15.0, "y": 75.0, "rot": 180,
            "part": "TYPE-C-16PIN-2MD", "lcsc": "C2765186",
            "label": "USB-C", "color": "#78909c"},

    # ── DC barrel jack 48V ──
    "J5": {"fp": "BARREL", "x": 105.0, "y": 70.0, "rot": 0,
            "part": "PJ-002AH (5.5x2.1)", "lcsc": "C111588",
            "label": "48V DC\nInput", "color": "#e65100"},

    # ── Fan header ──
    "J6": {"fp": "PIN2", "x": 85.0, "y": 75.0, "rot": 0,
            "part": "2-pin header 2.54mm", "lcsc": "C49257",
            "label": "FAN", "color": "#455a64"},

    # ── WS2812B LEDs ──
    "LED1": {"fp": "LED5050", "x": 45.0, "y": 72.0, "rot": 0,
             "part": "WS2812B", "lcsc": "C2761795",
             "label": "LED1", "color": "#f9a825"},
    "LED2": {"fp": "LED5050", "x": 55.0, "y": 72.0, "rot": 0,
             "part": "WS2812B", "lcsc": "C2761795",
             "label": "LED2", "color": "#f9a825"},

    # ── NTC inrush limiter ──
    "NTC1": {"fp": "0805", "x": 95.0, "y": 70.0, "rot": 0,
             "part": "NTC 5D-11 (5Ω)", "lcsc": "C82123",
             "label": "NTC", "color": "#006064"},

    # ── Polyfuse ──
    "F1": {"fp": "1812", "x": 85.0, "y": 55.0, "rot": 0,
            "part": "MF-MSMF250/24X (2.5A)", "lcsc": "C70069",
            "label": "FUSE", "color": "#880e4f"},

    # ── TVS on speaker out ──
    "D1": {"fp": "SMA", "x": 88.0, "y": 35.0, "rot": 0,
            "part": "SMBJ48A", "lcsc": "C134776",
            "label": "TVS", "color": "#263238"},

    # ── Schottky diode (LM2596) ──
    "D2": {"fp": "SOD123", "x": 105.0, "y": 55.0, "rot": 0,
            "part": "SS34 (3A 40V)", "lcsc": "C8678",
            "label": "D2", "color": "#263238"},

    # ── LM2596 inductor ──
    "L1": {"fp": "IND12", "x": 95.0, "y": 45.0, "rot": 0,
            "part": "33uH 3A shielded", "lcsc": "C408157",
            "label": "33uH", "color": "#006064"},

    # ── Bulk caps 48V ──
    "C1": {"fp": "ECAP10", "x": 75.0, "y": 55.0, "rot": 0,
            "part": "470uF/63V", "lcsc": "C249469",
            "label": "470u\n63V", "color": "#1a237e"},
    "C2": {"fp": "ECAP10", "x": 50.0, "y": 60.0, "rot": 0,
            "part": "470uF/63V", "lcsc": "C249469",
            "label": "470u\n63V", "color": "#1a237e"},

    # ── 5V output cap ──
    "C3": {"fp": "ECAP10", "x": 110.0, "y": 48.0, "rot": 0,
            "part": "220uF/16V", "lcsc": "C43331",
            "label": "220u", "color": "#1a237e"},

    # ── DAC decoupling ──
    "C4": {"fp": "0603", "x": 23.0, "y": 38.0, "rot": 90,
            "part": "100nF", "lcsc": "C1525",
            "label": "C4", "color": "#1a237e"},
    "C5": {"fp": "0603", "x": 38.0, "y": 38.0, "rot": 90,
            "part": "10uF", "lcsc": "C19702",
            "label": "C5", "color": "#1a237e"},

    # ── TPA3255 decoupling ──
    "C6": {"fp": "0805_C", "x": 50.0, "y": 45.0, "rot": 90,
            "part": "1uF/100V", "lcsc": "C302829",
            "label": "C6", "color": "#1a237e"},
    "C7": {"fp": "0805_C", "x": 70.0, "y": 45.0, "rot": 90,
            "part": "1uF/100V", "lcsc": "C302829",
            "label": "C7", "color": "#1a237e"},
    "C8": {"fp": "0603", "x": 60.0, "y": 56.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525",
            "label": "C8", "color": "#1a237e"},

    # ── AMS1117 caps ──
    "C9": {"fp": "0603", "x": 25.0, "y": 58.0, "rot": 0,
            "part": "10uF", "lcsc": "C19702",
            "label": "C9", "color": "#1a237e"},
    "C10": {"fp": "0603", "x": 35.0, "y": 58.0, "rot": 0,
             "part": "10uF", "lcsc": "C19702",
             "label": "C10", "color": "#1a237e"},

    # ── Feedback resistors (TPA3255) ──
    "R1": {"fp": "0603", "x": 48.0, "y": 42.0, "rot": 0,
            "part": "15k", "lcsc": "C22809",
            "label": "R1", "color": "#5d4037"},
    "R2": {"fp": "0603", "x": 48.0, "y": 48.0, "rot": 0,
            "part": "15k", "lcsc": "C22809",
            "label": "R2", "color": "#5d4037"},

    # ── USB-C CC resistors ──
    "R3": {"fp": "0603", "x": 12.0, "y": 72.0, "rot": 0,
            "part": "5.1k", "lcsc": "C23186",
            "label": "R3", "color": "#5d4037"},
    "R4": {"fp": "0603", "x": 18.0, "y": 72.0, "rot": 0,
            "part": "5.1k", "lcsc": "C23186",
            "label": "R4", "color": "#5d4037"},

    # ── LED current-limit ──
    "R5": {"fp": "0603", "x": 40.0, "y": 72.0, "rot": 0,
            "part": "100R", "lcsc": "C22775",
            "label": "R5", "color": "#5d4037"},
}


# ── Routes ────────────────────────────────────────────────────────────
ROUTES = [
    # 48V power rail
    ("+48V", HPWR, [(105.0, 70.0), (95.0, 70.0), (85.0, 65.0)]),
    ("+48V", HPWR, [(85.0, 65.0), (75.0, 55.0)]),
    ("+48V", HPWR, [(85.0, 65.0), (85.0, 55.0), (95.0, 45.0)]),  # → buck input
    ("+48V", HPWR, [(85.0, 65.0), (50.0, 60.0), (60.0, 45.0)]),  # → TPA3255 PVCC

    # 5V rail (LM2596 output → Pi5)
    ("+5V", PWR, [(110.0, 48.0), (95.0, 38.0), (75.0, 20.0)]),   # → Pi5 5V pins
    ("+5V", PWR, [(75.0, 20.0), (60.0, 15.0)]),                    # along Pi header

    # 3.3V rail (AMS1117 → DAC, LEDs)
    ("+3V3", TRACE, [(30.0, 56.8), (30.0, 45.0), (30.0, 40.0)]),  # → DAC
    ("+3V3", TRACE, [(30.0, 56.8), (45.0, 72.0)]),                 # → LED1
    ("+3V3", TRACE, [(45.0, 72.0), (55.0, 72.0)]),                 # → LED2

    # I2S: Pi5 → PCM5102A
    ("I2S_BCK", TRACE, [(42.0, 15.0), (42.0, 30.0), (33.75, 40.0)]),
    ("I2S_DATA", TRACE, [(44.5, 15.0), (44.5, 32.0), (33.75, 41.3)]),
    ("I2S_LRCK", TRACE, [(47.0, 15.0), (47.0, 34.0), (33.75, 42.6)]),

    # DAC analog out → TPA3255 input
    ("AUDIO_L", TRACE, [(26.25, 40.0), (26.0, 44.0), (48.0, 44.0), (55.15, 45.0)]),

    # TPA3255 → Speakon (speaker output)
    ("SPK+", HPWR, [(64.85, 41.0), (88.0, 35.0), (100.0, 20.0), (105.0, 15.0)]),
    ("SPK-", HPWR, [(64.85, 49.0), (88.0, 35.0), (100.0, 10.0), (105.0, 15.0)]),

    # LED data chain
    ("LED_DIN", TRACE, [(40.0, 72.0), (42.55, 72.0)]),             # R5 → LED1
    ("LED_DOUT", TRACE, [(47.45, 72.0), (52.55, 72.0)]),           # LED1 → LED2

    # Pi5 → LED data
    ("LED_GPIO", TRACE, [(50.0, 15.0), (40.0, 68.0), (40.0, 72.0)]),

    # USB-C CC resistors
    ("CC1", TRACE, [(12.0, 72.0), (13.4, 75.0)]),
    ("CC2", TRACE, [(18.0, 72.0), (16.6, 75.0)]),

    # Fan header → 5V
    ("FAN_5V", PWR, [(85.0, 75.0), (83.73, 75.0)]),

    # GND bus (wide trace)
    ("GND", HPWR, [(15.0, 22.0), (60.0, 22.0), (105.0, 22.0)]),
    ("GND", PWR, [(60.0, 22.0), (60.0, 55.0)]),
]

# Stitching vias for ground plane and thermal
VIAS = [
    # Ground plane stitching
    (10, 10), (30, 10), (50, 10), (70, 10), (90, 10), (110, 10),
    (10, 30), (30, 30), (50, 30), (70, 30), (90, 30), (110, 30),
    (10, 50), (30, 50), (50, 50), (70, 50), (90, 50), (110, 50),
    (10, 70), (30, 70), (50, 70), (70, 70), (90, 70), (110, 70),
    # Extra thermal vias under TPA3255
    (56, 43), (60, 43), (64, 43),
    (56, 47), (60, 47), (64, 47),
    # Extra thermal vias under LM2596
    (93, 60), (97, 60),
]


# ── Helpers ───────────────────────────────────────────────────────────
def xform(px, py, cx, cy, rot):
    r = math.radians(rot)
    return cx + px * math.cos(r) - py * math.sin(r), cy + px * math.sin(r) + py * math.cos(r)


class Gbr:
    def __init__(s, name):
        s.name, s.ap, s.nd, s.cmds = name, {}, 10, []

    def _a(s, sh, p):
        k = (sh, tuple(p))
        if k not in s.ap:
            s.ap[k] = s.nd
            s.nd += 1
        return s.ap[k]

    def _c(s, v):
        return int(round(v * 1e6))

    def pad(s, x, y, w, h):
        d = s._a("C", [w]) if abs(w - h) < 0.01 else s._a("R", [w, h])
        s.cmds += [f"D{d}*", f"X{s._c(x)}Y{s._c(y)}D03*"]

    def trace(s, x1, y1, x2, y2, w):
        d = s._a("C", [w])
        s.cmds += [f"D{d}*", f"X{s._c(x1)}Y{s._c(y1)}D02*", f"X{s._c(x2)}Y{s._c(y2)}D01*"]

    def circ(s, x, y, d_):
        d = s._a("C", [d_])
        s.cmds += [f"D{d}*", f"X{s._c(x)}Y{s._c(y)}D03*"]

    def rect_outline(s, x, y, w, h, lw=0.05):
        d = s._a("C", [lw])
        s.cmds.append(f"D{d}*")
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        s.cmds.append(f"X{s._c(pts[0][0])}Y{s._c(pts[0][1])}D02*")
        for px, py in pts[1:]:
            s.cmds.append(f"X{s._c(px)}Y{s._c(py)}D01*")

    def write(s, path):
        with open(path, 'w') as f:
            f.write("%FSLAX46Y46*%\n%MOMM*%\n")
            f.write(f"G04 Koe SUB {s.name}*\n%LPD*%\n")
            for (sh, p), dc in sorted(s.ap.items(), key=lambda x: x[1]):
                if sh == "C":
                    f.write(f"%ADD{dc}C,{p[0]:.3f}*%\n")
                elif sh == "R":
                    f.write(f"%ADD{dc}R,{p[0]:.3f}X{p[1]:.3f}*%\n")
            for c in s.cmds:
                f.write(c + "\n")
            f.write("M02*\n")


class Drl:
    def __init__(s):
        s.t, s.nt, s.h = {}, 1, []

    def hole(s, x, y, d):
        k = round(d, 3)
        if k not in s.t:
            s.t[k] = s.nt
            s.nt += 1
        s.h.append((s.t[k], x, y))

    def write(s, path):
        with open(path, 'w') as f:
            f.write("M48\n; Koe SUB 120x80mm TPA3255\nFMAT,2\nMETRIC,TZ\n")
            for d, t in sorted(s.t.items(), key=lambda x: x[1]):
                f.write(f"T{t}C{d:.3f}\n")
            f.write("%\n")
            ct = None
            for t, x, y in s.h:
                if t != ct:
                    f.write(f"T{t}\n")
                    ct = t
                f.write(f"X{x:.3f}Y{y:.3f}\n")
            f.write("M30\n")


def gen_gerbers():
    GBR.mkdir(parents=True, exist_ok=True)
    fc, bc, fm, bm, fs_, bs_, ec = [Gbr(n) for n in
        ["F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.SilkS", "B.SilkS", "Edge.Cuts"]]
    dr = Drl()

    # Board outline — rectangle
    ec.rect_outline(0, 0, BW, BH, 0.05)

    # Mounting holes
    for mx, my in MOUNTS:
        for g in (fc, bc):
            g.circ(mx, my, M4_PAD)
        for g in (fm, bm):
            g.circ(mx, my, M4_PAD + 0.2)
        dr.hole(mx, my, M4_DRILL)
        # Silkscreen circle around mount
        fs_.circ(mx, my, M4_PAD + 0.5)

    # Components
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]
        cx, cy, rot = c["x"], c["y"], c.get("rot", 0)
        sw, sh = fp["size"]
        co = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2), (sw / 2, sh / 2), (-sw / 2, sh / 2)]
        ca = [xform(a, b, cx, cy, rot) for a, b in co]
        for i in range(4):
            fs_.trace(ca[i][0], ca[i][1], ca[(i + 1) % 4][0], ca[(i + 1) % 4][1], 0.12)
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            ax, ay = xform(px, py, cx, cy, rot)
            if rot in (90, 270):
                pw, ph = ph, pw
            fc.pad(ax, ay, pw, ph)
            fm.pad(ax, ay, pw + 0.1, ph + 0.1)

    # Traces
    for _, w, pts in ROUTES:
        for i in range(len(pts) - 1):
            fc.trace(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w)

    # Vias
    for vx, vy in VIAS:
        for g in (fc, bc):
            g.circ(vx, vy, VIA_P)
        for g in (fm, bm):
            g.circ(vx, vy, VIA_P + 0.1)
        dr.hole(vx, vy, VIA_D)

    # Ground copper pour on back (simplified as large pad)
    bc.pad(BW / 2, BH / 2, BW - 2, BH - 2)

    # Write files
    pre = "koe-sub"
    for n, g in [("F_Cu", fc), ("B_Cu", bc), ("F_Mask", fm), ("B_Mask", bm),
                 ("F_SilkS", fs_), ("B_SilkS", bs_), ("Edge_Cuts", ec)]:
        g.write(GBR / f"{pre}-{n}.gbr")
    dr.write(GBR / f"{pre}.drl")

    zp = GBR / f"{pre}.zip"
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in GBR.glob(f"{pre}-*"):
            z.write(f, f.name)
        z.write(GBR / f"{pre}.drl", f"{pre}.drl")
    print(f"  Gerber ZIP: {zp}")


def gen_bom():
    lines = ["Comment,Designator,Footprint,LCSC Part#"]
    by = {}
    for ref, c in PARTS.items():
        k = (c.get("part", ""), c["fp"], c.get("lcsc", ""))
        by.setdefault(k, []).append(ref)
    for (p, fp, l), refs in by.items():
        lines.append(f"{p},{' '.join(refs)},{fp},{l}")
    (GBR / "BOM-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"  BOM: {GBR / 'BOM-JLCPCB.csv'}")


def gen_cpl():
    ROT = {"SOT223": 180, "TO263": 180}
    lines = ["Designator,Mid X(mm),Mid Y(mm),Layer,Rotation"]
    for ref, c in PARTS.items():
        rot = c.get("rot", 0) + ROT.get(c["fp"], 0)
        lines.append(f"{ref},{c['x']:.1f},{c['y']:.1f},Top,{rot % 360}")
    (GBR / "CPL-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"  CPL: {GBR / 'CPL-JLCPCB.csv'}")


# ── SVG ───────────────────────────────────────────────────────────────
def gen_svg():
    S = 6
    pad = 60
    img_w = int(BW * S + pad * 2)
    img_h = int(BH * S + pad * 2)
    ox, oy = pad, pad + 20

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{img_w}" height="{img_h + 160}">
<defs>
  <linearGradient id="pcb" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#0d5c0d"/><stop offset="100%" stop-color="#063806"/>
  </linearGradient>
  <filter id="sh"><feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.4"/></filter>
</defs>
<rect width="{img_w}" height="{img_h + 160}" fill="#0d0d14"/>

<!-- Title -->
<text x="{img_w // 2}" y="18" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="15" font-weight="600">Koe SUB v1 — 300W Class-D Subwoofer Board</text>
<text x="{img_w // 2}" y="35" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">120x80mm | 2-layer 2oz | Pi5 + TPA3255 + PCM5102A | 48V/10A</text>

<!-- Board -->
<rect x="{ox - 2}" y="{oy - 2}" width="{BW * S + 4}" height="{BH * S + 4}" rx="3" fill="#000" opacity="0.3"/>
<rect x="{ox}" y="{oy}" width="{BW * S}" height="{BH * S}" rx="2" fill="url(#pcb)" stroke="#c8a83e" stroke-width="1.5"/>
'''

    # Copper pour hint (back side)
    svg += f'<rect x="{ox + 4}" y="{oy + 4}" width="{BW * S - 8}" height="{BH * S - 8}" rx="2" fill="#0a4a0a" opacity="0.3" stroke="#1a6a1a" stroke-width="0.5" stroke-dasharray="4,3"/>\n'

    # Mounting holes
    for mx, my in MOUNTS:
        svg += f'<circle cx="{ox + mx * S}" cy="{oy + my * S}" r="{M4_DRILL * S / 2}" fill="#1a1a1a" stroke="#888" stroke-width="1"/>\n'
        svg += f'<circle cx="{ox + mx * S}" cy="{oy + my * S}" r="{M4_PAD * S / 2}" fill="none" stroke="#c8a83e" stroke-width="0.5" opacity="0.4"/>\n'

    # Traces
    net_colors = {
        "48V": "#ef5350", "5V": "#ff7043", "3V3": "#66bb6a",
        "I2S": "#42a5f5", "AUDIO": "#ab47bc", "SPK": "#ff7043",
        "LED": "#f9a825", "CC": "#78909c", "FAN": "#78909c",
        "GND": "#78909c",
    }
    for net, w, pts in ROUTES:
        c = "#78909c"
        for k, v in net_colors.items():
            if k in net:
                c = v
                break
        for i in range(len(pts) - 1):
            svg += f'<line x1="{ox + pts[i][0] * S}" y1="{oy + pts[i][1] * S}" '
            svg += f'x2="{ox + pts[i + 1][0] * S}" y2="{oy + pts[i + 1][1] * S}" '
            svg += f'stroke="{c}" stroke-width="{max(1.5, w * S * 0.5)}" opacity="0.35" stroke-linecap="round"/>\n'

    # Vias
    for vx, vy in VIAS:
        svg += f'<circle cx="{ox + vx * S}" cy="{oy + vy * S}" r="{VIA_P * S / 2 + 0.5}" fill="#1a1a1a" stroke="#666" stroke-width="0.4"/>\n'

    # Components
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]
        cx_, cy_ = c["x"], c["y"]
        rot = c.get("rot", 0)
        sw, sh = fp["size"]
        color = c.get("color", "#5d4037")
        sx, sy = ox + cx_ * S, oy + cy_ * S
        rw, rh = sw * S, sh * S

        svg += f'<g transform="translate({sx},{sy}) rotate({rot})" filter="url(#sh)">\n'

        # Pads
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            svg += f'<rect x="{px * S - pw * S / 2}" y="{py * S - ph * S / 2}" '
            svg += f'width="{pw * S}" height="{ph * S}" fill="#c8a83e" rx="0.5" opacity="0.45"/>\n'

        # Body
        rx = 3 if ref[0] in "UJ" else 1
        svg += f'<rect x="{-rw / 2}" y="{-rh / 2}" width="{rw}" height="{rh}" '
        svg += f'fill="{color}" stroke="#777" stroke-width="0.5" rx="{rx}"/>\n'

        # Pin 1 dot
        if ref[0] == "U":
            svg += f'<circle cx="{-rw / 2 + 3}" cy="{-rh / 2 + 3}" r="1.2" fill="#aaa" opacity="0.4"/>\n'

        # Label
        label = c.get("label", ref)
        lines = label.split('\n')
        for li, line in enumerate(lines):
            fy = 4 + (li - len(lines) / 2) * 10
            fs = 6 if ref[0] in "RCLFDN" else 7
            svg += f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" '
            svg += f'font-family="monospace" font-size="{fs}">{line}</text>\n'
        svg += '</g>\n'

    # Zone labels
    zones = [
        (15, 5, "ETHERNET"),
        (105, 5, "SPEAKER OUT"),
        (60, 5, "Pi5 GPIO HEADER"),
        (60, 78, "POWER + STATUS"),
        (105, 78, "48V INPUT"),
    ]
    for zx, zy, ztxt in zones:
        svg += f'<text x="{ox + zx * S}" y="{oy + zy * S}" text-anchor="middle" '
        svg += f'fill="#c8a83e" font-family="monospace" font-size="7" opacity="0.5">{ztxt}</text>\n'

    # Info panel
    ly = img_h + 50
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" '
    svg += f'font-family="monospace" font-size="9">120x80mm | 2-layer 2oz FR-4 | {len(PARTS)} parts | 4x M4 mounts</text>\n'

    ly += 18
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#ef5350" '
    svg += f'font-family="monospace" font-size="10" font-weight="bold">'
    svg += f'48V DC -> TPA3255 300W mono @4ohm -> Speakon NL4</text>\n'

    ly += 18
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#42a5f5" '
    svg += f'font-family="monospace" font-size="9">'
    svg += f'Pi5 WiFi UDP -> I2S -> PCM5102A DAC -> TPA3255 -> 15" woofer</text>\n'

    ly += 18
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#66bb6a" '
    svg += f'font-family="monospace" font-size="9">'
    svg += f'Power: 48V -> LM2596 5V/3A (Pi5) -> AMS1117 3.3V (DAC/LEDs)</text>\n'

    ly += 18
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" '
    svg += f'font-family="monospace" font-size="8">'
    svg += f'Protection: NTC inrush + polyfuse + TVS | Fan header | 2x WS2812B status</text>\n'

    svg += '</svg>\n'
    path = GBR / "koe-sub-layout.svg"
    path.write_text(svg)
    print(f"  SVG: {path}")


def check():
    errs = []
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]
        cx, cy = c["x"], c["y"]
        rot = c.get("rot", 0)
        sw, sh = fp["size"]
        corners = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2), (sw / 2, sh / 2), (-sw / 2, sh / 2)]
        for dx, dy in corners:
            rx, ry = xform(dx, dy, cx, cy, rot)
            if not in_rect(rx, ry, 0.5):
                errs.append(f"  {ref} ({rx:.1f},{ry:.1f}) outside board!")

    # Check component overlap (bounding box)
    refs = list(PARTS.keys())
    for i in range(len(refs)):
        ci = PARTS[refs[i]]
        fi = FP[ci["fp"]]
        for j in range(i + 1, len(refs)):
            cj = PARTS[refs[j]]
            fj = FP[cj["fp"]]
            dx = abs(ci["x"] - cj["x"])
            dy = abs(ci["y"] - cj["y"])
            min_dx = (fi["size"][0] + fj["size"][0]) / 2 + 0.5
            min_dy = (fi["size"][1] + fj["size"][1]) / 2 + 0.5
            if dx < min_dx and dy < min_dy:
                errs.append(f"  {refs[i]} <-> {refs[j]} overlap! (dx={dx:.1f}<{min_dx:.1f}, dy={dy:.1f}<{min_dy:.1f})")

    # Check mounting holes don't overlap components
    for mx, my in MOUNTS:
        for ref, c in PARTS.items():
            dx = abs(c["x"] - mx)
            dy = abs(c["y"] - my)
            fp = FP[c["fp"]]
            min_d = max(fp["size"]) / 2 + M4_PAD / 2 + 0.5
            if math.sqrt(dx ** 2 + dy ** 2) < min_d:
                errs.append(f"  {ref} too close to mount ({mx},{my})!")

    if errs:
        print("DRC WARNINGS:")
        for e in errs:
            print(e)
    else:
        print("  DRC: All OK")
    return len(errs) == 0


def main():
    print("=" * 65)
    print("Koe SUB v1 — 120x80mm 300W Class-D Subwoofer Board")
    print(f"  {len(PARTS)} parts | Pi5 + TPA3255 + PCM5102A | 48V/10A")
    print("=" * 65)
    check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()

    print(f"\n  Signal chain:")
    print(f"    WiFi UDP (Pi5) -> I2S -> PCM5102A -> TPA3255 -> Speakon NL4")
    print(f"  Power chain:")
    print(f"    48V DC barrel -> NTC inrush -> polyfuse -> TPA3255 PVCC")
    print(f"    48V -> LM2596 -> 5V/3A (Pi5)")
    print(f"    5V -> AMS1117 -> 3.3V (DAC, LEDs)")
    print(f"  Protection:")
    print(f"    NTC inrush limiter, polyfuse 2.5A, TVS on speaker output")
    print(f"  Thermal:")
    print(f"    2oz copper, heavy GND pour, thermal vias under TPA3255 + LM2596")


if __name__ == "__main__":
    main()
