#!/usr/bin/env python3
"""
Koe COIN Lite v2 — Production Gerber Generator (JLCPCB-ready)
==============================================================
Generates RS-274X Gerber files, Excellon drill file, BOM/CPL CSVs,
layout SVG, and a ZIP archive ready for JLCPCB upload.

Board: 28mm diameter round, 2-layer FR-4, 0.8mm thickness
MCU:   nRF5340-QKAA-R7 (QFN-94 7x7mm) — BLE 5.4 dual-core Cortex-M33
PA:    nRF21540-QFAA-R (QFN-16 4x4mm) — PA/LNA for 1km BLE range
Amp:   MAX98357AETE+T (QFN-16 1.6x1.6mm) — I2S Class-D 3W
LDO:   AP2112K-3.3TRG1 (SOT-23-5)
CHG:   TP4054 (SOT-23-5) — LiPo charger
LED:   WS2812B-2020
USB:   USB-C 16P (D+/D- connected to nRF5340 USB)
ANT:   Johanson 2450AT18B100 ceramic chip antenna (2.4GHz BLE)

Upgrade from v1: ESP32-C3 → nRF5340 + nRF21540 for BLE 5.4 + 1km range
Board increased from 26mm to 28mm to accommodate QFN-94 + PA/LNA.

v2 fixes (2026-04-10):
  - Replaced IFA PCB antenna with Johanson 2450AT18B100 ceramic chip antenna
  - Added GND keepout zone under antenna on back copper
  - Added F_Paste Gerber layer with QFN windowed paste for exposed pads
  - Removed R5 (33R) from RF path — direct LC match to antenna
  - Added missing DEC1/DEC2 decoupling caps per nRF5340 datasheet Table 13
  - 1.5mm wide antenna feed trace for 50-ohm microstrip on 1.0mm FR-4
  - Moved Y1 (32MHz) within 3mm of nRF5340 XC1/XC2
  - Moved Y2 (32.768kHz) within 5mm of nRF5340 P0.00/P0.01
  - Increased nRF5340 thermal vias from 5 to 9 (3x3 grid)
  - Added 4 SWD debug test pads (SWDIO, SWDCLK, GND, VCC)
  - USB-C upgraded to 16-pin with D+/D- routed to nRF5340 USB pins
  - QFN-94 pad protrusion increased from 0.2mm to 0.3mm

Pin assignments (source of truth for firmware overlay):
  P0.00 — XL1 (32.768kHz crystal)
  P0.01 — XL2 (32.768kHz crystal)
  P0.02 — NFC1 (repurposed as GPIO, AIN0)
  P0.04 — AIN2 (analog input, battery voltage divider)
  P0.06 — I2S DOUT (to MAX98357A DIN)
  P0.08 — Button input (active low, 10k pull-up R6)
  P0.13 — WS2812B LED data out (via 330R R3)
  P0.19 — nRF21540 TXEN
  P0.20 — nRF21540 RXEN
  P0.21 — nRF21540 MODE / ANT_SEL
  P0.25 — MAX98357A SD_MODE (amp enable)
  P0.26 — I2S BCLK (to MAX98357A)
  P0.27 — I2S LRCK/WS (to MAX98357A)
  P0.18 — SWDIO (debug pad TP1)
  P0.20 — SWDCLK (overlapped with RXEN — use dedicated SWD pins)
  SWDIO  — dedicated SWD pad TP1
  SWDCLK — dedicated SWD pad TP2
  D-     — USB D- (to USB-C connector)
  D+     — USB D+ (to USB-C connector)
  XC1/XC2 — 32MHz crystal (Y1)
  DEC1   — 1uF decoupling (C_DEC1)
  DEC2   — 100nF decoupling (C_DEC2)
  DECP   — 4.7uF decoupling (C9 on nRF21540, C7 reused)
  VDDH   — 10uF bulk (C5)

Usage:
    python3 hardware/gen_coin_lite_v2.py
"""

import math
import csv
import zipfile
from pathlib import Path

# ── Board parameters ──────────────────────────────────────────────────
BOARD_DIAMETER = 28.0  # mm (up from 26mm v1)
BOARD_RADIUS = BOARD_DIAMETER / 2.0
BOARD_CX = BOARD_RADIUS  # Center X (board origin at bottom-left of bounding box)
BOARD_CY = BOARD_RADIUS  # Center Y
CIRCLE_SEGS = 72  # segments to approximate circle outline

TRACE_W = 0.2    # signal trace width (mm)
RF_TRACE_W = 1.5 # 50-ohm microstrip on 1.0mm FR-4 (antenna feed)
PWR_W = 0.4      # power trace width (mm)
VBUS_W = 0.5     # USB VBUS trace width (mm)
VIA_DRILL = 0.3  # via drill diameter (mm)
VIA_PAD = 0.5    # via pad diameter (mm)
VIA_ANNULAR = 0.1  # mask opening expansion (mm)
MASK_EXP = 0.05  # solder mask expansion per side (mm)
POUR_MARGIN = 0.8  # pour inset from board edge (mm)

OUT_DIR = Path(__file__).resolve().parent.parent / "manufacturing" / "gerbers" / "koe-coin-lite-v2"
PREFIX = "koe-coin-lite-v2"


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
    return [
        (1, -1.1, 0.95,  0.6, 0.4),   # pin 1
        (2, -1.1, 0.0,   0.6, 0.4),   # pin 2
        (3, -1.1, -0.95, 0.6, 0.4),   # pin 3
        (4,  1.1, -0.95, 0.6, 0.4),   # pin 4
        (5,  1.1,  0.95, 0.6, 0.4),   # pin 5
    ]


FP = {}

# nRF5340-QKAA: QFN-94, 7x7mm, 0.4mm pitch
# 24 pads left, 23 pads bottom, 24 pads right, 23 pads top + exposed pad
def _nrf5340():
    p = []
    pitch = 0.4
    # Left side: 24 pads (0.3mm wide for better solderability)
    for i in range(24):
        p.append((i + 1, -3.5, -4.6 + i * pitch, 0.3, 0.7))
    # Bottom side: 23 pads
    for i in range(23):
        p.append((25 + i, -4.4 + i * pitch, 3.5, 0.7, 0.3))
    # Right side: 24 pads
    for i in range(24):
        p.append((48 + i, 3.5, 4.6 - i * pitch, 0.3, 0.7))
    # Top side: 23 pads
    for i in range(23):
        p.append((72 + i, 4.4 - i * pitch, -3.5, 0.7, 0.3))
    # Exposed thermal pad
    p.append((95, 0, 0, 5.0, 5.0))
    return p

FP["NRF5340"] = {
    "pads": _nrf5340(),
    "size": (7.0, 7.0),
}

# nRF21540-QFAA: QFN-16, 4x4mm, 0.5mm pitch (4 pads per side + exposed pad)
FP["NRF21540"] = {
    "pads": _qfn_pads(4, 4, 4, 4, 0.5, 2.0, 0.25, 0.7, 2.4, 2.4),
    "size": (4.0, 4.0),
}

# MAX98357AETE+T: QFN-16, 1.6x1.6mm body, 0.4mm pitch (4 pads per side + exposed pad)
FP["MAX98357"] = {
    "pads": _qfn_pads(4, 4, 4, 4, 0.4, 0.8, 0.2, 0.5, 0.8, 0.8),
    "size": (1.6, 1.6),
}

# AP2112K-3.3: SOT-23-5
FP["SOT23_5_LDO"] = {
    "pads": _sot23_5_pads(),
    "size": (2.9, 1.6),
}

# TP4054: SOT-23-5
FP["SOT23_5_CHG"] = {
    "pads": _sot23_5_pads(),
    "size": (2.9, 1.6),
}

# WS2812B-2020: 2x2mm
FP["WS2812B"] = {
    "pads": [
        (1, -0.65, -0.55, 0.5, 0.5), (2, 0.65, -0.55, 0.5, 0.5),
        (3, 0.65, 0.55, 0.5, 0.5), (4, -0.65, 0.55, 0.5, 0.5),
    ],
    "size": (2.0, 2.0),
}

# USB-C 16-pin — C2765186 (16P connector with D+/D- for data)
# Dual-row SMD pads, 0.5mm pitch, compact row spacing
FP["USBC_16P"] = {
    "pads": [
        # Row A (inner row)
        ("A1",  -2.75, 0.0, 0.3, 0.8),   # GND
        ("A4",  -1.75, 0.0, 0.3, 0.8),   # VBUS
        ("A5",  -0.75, 0.0, 0.3, 0.8),   # CC1
        ("A6",  -0.25, 0.0, 0.3, 0.8),   # D+
        ("A7",   0.25, 0.0, 0.3, 0.8),   # D-
        ("A8",   0.75, 0.0, 0.3, 0.8),   # SBU1 (unused)
        ("A9",   1.75, 0.0, 0.3, 0.8),   # VBUS
        ("A12",  2.75, 0.0, 0.3, 0.8),   # GND
        # Row B (outer row, 1.0mm offset from row A)
        ("B1",  -2.75, -1.0, 0.3, 0.8),  # GND
        ("B4",  -1.75, -1.0, 0.3, 0.8),  # VBUS
        ("B5",  -0.75, -1.0, 0.3, 0.8),  # CC2
        ("B6",  -0.25, -1.0, 0.3, 0.8),  # D- (flipped)
        ("B7",   0.25, -1.0, 0.3, 0.8),  # D+ (flipped)
        ("B8",   0.75, -1.0, 0.3, 0.8),  # SBU2 (unused)
        ("B9",   1.75, -1.0, 0.3, 0.8),  # VBUS
        ("B12",  2.75, -1.0, 0.3, 0.8),  # GND
    ],
    "size": (7.0, 2.5),
}

# JST-PH 2-pin (battery / speaker connector) — C131337
FP["JST_PH2"] = {
    "pads": [
        (1, -1.0, 0.0, 1.0, 1.5),
        (2,  1.0, 0.0, 1.0, 1.5),
    ],
    "size": (6.0, 4.5),
}

# Tact switch 3x4mm side-mount — C2936178
FP["SW_3X4"] = {
    "pads": [(1, -2.0, 0, 1.0, 0.8), (2, 2.0, 0, 1.0, 0.8)],
    "size": (3.0, 4.0),
}

# 32MHz crystal 2012 (2x1.2mm) — C2762297
FP["XTAL_2012"] = {
    "pads": [
        (1, -0.7, 0, 0.5, 0.9),
        (2, 0.7, 0, 0.5, 0.9),
    ],
    "size": (2.0, 1.2),
}

# 32.768kHz crystal 1610 (1.6x1mm) — C2838510
FP["XTAL_1610"] = {
    "pads": [
        (1, -0.55, 0, 0.4, 0.7),
        (2, 0.55, 0, 0.4, 0.7),
    ],
    "size": (1.6, 1.0),
}

# Johanson 2450AT18B100 ceramic chip antenna (2.5x1.0x0.6mm) — LCSC C138386
# 2-pad SMD: pad1=feed, pad2=GND (open)
FP["CHIP_ANT"] = {
    "pads": [
        (1, -0.85, 0, 0.6, 0.8),     # Feed (connect to matching network)
        (2,  0.85, 0, 0.6, 0.8),     # GND (leave open per datasheet)
    ],
    "size": (2.5, 1.0),
}

# Passives
FP["0402"] = {
    "pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)],
    "size": (1.6, 0.8),
}
FP["0603"] = {
    "pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)],
    "size": (2.2, 1.2),
}

# Test pad (1.0mm round, for SWD debug)
FP["TP_1MM"] = {
    "pads": [(1, 0, 0, 1.0, 1.0)],
    "size": (1.0, 1.0),
}


# ── Component placement (on 28mm circular board) ─────────────────────
# Board center is at (14, 14). Components arranged in circular layout.
# Using Gerber convention: (0,0) = bottom-left of bounding box.

CX, CY = BOARD_CX, BOARD_CY  # Board center (14, 14)

PARTS = {
    # ── U1: nRF5340-QKAA — main BLE 5.4 SoC, center of board ──
    "U1": {"fp": "NRF5340", "x": CX, "y": CY, "rot": 0,
            "part": "nRF5340-QKAA-R7", "lcsc": "C2652073",
            "label": "nRF5340\nQFN-94", "color": "#0d47a1"},

    # ── U2: nRF21540 PA/LNA — near antenna (top-right, toward board edge) ──
    "U2": {"fp": "NRF21540", "x": CX + 5.5, "y": CY + 6.0, "rot": 0,
            "part": "nRF21540-QFAA-R", "lcsc": "C2889059",
            "label": "nRF21540\nPA/LNA", "color": "#880e4f"},

    # ── U3: MAX98357A — I2S class-D amp (bottom-left) ──
    "U3": {"fp": "MAX98357", "x": CX - 5.0, "y": CY - 5.5, "rot": 0,
            "part": "MAX98357AETE+T", "lcsc": "C1506581",
            "label": "MAX98357\nAmp", "color": "#b71c1c"},

    # ── U4: AP2112K-3.3 LDO — near USB-C (bottom center-left) ──
    "U4": {"fp": "SOT23_5_LDO", "x": CX - 3.0, "y": CY - 9.5, "rot": 0,
            "part": "AP2112K-3.3TRG1", "lcsc": "C51118",
            "label": "LDO\n3.3V", "color": "#e65100"},

    # ── U5: TP4054 LiPo charger — near USB-C (bottom center-right) ──
    "U5": {"fp": "SOT23_5_CHG", "x": CX + 3.0, "y": CY - 9.5, "rot": 0,
            "part": "TP4054", "lcsc": "C32574",
            "label": "TP4054\nCHG", "color": "#f57f17"},

    # ── J1: USB-C 16P — data+charging, bottom edge (6 o'clock) ──
    "J1": {"fp": "USBC_16P", "x": CX, "y": 2.5, "rot": 0,
            "part": "USB-C 16P", "lcsc": "C2765186",
            "label": "USB-C", "color": "#78909c"},

    # ── BT1: JST-PH-2P battery connector — bottom-right (4-5 o'clock) ──
    "BT1": {"fp": "JST_PH2", "x": CX + 6.5, "y": CY - 6.5, "rot": 0,
             "part": "JST-PH-2P", "lcsc": "C131337",
             "label": "LiPo\nBAT", "color": "#ff5722"},

    # ── SPK1: JST-PH-2P speaker connector — left side (9 o'clock) ──
    "SPK1": {"fp": "JST_PH2", "x": CX - 8.5, "y": CY, "rot": 90,
              "part": "JST-PH-2P", "lcsc": "C131337",
              "label": "SPK", "color": "#795548"},

    # ── SW1: tactile switch — right side (3 o'clock) ──
    "SW1": {"fp": "SW_3X4", "x": CX + 10.0, "y": CY, "rot": 90,
             "part": "3x4mm Tact Switch", "lcsc": "C2936178",
             "label": "BTN", "color": "#455a64"},

    # ── LED1: WS2812B-2020 — top (12 o'clock, visible) ──
    "LED1": {"fp": "WS2812B", "x": CX, "y": CY + 11.0, "rot": 0,
              "part": "WS2812B-2020", "lcsc": "C2976072",
              "label": "LED1", "color": "#f9a825"},

    # ── Y1: 32MHz crystal — within 3mm of nRF5340 XC1/XC2 (left side) ──
    "Y1": {"fp": "XTAL_2012", "x": CX - 4.5, "y": CY + 1.0, "rot": 0,
            "part": "32MHz 2012", "lcsc": "C2762297",
            "label": "Y1\n32M", "color": "#546e7a"},

    # ── Y2: 32.768kHz crystal — within 5mm of nRF5340 P0.00/P0.01 ──
    "Y2": {"fp": "XTAL_1610", "x": CX - 4.5, "y": CY - 0.5, "rot": 0,
            "part": "32.768kHz 1610", "lcsc": "C2838510",
            "label": "Y2\n32k", "color": "#546e7a"},

    # ── ANT1: Johanson 2450AT18B100 chip antenna — board edge (1 o'clock) ──
    "ANT1": {"fp": "CHIP_ANT", "x": CX + 5.5, "y": CY + 10.5, "rot": 0,
              "part": "2450AT18B100", "lcsc": "C138386",
              "label": "ANT1\n2.4G", "color": "#00838f"},

    # ── Decoupling / bypass caps ──
    # nRF5340 bypass (DECVDD x4, VDDH, VDD)
    "C1":  {"fp": "0402", "x": CX + 3.5, "y": CY + 3.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C1", "color": "#1a237e"},
    "C2":  {"fp": "0402", "x": CX - 3.5, "y": CY + 3.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C2", "color": "#1a237e"},
    "C3":  {"fp": "0402", "x": CX + 3.5, "y": CY - 3.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C3", "color": "#1a237e"},
    "C4":  {"fp": "0402", "x": CX - 3.5, "y": CY - 3.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C4", "color": "#1a237e"},
    # nRF5340 VDDH bulk cap
    "C5":  {"fp": "0603", "x": CX + 5.0, "y": CY + 0.0, "rot": 90,
             "part": "10uF", "lcsc": "C15849", "label": "C5", "color": "#1a237e"},
    # nRF5340 VDD bulk cap
    "C6":  {"fp": "0402", "x": CX - 5.0, "y": CY + 0.0, "rot": 90,
             "part": "1uF", "lcsc": "C14445", "label": "C6", "color": "#1a237e"},

    # nRF21540 bypass caps (VDD_PA, VDD, VDDIO)
    "C7":  {"fp": "0402", "x": CX + 4.0, "y": CY + 8.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C7", "color": "#1a237e"},
    "C8":  {"fp": "0402", "x": CX + 7.5, "y": CY + 8.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C8", "color": "#1a237e"},
    "C9":  {"fp": "0603", "x": CX + 7.5, "y": CY + 4.5, "rot": 90,
             "part": "4.7uF", "lcsc": "C23733", "label": "C9", "color": "#1a237e"},

    # MAX98357A bypass
    "C10": {"fp": "0402", "x": CX - 4.0, "y": CY - 7.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C10", "color": "#1a237e"},

    # LDO input cap
    "C11": {"fp": "0603", "x": CX - 5.0, "y": CY - 8.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C11", "color": "#1a237e"},
    # LDO output cap
    "C12": {"fp": "0603", "x": CX - 1.0, "y": CY - 8.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C12", "color": "#1a237e"},

    # TP4054 charger caps
    "C13": {"fp": "0402", "x": CX + 5.0, "y": CY - 8.0, "rot": 0,
             "part": "4.7uF", "lcsc": "C23733", "label": "C13", "color": "#1a237e"},

    # Crystal load caps (32MHz) — moved with Y1
    "C14": {"fp": "0402", "x": CX - 5.5, "y": CY + 2.0, "rot": 90,
             "part": "12pF", "lcsc": "C1547", "label": "C14", "color": "#1a237e"},
    "C15": {"fp": "0402", "x": CX - 5.5, "y": CY + 0.0, "rot": 90,
             "part": "12pF", "lcsc": "C1547", "label": "C15", "color": "#1a237e"},

    # nRF21540 RF matching capacitor (antenna port)
    "C16": {"fp": "0402", "x": CX + 7.0, "y": CY + 9.0, "rot": 0,
             "part": "1.5pF", "lcsc": "C1546", "label": "C16", "color": "#1a237e"},

    # nRF5340 DEC1 pin decoupling (required per datasheet Table 13)
    "C_DEC1": {"fp": "0402", "x": CX + 2.0, "y": CY + 4.0, "rot": 0,
                "part": "1uF", "lcsc": "C14445", "label": "DEC1", "color": "#1a237e"},

    # nRF5340 DEC2 pin decoupling (required per datasheet Table 13)
    "C_DEC2": {"fp": "0402", "x": CX - 2.0, "y": CY + 4.0, "rot": 0,
                "part": "100nF", "lcsc": "C1525", "label": "DEC2", "color": "#1a237e"},

    # ── Resistors ──
    # USB CC pull-down (5.1k x2)
    "R1":  {"fp": "0402", "x": CX - 2.0, "y": CY - 11.5, "rot": 0,
             "part": "5.1k", "lcsc": "C25905", "label": "R1", "color": "#5d4037"},
    "R2":  {"fp": "0402", "x": CX + 2.0, "y": CY - 11.5, "rot": 0,
             "part": "5.1k", "lcsc": "C25905", "label": "R2", "color": "#5d4037"},

    # LED data series resistor (330R)
    "R3":  {"fp": "0402", "x": CX - 2.0, "y": CY + 8.0, "rot": 90,
             "part": "330R", "lcsc": "C25104", "label": "R3", "color": "#5d4037"},

    # nRF21540 MODE/TXEN/RXEN pull resistors (10k)
    "R4":  {"fp": "0402", "x": CX + 3.5, "y": CY + 5.5, "rot": 0,
             "part": "10k", "lcsc": "C25744", "label": "R4", "color": "#5d4037"},

    # R5 REMOVED — 33R series resistor in 2.4GHz RF path kills signal.
    # Matching network (L1 + C16) connects directly to chip antenna feed.

    # Button pull-up (10k)
    "R6":  {"fp": "0402", "x": CX + 8.0, "y": CY + 2.0, "rot": 90,
             "part": "10k", "lcsc": "C25744", "label": "R6", "color": "#5d4037"},

    # TP4054 charge current set (4.7k for ~210mA)
    "R7":  {"fp": "0402", "x": CX + 5.0, "y": CY - 10.0, "rot": 90,
             "part": "4.7k", "lcsc": "C25900", "label": "R7", "color": "#5d4037"},

    # nRF21540 RF matching inductor (handled as 0402 passive)
    "L1":  {"fp": "0402", "x": CX + 7.0, "y": CY + 7.5, "rot": 0,
             "part": "3.9nH", "lcsc": "C76851", "label": "L1", "color": "#37474f"},

    # ── SWD debug test pads (1.0mm round, near board edge) ──
    "TP1": {"fp": "TP_1MM", "x": CX - 9.0, "y": CY + 8.0, "rot": 0,
             "part": "Test Pad", "lcsc": "", "label": "SWDIO", "color": "#00695c"},
    "TP2": {"fp": "TP_1MM", "x": CX - 9.0, "y": CY + 6.5, "rot": 0,
             "part": "Test Pad", "lcsc": "", "label": "SWDCLK", "color": "#00695c"},
    "TP3": {"fp": "TP_1MM", "x": CX - 9.0, "y": CY + 5.0, "rot": 0,
             "part": "Test Pad", "lcsc": "", "label": "GND", "color": "#00695c"},
    "TP4": {"fp": "TP_1MM", "x": CX - 9.0, "y": CY + 3.5, "rot": 0,
             "part": "Test Pad", "lcsc": "", "label": "VCC", "color": "#00695c"},
}


# ── Routes (net_name, trace_width, waypoints) ────────────────────────
ROUTES = [
    # USB VBUS -> LDO and Charger
    ("+VBUS",  VBUS_W, [(CX, 2.5), (CX, CY - 8.0)]),
    ("+VBUS",  PWR_W,  [(CX, CY - 8.0), (CX - 3.0, CY - 9.5)]),        # → LDO
    ("+VBUS",  PWR_W,  [(CX, CY - 8.0), (CX + 3.0, CY - 9.5)]),        # → Charger

    # LDO 3.3V output -> nRF5340
    ("+3V3",   PWR_W,  [(CX - 3.0, CY - 9.5), (CX - 3.0, CY - 5.0), (CX, CY)]),

    # 3.3V -> MAX98357A
    ("+3V3",   TRACE_W, [(CX - 3.0, CY - 5.0), (CX - 5.0, CY - 5.5)]),

    # 3.3V -> nRF21540
    ("+3V3",   TRACE_W, [(CX, CY), (CX + 3.5, CY + 3.5), (CX + 5.5, CY + 6.0)]),

    # 3.3V -> LED (still at CY + 11.0)
    ("+3V3",   TRACE_W, [(CX, CY), (CX, CY + 8.0), (CX, CY + 11.0)]),

    # Battery -> Charger
    ("+VBAT",  PWR_W,  [(CX + 6.5, CY - 6.5), (CX + 3.0, CY - 9.5)]),

    # I2S: nRF5340 -> MAX98357A (P0.26=BCLK, P0.27=LRCK, P0.06=DOUT)
    ("I2S_BCK",  TRACE_W, [(CX - 2.0, CY - 3.5), (CX - 3.5, CY - 4.5), (CX - 5.0, CY - 4.8)]),
    ("I2S_WS",   TRACE_W, [(CX - 1.6, CY - 3.5), (CX - 3.0, CY - 4.8), (CX - 5.0, CY - 5.2)]),
    ("I2S_DOUT", TRACE_W, [(CX - 1.2, CY - 3.5), (CX - 2.5, CY - 5.0), (CX - 5.0, CY - 5.6)]),

    # Amp enable (P0.25 -> MAX98357A SD_MODE)
    ("AMP_SD",   TRACE_W, [(CX - 0.8, CY - 3.5), (CX - 2.0, CY - 5.2), (CX - 4.5, CY - 5.5)]),

    # Amp -> Speaker
    ("SPK_OUT",  TRACE_W, [(CX - 5.5, CY - 5.5), (CX - 7.0, CY - 3.0), (CX - 8.5, CY)]),

    # nRF5340 -> nRF21540 control (P0.19=TXEN, P0.20=RXEN, P0.21=MODE)
    ("PA_TXEN",  TRACE_W, [(CX + 3.5, CY + 1.2), (CX + 5.5, CY + 4.0)]),
    ("PA_RXEN",  TRACE_W, [(CX + 3.5, CY + 1.6), (CX + 5.0, CY + 4.5), (CX + 5.5, CY + 5.0)]),
    ("PA_ANT_SEL", TRACE_W, [(CX + 3.5, CY + 2.0), (CX + 4.5, CY + 4.0), (CX + 5.5, CY + 5.5)]),

    # nRF5340 RF -> nRF21540 RF_IN (antenna path, short and direct)
    ("RF_PATH", TRACE_W, [(CX + 3.5, CY + 4.6), (CX + 5.5, CY + 6.0)]),

    # nRF21540 ANT_OUT -> chip antenna (via matching network L1/C16, R5 removed)
    # 1.5mm wide trace for 50-ohm microstrip on 1.0mm FR-4
    ("PA_ANT_L", RF_TRACE_W, [(CX + 7.5, CY + 6.0), (CX + 7.0, CY + 7.5)]),  # ANT_OUT → L1
    ("PA_ANT_C", RF_TRACE_W, [(CX + 7.0, CY + 7.5), (CX + 7.0, CY + 9.0)]),  # L1 → C16
    ("PA_ANT_F", RF_TRACE_W, [(CX + 7.0, CY + 9.0), (CX + 5.5, CY + 10.5)]), # C16 → ANT1 feed (direct, no R5)

    # LED data from nRF5340 (P0.13)
    ("LED_DIN", TRACE_W, [(CX - 3.5, CY + 2.0), (CX - 2.0, CY + 8.0)]),        # → R3
    ("LED_R3",  TRACE_W, [(CX - 2.0, CY + 8.0), (CX - 2.0, CY + 9.0),
                           (CX, CY + 11.0)]),                                   # R3 → LED

    # Button -> nRF5340 (P0.08)
    ("BTN",     TRACE_W, [(CX + 10.0, CY), (CX + 6.0, CY + 1.0), (CX + 3.5, CY + 0.4)]),

    # USB CC pull-downs
    ("CC1",     TRACE_W, [(CX - 2.0, CY - 11.5), (CX - 0.75, 2.5)]),
    ("CC2",     TRACE_W, [(CX + 2.0, CY - 11.5), (CX + 0.75, 2.5)]),

    # Crystal connections (32MHz -> nRF5340 XC1/XC2) — Y1 moved closer
    ("XTAL_32M", TRACE_W, [(CX - 4.5, CY + 1.0), (CX - 3.5, CY + 1.0)]),
    # Crystal connections (32.768kHz -> nRF5340 P0.00/P0.01) — Y2 moved closer
    ("XTAL_32K", TRACE_W, [(CX - 4.5, CY - 0.5), (CX - 3.5, CY - 0.4)]),

    # Crystal load cap connections (moved with Y1)
    ("XC1_CAP", TRACE_W, [(CX - 5.5, CY + 2.0), (CX - 4.5 - 0.7, CY + 1.0)]),  # C14 → Y1 pin1
    ("XC2_CAP", TRACE_W, [(CX - 5.5, CY + 0.0), (CX - 4.5 + 0.7, CY + 1.0)]),  # C15 → Y1 pin2

    # USB D+/D- to nRF5340 USB pins (routed from USB-C J1 to nRF5340)
    ("USB_DP", TRACE_W, [(CX - 0.25, 2.5), (CX - 0.25, CY - 5.0),
                          (CX - 1.5, CY - 3.5)]),   # D+ → nRF5340 USB D+
    ("USB_DN", TRACE_W, [(CX + 0.25, 2.5), (CX + 0.25, CY - 5.0),
                          (CX - 1.0, CY - 3.5)]),   # D- → nRF5340 USB D-

    # SWD debug traces
    ("SWD_IO",  TRACE_W, [(CX - 9.0, CY + 8.0), (CX - 5.0, CY + 6.0),
                           (CX - 3.5, CY + 3.0)]),   # TP1 → nRF5340 SWDIO
    ("SWD_CLK", TRACE_W, [(CX - 9.0, CY + 6.5), (CX - 5.5, CY + 5.0),
                           (CX - 3.5, CY + 2.6)]),   # TP2 → nRF5340 SWDCLK

    # DEC1/DEC2 to nRF5340 DEC pins
    ("DEC1", TRACE_W, [(CX + 2.0, CY + 4.0), (CX + 1.5, CY + 3.5)]),
    ("DEC2", TRACE_W, [(CX - 2.0, CY + 4.0), (CX - 1.5, CY + 3.5)]),
]

# Via positions (GND stitching around the circular board)
VIAS = [
    # nRF5340 thermal pad: 3x3 grid (9 vias, issue #9)
    (CX - 1.5, CY - 1.5), (CX, CY - 1.5), (CX + 1.5, CY - 1.5),
    (CX - 1.5, CY),       (CX, CY),        (CX + 1.5, CY),
    (CX - 1.5, CY + 1.5), (CX, CY + 1.5), (CX + 1.5, CY + 1.5),
    # Mid ring
    (CX - 7, CY), (CX + 7, CY),
    (CX, CY + 7), (CX, CY - 7),
    # Corner ring
    (CX - 4, CY + 4), (CX + 4, CY + 4),
    (CX - 4, CY - 4), (CX + 4, CY - 4),
    # Near nRF21540 thermal pad
    (CX + 4, CY + 6), (CX + 7, CY + 6),
    # Near USB-C GND
    (CX - 3, CY - 10), (CX + 3, CY - 10),
    # Outer ring (stay within circle)
    (CX - 9, CY + 5), (CX + 9, CY + 5),
    (CX - 9, CY - 5), (CX + 9, CY - 5),
    # SWD test pad GND via
    (CX - 9, CY + 5.0),
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
        self.commands.append(
            f"X{self._coord(points[0][0])}Y{self._coord(points[0][1])}D02*")
        for x, y in points[1:]:
            self.commands.append(f"X{self._coord(x)}Y{self._coord(y)}D01*")

    def draw_circle(self, cx, cy, radius, width=0.05, segments=72):
        """Draw a circle outline using line segments."""
        pts = []
        for i in range(segments + 1):
            a = 2 * math.pi * i / segments
            pts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
        self.draw_polyline(pts, width)

    def fill_circle(self, cx, cy, radius, line_width=0.25, keepout_rects=None):
        """Fill a circular region with horizontal lines (copper pour).
        keepout_rects: list of (x_min, y_min, x_max, y_max) rectangles to exclude.
        """
        if keepout_rects is None:
            keepout_rects = []
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
                # Split line segments around keepout zones
                segments = [(x1, x2)]
                for kx1, ky1, kx2, ky2 in keepout_rects:
                    if y < ky1 or y > ky2:
                        continue
                    new_segs = []
                    for sx1, sx2 in segments:
                        if kx2 <= sx1 or kx1 >= sx2:
                            new_segs.append((sx1, sx2))
                        else:
                            if sx1 < kx1:
                                new_segs.append((sx1, kx1))
                            if sx2 > kx2:
                                new_segs.append((kx2, sx2))
                    segments = new_segs
                for sx1, sx2 in segments:
                    if sx2 - sx1 > line_width:
                        self.commands.append(
                            f"X{self._coord(sx1)}Y{self._coord(y)}D02*")
                        self.commands.append(
                            f"X{self._coord(sx2)}Y{self._coord(y)}D01*")
            y += step

    def draw_text(self, x, y, text, char_w=0.8, char_h=1.0, line_w=0.12):
        """Draw simple block text on silkscreen."""
        FONT = {
            'A': [(-1, 0), (-0.3, 1), (0.3, 1), (1, 0), None, (-0.65, 0.5), (0.65, 0.5)],
            'B': [(-1, 0), (-1, 1), (0.5, 1), (1, 0.8), (0.5, 0.5), (-1, 0.5), None,
                  (-1, 0.5), (0.5, 0.5), (1, 0.3), (0.5, 0), (-1, 0)],
            'C': [(1, 0.8), (0.5, 1), (-0.5, 1), (-1, 0.8), (-1, 0.2), (-0.5, 0),
                  (0.5, 0), (1, 0.2)],
            'D': [(-1, 0), (-1, 1), (0.5, 1), (1, 0.7), (1, 0.3), (0.5, 0), (-1, 0)],
            'E': [(1, 1), (-1, 1), (-1, 0.5), (0.5, 0.5), None, (-1, 0.5), (-1, 0), (1, 0)],
            'F': [(1, 1), (-1, 1), (-1, 0.5), (0.5, 0.5), None, (-1, 0.5), (-1, 0)],
            'G': [(1, 0.8), (0.5, 1), (-0.5, 1), (-1, 0.8), (-1, 0.2), (-0.5, 0),
                  (0.5, 0), (1, 0.3), (1, 0.5), (0.3, 0.5)],
            'H': [(-1, 0), (-1, 1), None, (-1, 0.5), (1, 0.5), None, (1, 0), (1, 1)],
            'I': [(-0.3, 1), (0.3, 1), None, (0, 1), (0, 0), None, (-0.3, 0), (0.3, 0)],
            'K': [(-1, 0), (-1, 1), None, (-1, 0.5), (1, 1), None, (-1, 0.5), (1, 0)],
            'L': [(-1, 1), (-1, 0), (1, 0)],
            'M': [(-1, 0), (-1, 1), (0, 0.5), (1, 1), (1, 0)],
            'N': [(-1, 0), (-1, 1), (1, 0), (1, 1)],
            'O': [(-0.5, 0), (-1, 0.3), (-1, 0.7), (-0.5, 1), (0.5, 1), (1, 0.7),
                  (1, 0.3), (0.5, 0), (-0.5, 0)],
            'P': [(-1, 0), (-1, 1), (0.5, 1), (1, 0.8), (1, 0.6), (0.5, 0.5), (-1, 0.5)],
            'R': [(-1, 0), (-1, 1), (0.5, 1), (1, 0.8), (1, 0.6), (0.5, 0.5), (-1, 0.5),
                  None, (0, 0.5), (1, 0)],
            'S': [(1, 0.8), (0.5, 1), (-0.5, 1), (-1, 0.8), (-1, 0.6), (1, 0.4),
                  (1, 0.2), (0.5, 0), (-0.5, 0), (-1, 0.2)],
            'T': [(-1, 1), (1, 1), None, (0, 1), (0, 0)],
            'U': [(-1, 1), (-1, 0.2), (-0.5, 0), (0.5, 0), (1, 0.2), (1, 1)],
            'V': [(-1, 1), (0, 0), (1, 1)],
            'W': [(-1, 1), (-0.5, 0), (0, 0.5), (0.5, 0), (1, 1)],
            'X': [(-1, 1), (1, 0), None, (-1, 0), (1, 1)],
            'Y': [(-1, 1), (0, 0.5), (1, 1), None, (0, 0.5), (0, 0)],
            'Z': [(-1, 1), (1, 1), (-1, 0), (1, 0)],
            ' ': [],
            '-': [(-0.5, 0.5), (0.5, 0.5)],
            '.': [(0, 0), (0, 0.1)],
            '0': [(-0.5, 0), (-1, 0.3), (-1, 0.7), (-0.5, 1), (0.5, 1), (1, 0.7),
                  (1, 0.3), (0.5, 0), (-0.5, 0)],
            '1': [(-0.3, 0.8), (0, 1), (0, 0), None, (-0.3, 0), (0.3, 0)],
            '2': [(-1, 0.8), (-0.5, 1), (0.5, 1), (1, 0.7), (1, 0.5), (-1, 0), (1, 0)],
            '3': [(-1, 0.8), (-0.5, 1), (0.5, 1), (1, 0.7), (0.5, 0.5), None,
                  (0.5, 0.5), (1, 0.3), (0.5, 0), (-0.5, 0), (-1, 0.2)],
            '4': [(-1, 1), (-1, 0.5), (1, 0.5), None, (0.5, 1), (0.5, 0)],
            '5': [(1, 1), (-1, 1), (-1, 0.5), (0.5, 0.5), (1, 0.3), (0.5, 0),
                  (-0.5, 0), (-1, 0.2)],
            '8': [(-0.5, 0.5), (-1, 0.7), (-0.5, 1), (0.5, 1), (1, 0.7), (0.5, 0.5),
                  (-0.5, 0.5), (-1, 0.3), (-0.5, 0), (0.5, 0), (1, 0.3), (0.5, 0.5)],
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
                    self.commands.append(
                        f"X{self._coord(gx)}Y{self._coord(gy)}D02*")
                    seg_start = False
                else:
                    self.commands.append(
                        f"X{self._coord(gx)}Y{self._coord(gy)}D01*")
            cx += char_w

    def write(self, filepath):
        with open(filepath, 'w', newline='\n') as f:
            f.write(f"G04 Koe COIN Lite v2 -- Generated by gen_coin_lite_v2.py*\n")
            f.write(f"G04 Layer: {self.layer_name}*\n")
            f.write("G04 Date: 2026-04-10*\n")
            if self.layer_function:
                f.write(f"%TF.FileFunction,{self.layer_function}*%\n")
            f.write("%TF.GenerationSoftware,KoeDevice,gen_coin_lite_v2.py,2.0*%\n")
            f.write("%TF.SameCoordinates,Original*%\n")
            f.write("%FSLAX36Y36*%\n")
            f.write("%MOMM*%\n")
            f.write("%LPD*%\n")
            for (shape, params), dcode in sorted(
                    self.apertures.items(), key=lambda x: x[1]):
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
            f.write("; Koe COIN Lite v2 -- 28mm round nRF5340 + nRF21540\n")
            f.write("; Generated by gen_coin_lite_v2.py\n")
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


# _draw_ifa_antenna REMOVED — replaced with Johanson 2450AT18B100 chip antenna.
# The chip antenna is placed as component ANT1 with standard SMD pads.
# No special trace drawing needed; the RF feed trace is in the ROUTES list.


# ── Main generation ──────────────────────────────────────────────────

def generate_all():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    f_cu = GerberWriter("F.Cu", "Copper,L1,Top")
    b_cu = GerberWriter("B.Cu", "Copper,L2,Bot")
    f_mask = GerberWriter("F.Mask", "Soldermask,Top")
    b_mask = GerberWriter("B.Mask", "Soldermask,Bot")
    f_paste = GerberWriter("F.Paste", "Paste,Top")
    f_silk = GerberWriter("F.SilkS", "Legend,Top")
    edge = GerberWriter("Edge.Cuts", "Profile,NP")
    drill = DrillWriter()

    # ── Board outline (Edge.Cuts) -- circular 28mm ──
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

        # Pin 1 indicator for ICs
        if ref.startswith("U"):
            dot_x, dot_y = xform(-hw + 0.5, -hh + 0.5, cx, cy, rot)
            f_silk.flash_circle(dot_x, dot_y, 0.3)

        # Reference designator on silkscreen
        f_silk.draw_text(cx - len(ref) * 0.35, cy - sh / 2 - 1.2, ref,
                         char_w=0.6, char_h=0.8, line_w=0.1)

        # Pads on F.Cu + F.Mask + F.Paste
        is_qfn_epad = False
        for pad_data in fp["pads"]:
            pin, px, py, pw, ph = pad_data
            ax, ay = xform(px, py, cx, cy, rot)
            rpw, rph = pw, ph
            if rot in (90, 270):
                rpw, rph = ph, pw

            f_cu.flash_pad(ax, ay, rpw, rph)
            f_mask.flash_pad(ax, ay, rpw + MASK_EXP * 2, rph + MASK_EXP * 2)

            # F.Paste: solder paste stencil apertures
            # For QFN exposed pads (large central pad), use windowed pattern
            # to prevent solder voids during reflow
            is_qfn_epad = (ref.startswith("U") and pin == len(fp["pads"])
                           and pw >= 2.0 and ph >= 2.0)
            if is_qfn_epad:
                # Windowed paste pattern: grid of smaller rectangles
                # For nRF5340 (5x5mm epad): 4x4 grid of 0.9mm squares, 0.35mm gaps
                # For smaller QFN epads: 2x2 grid
                if pw >= 4.0:
                    # Large epad (nRF5340): 4x4 grid
                    n_grid = 4
                    sq_size = 0.9
                    gap = (pw - n_grid * sq_size) / (n_grid + 1)
                    for gi in range(n_grid):
                        for gj in range(n_grid):
                            gpx = ax - pw / 2 + gap + sq_size / 2 + gi * (sq_size + gap)
                            gpy = ay - ph / 2 + gap + sq_size / 2 + gj * (sq_size + gap)
                            f_paste.flash_pad(gpx, gpy, sq_size, sq_size)
                else:
                    # Smaller epad: 2x2 grid
                    n_grid = 2
                    sq_size = pw * 0.35
                    gap = (pw - n_grid * sq_size) / (n_grid + 1)
                    for gi in range(n_grid):
                        for gj in range(n_grid):
                            gpx = ax - pw / 2 + gap + sq_size / 2 + gi * (sq_size + gap)
                            gpy = ay - ph / 2 + gap + sq_size / 2 + gj * (sq_size + gap)
                            f_paste.flash_pad(gpx, gpy, sq_size, sq_size)
            else:
                # Regular SMT pads: paste aperture 0.05mm smaller per side
                paste_w = max(rpw - 0.1, 0.15)
                paste_h = max(rph - 0.1, 0.15)
                f_paste.flash_pad(ax, ay, paste_w, paste_h)

    # ── Chip antenna ANT1 is placed as a regular SMD component above ──
    # No special trace drawing needed; RF feed routed via ROUTES.

    # ── Signal traces on F.Cu ──
    for net_name, width, waypoints in ROUTES:
        for i in range(len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]
            f_cu.draw_line(x1, y1, x2, y2, width)

    # ── Vias ──
    for vx, vy in VIAS:
        # Check via is inside the board circle with margin
        dist = math.sqrt((vx - BOARD_CX) ** 2 + (vy - BOARD_CY) ** 2)
        if dist > BOARD_RADIUS - 1.0:
            continue
        f_cu.flash_circle(vx, vy, VIA_PAD)
        b_cu.flash_circle(vx, vy, VIA_PAD)
        f_mask.flash_circle(vx, vy, VIA_PAD + VIA_ANNULAR)
        b_mask.flash_circle(vx, vy, VIA_PAD + VIA_ANNULAR)
        drill.add_hole(vx, vy, VIA_DRILL)

    # ── Back copper: GND pour (circular) with antenna keepout zone ──
    # Keepout rectangle under ANT1: at least 3mm x 5mm clearance zone (issue #2)
    ant1 = PARTS["ANT1"]
    ant_keepout = [(ant1["x"] - 2.5, ant1["y"] - 1.5,
                    ant1["x"] + 2.5, ant1["y"] + 3.5)]
    pour_r = BOARD_RADIUS - POUR_MARGIN
    b_cu.fill_circle(BOARD_CX, BOARD_CY, pour_r, 0.25, keepout_rects=ant_keepout)

    # ── Silkscreen: board name and version ──
    f_silk.draw_text(CX - 4.0, CY + 8.5, "COIN V2", char_w=0.7, char_h=0.9, line_w=0.12)
    f_silk.draw_text(CX - 2.5, CY - 11.0, "28MM", char_w=0.5, char_h=0.7, line_w=0.1)

    # ── Write all Gerber files ──
    layer_files = [
        ("F_Cu", f_cu),
        ("B_Cu", b_cu),
        ("F_Mask", f_mask),
        ("B_Mask", b_mask),
        ("F_Paste", f_paste),
        ("F_SilkS", f_silk),
        ("Edge_Cuts", edge),
    ]

    written_files = []
    for suffix, writer in layer_files:
        filepath = OUT_DIR / f"{PREFIX}-{suffix}.gbr"
        writer.write(filepath)
        written_files.append(filepath)
        print(f"  Gerber: {filepath.name} "
              f"({len(writer.commands)} cmds, {len(writer.apertures)} apertures)")

    drill_path = OUT_DIR / f"{PREFIX}.drl"
    drill.write(drill_path)
    written_files.append(drill_path)
    print(f"  Drill:  {drill_path.name} "
          f"({len(drill.holes)} holes, {len(drill.tools)} tools)")

    # ── BOM CSV (JLCPCB format) ──
    bom_path = OUT_DIR / f"BOM-JLCPCB.csv"
    _generate_bom(bom_path)
    written_files.append(bom_path)
    print(f"  BOM:    {bom_path.name}")

    # ── CPL CSV (JLCPCB format) ──
    cpl_path = OUT_DIR / f"CPL-JLCPCB.csv"
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
    """Generate BOM in JLCPCB format with LCSC part numbers."""
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
        for (part, fp_name, lcsc), refs in sorted(
                groups.items(), key=lambda x: x[1][0]):
            writer.writerow([part, " ".join(refs), fp_name, lcsc])


def _generate_cpl(filepath):
    """Generate CPL (Component Placement List) in JLCPCB format."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Rotation", "Layer"])
        for ref, comp in sorted(PARTS.items()):
            lcsc = comp.get("lcsc", "")
            if not lcsc:
                continue
            rot = comp.get("rot", 0) % 360
            writer.writerow([
                ref,
                f"{comp['x']:.2f}mm",
                f"{comp['y']:.2f}mm",
                rot,
                "Top",
            ])


# ── Layout SVG Generator ────────────────────────────────────────────
def gen_svg():
    """Generate a visual layout SVG for review."""
    S = 14  # scale factor px/mm
    pad = 60
    board_px = int(BOARD_DIAMETER * S)
    img_w = board_px + pad * 2
    img_h = board_px + pad * 2 + 200  # extra for legend
    ox = pad + board_px // 2  # SVG center X of board
    oy = pad + board_px // 2 + 20  # SVG center Y of board

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{img_w}" height="{img_h}">
<defs>
  <linearGradient id="pcb" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#0d5c0d"/><stop offset="100%" stop-color="#063806"/>
  </linearGradient>
  <filter id="sh"><feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.4"/></filter>
  <clipPath id="board-clip"><circle cx="{ox}" cy="{oy}" r="{BOARD_RADIUS * S}"/></clipPath>
</defs>
<rect width="{img_w}" height="{img_h}" fill="#0d0d14"/>

<!-- Title -->
<text x="{img_w // 2}" y="18" text-anchor="middle" fill="#e0e0e0"
  font-family="Helvetica,sans-serif" font-size="15" font-weight="600">
  Koe COIN Lite v2 -- nRF5340 + nRF21540 PA/LNA (1km BLE)</text>
<text x="{img_w // 2}" y="36" text-anchor="middle" fill="#888"
  font-family="sans-serif" font-size="10">
  28mm round | 2-layer FR-4 1.0mm | BLE 5.4 | MAX98357A Amp | USB-C 16P data+charge</text>

<!-- Board circle -->
<circle cx="{ox}" cy="{oy}" r="{BOARD_RADIUS * S + 2}" fill="#000" opacity="0.3"/>
<circle cx="{ox}" cy="{oy}" r="{BOARD_RADIUS * S}" fill="url(#pcb)"
  stroke="#c8a83e" stroke-width="1.5"/>

<!-- GND pour hint -->
<circle cx="{ox}" cy="{oy}" r="{(BOARD_RADIUS - POUR_MARGIN) * S}"
  fill="none" stroke="#1a5c1a" stroke-width="0.5" stroke-dasharray="4,4"/>
'''

    def bx(x):
        """Board X to SVG X."""
        return ox + (x - BOARD_CX) * S

    def by(y):
        """Board Y to SVG Y."""
        return oy + (y - BOARD_CY) * S

    # Traces
    net_colors = {
        "VBUS": "#ef5350", "VBAT": "#ff7043", "3V3": "#66bb6a",
        "I2S": "#42a5f5", "LED": "#f9a825", "SPK": "#ff8a65",
        "AMP": "#ff8a65", "CC": "#78909c", "BTN": "#78909c",
        "XTAL": "#78909c", "PA_": "#e91e63", "RF_": "#e91e63",
        "XC": "#78909c",
    }
    for net, w, pts in ROUTES:
        c = "#78909c"
        for k, v in net_colors.items():
            if k in net:
                c = v
                break
        for i in range(len(pts) - 1):
            svg += (f'<line x1="{bx(pts[i][0])}" y1="{by(pts[i][1])}" '
                    f'x2="{bx(pts[i + 1][0])}" y2="{by(pts[i + 1][1])}" '
                    f'stroke="{c}" stroke-width="{max(1.5, w * S * 0.4)}" '
                    f'opacity="0.35" stroke-linecap="round"/>\n')

    # Vias
    for vx_, vy_ in VIAS:
        dist = math.sqrt((vx_ - BOARD_CX) ** 2 + (vy_ - BOARD_CY) ** 2)
        if dist > BOARD_RADIUS - 1.0:
            continue
        svg += (f'<circle cx="{bx(vx_)}" cy="{by(vy_)}" '
                f'r="{VIA_PAD * S / 2 + 1}" fill="#1a1a1a" '
                f'stroke="#666" stroke-width="0.5"/>\n')

    # Components
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]
        cx_, cy_ = c["x"], c["y"]
        rot = c.get("rot", 0)
        sw, sh = fp["size"]
        color = c.get("color", "#5d4037")
        sx, sy = bx(cx_), by(cy_)
        rw, rh = sw * S, sh * S

        svg += f'<g transform="translate({sx},{sy}) rotate({rot})" filter="url(#sh)">\n'
        # Pads
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            svg += (f'<rect x="{px * S - pw * S / 2}" y="{py * S - ph * S / 2}" '
                    f'width="{pw * S}" height="{ph * S}" '
                    f'fill="#c8a83e" rx="0.3" opacity="0.45"/>\n')
        # Component body
        rx = 3 if ref[0] in "UJ" else 1
        svg += (f'<rect x="{-rw / 2}" y="{-rh / 2}" width="{rw}" height="{rh}" '
                f'fill="{color}" stroke="#777" stroke-width="0.5" rx="{rx}"/>\n')
        # Pin 1 dot for ICs
        if ref[0] == "U":
            svg += (f'<circle cx="{-rw / 2 + 4}" cy="{-rh / 2 + 4}" r="1.5" '
                    f'fill="#aaa" opacity="0.4"/>\n')
        # Label
        label = c.get("label", ref)
        lines = label.split('\n')
        for li, line in enumerate(lines):
            fy = 4 + (li - len(lines) / 2) * 10
            fs = 5 if ref[0] in "RCLY" else 7
            if ref.startswith("LED") or ref == "SW1" or ref == "ANT":
                fs = 6
            svg += (f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" '
                    f'font-family="monospace" font-size="{fs}">{line}</text>\n')
        svg += '</g>\n'

    # Antenna keepout zone visualization (dashed rectangle on back copper)
    ant1 = PARTS["ANT1"]
    kx1, ky1 = bx(ant1["x"] - 2.5), by(ant1["y"] - 1.5)
    kx2, ky2 = bx(ant1["x"] + 2.5), by(ant1["y"] + 3.5)
    svg += (f'<rect x="{kx1}" y="{min(ky1,ky2)}" '
            f'width="{abs(kx2-kx1)}" height="{abs(ky2-ky1)}" '
            f'fill="none" stroke="#ff5252" stroke-width="1" '
            f'stroke-dasharray="3,2" opacity="0.6"/>\n')
    svg += (f'<text x="{(kx1+kx2)/2}" y="{min(ky1,ky2)-3}" text-anchor="middle" '
            f'fill="#ff5252" font-family="monospace" font-size="5">GND KEEPOUT</text>\n')

    # Legend
    ly = oy + BOARD_RADIUS * S + 30
    svg += (f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" '
            f'font-family="monospace" font-size="9">'
            f'28mm round | 2-layer | {len(PARTS)} parts | '
            f'nRF5340 BLE 5.4 + nRF21540 PA/LNA 1km</text>\n')

    # Signal flow
    ly += 22
    flow_items = [
        ("nRF5340", "#0d47a1"), ("I2S", "#42a5f5"),
        ("MAX98357A", "#b71c1c"), ("Speaker", "#795548"),
    ]
    total_w = sum(len(t) * 6.5 + 20 for t, _ in flow_items)
    fx = (img_w - total_w) / 2
    for i, (text, col) in enumerate(flow_items):
        tw = len(text) * 6.5 + 10
        svg += (f'<rect x="{fx}" y="{ly - 10}" width="{tw}" height="16" '
                f'fill="{col}" rx="3" opacity="0.7"/>\n')
        svg += (f'<text x="{fx + tw / 2}" y="{ly + 2}" text-anchor="middle" '
                f'fill="#eee" font-family="monospace" font-size="8">{text}</text>\n')
        fx += tw + 5
        if i < len(flow_items) - 1:
            svg += (f'<text x="{fx - 2}" y="{ly + 2}" text-anchor="middle" '
                    f'fill="#888" font-family="monospace" font-size="10">'
                    f'&#8594;</text>\n')

    # RF flow
    ly += 24
    rf_items = [
        ("nRF5340", "#0d47a1"), ("nRF21540", "#880e4f"),
        ("Chip Ant", "#00838f"), ("1km BLE", "#00838f"),
    ]
    total_w = sum(len(t) * 6.5 + 20 for t, _ in rf_items)
    fx = (img_w - total_w) / 2
    for i, (text, col) in enumerate(rf_items):
        tw = len(text) * 6.5 + 10
        svg += (f'<rect x="{fx}" y="{ly - 10}" width="{tw}" height="16" '
                f'fill="{col}" rx="3" opacity="0.7"/>\n')
        svg += (f'<text x="{fx + tw / 2}" y="{ly + 2}" text-anchor="middle" '
                f'fill="#eee" font-family="monospace" font-size="8">{text}</text>\n')
        fx += tw + 5
        if i < len(rf_items) - 1:
            svg += (f'<text x="{fx - 2}" y="{ly + 2}" text-anchor="middle" '
                    f'fill="#888" font-family="monospace" font-size="10">'
                    f'&#8594;</text>\n')

    # Power flow
    ly += 28
    svg += (f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#ef5350" '
            f'font-family="monospace" font-size="9" font-weight="bold">'
            f'USB-C 5V &#8594; TP4054 (LiPo CHG) + AP2112K (3.3V LDO) '
            f'&#8594; nRF5340 + nRF21540 + MAX98357A</text>\n')

    ly += 18
    svg += (f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#c8a83e" '
            f'font-family="monospace" font-size="8">'
            f'nRF21540 PA/LNA: +20dBm TX / -95dBm RX sensitivity = 1km outdoor BLE range'
            f'</text>\n')

    svg += '</svg>\n'
    path = OUT_DIR / f"{PREFIX}-layout.svg"
    path.write_text(svg)
    print(f"  SVG:    {path.name}")


# ── DRC (Design Rule Check) ──────────────────────────────────────────
def run_drc():
    """Check all components are within the 28mm circular board."""
    errors = []
    warnings = []

    for ref, comp in PARTS.items():
        fp = FP[comp["fp"]]
        cx, cy = comp["x"], comp["y"]
        rot = comp.get("rot", 0)
        sw, sh = fp["size"]

        # Check all corners of component body
        hw, hh = sw / 2, sh / 2
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        for dx, dy in corners:
            ax, ay = xform(dx, dy, cx, cy, rot)
            dist = math.sqrt((ax - BOARD_CX) ** 2 + (ay - BOARD_CY) ** 2)
            if dist > BOARD_RADIUS:
                errors.append(
                    f"  {ref} corner ({ax:.1f},{ay:.1f}) is {dist:.1f}mm "
                    f"from center (>{BOARD_RADIUS}mm radius) -- OUTSIDE BOARD!")
            elif dist > BOARD_RADIUS - 0.5:
                warnings.append(
                    f"  {ref} corner ({ax:.1f},{ay:.1f}) is {dist:.1f}mm "
                    f"from center -- very close to edge (margin <0.5mm)")

        # Check all pad positions
        for pad_data in fp["pads"]:
            pin, px, py, pw, ph = pad_data
            ax, ay = xform(px, py, cx, cy, rot)
            dist = math.sqrt((ax - BOARD_CX) ** 2 + (ay - BOARD_CY) ** 2)
            pad_extent = max(pw, ph) / 2
            if dist + pad_extent > BOARD_RADIUS:
                errors.append(
                    f"  {ref} pad {pin} at ({ax:.1f},{ay:.1f}) extends "
                    f"beyond board edge!")

    # Check component-to-component spacing
    refs = list(PARTS.keys())
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            r1, r2 = refs[i], refs[j]
            c1, c2 = PARTS[r1], PARTS[r2]
            fp1, fp2 = FP[c1["fp"]], FP[c2["fp"]]
            dx = c1["x"] - c2["x"]
            dy = c1["y"] - c2["y"]
            dist = math.sqrt(dx * dx + dy * dy)
            min_dist = (max(fp1["size"]) + max(fp2["size"])) / 2 * 0.6
            if dist < min_dist and r1[0] != "C" and r2[0] != "C" \
                    and r1[0] != "R" and r2[0] != "R" and r1[0] != "L" and r2[0] != "L":
                warnings.append(
                    f"  {r1} and {r2} are {dist:.1f}mm apart "
                    f"(min recommended: {min_dist:.1f}mm)")

    return errors, warnings


# ── Gerber Validation ─────────────────────────────────────────────────
def validate_gerbers():
    """Validate generated Gerber files for correctness."""
    errors = []
    warnings = []

    for gbr_file in OUT_DIR.glob("*.gbr"):
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

    drl_file = OUT_DIR / f"{PREFIX}.drl"
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

    required = ["F_Cu", "B_Cu", "F_Mask", "B_Mask", "F_Paste", "F_SilkS", "Edge_Cuts"]
    for layer in required:
        if not (OUT_DIR / f"{PREFIX}-{layer}.gbr").exists():
            errors.append(f"Missing required layer: {layer}")

    return errors, warnings


# ── Main ──────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("Koe COIN Lite v2 -- 28mm Round PCB Generator")
    print(f"  Board:  {BOARD_DIAMETER}mm diameter round, 2-layer FR-4, 1.0mm")
    print(f"  MCU:    nRF5340-QKAA-R7 (BLE 5.4, dual-core Cortex-M33)")
    print(f"  PA/LNA: nRF21540-QFAA-R (+20dBm TX, 1km BLE range)")
    print(f"  Ant:    Johanson 2450AT18B100 ceramic chip antenna")
    print(f"  Amp:    MAX98357AETE+T (I2S Class-D)")
    print(f"  USB:    USB-C 16P (D+/D- connected)")
    print(f"  Power:  AP2112K-3.3 LDO + TP4054 LiPo charger")
    print(f"  Parts:  {len(PARTS)} components")
    print(f"  Traces: {len(ROUTES)} routes")
    print(f"  Vias:   {len(VIAS)} positions")
    print(f"  Output: {OUT_DIR}")
    print("=" * 70)

    # DRC check (component placement)
    print("\nRunning DRC (component placement)...")
    drc_errors, drc_warnings = run_drc()
    if drc_warnings:
        print(f"  Warnings ({len(drc_warnings)}):")
        for w in drc_warnings:
            print(f"    {w}")
    if drc_errors:
        print(f"  ERRORS ({len(drc_errors)}):")
        for e in drc_errors:
            print(f"    ! {e}")
        print("\n  DRC FAILED. Fix placement before generating Gerbers.")
        return 1
    else:
        print(f"  DRC passed: All {len(PARTS)} components within "
              f"{BOARD_DIAMETER}mm circle.")

    # Generate files
    print("\nGenerating manufacturing files...")
    files, zip_path = generate_all()

    # Generate SVG layout
    print("\nGenerating layout SVG...")
    gen_svg()

    # Validate Gerber files
    print("\nValidating Gerber files...")
    val_errors, val_warnings = validate_gerbers()
    if val_warnings:
        print(f"  Warnings ({len(val_warnings)}):")
        for w in val_warnings:
            print(f"    - {w}")
    if val_errors:
        print(f"  ERRORS ({len(val_errors)}):")
        for e in val_errors:
            print(f"    ! {e}")
        print("\n  Validation FAILED.")
        return 1
    else:
        print("  All Gerber validation checks passed.")

    # Summary
    print("\n" + "=" * 70)
    print("Output files:")
    for f in sorted(OUT_DIR.iterdir()):
        print(f"  {f.name:50s} {f.stat().st_size:>8,} bytes")

    print(f"\nJLCPCB upload: {zip_path.name}")
    print("  1. Go to https://www.jlcpcb.com/")
    print("  2. Click 'Order Now' -> 'Add gerber file'")
    print(f"  3. Upload {zip_path.name}")
    print("  4. Select 2 layers, 1.0mm thickness, HASL finish")
    print("  5. For assembly: upload BOM-JLCPCB.csv + CPL-JLCPCB.csv")
    print("  6. Board shape: round 28mm diameter")

    print(f"\nKey upgrade from COIN Lite v1:")
    print(f"  ESP32-C3 (WiFi only, 10m) -> nRF5340 + nRF21540 (BLE 5.4, 1km)")
    print(f"  26mm -> 28mm (room for QFN-94 + PA/LNA)")
    print(f"  nRF21540: +20dBm TX power, -95dBm RX sensitivity")
    print(f"\nv2 hardware fixes applied:")
    print(f"  [1] Chip antenna (Johanson 2450AT18B100) replaces IFA trace")
    print(f"  [2] GND keepout zone under ANT1 on back copper")
    print(f"  [3] F_Paste Gerber layer with windowed QFN paste pattern")
    print(f"  [4] R5 (33R) removed from RF path")
    print(f"  [5] DEC1 (1uF) + DEC2 (100nF) decoupling caps added")
    print(f"  [6] 1.5mm RF trace width for 50-ohm on 1.0mm FR-4")
    print(f"  [7] Y2 (32.768kHz) moved within 5mm of nRF5340")
    print(f"  [8] Y1 (32MHz) moved within 3mm of nRF5340 XC1/XC2")
    print(f"  [9] 3x3 thermal via grid (9 vias) under nRF5340")
    print(f"  [10] SWD debug pads: TP1=SWDIO, TP2=SWDCLK, TP3=GND, TP4=VCC")
    print(f"  [11] USB-C 16P with D+/D- routed to nRF5340")
    print(f"  [12] QFN-94 pad width increased from 0.2mm to 0.3mm")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
