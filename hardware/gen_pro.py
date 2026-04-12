#!/usr/bin/env python3
"""
Koe Pro PCB — 50x35mm Compact Board for Musicians/Performers
=============================================================
High-quality audio input with UWB time sync for sub-μs precision.

Board: 50x35mm, 4-layer FR-4 (UWB impedance control)
MCU: ESP32-S3-MINI-1-N8R2 (WiFi + BLE)
UWB: DW3000 (Qorvo, QFN-48, 6.5x6.5mm) — sub-μs time sync
ADC: PCM1808 (24-bit, SSOP-20) — guitar/mic line input
Mic: INMP441 MEMS (I2S digital)
Amp: MAX98357A (I2S monitoring)
Charger: MCP73831 (LiPo)
LDO: AP2112K-3.3
Connectors: USB-C, 3.5mm TRS, SMA (UWB antenna)
"""

import math
import zipfile
from pathlib import Path

BOARD_W = 50.0
BOARD_H = 35.0
TRACE, PWR, VIA_D, VIA_P = 0.15, 0.4, 0.25, 0.5

OUT = Path(__file__).parent / "kicad"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-pro"


def in_rect(x, y, m=0.5):
    return m <= x <= BOARD_W - m and m <= y <= BOARD_H - m


# ── Footprints ────────────────────────────────────────────────────────
FP = {}

# ESP32-S3-MINI-1: 15.4x20.5mm module, castellated
def _esp32s3():
    p = []
    for i in range(19):
        p.append((i+1, -7.2, -11.43 + i * 1.27, 0.5, 0.9))
    for i in range(19):
        p.append((20+i, 7.2, -11.43 + i * 1.27, 0.5, 0.9))
    p.append((39, 0, 10.0, 6.0, 2.4))
    return p

FP["ESP32S3"] = {"pads": _esp32s3(), "size": (15.4, 20.5)}

# DW3000: QFN-48, 6.5x6.5mm, 0.5mm pitch
def _dw3000():
    p = []
    # 12 pads per side
    for i in range(12):
        p.append((i+1, -3.25, -2.75 + i * 0.5, 0.25, 0.8))   # Left
    for i in range(12):
        p.append((13+i, -2.75 + i * 0.5, 3.25, 0.8, 0.25))    # Bottom
    for i in range(12):
        p.append((25+i, 3.25, 2.75 - i * 0.5, 0.25, 0.8))     # Right
    for i in range(12):
        p.append((37+i, 2.75 - i * 0.5, -3.25, 0.8, 0.25))    # Top
    # Exposed thermal pad
    p.append((49, 0, 0, 4.0, 4.0))
    return p

FP["DW3000"] = {"pads": _dw3000(), "size": (6.5, 6.5)}

# PCM1808: SSOP-20, 7.5x6.2mm, 0.65mm pitch
def _pcm1808():
    p = []
    for i in range(10):
        p.append((i+1, -3.75, -2.925 + i * 0.65, 0.3, 1.2))
    for i in range(10):
        p.append((11+i, 3.75, -2.925 + i * 0.65, 0.3, 1.2))
    return p

FP["PCM1808"] = {"pads": _pcm1808(), "size": (7.5, 6.2)}

# INMP441: LGA-8, 4.72x3.76mm
FP["INMP441"] = {"pads": [
    (1, -1.5, -1.25, 0.6, 0.7),  # WS
    (2, -1.5,  0.0,  0.6, 0.7),  # SEL (L/R)
    (3, -1.5,  1.25, 0.6, 0.7),  # GND
    (4,  1.5,  1.25, 0.6, 0.7),  # VDD
    (5,  1.5,  0.0,  0.6, 0.7),  # SD (data)
    (6,  1.5, -1.25, 0.6, 0.7),  # SCK
    # Bottom pad
    (7, 0, 0, 2.7, 1.5),
], "size": (4.72, 3.76)}

# MAX98357A: QFN-16, 3.24x3.24mm, 0.5mm pitch
def _max98357():
    p = []
    for i in range(4):
        p.append((i+1, -1.62, -0.75 + i * 0.5, 0.25, 0.7))
    for i in range(4):
        p.append((5+i, -0.75 + i * 0.5, 1.62, 0.7, 0.25))
    for i in range(4):
        p.append((9+i, 1.62, 0.75 - i * 0.5, 0.25, 0.7))
    for i in range(4):
        p.append((13+i, 0.75 - i * 0.5, -1.62, 0.7, 0.25))
    p.append((17, 0, 0, 1.7, 1.7))  # Exposed pad
    return p

FP["MAX98357"] = {"pads": _max98357(), "size": (3.24, 3.24)}

# MCP73831: SOT-23-5
FP["SOT23_5"] = {"pads": [
    (1, -1.3, -0.95, 0.6, 1.0),
    (2, -1.3,  0.0,  0.6, 1.0),
    (3, -1.3,  0.95, 0.6, 1.0),
    (4,  1.3,  0.95, 0.6, 1.0),
    (5,  1.3, -0.95, 0.6, 1.0),
], "size": (3.0, 3.0)}

# AP2112K-3.3: SOT-23-5 (same footprint)
# reuse SOT23_5

# USB-C (16-pin SMD)
FP["USBC"] = {"pads": [
    ("V1", -2.75, -1.0, 0.6, 1.2), ("V2", 2.75, -1.0, 0.6, 1.2),
    ("D-", -0.25, -1.0, 0.3, 1.0), ("D+", 0.25, -1.0, 0.3, 1.0),
    ("C1", -1.75, -1.0, 0.3, 1.0), ("C2", 1.75, -1.0, 0.3, 1.0),
    ("G1", -3.5, -1.0, 0.5, 1.0),  ("G2", 3.5, -1.0, 0.5, 1.0),
    ("S1", -4.15, 0.5, 0.6, 1.6),  ("S2", 4.15, 0.5, 0.6, 1.6),
], "size": (9.0, 3.5)}

# 3.5mm TRS jack (through-hole, 5-pin)
FP["TRS_35MM"] = {"pads": [
    (1, -3.0, -2.5, 1.5, 1.5),   # Tip
    (2,  3.0, -2.5, 1.5, 1.5),   # Ring
    (3,  0.0,  3.0, 1.5, 1.5),   # Sleeve (GND)
    ("M1", -5.0, 0.0, 2.0, 2.0), # Mount
    ("M2",  5.0, 0.0, 2.0, 2.0), # Mount
], "size": (11.0, 7.0)}

# SMA connector (edge-mount, UWB antenna)
FP["SMA"] = {"pads": [
    (1, 0.0, 0.0, 1.5, 1.5),     # Center pin (signal)
    (2, -2.54, 0.0, 2.0, 2.0),   # GND
    (3,  2.54, 0.0, 2.0, 2.0),   # GND
], "size": (6.35, 5.0)}

# WS2812B-2020: 2x2mm
FP["WS2812B"] = {"pads": [
    (1, -0.65, -0.55, 0.5, 0.5), (2,  0.65, -0.55, 0.5, 0.5),
    (3,  0.65,  0.55, 0.5, 0.5), (4, -0.65,  0.55, 0.5, 0.5),
], "size": (2.0, 2.0)}

FP["SW"] = {"pads": [(1, -3.25, 0, 1.5, 1.0), (2, 3.25, 0, 1.5, 1.0)], "size": (6.0, 3.5)}

# Passive components
FP["0402"] = {"pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)], "size": (1.6, 0.8)}
FP["0603"] = {"pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)], "size": (2.2, 1.2)}
FP["0805"] = {"pads": [(1, -0.95, 0, 1.0, 1.2), (2, 0.95, 0, 1.0, 1.2)], "size": (2.8, 1.5)}

# Mounting hole M2.5 (compact board)
FP["M25_HOLE"] = {"pads": [
    (1, 0, 0, 4.0, 4.0),
], "size": (4.0, 4.0)}


# ── Components ────────────────────────────────────────────────────────
PARTS = {
    # ── MCU ──
    "U1": {"fp": "ESP32S3", "x": 13.0, "y": 17.5, "rot": 0,
            "part": "ESP32-S3-MINI-1-N8R2", "lcsc": "C2913202",
            "label": "ESP32-S3\nMINI-1", "color": "#0d47a1"},

    # ── UWB Module ──
    "U2": {"fp": "DW3000", "x": 35.0, "y": 10.0, "rot": 0,
            "part": "DW3000 (Qorvo QFN-48)", "lcsc": "C2843277",
            "label": "DW3000\nUWB", "color": "#880e4f"},

    # ── ADC (24-bit audio input) ──
    "U3": {"fp": "PCM1808", "x": 35.0, "y": 22.0, "rot": 0,
            "part": "PCM1808PWR", "lcsc": "C108818",
            "label": "PCM1808\n24-bit ADC", "color": "#4a148c"},

    # ── MEMS Microphone ──
    "U4": {"fp": "INMP441", "x": 5.0, "y": 5.0, "rot": 0,
            "part": "INMP441ACEZ-T", "lcsc": "C145280",
            "label": "INMP441\nMic", "color": "#1b5e20"},

    # ── I2S Amplifier ──
    "U5": {"fp": "MAX98357", "x": 25.0, "y": 30.0, "rot": 0,
            "part": "MAX98357AETE+T", "lcsc": "C1506581",
            "label": "MAX98357\nAmp", "color": "#b71c1c"},

    # ── LiPo Charger ──
    "U6": {"fp": "SOT23_5", "x": 25.0, "y": 5.0, "rot": 0,
            "part": "MCP73831T-2ACI/OT", "lcsc": "C424093",
            "label": "MCP73831\nCharger", "color": "#e65100"},

    # ── 3.3V LDO ──
    "U7": {"fp": "SOT23_5", "x": 15.0, "y": 5.0, "rot": 0,
            "part": "AP2112K-3.3TRG1", "lcsc": "C51118",
            "label": "AP2112K\n3.3V", "color": "#4e342e"},

    # ── USB-C ──
    "J1": {"fp": "USBC", "x": 25.0, "y": 2.0, "rot": 0,
            "part": "TYPE-C-16PIN-2MD", "lcsc": "C2765186",
            "label": "USB-C", "color": "#78909c"},

    # ── 3.5mm TRS Jack ──
    "J2": {"fp": "TRS_35MM", "x": 43.0, "y": 28.0, "rot": 0,
            "part": "PJ-320A (3.5mm TRS)", "lcsc": "C18438",
            "label": "3.5mm\nLine In", "color": "#263238"},

    # ── SMA Antenna (UWB) ──
    "J3": {"fp": "SMA", "x": 46.0, "y": 5.0, "rot": 0,
            "part": "SMA Edge-Mount", "lcsc": "C496549",
            "label": "SMA\nUWB", "color": "#ff6f00"},

    # ── Status LEDs (WS2812B-2020) ──
    "LED1": {"fp": "WS2812B", "x": 4.0, "y": 15.0, "rot": 0,
             "part": "WS2812B-2020", "lcsc": "C2976072",
             "label": "LED1", "color": "#f9a825"},
    "LED2": {"fp": "WS2812B", "x": 4.0, "y": 20.0, "rot": 0,
             "part": "WS2812B-2020", "lcsc": "C2976072",
             "label": "LED2", "color": "#f9a825"},

    # ── Reset button ──
    "SW1": {"fp": "SW", "x": 4.0, "y": 30.0, "rot": 0,
            "part": "EVQP0N02B", "lcsc": "C2936178",
            "label": "RST", "color": "#455a64"},

    # ── Mounting holes ──
    "MH1": {"fp": "M25_HOLE", "x": 3.0, "y": 3.0, "rot": 0,
             "part": "M2.5 mounting hole", "lcsc": "", "label": "M2.5", "color": "#333"},
    "MH2": {"fp": "M25_HOLE", "x": 47.0, "y": 3.0, "rot": 0,
             "part": "M2.5 mounting hole", "lcsc": "", "label": "M2.5", "color": "#333"},
    "MH3": {"fp": "M25_HOLE", "x": 3.0, "y": 32.0, "rot": 0,
             "part": "M2.5 mounting hole", "lcsc": "", "label": "M2.5", "color": "#333"},
    "MH4": {"fp": "M25_HOLE", "x": 47.0, "y": 32.0, "rot": 0,
             "part": "M2.5 mounting hole", "lcsc": "", "label": "M2.5", "color": "#333"},

    # ── Decoupling / filter caps ──
    # ESP32 bypass
    "C1": {"fp": "0402", "x": 8.0, "y": 10.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C1", "color": "#1a237e"},
    "C2": {"fp": "0402", "x": 18.0, "y": 10.0, "rot": 0,
            "part": "10uF", "lcsc": "C15849", "label": "C2", "color": "#1a237e"},
    # DW3000 bypass
    "C3": {"fp": "0402", "x": 32.0, "y": 5.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C3", "color": "#1a237e"},
    "C4": {"fp": "0402", "x": 38.0, "y": 5.0, "rot": 0,
            "part": "10nF", "lcsc": "C15195", "label": "C4", "color": "#1a237e"},
    # PCM1808 bypass
    "C5": {"fp": "0402", "x": 32.0, "y": 28.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C5", "color": "#1a237e"},
    "C6": {"fp": "0402", "x": 38.0, "y": 28.0, "rot": 0,
            "part": "10uF", "lcsc": "C15849", "label": "C6", "color": "#1a237e"},
    # LDO input/output caps
    "C7": {"fp": "0603", "x": 12.0, "y": 3.0, "rot": 0,
            "part": "10uF", "lcsc": "C15849", "label": "C7", "color": "#1a237e"},
    "C8": {"fp": "0603", "x": 18.0, "y": 3.0, "rot": 0,
            "part": "22uF", "lcsc": "C45783", "label": "C8", "color": "#1a237e"},
    # MAX98357 bypass
    "C9": {"fp": "0402", "x": 22.0, "y": 28.0, "rot": 0,
            "part": "10uF", "lcsc": "C15849", "label": "C9", "color": "#1a237e"},
    # MCP73831 input cap
    "C10": {"fp": "0603", "x": 28.0, "y": 3.0, "rot": 0,
             "part": "4.7uF", "lcsc": "C19666", "label": "C10", "color": "#1a237e"},

    # ── Resistors ──
    # USB CC pull-down
    "R1": {"fp": "0402", "x": 21.0, "y": 5.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R1", "color": "#5d4037"},
    "R2": {"fp": "0402", "x": 29.0, "y": 5.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R2", "color": "#5d4037"},
    # MCP73831 charge current (2k = 500mA)
    "R3": {"fp": "0402", "x": 25.0, "y": 8.0, "rot": 0,
            "part": "2k", "lcsc": "C4109", "label": "R3", "color": "#5d4037"},
    # LED data resistor
    "R4": {"fp": "0402", "x": 4.0, "y": 12.0, "rot": 90,
            "part": "330R", "lcsc": "C25104", "label": "R4", "color": "#5d4037"},
    # PCM1808 FMT pull (I2S mode)
    "R5": {"fp": "0402", "x": 30.0, "y": 18.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R5", "color": "#5d4037"},
    "R6": {"fp": "0402", "x": 30.0, "y": 20.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R6", "color": "#5d4037"},
}


# ── Routes ────────────────────────────────────────────────────────────
ROUTES = [
    # USB VBUS → charger → LDO
    ("+VBUS", PWR, [(25.0, 2.0), (25.0, 5.0)]),                         # USB → charger
    ("+VBAT", PWR, [(25.0, 5.0), (15.0, 5.0)]),                         # charger → LDO in
    ("+3V3", TRACE, [(15.0, 5.0), (13.0, 5.0), (13.0, 10.0)]),          # LDO → ESP32 bypass
    ("+3V3", TRACE, [(13.0, 10.0), (13.0, 17.5)]),                      # → ESP32
    ("+3V3", TRACE, [(13.0, 10.0), (35.0, 10.0)]),                      # → DW3000
    ("+3V3", TRACE, [(13.0, 17.5), (5.0, 15.0)]),                       # → LED1
    ("+3V3", TRACE, [(5.0, 15.0), (5.0, 20.0)]),                        # → LED2
    ("+3V3", TRACE, [(35.0, 22.0), (35.0, 18.0)]),                      # → PCM1808

    # SPI: ESP32 → DW3000 (MOSI:11, MISO:13, SCLK:12, CS:10, IRQ:9, RST:3)
    ("SPI_MOSI", TRACE, [(13.0+7.2, 17.5-3*1.27), (35.0-3.25, 10.0-1.5)]),
    ("SPI_SCLK", TRACE, [(13.0+7.2, 17.5-2*1.27), (35.0-3.25, 10.0-1.0)]),
    ("SPI_MISO", TRACE, [(13.0+7.2, 17.5-1*1.27), (35.0-3.25, 10.0-0.5)]),
    ("SPI_CS",   TRACE, [(13.0+7.2, 17.5-4*1.27), (35.0-3.25, 10.0+0.0)]),
    ("UWB_IRQ",  TRACE, [(13.0+7.2, 17.5-5*1.27), (35.0-3.25, 10.0+0.5)]),
    ("UWB_RST",  TRACE, [(13.0-7.2, 17.5-8*1.27), (35.0-3.25, 10.0+1.0)]),

    # I2S: ESP32 → PCM1808 (ADC input)
    ("I2S_BCK",  TRACE, [(13.0+7.2, 17.5+1*1.27), (35.0-3.75, 22.0-1.3)]),
    ("I2S_LRCK", TRACE, [(13.0+7.2, 17.5+2*1.27), (35.0-3.75, 22.0-0.65)]),
    ("I2S_DIN",  TRACE, [(13.0+7.2, 17.5+3*1.27), (35.0-3.75, 22.0+0.0)]),

    # I2S: ESP32 → MAX98357A (monitor amp)
    ("AMP_BCK",  TRACE, [(13.0+7.2, 17.5+4*1.27), (25.0-1.62, 30.0-0.75)]),
    ("AMP_LRCK", TRACE, [(13.0+7.2, 17.5+5*1.27), (25.0-1.62, 30.0-0.25)]),
    ("AMP_DIN",  TRACE, [(13.0+7.2, 17.5+6*1.27), (25.0-1.62, 30.0+0.25)]),

    # I2S: INMP441 mic → ESP32
    ("MIC_SD",   TRACE, [(5.0+1.5, 5.0+0.0), (13.0-7.2, 17.5+1*1.27)]),
    ("MIC_SCK",  TRACE, [(5.0+1.5, 5.0-1.25), (13.0-7.2, 17.5+2*1.27)]),
    ("MIC_WS",   TRACE, [(5.0-1.5, 5.0-1.25), (13.0-7.2, 17.5+3*1.27)]),

    # 3.5mm TRS → PCM1808 analog input
    ("LINE_TIP", TRACE, [(43.0-3.0, 28.0-2.5), (40.0, 25.0), (35.0+3.75, 22.0+1.3)]),
    ("LINE_GND", TRACE, [(43.0, 28.0+3.0), (40.0, 28.0), (35.0+3.75, 22.0+2.6)]),

    # UWB antenna
    ("UWB_ANT", TRACE, [(35.0+3.25, 10.0-2.75), (42.0, 5.0), (46.0, 5.0)]),

    # LED chain
    ("LED_DIN",   TRACE, [(13.0-7.2, 17.5-6*1.27), (4.0, 12.0)]),
    ("LED_CHAIN", TRACE, [(4.0+0.65, 15.0+0.55), (4.0-0.65, 20.0-0.55)]),

    # USB data
    ("USB_D+", 0.15, [(13.0-7.2, 17.5+7*1.27), (25.0+0.25, 2.0)]),
    ("USB_D-", 0.15, [(13.0-7.2, 17.5+8*1.27), (25.0-0.25, 2.0)]),

    # USB CC
    ("CC1", TRACE, [(21.0, 5.0), (25.0-1.75, 2.0)]),
    ("CC2", TRACE, [(29.0, 5.0), (25.0+1.75, 2.0)]),

    # Reset button
    ("RST", TRACE, [(4.0+3.25, 30.0), (13.0-7.2, 17.5+5*1.27)]),
]

VIAS = [
    (5, 5), (25, 5), (45, 5),
    (5, 17), (25, 17), (45, 17),
    (5, 30), (25, 30), (45, 30),
    (15, 12), (35, 12), (15, 25), (35, 25),
    # Extra GND vias near DW3000 thermal pad
    (33, 10), (35, 8), (37, 10), (35, 12),
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
        d = s._a("C", [w]); s.cmds.append(f"D{d}*")
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]
        for i, (x, y) in enumerate(corners):
            s.cmds.append(f"X{s._c(x)}Y{s._c(y)}D0{'2' if i == 0 else '1'}*")
    def write(s, path):
        with open(path, 'w') as f:
            f.write("%FSLAX46Y46*%\n%MOMM*%\n")
            f.write(f"G04 Koe PRO {s.name}*\n%LPD*%\n")
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
            f.write("M48\n; Koe PRO 50x35mm ESP32-S3 + DW3000 UWB\nFMAT,2\nMETRIC,TZ\n")
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

    # Mounting holes (M2.5 = 2.7mm drill)
    for ref in ("MH1", "MH2", "MH3", "MH4"):
        c = PARTS[ref]
        dr.hole(c["x"], c["y"], 2.7)

    # Through-hole component drills (3.5mm TRS jack)
    for ref in ("J2",):
        c = PARTS[ref]
        fp = FP[c["fp"]]
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            ax, ay = xform(px, py, c["x"], c["y"], c.get("rot", 0))
            dr.hole(ax, ay, 1.0)

    # Ground copper pour (back copper = full GND, 4-layer inner GND+PWR)
    bc.rect(1, 1, BOARD_W - 1, BOARD_H - 1, 0.3)

    pre = "koe-pro"
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
    ROT = {"SOT23_5": 180}
    lines = ["Designator,Mid X(mm),Mid Y(mm),Layer,Rotation"]
    for ref, c in PARTS.items():
        rot = c.get("rot", 0) + ROT.get(c["fp"], 0)
        lines.append(f"{ref},{c['x']:.1f},{c['y']:.1f},Top,{rot % 360}")
    (GBR / "CPL-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"CPL: {GBR / 'CPL-JLCPCB.csv'}")


# ── SVG ───────────────────────────────────────────────────────────────
def gen_svg():
    S = 10; pad = 60; img_w = int(BOARD_W * S + pad * 2); img_h = int(BOARD_H * S + pad * 2)
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
<text x="{img_w // 2}" y="22" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="16" font-weight="600">Koe Pro v1 -- ESP32-S3 + DW3000 UWB Musician Board</text>
<text x="{img_w // 2}" y="40" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">50x35mm | 4-layer FR-4 | PCM1808 24-bit ADC | INMP441 MEMS Mic | MAX98357A Monitor</text>

<!-- Board -->
<rect x="{ox - 2}" y="{oy - 2}" width="{BOARD_W * S + 4}" height="{BOARD_H * S + 4}" fill="#000" opacity="0.3" rx="3"/>
<rect x="{ox}" y="{oy}" width="{BOARD_W * S}" height="{BOARD_H * S}" fill="url(#pcb)" stroke="#c8a83e" stroke-width="1.5" rx="2"/>
'''

    # GND pour hint
    svg += f'<rect x="{ox + 4}" y="{oy + 4}" width="{BOARD_W * S - 8}" height="{BOARD_H * S - 8}" fill="none" stroke="#1a5c1a" stroke-width="0.5" stroke-dasharray="4,4" rx="1"/>\n'

    # Traces
    net_colors = {
        "VBUS": "#ef5350", "VBAT": "#ff7043", "3V3": "#66bb6a",
        "SPI": "#42a5f5", "I2S": "#42a5f5", "USB": "#ffca28",
        "UWB": "#e91e63", "LED": "#f9a825", "LINE": "#ce93d8",
        "MIC": "#81c784", "AMP": "#ff8a65", "CC": "#78909c",
        "RST": "#78909c",
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
        svg += f'<circle cx="{mx}" cy="{my}" r="{2.7 * S / 2}" fill="#1a1a1a" stroke="#888" stroke-width="1"/>\n'
        svg += f'<circle cx="{mx}" cy="{my}" r="{1.35 * S}" fill="none" stroke="#c8a83e" stroke-width="0.5" opacity="0.4"/>\n'

    # Components
    for ref, c in PARTS.items():
        if ref.startswith("MH"): continue
        fp = FP[c["fp"]]; cx_, cy_ = c["x"], c["y"]; rot = c.get("rot", 0)
        sw, sh = fp["size"]; color = c.get("color", "#5d4037")
        sx, sy = ox + cx_ * S, oy + cy_ * S; rw, rh = sw * S, sh * S

        svg += f'<g transform="translate({sx},{sy}) rotate({rot})" filter="url(#sh)">\n'
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            svg += f'<rect x="{px * S - pw * S / 2}" y="{py * S - ph * S / 2}" width="{pw * S}" height="{ph * S}" fill="#c8a83e" rx="0.3" opacity="0.45"/>\n'
        rx = 3 if ref[0] in "UJ" else 1
        svg += f'<rect x="{-rw / 2}" y="{-rh / 2}" width="{rw}" height="{rh}" fill="{color}" stroke="#777" stroke-width="0.5" rx="{rx}"/>\n'
        if ref[0] == "U":
            svg += f'<circle cx="{-rw / 2 + 4}" cy="{-rh / 2 + 4}" r="1.5" fill="#aaa" opacity="0.4"/>\n'
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
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="9">50x35mm | 4-layer | {len(PARTS)} parts | ESP32-S3 + DW3000 UWB + PCM1808 ADC</text>\n'

    # Signal flow
    ly += 22
    flow_items = [
        ("Guitar/Mic", "#ce93d8"), ("PCM1808", "#4a148c"), ("I2S", "#42a5f5"),
        ("ESP32-S3", "#0d47a1"), ("UWB Sync", "#880e4f"), ("WiFi", "#42a5f5"),
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
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#ef5350" font-family="monospace" font-size="9" font-weight="bold">USB-C 5V &#8594; MCP73831 &#8594; LiPo &#8594; AP2112K &#8594; 3.3V (all logic)</text>\n'
    ly += 16
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">DW3000 UWB for sub-us time sync | PCM1808 24-bit audio capture</text>\n'

    # Price
    ly += 22
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#c8a83e" font-family="monospace" font-size="9">PRO $199 | 3.5mm line in + MEMS mic | UWB sync | LiPo powered | Compact 50x35mm</text>\n'

    svg += '</svg>\n'
    path = GBR / "koe-pro-layout.svg"
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
        print("DRC: All components within 50x35mm board -- OK")
    return len(errs) == 0


def main():
    print("=" * 65)
    print("Koe Pro v1 -- 50x35mm Musician Board")
    print(f"  {len(PARTS)} parts | ESP32-S3 + DW3000 UWB | PCM1808 24-bit ADC")
    print(f"  INMP441 MEMS Mic | MAX98357A Monitor | MCP73831 LiPo")
    print("=" * 65)
    check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()
    print(f"\nSignal chain:")
    print(f"  Guitar/Mic 3.5mm --> PCM1808 ADC --> I2S --> ESP32-S3")
    print(f"  INMP441 MEMS mic --> I2S --> ESP32-S3")
    print(f"  ESP32-S3 --> I2S --> MAX98357A --> Monitor speaker")
    print(f"  ESP32-S3 <--> SPI <--> DW3000 UWB (sub-us sync)")
    print(f"\nPower:")
    print(f"  USB-C 5V --> MCP73831 --> LiPo charge")
    print(f"  LiPo/USB --> AP2112K --> 3.3V (all logic)")


if __name__ == "__main__":
    main()
