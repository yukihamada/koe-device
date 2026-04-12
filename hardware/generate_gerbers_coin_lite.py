#!/usr/bin/env python3
"""
Koe COIN Lite — Production Gerber Generator (JLCPCB-ready)
===========================================================
Generates RS-274X Gerber files, Excellon drill file, BOM/CPL CSVs,
and a ZIP archive ready for JLCPCB upload.

Board: 26mm diameter round, 2-layer FR-4, 0.8mm thickness
MCU:   ESP32-C3-MINI-1 (WiFi 2.4GHz, RISC-V, 4MB Flash)
Amp:   MAX98357A QFN-16 (I2S Class-D 3W)
LDO:   AP2112K-3.3 SOT-23-5
CHG:   TP4054 SOT-23-5
LED:   WS2812B-2020

Usage:
    python3 hardware/generate_gerbers_coin_lite.py
"""

import math
import zipfile
import csv
from pathlib import Path

# ── Board parameters ──────────────────────────────────────────────────
BOARD_DIAMETER = 26.0  # mm
BOARD_RADIUS = BOARD_DIAMETER / 2.0
BOARD_CX = BOARD_RADIUS  # Center X (board origin at bottom-left of bounding box)
BOARD_CY = BOARD_RADIUS  # Center Y
CIRCLE_SEGS = 72  # segments to approximate circle outline

TRACE_W = 0.2    # signal trace width (mm)
PWR_W = 0.4      # power trace width (mm)
VBUS_W = 0.5     # USB VBUS trace width (mm)
VIA_DRILL = 0.3  # via drill diameter (mm)
VIA_PAD = 0.5    # via pad diameter (mm)
VIA_ANNULAR = 0.1  # mask opening expansion (mm)
MASK_EXP = 0.05  # solder mask expansion per side (mm)
POUR_CLEARANCE = 0.3
POUR_MARGIN = 0.8  # pour inset from board edge (mm)

OUT_DIR = Path(__file__).resolve().parent.parent / "manufacturing" / "gerbers" / "koe-coin-lite-production"
PREFIX = "koe-coin-lite"


# ── Footprint library ────────────────────────────────────────────────

def _qfn_pads(n_left, n_bottom, n_right, n_top, pitch, body_half,
              pad_w, pad_h, epad_w, epad_h):
    """Generic QFN pad generator. Returns list of (pin, x, y, w, h)."""
    pads = []
    pin = 1
    start_y = -(n_left - 1) * pitch / 2
    for i in range(n_left):
        pads.append((pin, -body_half, start_y + i * pitch, pad_w, pad_h))
        pin += 1
    start_x = -(n_bottom - 1) * pitch / 2
    for i in range(n_bottom):
        pads.append((pin, start_x + i * pitch, body_half, pad_h, pad_w))
        pin += 1
    start_y = (n_right - 1) * pitch / 2
    for i in range(n_right):
        pads.append((pin, body_half, start_y - i * pitch, pad_w, pad_h))
        pin += 1
    start_x = (n_top - 1) * pitch / 2
    for i in range(n_top):
        pads.append((pin, start_x - i * pitch, -body_half, pad_h, pad_w))
        pin += 1
    pads.append((pin, 0, 0, epad_w, epad_h))
    return pads


def _sot23_5_pads():
    """SOT-23-5 pad generator (1.9mm x 1.3mm body, 0.95mm pitch)."""
    # Pins 1-3 on left (bottom to top), 4-5 on right (top to bottom)
    pads = [
        (1, -1.1, 0.95,  0.6, 0.4),   # pin 1
        (2, -1.1, 0.0,   0.6, 0.4),   # pin 2
        (3, -1.1, -0.95, 0.6, 0.4),   # pin 3
        (4,  1.1, -0.95, 0.6, 0.4),   # pin 4
        (5,  1.1,  0.95, 0.6, 0.4),   # pin 5
    ]
    return pads


FP = {}

# ESP32-C3-MINI-1: 15.4x12.3mm module with castellated pads
# Bottom pads (GND row + signal pads along edges)
_esp32c3_pads = []
# Bottom row: 9 pads, 1.27mm pitch, centered
for i in range(9):
    _esp32c3_pads.append((i + 1, -5.08 + i * 1.27, 6.15, 0.7, 1.0))
# Left side: 4 pads
for i in range(4):
    _esp32c3_pads.append((10 + i, -7.7, 3.5 - i * 1.27, 1.0, 0.7))
# Right side: 4 pads
for i in range(4):
    _esp32c3_pads.append((14 + i, 7.7, 3.5 - i * 1.27, 1.0, 0.7))
# GND pad (large central pad on bottom)
_esp32c3_pads.append((18, 0, 3.5, 5.0, 5.0))

FP["ESP32C3"] = {
    "pads": _esp32c3_pads,
    "size": (15.4, 12.3),
    "silk_margin": 0.3,
}

# MAX98357A: QFN-16, 3x3mm, 0.5mm pitch (4 per side)
FP["MAX98357"] = {
    "pads": _qfn_pads(4, 4, 4, 4, 0.5, 1.5, 0.25, 0.5, 1.7, 1.7),
    "size": (3.0, 3.0),
    "silk_margin": 0.25,
}

# AP2112K-3.3: SOT-23-5
FP["SOT23_5_LDO"] = {
    "pads": _sot23_5_pads(),
    "size": (2.9, 1.6),
    "silk_margin": 0.2,
}

# TP4054: SOT-23-5
FP["SOT23_5_CHG"] = {
    "pads": _sot23_5_pads(),
    "size": (2.9, 1.6),
    "silk_margin": 0.2,
}

# WS2812B-2020
FP["WS2812B"] = {
    "pads": [
        (1, -0.65, -0.55, 0.5, 0.5), (2, 0.65, -0.55, 0.5, 0.5),
        (3, 0.65, 0.55, 0.5, 0.5), (4, -0.65, 0.55, 0.5, 0.5),
    ],
    "size": (2.0, 2.0),
}

# USB-C 6-pin (charging only)
FP["USBC_6P"] = {
    "pads": [
        ("V1", -1.75, -0.8, 0.5, 1.0),   # VBUS
        ("V2",  1.75, -0.8, 0.5, 1.0),   # VBUS
        ("C1", -0.75, -0.8, 0.3, 1.0),   # CC1
        ("C2",  0.75, -0.8, 0.3, 1.0),   # CC2
        ("G1", -2.75, -0.8, 0.5, 1.0),   # GND
        ("G2",  2.75, -0.8, 0.5, 1.0),   # GND
    ],
    "size": (7.0, 3.2),
}

# Tact switch 3x4mm side-mount
FP["SW_3X4"] = {
    "pads": [(1, -2.0, 0, 1.0, 0.8), (2, 2.0, 0, 1.0, 0.8)],
    "size": (3.0, 4.0),
}

# Speaker pads (simple 2-pad)
FP["SPK_PAD"] = {
    "pads": [(1, -1.5, 0, 1.5, 2.0), (2, 1.5, 0, 1.5, 2.0)],
    "size": (5.0, 2.5),
}

# Battery pads (simple 2-pad)
FP["BAT_PAD"] = {
    "pads": [(1, -1.5, 0, 1.5, 2.0), (2, 1.5, 0, 1.5, 2.0)],
    "size": (5.0, 2.5),
}

# Passives
FP["0402"] = {
    "pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)],
    "size": (1.6, 0.8),
}


# ── Component placement (on 26mm circular board) ─────────────────────
# Board center is at (13, 13). Components arranged in circular layout.
# 12 o'clock = top (y=0 in board coords means top in Gerber).
# Using Gerber convention: (0,0) = bottom-left of bounding box.

CX, CY = BOARD_CX, BOARD_CY  # Board center

PARTS = {
    # ESP32-C3-MINI-1 at center-top, antenna pointing up (12 o'clock)
    "U1":   {"fp": "ESP32C3",    "x": CX,       "y": CY + 2.0,  "rot": 0,
             "part": "ESP32-C3-MINI-1",   "lcsc": "C2838502"},

    # MAX98357A at bottom-left (7-8 o'clock)
    "U2":   {"fp": "MAX98357",   "x": CX - 4.5, "y": CY - 4.0,  "rot": 0,
             "part": "MAX98357AETE+T",    "lcsc": "C1506581"},

    # AP2112K-3.3 LDO near USB-C (5-6 o'clock)
    "U3":   {"fp": "SOT23_5_LDO","x": CX - 2.5, "y": CY - 8.5,  "rot": 0,
             "part": "AP2112K-3.3TRG1",   "lcsc": "C51118"},

    # TP4054 charger near USB-C (6 o'clock)
    "U4":   {"fp": "SOT23_5_CHG","x": CX + 2.5, "y": CY - 8.5,  "rot": 0,
             "part": "TP4054",             "lcsc": "C32574"},

    # WS2812B LED at 12 o'clock (top, near antenna)
    "LED1": {"fp": "WS2812B",   "x": CX,       "y": CY + 10.5, "rot": 0,
             "part": "WS2812B-2020",       "lcsc": "C2976072"},

    # USB-C at bottom edge (6 o'clock)
    "J1":   {"fp": "USBC_6P",   "x": CX,       "y": 1.6,       "rot": 0,
             "part": "USB-C 6P Charging",  "lcsc": "C2765186"},

    # Button at 3 o'clock (right side)
    "SW1":  {"fp": "SW_3X4",    "x": CX + 9.5, "y": CY,        "rot": 90,
             "part": "3x4mm Tact Switch",  "lcsc": "C2936178"},

    # Speaker pads at 9 o'clock (left side)
    "SPK1": {"fp": "SPK_PAD",   "x": CX - 10.0,"y": CY,        "rot": 90,
             "part": "20mm Speaker Pads",  "lcsc": ""},

    # Battery pads at bottom-right (4-5 o'clock)
    "BT1":  {"fp": "BAT_PAD",   "x": CX + 5.5, "y": CY - 6.0,  "rot": 0,
             "part": "LiPo 300mAh Pads",   "lcsc": ""},

    # Decoupling caps (distributed around components)
    "C1":   {"fp": "0402", "x": CX + 3.0,  "y": CY + 5.0,  "rot": 0,
             "part": "100nF 0402",   "lcsc": "C1525"},
    "C2":   {"fp": "0402", "x": CX - 3.0,  "y": CY + 5.0,  "rot": 0,
             "part": "100nF 0402",   "lcsc": "C1525"},
    "C3":   {"fp": "0402", "x": CX - 2.5,  "y": CY - 3.0,  "rot": 0,
             "part": "10uF 0402",    "lcsc": "C15849"},
    "C4":   {"fp": "0402", "x": CX + 2.5,  "y": CY - 3.0,  "rot": 0,
             "part": "100nF 0402",   "lcsc": "C1525"},
    "C5":   {"fp": "0402", "x": CX - 6.0,  "y": CY - 2.5,  "rot": 0,
             "part": "10uF 0402",    "lcsc": "C15849"},
    "C6":   {"fp": "0402", "x": CX + 1.0,  "y": CY - 6.5,  "rot": 90,
             "part": "1uF 0402",     "lcsc": "C14445"},
    "C7":   {"fp": "0402", "x": CX - 1.0,  "y": CY - 6.5,  "rot": 90,
             "part": "4.7uF 0402",   "lcsc": "C23733"},

    # Pull-up / divider resistors
    "R1":   {"fp": "0402", "x": CX + 5.0,  "y": CY + 3.0,  "rot": 0,
             "part": "10k 0402",     "lcsc": "C25744"},
    "R2":   {"fp": "0402", "x": CX - 5.0,  "y": CY + 3.0,  "rot": 0,
             "part": "5.1k 0402",    "lcsc": "C25905"},
    "R3":   {"fp": "0402", "x": CX - 4.0,  "y": CY - 6.0,  "rot": 0,
             "part": "5.1k 0402",    "lcsc": "C25905"},
}


# ── Routes (net_name, trace_width, waypoints) ────────────────────────
ROUTES = [
    # USB VBUS -> LDO and Charger
    ("+VBUS",      VBUS_W, [(CX, 1.6), (CX, CY - 7.0)]),
    ("+VBUS",      PWR_W,  [(CX, CY - 7.0), (CX - 2.5, CY - 8.5)]),
    ("+VBUS",      PWR_W,  [(CX, CY - 7.0), (CX + 2.5, CY - 8.5)]),
    # LDO 3.3V output -> ESP32-C3
    ("+3V3",       PWR_W,  [(CX - 2.5, CY - 8.5), (CX - 2.5, CY - 5.0), (CX, CY + 2.0)]),
    # 3.3V -> MAX98357A
    ("+3V3",       TRACE_W,[(CX - 2.5, CY - 5.0), (CX - 4.5, CY - 4.0)]),
    # 3.3V -> LED
    ("+3V3",       TRACE_W,[(CX, CY + 2.0), (CX, CY + 10.5)]),
    # Battery -> Charger
    ("+VBAT",      PWR_W,  [(CX + 5.5, CY - 6.0), (CX + 2.5, CY - 8.5)]),
    # I2S: ESP32-C3 -> MAX98357A
    ("I2S_BCK",    TRACE_W,[(CX - 2.0, CY + 2.0), (CX - 3.0, CY - 2.0), (CX - 4.5, CY - 2.5)]),
    ("I2S_WS",     TRACE_W,[(CX - 1.0, CY + 2.0), (CX - 2.0, CY - 2.0), (CX - 4.5, CY - 3.0)]),
    ("I2S_DOUT",   TRACE_W,[(CX + 0.0, CY + 2.0), (CX - 1.0, CY - 2.0), (CX - 4.5, CY - 3.5)]),
    ("AMP_SD",     TRACE_W,[(CX + 1.0, CY + 2.0), (CX - 0.5, CY - 1.5), (CX - 3.0, CY - 4.0)]),
    # Amp -> Speaker
    ("SPK_OUT",    TRACE_W,[(CX - 6.0, CY - 4.0), (CX - 8.0, CY - 2.0), (CX - 10.0, CY)]),
    # LED data from ESP32
    ("LED_DIN",    TRACE_W,[(CX + 2.0, CY + 2.0), (CX + 2.0, CY + 8.0), (CX, CY + 10.5)]),
    # Button -> ESP32
    ("BTN",        TRACE_W,[(CX + 9.5, CY), (CX + 5.0, CY + 2.0), (CX + 3.0, CY + 2.0)]),
    # USB CC pull-downs
    ("CC1",        TRACE_W,[(CX - 4.0, CY - 6.0), (CX - 0.75, 1.6)]),
    ("CC2",        TRACE_W,[(CX + 5.0, CY + 3.0), (CX + 0.75, 1.6)]),
]

# Via positions (GND stitching)
VIAS = [
    (CX, CY),
    (CX - 5, CY + 5), (CX + 5, CY + 5),
    (CX - 5, CY - 5), (CX + 5, CY - 5),
    (CX - 3, CY - 1), (CX + 3, CY - 1),
    (CX, CY + 7), (CX, CY - 4),
    (CX - 7, CY), (CX + 7, CY),
]


# ── Coordinate transform ─────────────────────────────────────────────
def xform(px, py, cx, cy, rot):
    """Transform local pad coordinate to board coordinate."""
    r = math.radians(rot)
    return (cx + px * math.cos(r) - py * math.sin(r),
            cy + px * math.sin(r) + py * math.cos(r))


# ── RS-274X Gerber Writer ─────────────────────────────────────────────
class GerberWriter:
    """Generates proper RS-274X Gerber files with FSLAX36Y36 format."""

    def __init__(self, layer_name, layer_function=None):
        self.layer_name = layer_name
        self.layer_function = layer_function
        self.apertures = {}
        self.next_dcode = 10
        self.commands = []

    def _get_aperture(self, shape, params):
        key = (shape, tuple(round(p, 4) for p in params))
        if key not in self.apertures:
            self.apertures[key] = self.next_dcode
            self.next_dcode += 1
        return self.apertures[key]

    @staticmethod
    def _coord(v):
        return int(round(v * 1e6))

    def flash_pad(self, x, y, w, h):
        if abs(w - h) < 0.005:
            d = self._get_aperture("C", [w])
        else:
            d = self._get_aperture("R", [w, h])
        self.commands.append(f"D{d}*")
        self.commands.append(f"X{self._coord(x)}Y{self._coord(y)}D03*")

    def flash_circle(self, x, y, diameter):
        d = self._get_aperture("C", [diameter])
        self.commands.append(f"D{d}*")
        self.commands.append(f"X{self._coord(x)}Y{self._coord(y)}D03*")

    def draw_line(self, x1, y1, x2, y2, width):
        d = self._get_aperture("C", [width])
        self.commands.append(f"D{d}*")
        self.commands.append(f"X{self._coord(x1)}Y{self._coord(y1)}D02*")
        self.commands.append(f"X{self._coord(x2)}Y{self._coord(y2)}D01*")

    def draw_polyline(self, points, width):
        if len(points) < 2:
            return
        d = self._get_aperture("C", [width])
        self.commands.append(f"D{d}*")
        self.commands.append(f"X{self._coord(points[0][0])}Y{self._coord(points[0][1])}D02*")
        for x, y in points[1:]:
            self.commands.append(f"X{self._coord(x)}Y{self._coord(y)}D01*")

    def draw_circle(self, cx, cy, radius, width=0.05, segments=72):
        """Draw a circle outline using line segments."""
        pts = []
        for i in range(segments + 1):
            a = 2 * math.pi * i / segments
            pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
        self.draw_polyline(pts, width)

    def fill_circle(self, cx, cy, radius, line_width=0.25):
        """Fill a circular region with horizontal lines (copper pour)."""
        d = self._get_aperture("C", [line_width])
        self.commands.append(f"D{d}*")
        step = line_width * 0.8
        y = cy - radius
        while y <= cy + radius:
            dy = y - cy
            if abs(dy) <= radius:
                half_w = math.sqrt(radius * radius - dy * dy)
                x1 = cx - half_w
                x2 = cx + half_w
                self.commands.append(f"X{self._coord(x1)}Y{self._coord(y)}D02*")
                self.commands.append(f"X{self._coord(x2)}Y{self._coord(y)}D01*")
            y += step

    def draw_text(self, x, y, text, char_w=0.8, char_h=1.0, line_w=0.12):
        """Draw simple block text on silkscreen."""
        FONT = {
            'A': [(-1,0),(-0.3,1),(0.3,1),(1,0),None,(-0.65,0.5),(0.65,0.5)],
            'C': [(1,0.8),(0.5,1),(-0.5,1),(-1,0.8),(-1,0.2),(-0.5,0),(0.5,0),(1,0.2)],
            'D': [(-1,0),(-1,1),(0.5,1),(1,0.7),(1,0.3),(0.5,0),(-1,0)],
            'E': [(1,1),(-1,1),(-1,0.5),(0.5,0.5),None,(-1,0.5),(-1,0),(1,0)],
            'I': [(-0.3,1),(0.3,1),None,(0,1),(0,0),None,(-0.3,0),(0.3,0)],
            'K': [(-1,0),(-1,1),None,(-1,0.5),(1,1),None,(-1,0.5),(1,0)],
            'L': [(-1,1),(-1,0),(1,0)],
            'M': [(-1,0),(-1,1),(0,0.5),(1,1),(1,0)],
            'N': [(-1,0),(-1,1),(1,0),(1,1)],
            'O': [(-0.5,0),(-1,0.3),(-1,0.7),(-0.5,1),(0.5,1),(1,0.7),(1,0.3),(0.5,0),(-0.5,0)],
            'T': [(-1,1),(1,1),None,(0,1),(0,0)],
            'V': [(-1,1),(0,0),(1,1)],
            ' ': [],
            '-': [(-0.5,0.5),(0.5,0.5)],
            '.': [(0,0),(0,0.1)],
            '0': [(-0.5,0),(-1,0.3),(-1,0.7),(-0.5,1),(0.5,1),(1,0.7),(1,0.3),(0.5,0),(-0.5,0)],
            '1': [(-0.3,0.8),(0,1),(0,0),None,(-0.3,0),(0.3,0)],
            '2': [(-1,0.8),(-0.5,1),(0.5,1),(1,0.7),(1,0.5),(-1,0),(1,0)],
        }
        d = self._get_aperture("C", [line_w])
        cx = x
        for ch in text.upper():
            glyph = FONT.get(ch, [])
            seg_start = True
            for pt in glyph:
                if pt is None:
                    seg_start = True
                    continue
                gx = cx + pt[0] * char_w * 0.5
                gy = y + pt[1] * char_h - char_h * 0.5
                if seg_start:
                    self.commands.append(f"D{d}*")
                    self.commands.append(f"X{self._coord(gx)}Y{self._coord(gy)}D02*")
                    seg_start = False
                else:
                    self.commands.append(f"X{self._coord(gx)}Y{self._coord(gy)}D01*")
            cx += char_w

    def write(self, filepath):
        with open(filepath, 'w', newline='\n') as f:
            f.write(f"G04 Koe COIN Lite -- Generated by generate_gerbers_coin_lite.py*\n")
            f.write(f"G04 Layer: {self.layer_name}*\n")
            f.write(f"G04 Date: 2026-03-27*\n")
            if self.layer_function:
                f.write(f"%TF.FileFunction,{self.layer_function}*%\n")
            f.write("%TF.GenerationSoftware,KoeDevice,generate_gerbers_coin_lite.py,1.0*%\n")
            f.write("%TF.SameCoordinates,Original*%\n")
            f.write("%FSLAX36Y36*%\n")
            f.write("%MOMM*%\n")
            f.write("%LPD*%\n")
            for (shape, params), dcode in sorted(self.apertures.items(), key=lambda x: x[1]):
                if shape == "C":
                    f.write(f"%ADD{dcode}C,{params[0]:.4f}*%\n")
                elif shape == "R":
                    f.write(f"%ADD{dcode}R,{params[0]:.4f}X{params[1]:.4f}*%\n")
            for cmd in self.commands:
                f.write(cmd + "\n")
            f.write("M02*\n")


# ── Excellon Drill Writer ─────────────────────────────────────────────
class DrillWriter:
    def __init__(self):
        self.tools = {}
        self.next_tool = 1
        self.holes = []

    def add_hole(self, x, y, diameter):
        d = round(diameter, 3)
        if d not in self.tools:
            self.tools[d] = self.next_tool
            self.next_tool += 1
        self.holes.append((self.tools[d], x, y))

    def write(self, filepath):
        with open(filepath, 'w', newline='\n') as f:
            f.write("M48\n")
            f.write("; Koe COIN Lite -- 26mm round ESP32-C3\n")
            f.write("; Generated by generate_gerbers_coin_lite.py\n")
            f.write("FMAT,2\n")
            f.write("METRIC,TZ\n")
            for d, t in sorted(self.tools.items(), key=lambda x: x[1]):
                f.write(f"T{t}C{d:.3f}\n")
            f.write("%\n")
            f.write("G90\n")
            f.write("G05\n")
            current_tool = None
            for t, x, y in sorted(self.holes, key=lambda h: h[0]):
                if t != current_tool:
                    f.write(f"T{t}\n")
                    current_tool = t
                f.write(f"X{x:.3f}Y{y:.3f}\n")
            f.write("T0\n")
            f.write("M30\n")


# ── Main generation ──────────────────────────────────────────────────

def generate_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    f_cu = GerberWriter("F.Cu", "Copper,L1,Top")
    b_cu = GerberWriter("B.Cu", "Copper,L2,Bot")
    f_mask = GerberWriter("F.Mask", "Soldermask,Top")
    b_mask = GerberWriter("B.Mask", "Soldermask,Bot")
    f_silk = GerberWriter("F.SilkS", "Legend,Top")
    edge = GerberWriter("Edge.Cuts", "Profile,NP")
    drill = DrillWriter()

    # ── Board outline (Edge.Cuts) — circular ──
    edge.draw_circle(BOARD_CX, BOARD_CY, BOARD_RADIUS, 0.05, CIRCLE_SEGS)

    # ── Component pads and silkscreen ──
    for ref, comp in PARTS.items():
        fp = FP[comp["fp"]]
        cx, cy = comp["x"], comp["y"]
        rot = comp.get("rot", 0)
        sw, sh = fp["size"]

        # Silkscreen: component outline
        hw, hh = sw / 2, sh / 2
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        transformed = [xform(dx, dy, cx, cy, rot) for dx, dy in corners]
        for i in range(4):
            x1, y1 = transformed[i]
            x2, y2 = transformed[(i + 1) % 4]
            f_silk.draw_line(x1, y1, x2, y2, 0.12)

        # Pin 1 indicator
        if ref.startswith("U"):
            dot_x, dot_y = xform(-hw + 0.5, -hh + 0.5, cx, cy, rot)
            f_silk.flash_circle(dot_x, dot_y, 0.3)

        # Reference designator
        f_silk.draw_text(cx - len(ref) * 0.35, cy - sh / 2 - 1.2, ref,
                         char_w=0.6, char_h=0.8, line_w=0.1)

        # Pads
        for pad_data in fp["pads"]:
            pin, px, py, pw, ph = pad_data
            ax, ay = xform(px, py, cx, cy, rot)
            rpw, rph = pw, ph
            if rot in (90, 270):
                rpw, rph = ph, pw

            f_cu.flash_pad(ax, ay, rpw, rph)
            f_mask.flash_pad(ax, ay, rpw + MASK_EXP * 2, rph + MASK_EXP * 2)

    # ── Signal traces on F.Cu ──
    for net_name, width, waypoints in ROUTES:
        for i in range(len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]
            f_cu.draw_line(x1, y1, x2, y2, width)

    # ── Vias ──
    for vx, vy in VIAS:
        # Check via is inside the board circle
        dist = math.sqrt((vx - BOARD_CX)**2 + (vy - BOARD_CY)**2)
        if dist > BOARD_RADIUS - 1.0:
            continue
        f_cu.flash_circle(vx, vy, VIA_PAD)
        b_cu.flash_circle(vx, vy, VIA_PAD)
        f_mask.flash_circle(vx, vy, VIA_PAD + VIA_ANNULAR)
        b_mask.flash_circle(vx, vy, VIA_PAD + VIA_ANNULAR)
        drill.add_hole(vx, vy, VIA_DRILL)

    # ── Back copper: GND pour (circular) ──
    pour_r = BOARD_RADIUS - POUR_MARGIN
    b_cu.fill_circle(BOARD_CX, BOARD_CY, pour_r, 0.25)

    # ── Silkscreen: board name ──
    f_silk.draw_text(CX - 3.5, CY + 8.0, "COIN", char_w=0.8, char_h=1.0, line_w=0.12)
    f_silk.draw_text(CX - 2.5, CY - 10.5, "V1.0", char_w=0.5, char_h=0.7, line_w=0.1)

    # ── Write all files ──
    layer_files = [
        ("F_Cu", f_cu),
        ("B_Cu", b_cu),
        ("F_Mask", f_mask),
        ("B_Mask", b_mask),
        ("F_SilkS", f_silk),
        ("Edge_Cuts", edge),
    ]

    written_files = []
    for suffix, writer in layer_files:
        filepath = OUT_DIR / f"{PREFIX}-{suffix}.gbr"
        writer.write(filepath)
        written_files.append(filepath)
        print(f"  Gerber: {filepath.name} ({len(writer.commands)} cmds, {len(writer.apertures)} apertures)")

    drill_path = OUT_DIR / f"{PREFIX}.drl"
    drill.write(drill_path)
    written_files.append(drill_path)
    print(f"  Drill:  {drill_path.name} ({len(drill.holes)} holes, {len(drill.tools)} tools)")

    # ── BOM CSV (JLCPCB format) ──
    bom_path = OUT_DIR / f"{PREFIX}-BOM-JLCPCB.csv"
    _generate_bom(bom_path)
    written_files.append(bom_path)
    print(f"  BOM:    {bom_path.name}")

    # ── CPL CSV (JLCPCB format) ──
    cpl_path = OUT_DIR / f"{PREFIX}-CPL-JLCPCB.csv"
    _generate_cpl(cpl_path)
    written_files.append(cpl_path)
    print(f"  CPL:    {cpl_path.name}")

    # ── ZIP archive ──
    zip_path = OUT_DIR / f"{PREFIX}-gerbers.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in written_files:
            zf.write(f, f.name)
    print(f"  ZIP:    {zip_path.name} ({zip_path.stat().st_size:,} bytes)")

    return written_files, zip_path


def _generate_bom(filepath):
    groups = {}
    for ref, comp in PARTS.items():
        lcsc = comp.get("lcsc", "")
        if not lcsc:
            continue
        key = (comp["part"], comp["fp"], lcsc)
        groups.setdefault(key, []).append(ref)

    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (part, fp_name, lcsc), refs in sorted(groups.items(), key=lambda x: x[1][0]):
            writer.writerow([part, " ".join(refs), fp_name, lcsc])


def _generate_cpl(filepath):
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Rotation", "Layer"])
        for ref, comp in sorted(PARTS.items()):
            lcsc = comp.get("lcsc", "")
            if not lcsc:
                continue
            rot = comp.get("rot", 0) % 360
            writer.writerow([ref, f"{comp['x']:.2f}mm", f"{comp['y']:.2f}mm", rot, "Top"])


def validate_gerbers(out_dir):
    errors = []
    warnings = []

    for gbr_file in out_dir.glob("*.gbr"):
        content = gbr_file.read_text()
        name = gbr_file.name

        if "%FSLAX36Y36*%" not in content:
            errors.append(f"{name}: Missing format specification %FSLAX36Y36*%")
        if "%MOMM*%" not in content:
            errors.append(f"{name}: Missing unit specification %MOMM*%")
        if "M02*" not in content:
            errors.append(f"{name}: Missing end-of-file M02*")
        if "%LPD*%" not in content:
            errors.append(f"{name}: Missing polarity %LPD*%")
        if "%ADD" not in content:
            errors.append(f"{name}: No aperture definitions found")

        has_d01 = "D01*" in content
        has_d03 = "D03*" in content
        if not has_d01 and not has_d03:
            warnings.append(f"{name}: No draw (D01) or flash (D03) commands")

        if "Edge_Cuts" in name and "D01*" not in content:
            errors.append(f"{name}: Edge cuts must have line draws (D01)")

    drl_file = out_dir / f"{PREFIX}.drl"
    if drl_file.exists():
        content = drl_file.read_text()
        if "M48" not in content:
            errors.append(f"{drl_file.name}: Missing M48 header")
        if "METRIC" not in content:
            errors.append(f"{drl_file.name}: Missing METRIC specification")
        if "M30" not in content:
            errors.append(f"{drl_file.name}: Missing M30 end-of-file")
    else:
        errors.append("Drill file missing!")

    required = ["F_Cu", "B_Cu", "F_Mask", "B_Mask", "F_SilkS", "Edge_Cuts"]
    for layer in required:
        if not (out_dir / f"{PREFIX}-{layer}.gbr").exists():
            errors.append(f"Missing required layer: {layer}")

    return errors, warnings


def main():
    print("=" * 65)
    print("Koe COIN Lite -- Production Gerber Generator")
    print(f"  Board:  {BOARD_DIAMETER}mm diameter round, 2-layer FR-4, 0.8mm")
    print(f"  Parts:  {len(PARTS)} components")
    print(f"  Traces: {len(ROUTES)} routes")
    print(f"  Vias:   {len(VIAS)} positions")
    print(f"  Output: {OUT_DIR}")
    print("=" * 65)

    print("\nGenerating manufacturing files...")
    files, zip_path = generate_all()

    print("\nValidating Gerber files...")
    errors, warnings = validate_gerbers(OUT_DIR)

    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    ! {e}")
        print("\nValidation FAILED. Fix errors before uploading to JLCPCB.")
        return 1
    else:
        print("  All checks passed.")

    print("\n" + "=" * 65)
    print("Output files:")
    for f in sorted(OUT_DIR.iterdir()):
        print(f"  {f.name:45s} {f.stat().st_size:>8,} bytes")
    print(f"\nJLCPCB upload: {zip_path.name}")
    print("  1. Go to https://www.jlcpcb.com/")
    print("  2. Click 'Order Now' -> 'Add gerber file'")
    print(f"  3. Upload {zip_path.name}")
    print("  4. Select 2 layers, 0.8mm thickness, HASL finish")
    print(f"  5. For assembly: upload BOM + CPL CSVs")
    print("  6. Board shape: round 26mm diameter")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
