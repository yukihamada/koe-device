#!/usr/bin/env python3
"""
Koe FILL PCB — 100x80mm Rectangle, ESP32-S3 + Pi CM5 Powered Speaker
======================================================================
Mid-range powered speaker for festivals.
Receives audio from STAGE via WiFi UDP, amplifies through 8" woofer + 1" horn.

Board: 100x80mm, 2-layer FR-4
MCU: ESP32-S3-MINI-1-N8R2 (WiFi receiver)
Compute: Raspberry Pi CM5 (2x 100-pin high-density connector)
DAC: PCM5102A (I2S → analog)
Amp: TPA3116D2 Class-D 2x50W (HTSSOP-32)
Power: 24V DC → LM2596 5V buck → AMS1117-3.3
Connectors: Speakon NL4, USB-C, DC barrel jack
"""

import math
import zipfile
from pathlib import Path

BOARD_W = 100.0
BOARD_H = 80.0
TRACE, PWR, VIA_D, VIA_P = 0.2, 0.5, 0.3, 0.6

OUT = Path(__file__).parent / "kicad"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-fill"

def in_rect(x, y, m=0.5):
    return m <= x <= BOARD_W - m and m <= y <= BOARD_H - m

# ── Footprints ────────────────────────────────────────────────────────
FP = {}

# ESP32-S3-MINI-1: 15.4x20.5mm module, castellated
# Simplified: 2 rows of pads along long edges + GND pad
def _esp32s3():
    p = []
    # Left side: 19 pads, 1.27mm pitch
    for i in range(19):
        p.append((i+1, -7.2, -11.43 + i * 1.27, 0.5, 0.9))
    # Right side: 19 pads
    for i in range(19):
        p.append((20+i, 7.2, -11.43 + i * 1.27, 0.5, 0.9))
    # Bottom GND pad
    p.append((39, 0, 10.0, 6.0, 2.4))
    return p

FP["ESP32S3"] = {"pads": _esp32s3(), "size": (15.4, 20.5)}

# TPA3116D2: HTSSOP-32, 11x6.1mm, 0.65mm pitch
def _tpa3116():
    p = []
    # Left: 16 pins
    for i in range(16):
        p.append((i+1, -5.35, -4.875 + i * 0.65, 0.3, 1.2))
    # Right: 16 pins
    for i in range(16):
        p.append((17+i, 5.35, -4.875 + i * 0.65, 0.3, 1.2))
    # Exposed thermal pad
    p.append((33, 0, 0, 6.0, 4.5))
    return p

FP["TPA3116"] = {"pads": _tpa3116(), "size": (11.0, 6.5)}

# PCM5102A: SSOP-20, 6.5x7.5mm, 0.65mm pitch
def _pcm5102():
    p = []
    for i in range(10):
        p.append((i+1, -3.75, -2.925 + i * 0.65, 0.4, 1.5))
    for i in range(10):
        p.append((11+i, 3.75, -2.925 + i * 0.65, 0.4, 1.5))
    return p

FP["PCM5102"] = {"pads": _pcm5102(), "size": (6.5, 7.5)}

# LM2596: TO-263-5 (D2PAK-5), buck converter
FP["TO263"] = {"pads": [
    (1, -3.4, -5.0, 1.5, 2.5),
    (2, -1.7, -5.0, 1.5, 2.5),
    (3, 0.0, -5.0, 1.5, 2.5),
    (4, 1.7, -5.0, 1.5, 2.5),
    (5, 3.4, -5.0, 1.5, 2.5),
    (6, 0.0, 3.0, 10.0, 8.5),  # Thermal tab
], "size": (10.5, 15.3)}

# AMS1117-3.3: SOT-223
FP["SOT223"] = {"pads": [
    (1, -2.3, 3.25, 0.8, 1.5),
    (2, 0.0, 3.25, 0.8, 1.5),
    (3, 2.3, 3.25, 0.8, 1.5),
    (4, 0.0, -3.25, 3.0, 1.5),  # Tab
], "size": (6.5, 7.0)}

# Raspberry Pi CM5 connector: 2x 100-pin Hirose DF40 (0.4mm pitch)
# Each connector: ~21x3mm footprint
def _cm5_conn():
    p = []
    for i in range(50):
        p.append((i*2+1, -9.8 + i * 0.4, -0.85, 0.2, 0.7))
        p.append((i*2+2, -9.8 + i * 0.4,  0.85, 0.2, 0.7))
    return p

FP["CM5_CONN"] = {"pads": _cm5_conn(), "size": (21.0, 3.0)}

# Speakon NL4: 4-pin panel mount (through-hole pads)
FP["SPEAKON"] = {"pads": [
    (1, -5.0, -5.0, 2.5, 2.5),
    (2, 5.0, -5.0, 2.5, 2.5),
    (3, -5.0, 5.0, 2.5, 2.5),
    (4, 5.0, 5.0, 2.5, 2.5),
    # Mounting tabs
    ("M1", -10.0, 0.0, 3.0, 3.0),
    ("M2", 10.0, 0.0, 3.0, 3.0),
], "size": (24.0, 14.0)}

# DC barrel jack: 2.1mm x 5.5mm (through-hole)
FP["DC_BARREL"] = {"pads": [
    (1, 0.0, 0.0, 2.5, 2.5),   # Center pin (+24V)
    (2, -4.7, 0.0, 2.5, 2.5),  # Sleeve (GND)
    (3, -4.7, 4.5, 2.5, 2.5),  # Switch
], "size": (14.0, 9.0)}

# USB-C (16-pin SMD)
FP["USBC"] = {"pads": [
    ("V1",-2.75,-1.0,0.6,1.2), ("V2",2.75,-1.0,0.6,1.2),
    ("D-",-0.25,-1.0,0.3,1.0), ("D+",0.25,-1.0,0.3,1.0),
    ("C1",-1.75,-1.0,0.3,1.0), ("C2",1.75,-1.0,0.3,1.0),
    ("G1",-3.5,-1.0,0.5,1.0),  ("G2",3.5,-1.0,0.5,1.0),
    ("S1",-4.15,0.5,0.6,1.6),  ("S2",4.15,0.5,0.6,1.6),
], "size": (9.0, 3.5)}

FP["WS2812B"] = {"pads": [
    (1,-2.45,-1.6,1.0,1.0), (2,2.45,-1.6,1.0,1.0),
    (3,2.45,1.6,1.0,1.0),   (4,-2.45,1.6,1.0,1.0),
], "size": (5.0, 5.0)}

FP["SW"] = {"pads": [(1,-3.25,0,1.5,1.0),(2,3.25,0,1.5,1.0)], "size": (6.0, 3.5)}

# Fan header: 2-pin, 2.54mm pitch
FP["FAN_HDR"] = {"pads": [
    (1, -1.27, 0, 1.6, 1.6),
    (2, 1.27, 0, 1.6, 1.6),
], "size": (5.08, 2.54)}

# Mounting hole M4
FP["M4_HOLE"] = {"pads": [
    (1, 0, 0, 5.5, 5.5),  # Annular ring
], "size": (5.5, 5.5)}

# Passive components
FP["0402"] = {"pads": [(1,-0.48,0,0.56,0.62),(2,0.48,0,0.56,0.62)], "size": (1.6, 0.8)}
FP["0603"] = {"pads": [(1,-0.75,0,0.8,1.0),(2,0.75,0,0.8,1.0)], "size": (2.2, 1.2)}
FP["0805"] = {"pads": [(1,-0.95,0,1.0,1.2),(2,0.95,0,1.0,1.2)], "size": (2.8, 1.5)}
FP["1206"] = {"pads": [(1,-1.4,0,1.2,1.6),(2,1.4,0,1.2,1.6)], "size": (4.0, 2.0)}

# Electrolytic cap (8mm radial SMD)
FP["CAP_8MM"] = {"pads": [
    (1, -1.5, 0, 2.0, 2.0),
    (2, 1.5, 0, 2.0, 2.0),
], "size": (8.0, 8.0)}

# Inductor (LM2596 requires 33uH power inductor, ~12x12mm)
FP["IND_12MM"] = {"pads": [
    (1, -4.5, 0, 3.0, 3.0),
    (2, 4.5, 0, 3.0, 3.0),
], "size": (12.0, 12.0)}

# Schottky diode (LM2596 requires fast recovery, SMA/SMB)
FP["SMB"] = {"pads": [
    (1, -2.0, 0, 2.0, 2.5),
    (2, 2.0, 0, 2.0, 2.5),
], "size": (5.3, 3.6)}


# ── Components ────────────────────────────────────────────────────────
PARTS = {
    # ── MCU ──
    "U1": {"fp": "ESP32S3", "x": 15.0, "y": 40.0, "rot": 0,
            "part": "ESP32-S3-MINI-1-N8R2", "lcsc": "C2913202",
            "label": "ESP32-S3\nMINI-1", "color": "#0d47a1"},

    # ── Class-D Amp ──
    "U2": {"fp": "TPA3116", "x": 65.0, "y": 40.0, "rot": 0,
            "part": "TPA3116D2DADR", "lcsc": "C37833",
            "label": "TPA3116\n2x50W", "color": "#b71c1c"},

    # ── DAC ──
    "U3": {"fp": "PCM5102", "x": 40.0, "y": 40.0, "rot": 0,
            "part": "PCM5102APWR", "lcsc": "C107634",
            "label": "PCM5102A\nDAC", "color": "#4a148c"},

    # ── 5V Buck (LM2596-5.0) ──
    "U4": {"fp": "TO263", "x": 65.0, "y": 67.0, "rot": 0,
            "part": "LM2596S-5.0/NOPB", "lcsc": "C29781",
            "label": "LM2596\n5V Buck", "color": "#4e342e"},

    # ── 3.3V LDO ──
    "U5": {"fp": "SOT223", "x": 15.0, "y": 67.0, "rot": 0,
            "part": "AMS1117-3.3", "lcsc": "C6186",
            "label": "AMS1117\n3.3V", "color": "#4e342e"},

    # ── Pi CM5 connectors ──
    "J1": {"fp": "CM5_CONN", "x": 50.0, "y": 15.0, "rot": 0,
            "part": "DF40HC(3.0)-100DS-0.4V", "lcsc": "C2906057",
            "label": "CM5 Conn A", "color": "#006064"},
    "J2": {"fp": "CM5_CONN", "x": 50.0, "y": 22.0, "rot": 0,
            "part": "DF40HC(3.0)-100DS-0.4V", "lcsc": "C2906057",
            "label": "CM5 Conn B", "color": "#006064"},

    # ── Speakon NL4 ──
    "J3": {"fp": "SPEAKON", "x": 88.0, "y": 40.0, "rot": 0,
            "part": "NL4MP", "lcsc": "",
            "label": "Speakon\nNL4", "color": "#263238"},

    # ── USB-C ──
    "J4": {"fp": "USBC", "x": 15.0, "y": 4.0, "rot": 0,
            "part": "TYPE-C-16PIN-2MD", "lcsc": "C2765186",
            "label": "USB-C", "color": "#78909c"},

    # ── DC Barrel Jack ──
    "J5": {"fp": "DC_BARREL", "x": 88.0, "y": 67.0, "rot": 0,
            "part": "PJ-102AH (5.5x2.1mm)", "lcsc": "C136744",
            "label": "24V DC\nInput", "color": "#e65100"},

    # ── Fan header ──
    "J6": {"fp": "FAN_HDR", "x": 40.0, "y": 72.0, "rot": 0,
            "part": "2-pin header 2.54mm", "lcsc": "C49661",
            "label": "FAN", "color": "#455a64"},

    # ── Status LEDs ──
    "LED1": {"fp": "WS2812B", "x": 6.0, "y": 15.0, "rot": 0,
             "part": "WS2812B-5050", "lcsc": "C114586",
             "label": "LED1", "color": "#f9a825"},
    "LED2": {"fp": "WS2812B", "x": 6.0, "y": 25.0, "rot": 0,
             "part": "WS2812B-5050", "lcsc": "C114586",
             "label": "LED2", "color": "#f9a825"},

    # ── Reset button ──
    "SW1": {"fp": "SW", "x": 6.0, "y": 55.0, "rot": 0,
            "part": "EVQP0N02B", "lcsc": "C2936178",
            "label": "RST", "color": "#455a64"},

    # ── Mounting holes ──
    "MH1": {"fp": "M4_HOLE", "x": 4.0, "y": 4.0, "rot": 0,
             "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH2": {"fp": "M4_HOLE", "x": 96.0, "y": 4.0, "rot": 0,
             "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH3": {"fp": "M4_HOLE", "x": 4.0, "y": 76.0, "rot": 0,
             "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH4": {"fp": "M4_HOLE", "x": 96.0, "y": 76.0, "rot": 0,
             "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},

    # ── Buck converter external components ──
    # LM2596 requires: 680uF input, 220uF output, 33uH inductor, Schottky diode
    "D1": {"fp": "SMB", "x": 55.0, "y": 72.0, "rot": 0,
            "part": "SS34 (3A Schottky)", "lcsc": "C8678",
            "label": "D1", "color": "#263238"},
    "L1": {"fp": "IND_12MM", "x": 50.0, "y": 60.0, "rot": 0,
            "part": "33uH 3A", "lcsc": "C408428",
            "label": "33uH", "color": "#006064"},

    # ── Electrolytic caps (buck converter) ──
    "C1": {"fp": "CAP_8MM", "x": 78.0, "y": 72.0, "rot": 0,
            "part": "680uF/35V", "lcsc": "C249462",
            "label": "680u", "color": "#1a237e"},
    "C2": {"fp": "CAP_8MM", "x": 38.0, "y": 60.0, "rot": 0,
            "part": "220uF/10V", "lcsc": "C65221",
            "label": "220u", "color": "#1a237e"},

    # ── Decoupling / filter caps ──
    "C3": {"fp": "0805", "x": 20.0, "y": 30.0, "rot": 0,
            "part": "100nF", "lcsc": "C49678", "label": "C3", "color": "#1a237e"},
    "C4": {"fp": "0805", "x": 20.0, "y": 50.0, "rot": 0,
            "part": "10uF", "lcsc": "C15850", "label": "C4", "color": "#1a237e"},
    "C5": {"fp": "0805", "x": 35.0, "y": 30.0, "rot": 0,
            "part": "100nF", "lcsc": "C49678", "label": "C5", "color": "#1a237e"},
    "C6": {"fp": "0805", "x": 35.0, "y": 50.0, "rot": 0,
            "part": "10uF", "lcsc": "C15850", "label": "C6", "color": "#1a237e"},
    # TPA3116 supply bypass (24V side)
    "C7": {"fp": "1206", "x": 60.0, "y": 30.0, "rot": 0,
            "part": "10uF/50V", "lcsc": "C13585", "label": "C7", "color": "#1a237e"},
    "C8": {"fp": "0805", "x": 70.0, "y": 30.0, "rot": 0,
            "part": "100nF", "lcsc": "C49678", "label": "C8", "color": "#1a237e"},
    # AMS1117 caps
    "C9": {"fp": "0805", "x": 10.0, "y": 60.0, "rot": 0,
            "part": "10uF", "lcsc": "C15850", "label": "C9", "color": "#1a237e"},
    "C10": {"fp": "0805", "x": 22.0, "y": 60.0, "rot": 0,
             "part": "22uF", "lcsc": "C45783", "label": "C10", "color": "#1a237e"},
    # PCM5102 DVDD decoupling
    "C11": {"fp": "0805", "x": 45.0, "y": 30.0, "rot": 0,
             "part": "100nF", "lcsc": "C49678", "label": "C11", "color": "#1a237e"},
    "C12": {"fp": "0805", "x": 45.0, "y": 50.0, "rot": 0,
             "part": "2.2uF", "lcsc": "C49217", "label": "C12", "color": "#1a237e"},

    # ── Resistors ──
    # USB CC resistors
    "R1": {"fp": "0402", "x": 11.0, "y": 8.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R1", "color": "#5d4037"},
    "R2": {"fp": "0402", "x": 19.0, "y": 8.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R2", "color": "#5d4037"},
    # TPA3116 gain set (200k = 26dB)
    "R3": {"fp": "0805", "x": 60.0, "y": 50.0, "rot": 90,
            "part": "200k", "lcsc": "C17574", "label": "R3", "color": "#5d4037"},
    "R4": {"fp": "0805", "x": 70.0, "y": 50.0, "rot": 90,
            "part": "200k", "lcsc": "C17574", "label": "R4", "color": "#5d4037"},
    # LED data resistor
    "R5": {"fp": "0402", "x": 6.0, "y": 35.0, "rot": 90,
            "part": "330R", "lcsc": "C25104", "label": "R5", "color": "#5d4037"},
    # PCM5102 FLT/DEMP/XSMT pull
    "R6": {"fp": "0402", "x": 40.0, "y": 30.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R6", "color": "#5d4037"},
}


# ── Routes ────────────────────────────────────────────────────────────
ROUTES = [
    # 24V power: DC barrel → amp supply + buck converter
    ("+24V", PWR, [(88.0, 67.0), (78.0, 67.0), (65.0, 67.0)]),   # DC → buck
    ("+24V", PWR, [(78.0, 67.0), (78.0, 40.0), (65.0+5.35, 40.0)]),  # DC → TPA3116

    # 5V from buck
    ("+5V", PWR, [(50.0, 60.0), (38.0, 60.0), (15.0, 60.0)]),  # Buck out → LDO in
    ("+5V", PWR, [(38.0, 60.0), (38.0, 22.0), (50.0, 22.0)]),  # → CM5 connector
    ("+5V", PWR, [(15.0, 60.0), (15.0, 55.0)]),                 # → near ESP area

    # 3.3V from LDO
    ("+3V3", TRACE, [(15.0, 63.75), (15.0, 52.0), (15.0, 40.0)]),  # LDO → ESP32
    ("+3V3", TRACE, [(15.0, 40.0), (20.0, 40.0), (40.0, 40.0)]),   # → PCM5102
    ("+3V3", TRACE, [(15.0, 25.0), (6.0, 25.0)]),                   # → LED2
    ("+3V3", TRACE, [(6.0, 25.0), (6.0, 15.0)]),                    # → LED1

    # I2S: ESP32 → PCM5102A
    ("I2S_BCK", TRACE, [(15.0+7.2, 35.0), (40.0-3.75, 37.8)]),
    ("I2S_LRCK", TRACE, [(15.0+7.2, 36.27), (40.0-3.75, 38.45)]),
    ("I2S_DIN", TRACE, [(15.0+7.2, 37.54), (40.0-3.75, 39.1)]),

    # Analog: PCM5102A → TPA3116
    ("OUTL", TRACE, [(40.0+3.75, 38.45), (55.0, 38.45), (65.0-5.35, 38.45)]),
    ("OUTR", TRACE, [(40.0+3.75, 39.1), (55.0, 39.1), (65.0-5.35, 39.1)]),

    # Amp → Speakon
    ("SPK1+", PWR, [(65.0+5.35, 36.0), (78.0, 35.0), (88.0-5.0, 35.0)]),
    ("SPK1-", PWR, [(65.0+5.35, 37.0), (78.0, 38.0), (88.0-5.0, 38.0)]),
    ("SPK2+", PWR, [(65.0+5.35, 42.0), (78.0, 43.0), (88.0-5.0, 43.0)]),
    ("SPK2-", PWR, [(65.0+5.35, 44.0), (78.0, 45.0), (88.0+5.0, 45.0)]),

    # LED chain
    ("LED_DIN", TRACE, [(15.0-7.2, 40.0-4*1.27), (6.0, 35.0)]),
    ("LED_CHAIN", TRACE, [(6.0+2.45, 15.0+1.6), (6.0-2.45, 25.0-1.6)]),

    # USB data
    ("USB_D+", 0.2, [(15.0-7.2, 40.0+2*1.27), (15.0+0.25, 4.0)]),
    ("USB_D-", 0.2, [(15.0-7.2, 40.0+3*1.27), (15.0-0.25, 4.0)]),

    # USB CC
    ("CC1", TRACE, [(11.0, 8.0), (15.0-1.75, 4.0)]),
    ("CC2", TRACE, [(19.0, 8.0), (15.0+1.75, 4.0)]),

    # ESP32 → CM5 (SPI/UART)
    ("SPI", TRACE, [(15.0+7.2, 40.0-2*1.27), (29.0, 15.0)]),

    # Fan
    ("FAN_PWR", TRACE, [(40.0-1.27, 72.0), (38.0, 60.0)]),

    # Reset button
    ("RST", TRACE, [(6.0+3.25, 55.0), (15.0-7.2, 40.0+5*1.27)]),
]

VIAS = [
    (10, 10), (50, 10), (90, 10),
    (10, 40), (30, 40), (50, 40), (70, 40), (90, 40),
    (10, 70), (30, 70), (50, 70), (70, 70), (90, 70),
    (25, 25), (75, 25), (25, 55), (75, 55),
    # Extra GND vias near amp thermal pad
    (62, 40), (65, 43), (68, 40), (65, 37),
]


# ── Helpers ───────────────────────────────────────────────────────────
def xform(px, py, cx, cy, rot):
    r = math.radians(rot)
    return cx + px * math.cos(r) - py * math.sin(r), cy + px * math.sin(r) + py * math.cos(r)

class Gbr:
    def __init__(s, name): s.name, s.ap, s.nd, s.cmds = name, {}, 10, []
    def _a(s, sh, p):
        k = (sh, tuple(p))
        if k not in s.ap: s.ap[k] = s.nd; s.nd += 1
        return s.ap[k]
    def _c(s, v): return int(round(v * 1e6))
    def pad(s, x, y, w, h):
        d = s._a("C", [w]) if abs(w - h) < .01 else s._a("R", [w, h])
        s.cmds += [f"D{d}*", f"X{s._c(x)}Y{s._c(y)}D03*"]
    def trace(s, x1, y1, x2, y2, w):
        d = s._a("C", [w])
        s.cmds += [f"D{d}*", f"X{s._c(x1)}Y{s._c(y1)}D02*", f"X{s._c(x2)}Y{s._c(y2)}D01*"]
    def circ(s, x, y, d_):
        d = s._a("C", [d_]); s.cmds += [f"D{d}*", f"X{s._c(x)}Y{s._c(y)}D03*"]
    def rect(s, x1, y1, x2, y2, w=0.05):
        """Draw rectangle outline"""
        d = s._a("C", [w]); s.cmds.append(f"D{d}*")
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
        for i, (x, y) in enumerate(corners):
            s.cmds.append(f"X{s._c(x)}Y{s._c(y)}D0{'2' if i == 0 else '1'}*")
    def write(s, path):
        with open(path, 'w') as f:
            f.write("%FSLAX46Y46*%\n%MOMM*%\n")
            f.write(f"G04 Koe FILL {s.name}*\n%LPD*%\n")
            for (sh, p), dc in sorted(s.ap.items(), key=lambda x: x[1]):
                if sh == "C": f.write(f"%ADD{dc}C,{p[0]:.3f}*%\n")
                elif sh == "R": f.write(f"%ADD{dc}R,{p[0]:.3f}X{p[1]:.3f}*%\n")
            for c in s.cmds: f.write(c + "\n")
            f.write("M02*\n")

class Drl:
    def __init__(s): s.t, s.nt, s.h = {}, 1, []
    def hole(s, x, y, d):
        k = round(d, 3)
        if k not in s.t: s.t[k] = s.nt; s.nt += 1
        s.h.append((s.t[k], x, y))
    def write(s, path):
        with open(path, 'w') as f:
            f.write("M48\n; Koe FILL 100x80mm ESP32-S3 + Pi CM5\nFMAT,2\nMETRIC,TZ\n")
            for d, t in sorted(s.t.items(), key=lambda x: x[1]): f.write(f"T{t}C{d:.3f}\n")
            f.write("%\n"); ct = None
            for t, x, y in s.h:
                if t != ct: f.write(f"T{t}\n"); ct = t
                f.write(f"X{x:.3f}Y{y:.3f}\n")
            f.write("M30\n")


def gen_gerbers():
    GBR.mkdir(parents=True, exist_ok=True)
    fc, bc, fm, bm, fs_, bs_, ec = [Gbr(n) for n in
        ["F.Cu", "B.Cu", "F.Mask", "B.Mask", "F.SilkS", "B.SilkS", "Edge.Cuts"]]
    dr = Drl()

    # Rectangular board outline
    ec.rect(0, 0, BOARD_W, BOARD_H)

    # Place components
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]; cx, cy, rot = c["x"], c["y"], c.get("rot", 0)
        sw, sh = fp["size"]
        co = [(-sw/2, -sh/2), (sw/2, -sh/2), (sw/2, sh/2), (-sw/2, sh/2)]
        ca = [xform(a, b, cx, cy, rot) for a, b in co]
        for i in range(4):
            fs_.trace(ca[i][0], ca[i][1], ca[(i+1)%4][0], ca[(i+1)%4][1], 0.12)
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            ax, ay = xform(px, py, cx, cy, rot)
            if rot in (90, 270): pw, ph = ph, pw
            fc.pad(ax, ay, pw, ph); fm.pad(ax, ay, pw + 0.1, ph + 0.1)

    # Traces
    for _, w, pts in ROUTES:
        for i in range(len(pts) - 1):
            fc.trace(pts[i][0], pts[i][1], pts[i+1][0], pts[i+1][1], w)

    # Vias
    for vx, vy in VIAS:
        for g in (fc, bc): g.circ(vx, vy, VIA_P)
        for g in (fm, bm): g.circ(vx, vy, VIA_P + 0.1)
        dr.hole(vx, vy, VIA_D)

    # Mounting holes (M4 = 4.3mm drill)
    for ref in ("MH1", "MH2", "MH3", "MH4"):
        c = PARTS[ref]
        dr.hole(c["x"], c["y"], 4.3)

    # Through-hole component drills (Speakon, DC barrel)
    for ref in ("J3", "J5"):
        c = PARTS[ref]
        fp = FP[c["fp"]]
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            ax, ay = xform(px, py, c["x"], c["y"], c.get("rot", 0))
            dr.hole(ax, ay, 1.2)

    # Ground copper pour annotation (back copper = full GND)
    bc.rect(1, 1, BOARD_W - 1, BOARD_H - 1, 0.3)

    pre = "koe-fill"
    for n, g in [("F_Cu", fc), ("B_Cu", bc), ("F_Mask", fm), ("B_Mask", bm),
                 ("F_SilkS", fs_), ("B_SilkS", bs_), ("Edge_Cuts", ec)]:
        g.write(GBR / f"{pre}-{n}.gbr")
    dr.write(GBR / f"{pre}.drl")

    zp = GBR / f"{pre}.zip"
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in GBR.glob(f"{pre}-*"): z.write(f, f.name)
        z.write(GBR / f"{pre}.drl", f"{pre}.drl")
    print(f"Gerber ZIP: {zp}")


def gen_bom():
    lines = ["Comment,Designator,Footprint,LCSC Part#"]
    by = {}
    for ref, c in PARTS.items():
        k = (c.get("part", ""), c["fp"], c.get("lcsc", ""))
        by.setdefault(k, []).append(ref)
    for (p, fp, l), refs in by.items():
        lines.append(f"{p},{' '.join(refs)},{fp},{l}")
    (GBR / "BOM-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"BOM: {GBR / 'BOM-JLCPCB.csv'}")


def gen_cpl():
    ROT = {"SOT223": 180, "TO263": 180}
    lines = ["Designator,Mid X(mm),Mid Y(mm),Layer,Rotation"]
    for ref, c in PARTS.items():
        rot = c.get("rot", 0) + ROT.get(c["fp"], 0)
        lines.append(f"{ref},{c['x']:.1f},{c['y']:.1f},Top,{rot % 360}")
    (GBR / "CPL-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"CPL: {GBR / 'CPL-JLCPCB.csv'}")


# ── SVG ───────────────────────────────────────────────────────────────
def gen_svg():
    S = 8; pad = 60; img_w = int(BOARD_W * S + pad * 2); img_h = int(BOARD_H * S + pad * 2)
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
<text x="{img_w // 2}" y="22" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="16" font-weight="600">Koe FILL v1 -- ESP32-S3 + Pi CM5 Powered Speaker</text>
<text x="{img_w // 2}" y="40" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">100x80mm | 2-layer FR-4 | TPA3116D2 2x50W | PCM5102A DAC | 24V DC</text>

<!-- Board -->
<rect x="{ox - 2}" y="{oy - 2}" width="{BOARD_W * S + 4}" height="{BOARD_H * S + 4}" fill="#000" opacity="0.3" rx="3"/>
<rect x="{ox}" y="{oy}" width="{BOARD_W * S}" height="{BOARD_H * S}" fill="url(#pcb)" stroke="#c8a83e" stroke-width="1.5" rx="2"/>
'''

    # Copper pour hint (back side GND)
    svg += f'<rect x="{ox + 4}" y="{oy + 4}" width="{BOARD_W * S - 8}" height="{BOARD_H * S - 8}" fill="none" stroke="#1a5c1a" stroke-width="0.5" stroke-dasharray="4,4" rx="1"/>\n'

    # Amp thermal relief zone
    amp = PARTS["U2"]
    ax, ay = ox + amp["x"] * S, oy + amp["y"] * S
    svg += f'<rect x="{ax - 30}" y="{ay - 20}" width="60" height="40" fill="#4a2800" opacity="0.15" rx="3"/>\n'
    svg += f'<text x="{ax}" y="{ay + 30}" text-anchor="middle" fill="#8b4513" font-family="monospace" font-size="6" opacity="0.5">thermal relief zone</text>\n'

    # Traces
    net_colors = {
        "24V": "#ef5350", "5V": "#ff7043", "3V3": "#66bb6a",
        "I2S": "#42a5f5", "SPI": "#42a5f5", "USB": "#ffca28",
        "SPK": "#ff5722", "LED": "#f9a825", "FAN": "#78909c",
        "CC": "#78909c", "RST": "#78909c", "OUT": "#ce93d8",
    }
    for net, w, pts in ROUTES:
        c = "#78909c"
        for k, v in net_colors.items():
            if k in net: c = v; break
        for i in range(len(pts) - 1):
            svg += f'<line x1="{ox + pts[i][0] * S}" y1="{oy + pts[i][1] * S}" x2="{ox + pts[i+1][0] * S}" y2="{oy + pts[i+1][1] * S}" stroke="{c}" stroke-width="{max(1.5, w * S * 0.5)}" opacity="0.35" stroke-linecap="round"/>\n'

    # Vias
    for vx, vy in VIAS:
        svg += f'<circle cx="{ox + vx * S}" cy="{oy + vy * S}" r="{VIA_P * S / 2 + 1}" fill="#1a1a1a" stroke="#666" stroke-width="0.5"/>\n'

    # Mounting holes
    for ref in ("MH1", "MH2", "MH3", "MH4"):
        c = PARTS[ref]
        mx, my = ox + c["x"] * S, oy + c["y"] * S
        svg += f'<circle cx="{mx}" cy="{my}" r="{4.3 * S / 2}" fill="#1a1a1a" stroke="#888" stroke-width="1"/>\n'
        svg += f'<circle cx="{mx}" cy="{my}" r="{2.15 * S}" fill="none" stroke="#c8a83e" stroke-width="0.5" opacity="0.4"/>\n'

    # Components
    for ref, c in PARTS.items():
        if ref.startswith("MH"): continue
        fp = FP[c["fp"]]; cx_, cy_ = c["x"], c["y"]; rot = c.get("rot", 0)
        sw, sh = fp["size"]; color = c.get("color", "#5d4037")
        sx, sy = ox + cx_ * S, oy + cy_ * S; rw, rh = sw * S, sh * S

        svg += f'<g transform="translate({sx},{sy}) rotate({rot})" filter="url(#sh)">\n'
        # Pads
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            svg += f'<rect x="{px * S - pw * S / 2}" y="{py * S - ph * S / 2}" width="{pw * S}" height="{ph * S}" fill="#c8a83e" rx="0.3" opacity="0.45"/>\n'
        # Body
        rx = 3 if ref[0] in "UJ" else 1
        svg += f'<rect x="{-rw / 2}" y="{-rh / 2}" width="{rw}" height="{rh}" fill="{color}" stroke="#777" stroke-width="0.5" rx="{rx}"/>\n'
        if ref[0] == "U":
            svg += f'<circle cx="{-rw / 2 + 4}" cy="{-rh / 2 + 4}" r="1.5" fill="#aaa" opacity="0.4"/>\n'
        # Label
        label = c.get("label", ref)
        lines = label.split('\n')
        for li, line in enumerate(lines):
            fy = 4 + (li - len(lines) / 2) * 10
            fs = 5 if ref[0] in "RCLY" else 7
            if ref.startswith("LED") or ref == "SW1": fs = 6
            svg += f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="{fs}">{line}</text>\n'
        svg += '</g>\n'

    # Legend
    ly = img_h + 15
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="9">100x80mm | 2-layer | {len(PARTS)} parts | ESP32-S3 WiFi + Pi CM5 compute</text>\n'

    # Signal flow
    ly += 22
    flow_items = [
        ("WiFi UDP", "#42a5f5"), ("ESP32-S3", "#0d47a1"), ("I2S", "#42a5f5"),
        ("PCM5102A", "#4a148c"), ("Analog", "#ce93d8"), ("TPA3116D2", "#b71c1c"),
        ("Speakon", "#263238"),
    ]
    total_w = sum(len(t) * 6.5 + 20 for t, _ in flow_items)
    fx = (img_w - total_w) / 2
    for i, (text, col) in enumerate(flow_items):
        tw = len(text) * 6.5 + 10
        svg += f'<rect x="{fx}" y="{ly - 10}" width="{tw}" height="16" fill="{col}" rx="3" opacity="0.7"/>\n'
        svg += f'<text x="{fx + tw / 2}" y="{ly + 2}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="8">{text}</text>\n'
        fx += tw + 5
        if i < len(flow_items) - 1:
            svg += f'<text x="{fx - 2}" y="{ly + 2}" text-anchor="middle" fill="#888" font-family="monospace" font-size="10">&#8594;</text>\n'

    # Power flow
    ly += 28
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#ef5350" font-family="monospace" font-size="9" font-weight="bold">24V DC &#8594; LM2596 &#8594; 5V (Pi/ESP) &#8594; AMS1117 &#8594; 3.3V (logic)</text>\n'
    ly += 16
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">24V direct to TPA3116D2 for 2x50W speaker drive</text>\n'

    # Price
    ly += 22
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#c8a83e" font-family="monospace" font-size="9">FILL $1500 | 8" woofer + 1" horn | WiFi UDP receiver | Pi CM5 DSP</text>\n'

    svg += '</svg>\n'
    path = GBR / "koe-fill-layout.svg"
    path.write_text(svg)
    print(f"SVG: {path}")


def check():
    errs = []
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]; cx, cy = c["x"], c["y"]; sw, sh = fp["size"]
        rot = c.get("rot", 0)
        corners = [(-sw/2, -sh/2), (sw/2, -sh/2), (sw/2, sh/2), (-sw/2, sh/2)]
        for dx, dy in corners:
            ax, ay = xform(dx, dy, cx, cy, rot)
            if not in_rect(ax, ay, 0):
                errs.append(f"  {ref} ({ax:.1f},{ay:.1f}) outside board!")
    if errs:
        print("DRC WARNINGS:")
        for e in errs: print(e)
    else:
        print("DRC: All components within 100x80mm board -- OK")
    return len(errs) == 0


def main():
    print("=" * 65)
    print("Koe FILL v1 -- 100x80mm Powered Speaker Board")
    print(f"  {len(PARTS)} parts | ESP32-S3 + Pi CM5 | TPA3116D2 2x50W")
    print(f"  PCM5102A DAC | 24V DC input | Speakon NL4 output")
    print("=" * 65)
    check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()
    print(f"\nSignal chain:")
    print(f"  WiFi UDP --> ESP32-S3 --> I2S --> PCM5102A DAC")
    print(f"  PCM5102A analog out --> TPA3116D2 amp --> Speakon NL4")
    print(f"\nPower:")
    print(f"  24V DC barrel --> TPA3116D2 (direct, 2x50W)")
    print(f"  24V DC --> LM2596 --> 5V (Pi CM5, ESP32)")
    print(f"  5V --> AMS1117 --> 3.3V (ESP32 logic, DAC)")


if __name__ == "__main__":
    main()
