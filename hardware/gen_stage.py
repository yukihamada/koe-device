#!/usr/bin/env python3
"""
Koe STAGE PCB — 85x55mm Credit-Card, ESP32-S3 + PCM1808 ADC
=============================================================
Festival bridge device: PA line-in → WiFi UDP broadcast + BLE Auracast
Board: 85x55mm rectangle, 4-layer, 1.6mm FR-4
Power: USB-C PD 5V/3A + 5V DC barrel jack (backup)
"""

import math
import zipfile
from pathlib import Path

BOARD_W = 85.0
BOARD_H = 55.0
CX, CY = BOARD_W / 2.0, BOARD_H / 2.0
TRACE, PWR, VIA_D, VIA_P = 0.2, 0.4, 0.3, 0.6
MOUNT_HOLE_D = 3.2  # M3
MOUNT_INSET = 4.0

OUT = Path(__file__).parent / "kicad"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-stage"

# ── Footprints ────────────────────────────────────────────────────────
FP = {}

# ESP32-S3-WROOM-1-N16R8: 18x25.5mm module, castellated pads
# Pads along left, bottom, right edges
def _esp32s3():
    p = []
    # Left side: 14 pins, 1.27mm pitch, starting from top
    for i in range(14):
        p.append((i + 1, -9.0, -12.0 + i * 1.27, 0.9, 0.6))
    # Bottom: 8 pins
    for i in range(8):
        p.append((15 + i, -5.08 + i * 1.27, 12.75, 0.6, 0.9))
    # Right side: 14 pins
    for i in range(14):
        p.append((23 + i, 9.0, 12.0 - i * 1.27, 0.9, 0.6))
    # GND pad
    p.append((37, 0, 13.5, 6.0, 2.0))
    return p

FP["ESP32S3"] = {"pads": _esp32s3(), "size": (18.0, 25.5)}

# PCM1808: SOIC-14 (audio ADC, 24-bit I2S)
def _soic14():
    p = []
    for i in range(7):
        p.append((i + 1, -2.7, -3.81 + i * 1.27, 0.6, 1.55))
    for i in range(7):
        p.append((8 + i, 2.7, 3.81 - i * 1.27, 0.6, 1.55))
    return p

FP["SOIC14"] = {"pads": _soic14(), "size": (6.0, 10.0)}

# AMS1117-3.3: SOT-223 LDO
FP["SOT223"] = {"pads": [
    (1, -2.3, -1.5, 1.2, 0.7),  # GND
    (2, -2.3, 0.0, 1.2, 0.7),   # VOUT
    (3, -2.3, 1.5, 1.2, 0.7),   # VIN
    (4, 2.3, 0.0, 1.2, 3.0),    # TAB (VOUT)
], "size": (6.5, 3.5)}

# USB-C 16-pin
FP["USBC"] = {"pads": [
    ("V1", -2.4, -1.0, 0.5, 1.0), ("V2", 2.4, -1.0, 0.5, 1.0),
    ("D-", -0.8, -1.0, 0.3, 1.0), ("D+", -0.4, -1.0, 0.3, 1.0),
    ("C1", -1.6, -1.0, 0.3, 1.0), ("C2", 1.6, -1.0, 0.3, 1.0),
    ("G1", -3.2, -1.0, 0.5, 1.0), ("G2", 3.2, -1.0, 0.5, 1.0),
    ("S1", -3.65, 0.0, 0.6, 1.2), ("S2", 3.65, 0.0, 0.6, 1.2),
], "size": (7.35, 3.2)}

# 3.5mm audio jack (PJ-320A or similar, through-hole)
FP["JACK35"] = {"pads": [
    (1, -3.5, 0.0, 1.8, 1.8),   # Tip (Left)
    (2, 3.5, 0.0, 1.8, 1.8),    # Ring (Right)
    (3, 0.0, -3.0, 1.8, 1.8),   # Sleeve (GND)
    (4, 0.0, 3.0, 1.8, 1.8),    # Switch
], "size": (12.0, 6.0)}

# RJ45 (Ethernet, optional - through-hole)
FP["RJ45"] = {"pads": [
    (1, -4.445, 0, 0.8, 1.6), (2, -3.175, 0, 0.8, 1.6),
    (3, -1.905, 0, 0.8, 1.6), (4, -0.635, 0, 0.8, 1.6),
    (5, 0.635, 0, 0.8, 1.6), (6, 1.905, 0, 0.8, 1.6),
    (7, 3.175, 0, 0.8, 1.6), (8, 4.445, 0, 0.8, 1.6),
    ("S1", -7.0, 3.0, 1.6, 1.6), ("S2", 7.0, 3.0, 1.6, 1.6),
], "size": (16.0, 13.5)}

# SMA connector (edge-mount)
FP["SMA"] = {"pads": [
    (1, 0.0, 0.0, 1.5, 1.5),    # Center pin
    ("G1", -2.54, 0.0, 1.8, 1.8), ("G2", 2.54, 0.0, 1.8, 1.8),
], "size": (6.35, 4.0)}

# DC barrel jack (5.5x2.1mm, through-hole)
FP["BARREL"] = {"pads": [
    (1, 0.0, 0.0, 2.0, 2.0),   # Center (+5V)
    (2, -4.5, 0.0, 2.0, 2.0),  # Shell (GND)
    (3, 3.0, 3.0, 2.0, 2.0),   # Switch
], "size": (9.0, 9.0)}

# WS2812B-5050 (standard 5050)
FP["WS2812B"] = {"pads": [
    (1, -2.45, -1.6, 1.0, 1.0),  # VDD
    (2, 2.45, -1.6, 1.0, 1.0),   # DOUT
    (3, 2.45, 1.6, 1.0, 1.0),    # GND
    (4, -2.45, 1.6, 1.0, 1.0),   # DIN
], "size": (5.0, 5.0)}

# Tactile switch (6x6mm through-hole)
FP["SW6x6"] = {"pads": [
    (1, -3.25, -2.25, 1.2, 1.2),
    (2, 3.25, -2.25, 1.2, 1.2),
    (3, -3.25, 2.25, 1.2, 1.2),
    (4, 3.25, 2.25, 1.2, 1.2),
], "size": (6.0, 6.0)}

# Passives
FP["0402"] = {"pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)], "size": (1.6, 0.8)}
FP["0603"] = {"pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)], "size": (2.2, 1.2)}
FP["0805"] = {"pads": [(1, -1.0, 0, 1.0, 1.25), (2, 1.0, 0, 1.0, 1.25)], "size": (2.8, 1.5)}
FP["SOD323"] = {"pads": [(1, -1.15, 0, 0.6, 0.5), (2, 1.15, 0, 0.6, 0.5)], "size": (2.8, 1.3)}

# Mounting hole (M3)
FP["M3_HOLE"] = {"pads": [
    (1, 0.0, 0.0, 3.6, 3.6),  # annular ring
], "size": (3.6, 3.6)}

# ESD protection (SOT-23-6 for USB, SOIC-8 for general)
FP["SOT236"] = {"pads": [
    (1, -1.1, 0.95, 0.6, 0.7), (2, -1.1, 0, 0.6, 0.7), (3, -1.1, -0.95, 0.6, 0.7),
    (4, 1.1, -0.95, 0.6, 0.7), (5, 1.1, 0, 0.6, 0.7), (6, 1.1, 0.95, 0.6, 0.7),
], "size": (3.0, 3.0)}

# ── Components ────────────────────────────────────────────────────────
PARTS = {
    # ── MCU ──
    "U1": {"fp": "ESP32S3", "x": 35.0, "y": 27.5, "rot": 0,
            "part": "ESP32-S3-WROOM-1-N16R8", "lcsc": "C2913202",
            "label": "ESP32-S3\nWROOM-1\nN16R8", "color": "#0d47a1"},

    # ── Audio ADC ──
    "U2": {"fp": "SOIC14", "x": 16.0, "y": 27.5, "rot": 0,
            "part": "PCM1808PWR", "lcsc": "C93521",
            "label": "PCM1808\nADC", "color": "#b71c1c"},

    # ── LDO 3.3V ──
    "U3": {"fp": "SOT223", "x": 65.0, "y": 10.0, "rot": 0,
            "part": "AMS1117-3.3", "lcsc": "C6186",
            "label": "AMS1117\n3.3V", "color": "#4e342e"},

    # ── USB ESD Protection ──
    "U4": {"fp": "SOT236", "x": 72.0, "y": 48.0, "rot": 0,
            "part": "USBLC6-2SC6", "lcsc": "C7519",
            "label": "ESD", "color": "#263238"},

    # ── Audio Jack ESD ──
    "U5": {"fp": "SOT236", "x": 10.0, "y": 48.0, "rot": 0,
            "part": "PESD5V0S2BT", "lcsc": "C2827654",
            "label": "ESD", "color": "#263238"},

    # ── USB-C ──
    "J1": {"fp": "USBC", "x": 72.0, "y": 53.0, "rot": 0,
            "part": "TYPE-C-16PIN-2MD", "lcsc": "C2765186",
            "label": "USB-C", "color": "#78909c"},

    # ── 3.5mm Line-In Jack ──
    "J2": {"fp": "JACK35", "x": 6.0, "y": 27.5, "rot": 90,
            "part": "PJ-320A", "lcsc": "C145819",
            "label": "LINE\nIN", "color": "#00695c"},

    # ── RJ45 Ethernet (optional) ──
    "J3": {"fp": "RJ45", "x": 72.0, "y": 25.0, "rot": 0,
            "part": "HR911105A", "lcsc": "C12084",
            "label": "RJ45\n(OPT)", "color": "#37474f"},

    # ── SMA WiFi Antenna ──
    "J4": {"fp": "SMA", "x": 80.0, "y": 35.0, "rot": 90,
            "part": "SMA-KE", "lcsc": "C496554",
            "label": "WiFi\nANT", "color": "#f57f17"},

    # ── SMA BLE Antenna ──
    "J5": {"fp": "SMA", "x": 80.0, "y": 45.0, "rot": 90,
            "part": "SMA-KE", "lcsc": "C496554",
            "label": "BLE\nANT", "color": "#7b1fa2"},

    # ── DC Barrel Jack ──
    "J6": {"fp": "BARREL", "x": 6.0, "y": 10.0, "rot": 0,
            "part": "DC-005", "lcsc": "C381116",
            "label": "5V DC\nIN", "color": "#e65100"},

    # ── Status LEDs ──
    "LED1": {"fp": "WS2812B", "x": 42.5, "y": 6.0, "rot": 0,
             "part": "WS2812B-5050", "lcsc": "C2761795",
             "label": "WiFi", "color": "#66bb6a"},
    "LED2": {"fp": "WS2812B", "x": 50.0, "y": 6.0, "rot": 0,
             "part": "WS2812B-5050", "lcsc": "C2761795",
             "label": "BLE", "color": "#42a5f5"},
    "LED3": {"fp": "WS2812B", "x": 57.5, "y": 6.0, "rot": 0,
             "part": "WS2812B-5050", "lcsc": "C2761795",
             "label": "Audio", "color": "#ef5350"},

    # ── Buttons ──
    "SW1": {"fp": "SW6x6", "x": 28.0, "y": 6.0, "rot": 0,
            "part": "TS-1187A-B-A-B", "lcsc": "C318884",
            "label": "MODE", "color": "#455a64"},
    "SW2": {"fp": "SW6x6", "x": 18.0, "y": 6.0, "rot": 0,
            "part": "TS-1187A-B-A-B", "lcsc": "C318884",
            "label": "RST", "color": "#455a64"},

    # ── Mounting Holes ──
    "MH1": {"fp": "M3_HOLE", "x": MOUNT_INSET, "y": MOUNT_INSET, "rot": 0,
            "part": "M3 Mounting Hole", "lcsc": "", "label": "M3", "color": "#616161"},
    "MH2": {"fp": "M3_HOLE", "x": BOARD_W - MOUNT_INSET, "y": MOUNT_INSET, "rot": 0,
            "part": "M3 Mounting Hole", "lcsc": "", "label": "M3", "color": "#616161"},
    "MH3": {"fp": "M3_HOLE", "x": MOUNT_INSET, "y": BOARD_H - MOUNT_INSET, "rot": 0,
            "part": "M3 Mounting Hole", "lcsc": "", "label": "M3", "color": "#616161"},
    "MH4": {"fp": "M3_HOLE", "x": BOARD_W - MOUNT_INSET, "y": BOARD_H - MOUNT_INSET, "rot": 0,
            "part": "M3 Mounting Hole", "lcsc": "", "label": "M3", "color": "#616161"},

    # ── Schottky Diode (power OR for USB-C / barrel) ──
    "D1": {"fp": "SOD323", "x": 50.0, "y": 10.0, "rot": 0,
            "part": "BAT54C", "lcsc": "C181054",
            "label": "D1", "color": "#263238"},
    "D2": {"fp": "SOD323", "x": 20.0, "y": 10.0, "rot": 0,
            "part": "BAT54C", "lcsc": "C181054",
            "label": "D2", "color": "#263238"},

    # ── USB CC Resistors ──
    "R1": {"fp": "0402", "x": 66.0, "y": 50.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R1", "color": "#5d4037"},
    "R2": {"fp": "0402", "x": 78.0, "y": 50.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R2", "color": "#5d4037"},

    # ── PCM1808 Input Resistors (anti-alias) ──
    "R3": {"fp": "0402", "x": 10.0, "y": 22.0, "rot": 0,
            "part": "1k", "lcsc": "C11702", "label": "R3", "color": "#5d4037"},
    "R4": {"fp": "0402", "x": 10.0, "y": 33.0, "rot": 0,
            "part": "1k", "lcsc": "C11702", "label": "R4", "color": "#5d4037"},

    # ── Pull-up/down for ESP32 ──
    "R5": {"fp": "0402", "x": 48.0, "y": 14.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R5", "color": "#5d4037"},
    "R6": {"fp": "0402", "x": 48.0, "y": 17.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R6", "color": "#5d4037"},

    # ── LED current-limit ──
    "R7": {"fp": "0402", "x": 35.0, "y": 6.0, "rot": 0,
            "part": "330", "lcsc": "C25195", "label": "R7", "color": "#5d4037"},

    # ── Decoupling Caps (ESP32-S3) ──
    "C1": {"fp": "0402", "x": 24.0, "y": 18.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C1", "color": "#1a237e"},
    "C2": {"fp": "0603", "x": 24.0, "y": 38.0, "rot": 0,
            "part": "10uF", "lcsc": "C19702", "label": "C2", "color": "#1a237e"},
    "C3": {"fp": "0402", "x": 44.0, "y": 43.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C3", "color": "#1a237e"},
    "C4": {"fp": "0603", "x": 44.0, "y": 46.0, "rot": 0,
            "part": "10uF", "lcsc": "C19702", "label": "C4", "color": "#1a237e"},

    # ── LDO decoupling ──
    "C5": {"fp": "0805", "x": 55.0, "y": 7.0, "rot": 0,
            "part": "22uF", "lcsc": "C45783", "label": "C5", "color": "#1a237e"},
    "C6": {"fp": "0805", "x": 65.0, "y": 7.0, "rot": 0,
            "part": "22uF", "lcsc": "C45783", "label": "C6", "color": "#1a237e"},

    # ── PCM1808 decoupling ──
    "C7": {"fp": "0402", "x": 16.0, "y": 20.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C7", "color": "#1a237e"},
    "C8": {"fp": "0603", "x": 16.0, "y": 35.0, "rot": 0,
            "part": "10uF", "lcsc": "C19702", "label": "C8", "color": "#1a237e"},
    "C9": {"fp": "0402", "x": 22.0, "y": 25.0, "rot": 90,
            "part": "100nF", "lcsc": "C1525", "label": "C9", "color": "#1a237e"},
    "C10": {"fp": "0402", "x": 22.0, "y": 30.0, "rot": 90,
             "part": "100nF", "lcsc": "C1525", "label": "C10", "color": "#1a237e"},

    # ── USB bulk caps ──
    "C11": {"fp": "0603", "x": 72.0, "y": 44.0, "rot": 0,
             "part": "10uF", "lcsc": "C19702", "label": "C11", "color": "#1a237e"},
    "C12": {"fp": "0402", "x": 72.0, "y": 41.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C12", "color": "#1a237e"},
}

# ── Routes ────────────────────────────────────────────────────────────
ROUTES = [
    # Power: USB-C 5V → Diode → LDO
    ("+5V_USB", PWR, [(72.0, 53.0), (72.0, 48.0), (55.0, 10.0), (50.0, 10.0)]),
    # Power: Barrel → Diode → LDO
    ("+5V_DC", PWR, [(6.0, 10.0), (20.0, 10.0)]),
    # Power merge to LDO
    ("+5V", PWR, [(50.0, 10.0), (55.0, 10.0), (62.7, 10.0)]),
    ("+5V_BAR", PWR, [(20.0, 10.0), (40.0, 10.0), (50.0, 10.0)]),
    # LDO → 3.3V rail
    ("+3V3", PWR, [(67.3, 10.0), (67.3, 15.0), (42.5, 15.0), (35.0, 15.0)]),
    # 3.3V to ESP32
    ("+3V3_ESP", TRACE, [(35.0, 15.0), (35.0, 15.0)]),
    # 3.3V to PCM1808
    ("+3V3_ADC", TRACE, [(35.0, 15.0), (16.0, 20.0)]),
    # 3.3V to LEDs
    ("+3V3_LED", TRACE, [(42.5, 15.0), (42.5, 6.0)]),

    # I2S: PCM1808 → ESP32-S3
    ("I2S_BCK", TRACE, [(18.7, 24.7), (26.0, 24.7), (26.0, 22.0)]),
    ("I2S_WS", TRACE, [(18.7, 26.0), (26.0, 26.0)]),
    ("I2S_DOUT", TRACE, [(18.7, 27.3), (26.0, 27.3), (26.0, 28.0)]),
    ("I2S_SCK", TRACE, [(18.7, 28.6), (26.0, 30.0)]),

    # Audio jack → PCM1808
    ("AUDIO_L", TRACE, [(6.0, 24.0), (10.0, 22.0), (13.3, 23.7)]),
    ("AUDIO_R", TRACE, [(6.0, 31.0), (10.0, 33.0), (13.3, 27.3)]),

    # LED chain (WS2812B daisy)
    ("LED_DIN", TRACE, [(35.0, 6.0), (40.0, 6.0), (42.5, 6.0)]),
    ("LED_1_2", TRACE, [(44.95, 6.0), (50.0, 6.0)]),
    ("LED_2_3", TRACE, [(52.45, 6.0), (57.5, 6.0)]),

    # USB D+/D-
    ("USB_D+", 0.2, [(72.0 - 0.4, 51.0), (72.0 - 0.4, 48.0)]),
    ("USB_D-", 0.2, [(72.0 - 0.8, 51.0), (72.0 - 0.8, 48.0)]),

    # USB CC resistors
    ("CC1", TRACE, [(66.0, 50.0), (70.4, 52.0)]),
    ("CC2", TRACE, [(78.0, 50.0), (73.6, 52.0)]),

    # Button connections
    ("BTN_MODE", TRACE, [(31.25, 6.0), (35.0, 14.0)]),
    ("BTN_RST", TRACE, [(21.25, 6.0), (26.0, 14.0)]),

    # GND plane connections (vias)
    ("GND", PWR, [(35.0, 40.0), (35.0, 45.0), (50.0, 45.0)]),

    # Antenna traces
    ("ANT_WIFI", TRACE, [(44.0, 27.5), (60.0, 35.0), (77.0, 35.0)]),
    ("ANT_BLE", TRACE, [(44.0, 30.0), (60.0, 45.0), (77.0, 45.0)]),
]

# Via positions (power plane stitching + signal)
VIAS = [
    # Power stitching
    (15, 10), (25, 10), (35, 10), (45, 10), (55, 10),
    # GND plane stitching
    (10, 15), (30, 15), (50, 15), (70, 15),
    (10, 40), (30, 40), (50, 40), (70, 40),
    # Signal vias
    (26, 25), (26, 30), (35, 20), (35, 35),
    (60, 25), (60, 35), (60, 45),
    # Mounting hole area
    (8, 8), (77, 8), (8, 47), (77, 47),
]


# ── Helpers ───────────────────────────────────────────────────────────
def in_rect(x, y, m=0.5):
    return m <= x <= BOARD_W - m and m <= y <= BOARD_H - m


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
        d = s._a("C", [w]) if abs(w - h) < .01 else s._a("R", [w, h])
        s.cmds += [f"D{d}*", f"X{s._c(x)}Y{s._c(y)}D03*"]

    def trace(s, x1, y1, x2, y2, w):
        d = s._a("C", [w])
        s.cmds += [f"D{d}*", f"X{s._c(x1)}Y{s._c(y1)}D02*", f"X{s._c(x2)}Y{s._c(y2)}D01*"]

    def circ(s, x, y, d_):
        d = s._a("C", [d_])
        s.cmds += [f"D{d}*", f"X{s._c(x)}Y{s._c(y)}D03*"]

    def rect(s, x, y, w, h, line_w=0.05):
        """Draw rectangle outline"""
        d = s._a("C", [line_w])
        corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        for i in range(4):
            x1, y1 = corners[i]
            x2, y2 = corners[(i + 1) % 4]
            s.cmds += [f"D{d}*", f"X{s._c(x1)}Y{s._c(y1)}D02*", f"X{s._c(x2)}Y{s._c(y2)}D01*"]

    def write(s, path):
        with open(path, 'w') as f:
            f.write("%FSLAX46Y46*%\n%MOMM*%\n")
            f.write(f"G04 Koe STAGE {s.name}*\n%LPD*%\n")
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
            f.write("M48\n; Koe STAGE 85x55mm ESP32-S3 + PCM1808\nFMAT,2\nMETRIC,TZ\n")
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
    # Inner layers for 4-layer
    in1, in2 = Gbr("In1.Cu"), Gbr("In2.Cu")
    dr = Drl()

    # Board outline (rectangle)
    ec.rect(0, 0, BOARD_W, BOARD_H, 0.05)

    # Mounting holes
    for ref in ("MH1", "MH2", "MH3", "MH4"):
        c = PARTS[ref]
        dr.hole(c["x"], c["y"], MOUNT_HOLE_D)

    # Place components
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]
        cx, cy, rot = c["x"], c["y"], c.get("rot", 0)
        sw, sh = fp["size"]
        co = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2), (sw / 2, sh / 2), (-sw / 2, sh / 2)]
        ca = [xform(a, b, cx, cy, rot) for a, b in co]
        for i in range(4):
            fs_.trace(ca[i][0], ca[i][1], ca[(i + 1) % 4][0], ca[(i + 1) % 4][1], 0.1)
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
        for g in (fc, bc, in1, in2):
            g.circ(vx, vy, VIA_P)
        for g in (fm, bm):
            g.circ(vx, vy, VIA_P + 0.1)
        dr.hole(vx, vy, VIA_D)

    # GND fill on inner layer 1 (represented as border outline)
    in1.rect(0.5, 0.5, BOARD_W - 1.0, BOARD_H - 1.0, PWR)
    # Power fill on inner layer 2
    in2.rect(0.5, 0.5, BOARD_W - 1.0, BOARD_H - 1.0, PWR)

    pre = "koe-stage"
    for n, g in [("F_Cu", fc), ("B_Cu", bc), ("In1_Cu", in1), ("In2_Cu", in2),
                 ("F_Mask", fm), ("B_Mask", bm), ("F_SilkS", fs_), ("B_SilkS", bs_), ("Edge_Cuts", ec)]:
        g.write(GBR / f"{pre}-{n}.gbr")
    dr.write(GBR / f"{pre}.drl")
    zp = GBR / f"{pre}.zip"
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in GBR.glob(f"{pre}-*"):
            z.write(f, f.name)
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
    ROT = {"SOT223": 180, "SOIC14": 0}
    lines = ["Designator,Mid X(mm),Mid Y(mm),Layer,Rotation"]
    for ref, c in PARTS.items():
        rot = c.get("rot", 0) + ROT.get(c["fp"], 0)
        lines.append(f"{ref},{c['x']:.1f},{c['y']:.1f},Top,{rot % 360}")
    (GBR / "CPL-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"CPL: {GBR / 'CPL-JLCPCB.csv'}")


# ── SVG ───────────────────────────────────────────────────────────────
def gen_svg():
    S = 8
    pad = 60
    img_w = int(BOARD_W * S + pad * 2)
    img_h = int(BOARD_H * S + pad * 2)
    ox, oy = pad, pad + 20

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{img_w}" height="{img_h + 200}">
<defs>
  <linearGradient id="pcb" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#0d5c0d"/><stop offset="100%" stop-color="#063806"/>
  </linearGradient>
  <filter id="sh"><feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.4"/></filter>
  <pattern id="grid" width="{1.27 * S}" height="{1.27 * S}" patternUnits="userSpaceOnUse">
    <path d="M {1.27 * S} 0 L 0 0 0 {1.27 * S}" fill="none" stroke="#1a3a1a" stroke-width="0.3"/>
  </pattern>
</defs>
<rect width="{img_w}" height="{img_h + 200}" fill="#0d0d14"/>

<!-- Title -->
<text x="{img_w // 2}" y="18" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="15" font-weight="600">Koe STAGE v1 — ESP32-S3 + PCM1808 Festival Bridge</text>
<text x="{img_w // 2}" y="35" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">85x55mm | 4-layer FR-4 | PA Line-In → WiFi UDP + BLE Auracast</text>

<!-- Board shadow -->
<rect x="{ox + 3}" y="{oy + 3}" width="{BOARD_W * S}" height="{BOARD_H * S}" rx="4" fill="#000" opacity="0.35"/>
<!-- Board -->
<rect x="{ox}" y="{oy}" width="{BOARD_W * S}" height="{BOARD_H * S}" rx="3" fill="url(#pcb)" stroke="#c8a83e" stroke-width="1.5"/>
<!-- Grid overlay -->
<rect x="{ox}" y="{oy}" width="{BOARD_W * S}" height="{BOARD_H * S}" rx="3" fill="url(#grid)" opacity="0.15"/>
'''

    # Mounting holes
    for ref in ("MH1", "MH2", "MH3", "MH4"):
        c = PARTS[ref]
        hx, hy = ox + c["x"] * S, oy + c["y"] * S
        svg += f'<circle cx="{hx}" cy="{hy}" r="{MOUNT_HOLE_D * S / 2 + 2}" fill="#1a1a1a" stroke="#888" stroke-width="1"/>\n'
        svg += f'<circle cx="{hx}" cy="{hy}" r="{MOUNT_HOLE_D * S / 2 - 2}" fill="#0d0d14"/>\n'

    # Traces
    net_colors = {
        "5V": "#ef5350", "3V3": "#66bb6a", "GND": "#78909c",
        "I2S": "#42a5f5", "AUDIO": "#ff7043", "USB": "#ffca28",
        "LED": "#f9a825", "CC": "#78909c", "BTN": "#78909c",
        "ANT": "#ce93d8", "BAR": "#ef5350",
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
            svg += f'stroke="{c}" stroke-width="{max(1.5, w * S * 0.5)}" opacity="0.4" stroke-linecap="round"/>\n'

    # Vias
    for vx, vy in VIAS:
        svg += f'<circle cx="{ox + vx * S}" cy="{oy + vy * S}" r="{VIA_P * S / 2 + 1}" fill="#1a1a1a" stroke="#666" stroke-width="0.5"/>\n'

    # Components
    for ref, c in PARTS.items():
        if ref.startswith("MH"):
            continue
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
        # Pin 1 dot for ICs
        if ref[0] == "U":
            svg += f'<circle cx="{-rw / 2 + 3}" cy="{-rh / 2 + 3}" r="1.2" fill="#aaa" opacity="0.4"/>\n'
        # Label
        label = c.get("label", ref)
        lines_ = label.split('\n')
        for li, line in enumerate(lines_):
            fy = 4 + (li - len(lines_) / 2) * 10
            fs = 6 if ref[0] in "RCLD" else 7
            if ref.startswith("LED") or ref.startswith("SW"):
                fs = 6
            svg += f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" '
            svg += f'font-family="monospace" font-size="{fs}">{line}</text>\n'
        svg += '</g>\n'

    # Ref labels outside components for key parts
    key_labels = [
        (35.0, 50.0, "ESP32-S3-WROOM-1", "#42a5f5"),
        (16.0, 40.0, "PCM1808 24-bit ADC", "#ef5350"),
        (65.0, 4.0, "AMS1117-3.3", "#ff7043"),
    ]
    for lx, ly, txt, col in key_labels:
        svg += f'<text x="{ox + lx * S}" y="{oy + ly * S}" text-anchor="middle" '
        svg += f'fill="{col}" font-family="monospace" font-size="7" opacity="0.6">{txt}</text>\n'

    # Zone labels (functional areas)
    zones = [
        (6, 27.5, "AUDIO\nINPUT", "#ff7043"),
        (72, 53, "USB-C\nPOWER", "#ffca28"),
        (72, 15, "ETHERNET\n(OPT)", "#78909c"),
        (80, 40, "ANTENNA\nPORT", "#ce93d8"),
    ]
    for zx, zy, ztxt, zcol in zones:
        lines_ = ztxt.split('\n')
        for i, line in enumerate(lines_):
            svg += f'<text x="{ox + zx * S}" y="{oy + zy * S + (i - len(lines_) / 2) * 10}" '
            svg += f'text-anchor="middle" fill="{zcol}" font-family="monospace" font-size="6" opacity="0.4">{line}</text>\n'

    # Info section below board
    ly = img_h + 55
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" '
    svg += f'font-family="monospace" font-size="9">85x55mm | 4-layer FR-4 | {len(PARTS)} parts | ESP32-S3 WiFi+BLE 5.0</text>\n'

    ly += 22
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#66bb6a" '
    svg += f'font-family="monospace" font-size="10" font-weight="bold">Signal Flow: PA Mixer → 3.5mm → PCM1808 (24-bit I2S) → ESP32-S3</text>\n'

    ly += 18
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#42a5f5" '
    svg += f'font-family="monospace" font-size="9">→ WiFi UDP (speakers) + BLE Auracast (COIN wearables)</text>\n'

    ly += 18
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#c8a83e" '
    svg += f'font-family="monospace" font-size="9">Power: USB-C PD 5V/3A | DC barrel 5V backup | AMS1117-3.3 LDO</text>\n'

    # Block diagram
    ly += 25
    blocks = [
        (60, "3.5mm\nLine-In", "#00695c", 70, 30),
        (175, "PCM1808\n24-bit ADC", "#b71c1c", 90, 30),
        (310, "ESP32-S3\nN16R8", "#0d47a1", 100, 30),
        (460, "WiFi UDP\n→ Speakers", "#66bb6a", 95, 30),
        (600, "BLE Auracast\n→ COINs", "#7b1fa2", 100, 30),
    ]
    for bx, btxt, bcol, bw, bh in blocks:
        svg += f'<rect x="{bx}" y="{ly}" width="{bw}" height="{bh}" fill="{bcol}" rx="4" opacity="0.8"/>\n'
        lines_ = btxt.split('\n')
        for i, line in enumerate(lines_):
            svg += f'<text x="{bx + bw // 2}" y="{ly + 12 + i * 11}" text-anchor="middle" '
            svg += f'fill="#eee" font-family="monospace" font-size="7">{line}</text>\n'
    # Arrows
    for ax in [130, 265, 410, 555]:
        svg += f'<line x1="{ax}" y1="{ly + 15}" x2="{ax + 40}" y2="{ly + 15}" stroke="#888" stroke-width="1.5" marker-end="url(#arrow)"/>\n'

    svg += f'''<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#888"/></marker></defs>\n'''

    ly += 50
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" '
    svg += f'font-family="monospace" font-size="8">Koe STAGE v1 | koe.live | github.com/yukihamada/koe-device</text>\n'

    svg += '</svg>\n'
    path = GBR / "koe-stage-layout.svg"
    path.write_text(svg)
    print(f"SVG: {path}")


def check():
    errs = []
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]
        cx, cy = c["x"], c["y"]
        rot = c.get("rot", 0)
        sw, sh = fp["size"]
        corners = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2), (sw / 2, sh / 2), (-sw / 2, sh / 2)]
        for dx, dy in corners:
            ax, ay = xform(dx, dy, cx, cy, rot)
            if not in_rect(ax, ay, -0.5):  # allow 0.5mm overhang for edge connectors
                errs.append(f"  {ref} corner ({ax:.1f},{ay:.1f}) outside board!")

    # Check component overlap (simple bounding box)
    placed = []
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]
        cx, cy = c["x"], c["y"]
        sw, sh = fp["size"]
        rot = c.get("rot", 0)
        if rot in (90, 270):
            sw, sh = sh, sw
        placed.append((ref, cx - sw / 2, cy - sh / 2, cx + sw / 2, cy + sh / 2))

    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            r1, x1a, y1a, x1b, y1b = placed[i]
            r2, x2a, y2a, x2b, y2b = placed[j]
            if x1a < x2b and x1b > x2a and y1a < y2b and y1b > y2a:
                # Allow mounting holes to overlap with nearby parts
                if r1.startswith("MH") or r2.startswith("MH"):
                    continue
                # Allow small passives near ICs
                if (r1[0] in "RCL" and r2[0] in "RCL"):
                    continue
                errs.append(f"  OVERLAP: {r1} and {r2}")

    if errs:
        print("DRC WARNINGS:")
        for e in errs:
            print(e)
    else:
        print("DRC: All OK")
    return len(errs) == 0


def main():
    print("=" * 65)
    print("Koe STAGE v1 — 85x55mm ESP32-S3 + PCM1808 Festival Bridge")
    print(f"  {len(PARTS)} parts | USB-C PD 5V/3A | WiFi UDP + BLE Auracast")
    print("=" * 65)
    check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()
    print(f"\nSignal flow:")
    print(f"  PA Mixer → 3.5mm jack → PCM1808 ADC (24-bit I2S)")
    print(f"  → ESP32-S3 processing")
    print(f"  → WiFi UDP broadcast (speakers)")
    print(f"  → BLE Auracast (COIN wearables)")
    print(f"\nPower:")
    print(f"  USB-C PD: 5V / 3A (primary)")
    print(f"  DC barrel: 5V (backup)")
    print(f"  AMS1117-3.3: 800mA LDO → 3.3V rail")


if __name__ == "__main__":
    main()
