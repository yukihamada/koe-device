#!/usr/bin/env python3
"""
Koe Pro v2 — Production Gerber Generator (JLCPCB-ready)
========================================================
Generates RS-274X Gerber files, Excellon drill file, BOM/CPL CSVs,
and a ZIP archive ready for JLCPCB upload.

Board: 45x30mm, 4-layer FR-4
MCU:   nRF5340-QKAA (QFN-94, BLE 5.3)
UWB:   DW3000 (QFN-48, sub-us sync)
ADC:   AK5720VT (SSOP-16, 24-bit)
DAC:   PCM5102APWR (TSSOP-20, 32-bit)
Amp:   MAX98357AETE+T (QFN-16)
PMIC:  nPM1300-QEAA-R7 (QFN-32)

Usage:
    python3 hardware/generate_gerbers.py
"""

import math
import zipfile
import csv
import io
from pathlib import Path

# ── Board parameters ──────────────────────────────────────────────────
BOARD_W = 45.0   # mm
BOARD_H = 30.0   # mm
CORNER_R = 1.0   # mm radius for rounded corners
CORNER_SEGS = 8  # arc segments per corner

TRACE_W = 0.15   # signal trace width (mm)
PWR_W = 0.4      # power trace width (mm)
VBUS_W = 0.5     # USB VBUS trace width (mm)
VIA_DRILL = 0.3  # via drill diameter (mm)
VIA_PAD = 0.5    # via pad diameter (mm)
VIA_ANNULAR = 0.1  # mask opening expansion (mm)
MASK_EXP = 0.05  # solder mask expansion per side (mm)
POUR_CLEARANCE = 0.3  # clearance around vias in copper pour (mm)
POUR_MARGIN = 0.5     # pour inset from board edge (mm)

OUT_DIR = Path(__file__).resolve().parent.parent / "manufacturing" / "gerbers" / "koe-pro-v2-production"
PREFIX = "koe-pro-v2"


# ── Footprint library ────────────────────────────────────────────────
def _qfn_pads(n_left, n_bottom, n_right, n_top, pitch, body_half,
              pad_w, pad_h, epad_w, epad_h):
    """Generic QFN pad generator. Returns list of (pin, x, y, w, h)."""
    pads = []
    pin = 1
    # Left side (top to bottom)
    start_y = -(n_left - 1) * pitch / 2
    for i in range(n_left):
        pads.append((pin, -body_half, start_y + i * pitch, pad_w, pad_h))
        pin += 1
    # Bottom side (left to right)
    start_x = -(n_bottom - 1) * pitch / 2
    for i in range(n_bottom):
        pads.append((pin, start_x + i * pitch, body_half, pad_h, pad_w))
        pin += 1
    # Right side (bottom to top)
    start_y = (n_right - 1) * pitch / 2
    for i in range(n_right):
        pads.append((pin, body_half, start_y - i * pitch, pad_w, pad_h))
        pin += 1
    # Top side (right to left)
    start_x = (n_top - 1) * pitch / 2
    for i in range(n_top):
        pads.append((pin, start_x - i * pitch, -body_half, pad_h, pad_w))
        pin += 1
    # Exposed thermal pad
    pads.append((pin, 0, 0, epad_w, epad_h))
    return pads


def _ssop_pads(n_per_side, pitch, body_half_x, pad_w, pad_h):
    """SSOP/TSSOP pad generator."""
    pads = []
    start_y = -(n_per_side - 1) * pitch / 2
    for i in range(n_per_side):
        pads.append((i + 1, -body_half_x, start_y + i * pitch, pad_w, pad_h))
    for i in range(n_per_side):
        pads.append((n_per_side + i + 1, body_half_x, start_y + i * pitch, pad_w, pad_h))
    return pads


FP = {}

# nRF5340-QKAA: QFN-94, 7x7mm, 0.4mm pitch (24+23+24+23 + epad)
FP["NRF5340"] = {
    "pads": _qfn_pads(24, 23, 24, 23, 0.4, 3.5, 0.2, 0.7, 5.0, 5.0),
    "size": (7.0, 7.0),
    "silk_margin": 0.25,
}

# DW3000: QFN-48, 6x6mm, 0.5mm pitch (12 per side)
FP["DW3000"] = {
    "pads": _qfn_pads(12, 12, 12, 12, 0.5, 3.0, 0.25, 0.8, 4.0, 4.0),
    "size": (6.0, 6.0),
    "silk_margin": 0.25,
}

# AK5720: SSOP-16, 5.3x6.2mm, 0.65mm pitch
FP["AK5720"] = {
    "pads": _ssop_pads(8, 0.65, 2.65, 0.4, 1.5),
    "size": (5.3, 6.2),
    "silk_margin": 0.2,
}

# PCM5102A: TSSOP-20, 4.4x6.5mm, 0.65mm pitch
FP["PCM5102A"] = {
    "pads": _ssop_pads(10, 0.65, 2.2, 0.4, 1.5),
    "size": (4.4, 6.5),
    "silk_margin": 0.2,
}

# MAX98357A: QFN-16, 3x3mm, 0.5mm pitch (4 per side)
FP["MAX98357"] = {
    "pads": _qfn_pads(4, 4, 4, 4, 0.5, 1.5, 0.25, 0.5, 1.7, 1.7),
    "size": (3.0, 3.0),
    "silk_margin": 0.25,
}

# nPM1300: QFN-32, 5x5mm, 0.5mm pitch (8 per side)
FP["NPM1300"] = {
    "pads": _qfn_pads(8, 8, 8, 8, 0.5, 2.5, 0.25, 0.7, 3.35, 3.35),
    "size": (5.0, 5.0),
    "silk_margin": 0.25,
}

# Crystals
FP["XTAL_2012"] = {
    "pads": [(1, -0.7, 0, 0.5, 0.9), (2, 0.7, 0, 0.5, 0.9)],
    "size": (2.0, 1.2),
}
FP["XTAL_1610"] = {
    "pads": [(1, -0.55, 0, 0.4, 0.7), (2, 0.55, 0, 0.4, 0.7)],
    "size": (1.6, 1.0),
}

# USB-C 16-pin mid-mount
FP["USBC"] = {
    "pads": [
        ("V1", -2.75, -1.0, 0.6, 1.2), ("V2", 2.75, -1.0, 0.6, 1.2),
        ("D-", -0.25, -1.0, 0.3, 1.0), ("D+", 0.25, -1.0, 0.3, 1.0),
        ("C1", -1.75, -1.0, 0.3, 1.0), ("C2", 1.75, -1.0, 0.3, 1.0),
        ("G1", -3.5, -1.0, 0.5, 1.0), ("G2", 3.5, -1.0, 0.5, 1.0),
        ("S1", -4.15, 0.5, 0.6, 1.6), ("S2", 4.15, 0.5, 0.6, 1.6),
    ],
    "size": (9.0, 3.5),
}

# 3.5mm TRS jack (PJ-320A, through-hole pads)
FP["TRS_35MM"] = {
    "pads": [
        (1, -3.0, -2.5, 1.5, 1.5),
        (2, 3.0, -2.5, 1.5, 1.5),
        (3, 0.0, 3.0, 1.5, 1.5),
        ("M1", -5.0, 0.0, 2.0, 2.0),
        ("M2", 5.0, 0.0, 2.0, 2.0),
    ],
    "size": (11.0, 7.0),
    "thru_hole": True,
    "drill": 1.0,
}

# SMA edge-mount (UWB antenna)
FP["SMA"] = {
    "pads": [
        (1, 0.0, 0.0, 1.5, 1.5),
        (2, -2.54, 0.0, 2.0, 2.0),
        (3, 2.54, 0.0, 2.0, 2.0),
    ],
    "size": (6.35, 5.0),
}

# PCB BLE antenna feed
FP["PCB_ANT"] = {
    "pads": [(1, 0.0, 0.0, 0.8, 0.8)],
    "size": (8.0, 3.0),
}

# WS2812B-2020
FP["WS2812B"] = {
    "pads": [
        (1, -0.65, -0.55, 0.5, 0.5), (2, 0.65, -0.55, 0.5, 0.5),
        (3, 0.65, 0.55, 0.5, 0.5), (4, -0.65, 0.55, 0.5, 0.5),
    ],
    "size": (2.0, 2.0),
}

# Tactile button 3x3mm
FP["SW"] = {
    "pads": [(1, -2.0, 0, 1.0, 0.8), (2, 2.0, 0, 1.0, 0.8)],
    "size": (3.0, 3.0),
}

# JST-PH 2-pin battery
FP["JST_PH2"] = {
    "pads": [(1, -1.0, 0.0, 1.0, 1.5), (2, 1.0, 0.0, 1.0, 1.5)],
    "size": (6.0, 4.5),
}

# Speaker connector 2-pin
FP["SPK_CONN"] = {
    "pads": [(1, -1.0, 0.0, 1.0, 1.2), (2, 1.0, 0.0, 1.0, 1.2)],
    "size": (4.0, 3.0),
}

# Passives
FP["0402"] = {"pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)], "size": (1.6, 0.8)}
FP["0603"] = {"pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)], "size": (2.2, 1.2)}
FP["0805"] = {"pads": [(1, -0.95, 0, 1.0, 1.2), (2, 0.95, 0, 1.0, 1.2)], "size": (2.8, 1.5)}

# Mounting hole M2
FP["M2_HOLE"] = {
    "pads": [(1, 0, 0, 3.5, 3.5)],
    "size": (3.5, 3.5),
    "thru_hole": True,
    "drill": 2.2,
}


# ── Component placement (from gen_pro_v2.py) ─────────────────────────
PARTS = {
    "U1":  {"fp": "NRF5340",  "x": 14.0,  "y": 14.0,  "rot": 0,
            "part": "nRF5340-QKAA-R7",     "lcsc": "C2652073"},
    "U2":  {"fp": "DW3000",   "x": 33.0,  "y": 8.0,   "rot": 0,
            "part": "DW3000 (Qorvo QFN-48)", "lcsc": "C2843371"},
    "U3":  {"fp": "AK5720",   "x": 10.0,  "y": 25.0,  "rot": 0,
            "part": "AK5720VT",             "lcsc": "C2690387"},
    "U4":  {"fp": "PCM5102A", "x": 22.5,  "y": 25.0,  "rot": 0,
            "part": "PCM5102APWR",          "lcsc": "C108774"},
    "U5":  {"fp": "MAX98357", "x": 34.0,  "y": 25.0,  "rot": 0,
            "part": "MAX98357AETE+T",       "lcsc": "C1506581"},
    "U6":  {"fp": "NPM1300",  "x": 22.5,  "y": 5.0,   "rot": 0,
            "part": "nPM1300-QEAA-R7",     "lcsc": "C5303826"},
    "Y1":  {"fp": "XTAL_2012","x": 10.0,  "y": 10.0,  "rot": 0,
            "part": "32MHz 2012",           "lcsc": "C2762297"},
    "Y2":  {"fp": "XTAL_1610","x": 10.0,  "y": 12.0,  "rot": 0,
            "part": "32.768kHz 1610",       "lcsc": "C2838510"},
    "J1":  {"fp": "USBC",     "x": 22.5,  "y": 1.5,   "rot": 0,
            "part": "TYPE-C-16PIN-2MD",     "lcsc": "C2765186"},
    "J2":  {"fp": "TRS_35MM", "x": 1.5,   "y": 15.0,  "rot": 90,
            "part": "PJ-320A (3.5mm TRS)",  "lcsc": "C18438"},
    "J3":  {"fp": "SMA",      "x": 42.0,  "y": 4.0,   "rot": 0,
            "part": "SMA Edge-Mount",       "lcsc": "C496549"},
    "J4":  {"fp": "PCB_ANT",  "x": 40.0,  "y": 27.0,  "rot": 0,
            "part": "PCB Antenna (BLE)",    "lcsc": ""},
    "D1":  {"fp": "WS2812B",  "x": 7.0,   "y": 7.0,   "rot": 0,
            "part": "WS2812B-2020",         "lcsc": "C2976072"},
    "D2":  {"fp": "WS2812B",  "x": 7.0,   "y": 4.0,   "rot": 0,
            "part": "WS2812B-2020",         "lcsc": "C2976072"},
    "SW1": {"fp": "SW",       "x": 3.5,   "y": 25.0,  "rot": 0,
            "part": "3x3mm Tactile SMD",    "lcsc": "C2936178"},
    "BT1": {"fp": "JST_PH2",  "x": 42.0,  "y": 15.0,  "rot": 0,
            "part": "JST-PH-2P",            "lcsc": "C131337"},
    "SPK1":{"fp": "SPK_CONN", "x": 42.0,  "y": 21.0,  "rot": 0,
            "part": "Speaker 20mm Conn",    "lcsc": "C160404"},
    "MH1": {"fp": "M2_HOLE",  "x": 2.5,   "y": 2.5,   "rot": 0,
            "part": "M2 mounting hole",     "lcsc": ""},
    "MH2": {"fp": "M2_HOLE",  "x": 42.5,  "y": 2.5,   "rot": 0,
            "part": "M2 mounting hole",     "lcsc": ""},
    "MH3": {"fp": "M2_HOLE",  "x": 2.5,   "y": 27.5,  "rot": 0,
            "part": "M2 mounting hole",     "lcsc": ""},
    "MH4": {"fp": "M2_HOLE",  "x": 42.5,  "y": 27.5,  "rot": 0,
            "part": "M2 mounting hole",     "lcsc": ""},
    # Decoupling caps
    "C1":  {"fp": "0402", "x": 11.0,  "y": 16.5, "rot": 0, "part": "100nF", "lcsc": "C1525"},
    "C2":  {"fp": "0402", "x": 17.0,  "y": 16.5, "rot": 0, "part": "100nF", "lcsc": "C1525"},
    "C3":  {"fp": "0603", "x": 11.0,  "y": 18.0, "rot": 0, "part": "10uF",  "lcsc": "C15849"},
    "C4":  {"fp": "0402", "x": 17.0,  "y": 18.0, "rot": 0, "part": "1uF",   "lcsc": "C14445"},
    "C5":  {"fp": "0402", "x": 30.0,  "y": 4.0,  "rot": 0, "part": "100nF", "lcsc": "C1525"},
    "C6":  {"fp": "0402", "x": 36.0,  "y": 4.0,  "rot": 0, "part": "10nF",  "lcsc": "C15195"},
    "C7":  {"fp": "0402", "x": 7.5,   "y": 23.0, "rot": 0, "part": "100nF", "lcsc": "C1525"},
    "C8":  {"fp": "0402", "x": 12.5,  "y": 23.0, "rot": 0, "part": "10uF",  "lcsc": "C15849"},
    "C9":  {"fp": "0402", "x": 20.0,  "y": 22.0, "rot": 0, "part": "100nF", "lcsc": "C1525"},
    "C10": {"fp": "0402", "x": 25.0,  "y": 22.0, "rot": 0, "part": "10uF",  "lcsc": "C15849"},
    "C11": {"fp": "0402", "x": 31.5,  "y": 23.0, "rot": 0, "part": "10uF",  "lcsc": "C15849"},
    "C12": {"fp": "0603", "x": 19.0,  "y": 3.0,  "rot": 0, "part": "10uF",  "lcsc": "C15849"},
    "C13": {"fp": "0603", "x": 26.0,  "y": 3.0,  "rot": 0, "part": "22uF",  "lcsc": "C45783"},
    "C14": {"fp": "0402", "x": 9.0,   "y": 9.0,  "rot": 0, "part": "12pF",  "lcsc": "C1547"},
    "C15": {"fp": "0402", "x": 11.0,  "y": 9.0,  "rot": 0, "part": "12pF",  "lcsc": "C1547"},
    # Resistors
    "R1":  {"fp": "0402", "x": 19.5,  "y": 5.0,  "rot": 90, "part": "5.1k", "lcsc": "C25905"},
    "R2":  {"fp": "0402", "x": 25.5,  "y": 5.0,  "rot": 90, "part": "5.1k", "lcsc": "C25905"},
    "R3":  {"fp": "0402", "x": 7.0,   "y": 9.5,  "rot": 90, "part": "330R", "lcsc": "C25104"},
    "R4":  {"fp": "0402", "x": 14.0,  "y": 8.0,  "rot": 0,  "part": "4.7k", "lcsc": "C25900"},
    "R5":  {"fp": "0402", "x": 14.0,  "y": 9.5,  "rot": 0,  "part": "4.7k", "lcsc": "C25900"},
    "R6":  {"fp": "0402", "x": 7.5,   "y": 27.0, "rot": 0,  "part": "10k",  "lcsc": "C25744"},
    "R7":  {"fp": "0402", "x": 20.0,  "y": 28.0, "rot": 0,  "part": "10k",  "lcsc": "C25744"},
    "R8":  {"fp": "0402", "x": 25.0,  "y": 28.0, "rot": 0,  "part": "10k",  "lcsc": "C25744"},
    "R9":  {"fp": "0402", "x": 3.5,   "y": 22.5, "rot": 0,  "part": "10k",  "lcsc": "C25744"},
    # Inductors
    "L1":  {"fp": "0805", "x": 22.5,  "y": 8.5,  "rot": 0,  "part": "10uH", "lcsc": "C408412"},
    "L2":  {"fp": "0805", "x": 27.5,  "y": 8.5,  "rot": 0,  "part": "4.7uH","lcsc": "C408335"},
    # DW3000 UWB support components
    "Y3":  {"fp": "XTAL_1610","x": 36.0, "y": 10.0, "rot": 0, "part": "38.4MHz TCXO","lcsc": "C2838510"},
    "C16": {"fp": "0402", "x": 30.0,  "y": 6.0,  "rot": 0,  "part": "100nF", "lcsc": "C1525"},
    "C17": {"fp": "0402", "x": 36.0,  "y": 6.0,  "rot": 0,  "part": "100nF", "lcsc": "C1525"},
    "C18": {"fp": "0402", "x": 30.0,  "y": 10.0, "rot": 0,  "part": "100nF", "lcsc": "C1525"},
    "C19": {"fp": "0402", "x": 36.0,  "y": 12.0, "rot": 0,  "part": "100nF", "lcsc": "C1525"},
    "L3":  {"fp": "0402", "x": 38.0,  "y": 6.0,  "rot": 0,  "part": "15nH",  "lcsc": "C76862"},
    "C20": {"fp": "0402", "x": 38.0,  "y": 8.0,  "rot": 0,  "part": "1.5pF", "lcsc": "C1546"},
    "R10": {"fp": "0402", "x": 30.0,  "y": 12.0, "rot": 0,  "part": "10k",   "lcsc": "C25744"},
    # PCM5102A support components
    "R11": {"fp": "0402", "x": 20.0,  "y": 27.0, "rot": 0,  "part": "10k",   "lcsc": "C25744"},
    "C21": {"fp": "0402", "x": 25.0,  "y": 27.0, "rot": 0,  "part": "1uF",   "lcsc": "C14445"},
    "C22": {"fp": "0603", "x": 20.0,  "y": 20.0, "rot": 0,  "part": "2.2uF", "lcsc": "C12530"},
    "C23": {"fp": "0603", "x": 25.0,  "y": 20.0, "rot": 0,  "part": "2.2uF", "lcsc": "C12530"},
    "C24": {"fp": "0603", "x": 22.5,  "y": 20.0, "rot": 0,  "part": "10uF",  "lcsc": "C15849"},
    "C25": {"fp": "0402", "x": 22.5,  "y": 27.0, "rot": 0,  "part": "100nF", "lcsc": "C1525"},
}


# ── Routes (net_name, trace_width, waypoints) ────────────────────────
ROUTES = [
    # USB VBUS -> nPM1300
    ("+VBUS",      VBUS_W, [(22.5, 1.5), (22.5, 5.0)]),
    # PMIC -> 3.3V distribution
    ("+3V3",       PWR_W,  [(22.5, 5.0), (22.5, 8.5)]),
    ("+3V3",       PWR_W,  [(22.5, 8.5), (14.0, 8.5), (14.0, 14.0)]),
    ("+3V3",       TRACE_W,[(14.0, 14.0), (10.0, 14.0), (10.0, 25.0)]),
    ("+3V3",       TRACE_W,[(14.0, 14.0), (22.5, 14.0), (22.5, 25.0)]),
    ("+3V3",       TRACE_W,[(22.5, 14.0), (33.0, 14.0), (33.0, 8.0)]),
    ("+3V3",       TRACE_W,[(33.0, 14.0), (34.0, 14.0), (34.0, 25.0)]),
    ("+3V3",       TRACE_W,[(10.0, 14.0), (7.0, 7.0)]),
    ("+3V3",       TRACE_W,[(7.0, 7.0), (7.0, 4.0)]),
    # Battery -> PMIC
    ("+VBAT",      PWR_W,  [(42.0, 15.0), (35.0, 10.0), (27.5, 8.5), (22.5, 5.0)]),
    # SPI: nRF5340 -> DW3000
    ("SPI_MOSI",   TRACE_W,[(17.5, 13.0), (30.0, 6.5)]),
    ("SPI_MISO",   TRACE_W,[(17.5, 13.4), (30.0, 7.0)]),
    ("SPI_SCLK",   TRACE_W,[(17.5, 13.8), (30.0, 7.5)]),
    ("SPI_CS",     TRACE_W,[(17.5, 14.2), (30.0, 8.0)]),
    ("UWB_IRQ",    TRACE_W,[(17.5, 14.6), (30.0, 8.5)]),
    ("UWB_RST",    TRACE_W,[(17.5, 15.0), (30.0, 9.0)]),
    # I2S0: nRF5340 -> AK5720
    ("I2S0_SCK",   TRACE_W,[(10.5, 12.0), (12.65, 23.4)]),
    ("I2S0_LRCK",  TRACE_W,[(10.5, 12.4), (12.65, 24.05)]),
    ("I2S0_SDIN",  TRACE_W,[(10.5, 12.8), (12.65, 24.7)]),
    ("I2S0_MCK",   TRACE_W,[(10.5, 13.2), (12.65, 25.35)]),
    # I2S1: nRF5340 -> PCM5102A
    ("I2S1_SCK",   TRACE_W,[(17.5, 15.4), (19.25, 23.7)]),
    ("I2S1_LRCK",  TRACE_W,[(17.5, 15.8), (19.25, 24.35)]),
    ("I2S1_SDOUT", TRACE_W,[(17.5, 16.2), (19.25, 25.0)]),
    ("I2S1_MCK",   TRACE_W,[(17.5, 16.6), (19.25, 25.65)]),
    # I2S amp: nRF5340 -> MAX98357A
    ("AMP_BCK",    TRACE_W,[(17.5, 17.0), (32.5, 24.25)]),
    ("AMP_LRCK",   TRACE_W,[(17.5, 17.4), (32.5, 24.75)]),
    ("AMP_DIN",    TRACE_W,[(17.5, 17.8), (32.5, 25.25)]),
    ("AMP_SD",     TRACE_W,[(17.5, 18.2), (32.5, 25.75)]),
    # I2C: nRF5340 -> nPM1300
    ("I2C_SDA",    TRACE_W,[(10.5, 14.4), (20.0, 4.75)]),
    ("I2C_SCL",    TRACE_W,[(10.5, 14.8), (20.0, 5.25)]),
    # Speaker amp -> connector
    ("SPK_OUT",    TRACE_W,[(35.5, 25.75), (42.0, 21.0)]),
    # TRS -> AK5720
    ("LINE_TIP",   TRACE_W,[(1.5, 12.0), (5.0, 22.0), (7.35, 23.4)]),
    ("LINE_GND",   TRACE_W,[(1.5, 18.0), (5.0, 28.0), (7.35, 26.6)]),
    # DW3000 TCXO connection
    ("UWB_TCXO",   TRACE_W,[(36.0, 8.0), (36.0, 10.0)]),
    # DW3000 RST pull-up
    ("UWB_RST_PU", TRACE_W,[(30.0, 12.0), (30.0, 9.0)]),
    # RF matching network: DW3000 -> L3 -> C20 -> SMA
    ("UWB_RF_L",   TRACE_W,[(36.0, 6.0), (38.0, 6.0)]),
    ("UWB_RF_C",   TRACE_W,[(38.0, 6.0), (38.0, 8.0)]),
    ("UWB_RF_OUT", TRACE_W,[(38.0, 6.0), (39.0, 4.0), (42.0, 4.0)]),
    # PCM5102A XSMT pull-up (R11)
    ("DAC_XSMT",   TRACE_W,[(20.3, 25.65), (20.0, 27.0)]),
    # PCM5102A SCK -> GND (auto-clock)
    ("DAC_SCK_GND",TRACE_W,[(20.3, 23.7), (20.3, 22.5)]),
    # PCM5102A charge pump cap (C21)
    ("DAC_CAPP",   TRACE_W,[(24.7, 24.7), (25.0, 27.0)]),
    # PCM5102A output coupling (C22/C23)
    ("DAC_VOUTL",  TRACE_W,[(24.7, 25.975), (20.0, 20.0)]),
    ("DAC_VOUTR",  TRACE_W,[(24.7, 26.625), (25.0, 20.0)]),
    # PCM5102A LDOO bypass (C24)
    ("DAC_LDOO",   TRACE_W,[(24.7, 27.275), (22.5, 20.0)]),
    # PCM5102A CPVDD bypass (C25)
    ("DAC_CPVDD",  TRACE_W,[(24.7, 24.025), (22.5, 27.0)]),
    # LED chain
    ("LED_DIN",    TRACE_W,[(10.5, 15.2), (7.0, 9.5)]),
    ("LED_R_OUT",  TRACE_W,[(7.0, 9.5), (7.0, 7.0)]),
    ("LED_CHAIN",  TRACE_W,[(7.65, 6.45), (6.35, 4.55)]),
    # Button
    ("BTN",        TRACE_W,[(10.5, 14.0), (5.5, 25.0)]),
    # USB data
    ("USB_D+",     TRACE_W,[(10.5, 16.4), (22.75, 1.5)]),
    ("USB_D-",     TRACE_W,[(10.5, 16.8), (22.25, 1.5)]),
    # USB CC
    ("CC1",        TRACE_W,[(19.5, 5.0), (20.75, 1.5)]),
    ("CC2",        TRACE_W,[(25.5, 5.0), (24.25, 1.5)]),
    # Crystal connections
    ("XTAL_32M",   TRACE_W,[(10.0, 10.0), (10.5, 10.8)]),
    ("XTAL_32K",   TRACE_W,[(10.0, 12.0), (10.5, 11.2)]),
    # BLE antenna
    ("BLE_ANT",    TRACE_W,[(17.5, 18.6), (40.0, 27.0)]),
]

# Via positions (GND stitching + signal vias)
VIAS = [
    (5, 5), (22.5, 5), (40, 5),
    (5, 15), (22.5, 15), (40, 15),
    (5, 25), (22.5, 25), (40, 25),
    (14, 10), (33, 10), (14, 20), (33, 20),
    # Near DW3000 thermal pad
    (31, 8), (33, 6), (35, 8), (33, 10),
    # Near nRF5340 thermal pad
    (12, 14), (14, 12), (16, 14), (14, 16),
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
        """Get or create aperture D-code. shape='C' for circle, 'R' for rect."""
        key = (shape, tuple(round(p, 4) for p in params))
        if key not in self.apertures:
            self.apertures[key] = self.next_dcode
            self.next_dcode += 1
        return self.apertures[key]

    @staticmethod
    def _coord(v):
        """Convert mm to Gerber integer (FSLAX36Y36 = 6 decimal places in mm)."""
        return int(round(v * 1e6))

    def flash_pad(self, x, y, w, h):
        """Flash a rectangular or circular pad."""
        if abs(w - h) < 0.005:
            d = self._get_aperture("C", [w])
        else:
            d = self._get_aperture("R", [w, h])
        self.commands.append(f"D{d}*")
        self.commands.append(f"X{self._coord(x)}Y{self._coord(y)}D03*")

    def flash_circle(self, x, y, diameter):
        """Flash a circular pad/via."""
        d = self._get_aperture("C", [diameter])
        self.commands.append(f"D{d}*")
        self.commands.append(f"X{self._coord(x)}Y{self._coord(y)}D03*")

    def draw_line(self, x1, y1, x2, y2, width):
        """Draw a trace segment."""
        d = self._get_aperture("C", [width])
        self.commands.append(f"D{d}*")
        self.commands.append(f"X{self._coord(x1)}Y{self._coord(y1)}D02*")
        self.commands.append(f"X{self._coord(x2)}Y{self._coord(y2)}D01*")

    def draw_polyline(self, points, width):
        """Draw connected line segments."""
        if len(points) < 2:
            return
        d = self._get_aperture("C", [width])
        self.commands.append(f"D{d}*")
        self.commands.append(f"X{self._coord(points[0][0])}Y{self._coord(points[0][1])}D02*")
        for x, y in points[1:]:
            self.commands.append(f"X{self._coord(x)}Y{self._coord(y)}D01*")

    def draw_rect_outline(self, x1, y1, x2, y2, width=0.1):
        """Draw a rectangle outline."""
        self.draw_polyline(
            [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)],
            width
        )

    def draw_rounded_rect(self, x1, y1, x2, y2, radius, width=0.1, segments=8):
        """Draw a rounded rectangle (board outline)."""
        r = radius
        pts = []
        # Bottom-left corner arc
        for i in range(segments + 1):
            a = math.pi + (math.pi / 2) * i / segments
            pts.append((x1 + r + r * math.cos(a), y1 + r + r * math.sin(a)))
        # Bottom-right corner arc
        for i in range(segments + 1):
            a = 1.5 * math.pi + (math.pi / 2) * i / segments
            pts.append((x2 - r + r * math.cos(a), y1 + r + r * math.sin(a)))
        # Top-right corner arc
        for i in range(segments + 1):
            a = 0 + (math.pi / 2) * i / segments
            pts.append((x2 - r + r * math.cos(a), y2 - r + r * math.sin(a)))
        # Top-left corner arc
        for i in range(segments + 1):
            a = math.pi / 2 + (math.pi / 2) * i / segments
            pts.append((x1 + r + r * math.cos(a), y2 - r + r * math.sin(a)))
        # Close the path
        pts.append(pts[0])
        self.draw_polyline(pts, width)

    def fill_rect(self, x1, y1, x2, y2, line_width=0.3):
        """Fill a rectangular region with horizontal lines (copper pour)."""
        d = self._get_aperture("C", [line_width])
        self.commands.append(f"D{d}*")
        y = y1
        step = line_width * 0.8  # overlap lines slightly
        while y <= y2:
            self.commands.append(f"X{self._coord(x1)}Y{self._coord(y)}D02*")
            self.commands.append(f"X{self._coord(x2)}Y{self._coord(y)}D01*")
            y += step

    def draw_text(self, x, y, text, char_w=0.8, char_h=1.0, line_w=0.12):
        """Draw simple block text on silkscreen using line segments."""
        # Simple bitmap font for basic characters
        FONT = {
            'A': [(-1,0),(-0.3,1),(0.3,1),(1,0),None,(-0.65,0.5),(0.65,0.5)],
            'B': [(-1,0),(-1,1),(0.5,1),(1,0.75),(0.5,0.5),(-1,0.5),None,
                  (0.5,0.5),(1,0.25),(0.5,0),(-1,0)],
            'C': [(1,0.8),(0.5,1),(-0.5,1),(-1,0.8),(-1,0.2),(-0.5,0),(0.5,0),(1,0.2)],
            'D': [(-1,0),(-1,1),(0.5,1),(1,0.7),(1,0.3),(0.5,0),(-1,0)],
            'E': [(1,1),(-1,1),(-1,0.5),(0.5,0.5),None,(-1,0.5),(-1,0),(1,0)],
            'F': [(1,1),(-1,1),(-1,0.5),(0.5,0.5),None,(-1,0.5),(-1,0)],
            'G': [(1,0.8),(0.5,1),(-0.5,1),(-1,0.8),(-1,0.2),(-0.5,0),(0.5,0),(1,0.2),(1,0.5),(0.3,0.5)],
            'H': [(-1,0),(-1,1),None,(1,0),(1,1),None,(-1,0.5),(1,0.5)],
            'I': [(-0.3,1),(0.3,1),None,(0,1),(0,0),None,(-0.3,0),(0.3,0)],
            'K': [(-1,0),(-1,1),None,(-1,0.5),(1,1),None,(-1,0.5),(1,0)],
            'L': [(-1,1),(-1,0),(1,0)],
            'M': [(-1,0),(-1,1),(0,0.5),(1,1),(1,0)],
            'N': [(-1,0),(-1,1),(1,0),(1,1)],
            'O': [(-0.5,0),(-1,0.3),(-1,0.7),(-0.5,1),(0.5,1),(1,0.7),(1,0.3),(0.5,0),(-0.5,0)],
            'P': [(-1,0),(-1,1),(0.5,1),(1,0.75),(0.5,0.5),(-1,0.5)],
            'R': [(-1,0),(-1,1),(0.5,1),(1,0.75),(0.5,0.5),(-1,0.5),None,(0,0.5),(1,0)],
            'S': [(1,0.8),(0.5,1),(-0.5,1),(-1,0.7),(1,0.3),(0.5,0),(-0.5,0),(-1,0.2)],
            'T': [(-1,1),(1,1),None,(0,1),(0,0)],
            'U': [(-1,1),(-1,0.2),(-0.5,0),(0.5,0),(1,0.2),(1,1)],
            'V': [(-1,1),(0,0),(1,1)],
            'W': [(-1,1),(-0.5,0),(0,0.5),(0.5,0),(1,1)],
            'X': [(-1,0),(1,1),None,(-1,1),(1,0)],
            'Y': [(-1,1),(0,0.5),(1,1),None,(0,0.5),(0,0)],
            'Z': [(-1,1),(1,1),(-1,0),(1,0)],
            '0': [(-0.5,0),(-1,0.3),(-1,0.7),(-0.5,1),(0.5,1),(1,0.7),(1,0.3),(0.5,0),(-0.5,0)],
            '1': [(-0.3,0.8),(0,1),(0,0),None,(-0.3,0),(0.3,0)],
            '2': [(-1,0.8),(-0.5,1),(0.5,1),(1,0.7),(1,0.5),(-1,0),(1,0)],
            '3': [(-1,0.8),(-0.5,1),(0.5,1),(1,0.7),(0.5,0.5),(1,0.3),(0.5,0),(-0.5,0),(-1,0.2)],
            '4': [(-1,1),(-1,0.4),(1,0.4),None,(0.5,1),(0.5,0)],
            '5': [(1,1),(-1,1),(-1,0.5),(0.5,0.5),(1,0.3),(0.5,0),(-1,0)],
            '6': [(0.5,1),(-0.5,1),(-1,0.7),(-1,0.2),(-0.5,0),(0.5,0),(1,0.3),(0.5,0.5),(-1,0.5)],
            '7': [(-1,1),(1,1),(0,0)],
            '8': [(-0.5,0.5),(-1,0.7),(-0.5,1),(0.5,1),(1,0.7),(0.5,0.5),(-0.5,0.5),(-1,0.3),(-0.5,0),(0.5,0),(1,0.3),(0.5,0.5)],
            '9': [(0.5,0.5),(1,0.7),(0.5,1),(-0.5,1),(-1,0.7),(-0.5,0.5),(1,0.5),(1,0.2),(0.5,0),(-0.5,0)],
            '-': [(-0.5,0.5),(0.5,0.5)],
            '.': [(0,0),(0,0.1)],
            ' ': [],
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
        """Write complete RS-274X Gerber file."""
        with open(filepath, 'w', newline='\n') as f:
            # Header
            f.write("G04 Koe Pro v2 -- Generated by generate_gerbers.py*\n")
            f.write(f"G04 Layer: {self.layer_name}*\n")
            f.write(f"G04 Date: 2026-03-27*\n")
            # File attributes (JLCPCB uses these for layer identification)
            if self.layer_function:
                f.write(f"%TF.FileFunction,{self.layer_function}*%\n")
            f.write("%TF.GenerationSoftware,KoeDevice,generate_gerbers.py,2.0*%\n")
            f.write("%TF.SameCoordinates,Original*%\n")
            # Format specification: Leading zeros omitted, Absolute, X3.6 Y3.6
            f.write("%FSLAX36Y36*%\n")
            # Units: millimeters
            f.write("%MOMM*%\n")
            # Polarity: Dark
            f.write("%LPD*%\n")
            # Aperture definitions
            for (shape, params), dcode in sorted(self.apertures.items(), key=lambda x: x[1]):
                if shape == "C":
                    f.write(f"%ADD{dcode}C,{params[0]:.4f}*%\n")
                elif shape == "R":
                    f.write(f"%ADD{dcode}R,{params[0]:.4f}X{params[1]:.4f}*%\n")
                elif shape == "O":
                    f.write(f"%ADD{dcode}O,{params[0]:.4f}X{params[1]:.4f}*%\n")
            # Drawing commands
            for cmd in self.commands:
                f.write(cmd + "\n")
            # End of file
            f.write("M02*\n")


# ── Excellon Drill Writer ─────────────────────────────────────────────
class DrillWriter:
    """Generates Excellon drill files."""

    def __init__(self):
        self.tools = {}
        self.next_tool = 1
        self.holes = []

    def add_hole(self, x, y, diameter):
        """Add a drill hole."""
        d = round(diameter, 3)
        if d not in self.tools:
            self.tools[d] = self.next_tool
            self.next_tool += 1
        self.holes.append((self.tools[d], x, y))

    def write(self, filepath):
        """Write Excellon drill file."""
        with open(filepath, 'w', newline='\n') as f:
            f.write("M48\n")
            f.write("; Koe Pro v2 -- 45x30mm nRF5340 + DW3000 UWB\n")
            f.write("; Generated by generate_gerbers.py\n")
            f.write("FMAT,2\n")
            f.write("METRIC,TZ\n")
            # Tool definitions
            for d, t in sorted(self.tools.items(), key=lambda x: x[1]):
                f.write(f"T{t}C{d:.3f}\n")
            f.write("%\n")
            f.write("G90\n")  # Absolute mode
            f.write("G05\n")  # Drill mode
            # Holes grouped by tool
            current_tool = None
            for t, x, y in sorted(self.holes, key=lambda h: h[0]):
                if t != current_tool:
                    f.write(f"T{t}\n")
                    current_tool = t
                f.write(f"X{x:.3f}Y{y:.3f}\n")
            f.write("T0\n")
            f.write("M30\n")


# ── Main generation functions ─────────────────────────────────────────

def generate_all():
    """Generate all manufacturing files."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Create layer writers
    f_cu = GerberWriter("F.Cu", "Copper,L1,Top")
    b_cu = GerberWriter("B.Cu", "Copper,L4,Bot")
    in1_cu = GerberWriter("In1.Cu", "Copper,L2,Inr")
    in2_cu = GerberWriter("In2.Cu", "Copper,L3,Inr")
    f_mask = GerberWriter("F.Mask", "Soldermask,Top")
    b_mask = GerberWriter("B.Mask", "Soldermask,Bot")
    f_silk = GerberWriter("F.SilkS", "Legend,Top")
    edge = GerberWriter("Edge.Cuts", "Profile,NP")
    drill = DrillWriter()

    # ── Board outline (Edge.Cuts) ──
    edge.draw_rounded_rect(0, 0, BOARD_W, BOARD_H, CORNER_R, 0.05, CORNER_SEGS)

    # ── Component pads and silkscreen ──
    for ref, comp in PARTS.items():
        fp = FP[comp["fp"]]
        cx, cy = comp["x"], comp["y"]
        rot = comp.get("rot", 0)
        sw, sh = fp["size"]
        is_thru = fp.get("thru_hole", False)

        # Silkscreen: component outline
        hw, hh = sw / 2, sh / 2
        corners = [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]
        transformed = [xform(dx, dy, cx, cy, rot) for dx, dy in corners]
        for i in range(4):
            x1, y1 = transformed[i]
            x2, y2 = transformed[(i + 1) % 4]
            f_silk.draw_line(x1, y1, x2, y2, 0.12)

        # Pin 1 indicator on silkscreen (dot for ICs)
        if ref.startswith("U"):
            margin = fp.get("silk_margin", 0.2)
            dot_x, dot_y = xform(-hw + 0.5, -hh + 0.5, cx, cy, rot)
            f_silk.flash_circle(dot_x, dot_y, 0.3)

        # Reference designator on silkscreen
        f_silk.draw_text(cx - len(ref) * 0.4, cy - sh / 2 - 1.2, ref,
                         char_w=0.7, char_h=0.9, line_w=0.1)

        # Pads
        for pad_data in fp["pads"]:
            pin, px, py, pw, ph = pad_data
            ax, ay = xform(px, py, cx, cy, rot)
            # Swap pad dimensions for rotated components
            rpw, rph = pw, ph
            if rot in (90, 270):
                rpw, rph = ph, pw

            # Front copper pad
            f_cu.flash_pad(ax, ay, rpw, rph)

            # Solder mask opening (slightly larger)
            f_mask.flash_pad(ax, ay, rpw + MASK_EXP * 2, rph + MASK_EXP * 2)

            # Through-hole components get pads on back and drill holes
            if is_thru:
                b_cu.flash_pad(ax, ay, rpw, rph)
                b_mask.flash_pad(ax, ay, rpw + MASK_EXP * 2, rph + MASK_EXP * 2)
                drill.add_hole(ax, ay, fp["drill"])

    # ── Signal traces on F.Cu ──
    for net_name, width, waypoints in ROUTES:
        for i in range(len(waypoints) - 1):
            x1, y1 = waypoints[i]
            x2, y2 = waypoints[i + 1]
            f_cu.draw_line(x1, y1, x2, y2, width)

    # ── Vias (all layers) ──
    for vx, vy in VIAS:
        # Pads on front and back copper
        f_cu.flash_circle(vx, vy, VIA_PAD)
        b_cu.flash_circle(vx, vy, VIA_PAD)
        in1_cu.flash_circle(vx, vy, VIA_PAD)
        in2_cu.flash_circle(vx, vy, VIA_PAD)
        # Mask openings
        f_mask.flash_circle(vx, vy, VIA_PAD + VIA_ANNULAR)
        b_mask.flash_circle(vx, vy, VIA_PAD + VIA_ANNULAR)
        # Drill
        drill.add_hole(vx, vy, VIA_DRILL)

    # ── Mounting holes (drill only, already placed as component pads) ──
    # Already handled by component pad placement above, but ensure drill entries
    for ref in ("MH1", "MH2", "MH3", "MH4"):
        comp = PARTS[ref]
        # M2 hole = 2.2mm drill (already added via thru_hole footprint)

    # ── Back copper: GND pour ──
    # Fill the back copper with a ground pour (hatched fill)
    m = POUR_MARGIN
    b_cu.fill_rect(m, m, BOARD_W - m, BOARD_H - m, 0.25)

    # ── Inner layer 1: GND plane ──
    in1_cu.fill_rect(m, m, BOARD_W - m, BOARD_H - m, 0.25)

    # ── Inner layer 2: 3.3V plane ──
    in2_cu.fill_rect(m, m, BOARD_W - m, BOARD_H - m, 0.25)

    # ── Silkscreen: board name and version ──
    f_silk.draw_text(18.0, 0.8, "KOE PRO V2", char_w=0.9, char_h=1.2, line_w=0.15)
    f_silk.draw_text(36.0, 29.0, "R2.0", char_w=0.6, char_h=0.8, line_w=0.1)

    # ── Write all Gerber files ──
    layer_files = [
        ("F_Cu", f_cu),
        ("B_Cu", b_cu),
        ("In1_Cu", in1_cu),
        ("In2_Cu", in2_cu),
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

    # Write drill file
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
    """Generate JLCPCB-format BOM CSV."""
    # Group by part
    groups = {}
    for ref, comp in PARTS.items():
        lcsc = comp.get("lcsc", "")
        if not lcsc:  # Skip parts without LCSC (mounting holes, PCB antenna)
            continue
        key = (comp["part"], comp["fp"], lcsc)
        groups.setdefault(key, []).append(ref)

    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for (part, fp_name, lcsc), refs in sorted(groups.items(), key=lambda x: x[1][0]):
            writer.writerow([part, " ".join(refs), fp_name, lcsc])


def _generate_cpl(filepath):
    """Generate JLCPCB-format CPL (Component Placement List) CSV."""
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Designator", "Mid X", "Mid Y", "Rotation", "Layer"])
        for ref, comp in sorted(PARTS.items()):
            lcsc = comp.get("lcsc", "")
            if not lcsc:
                continue
            rot = comp.get("rot", 0) % 360
            layer = "Top"  # All SMD on top for this board
            writer.writerow([ref, f"{comp['x']:.2f}mm", f"{comp['y']:.2f}mm", rot, layer])


def validate_gerbers(out_dir):
    """Basic validation of generated Gerber files."""
    errors = []
    warnings = []

    for gbr_file in out_dir.glob("*.gbr"):
        content = gbr_file.read_text()
        name = gbr_file.name

        # Check required headers
        if "%FSLAX36Y36*%" not in content:
            errors.append(f"{name}: Missing format specification %FSLAX36Y36*%")
        if "%MOMM*%" not in content:
            errors.append(f"{name}: Missing unit specification %MOMM*%")
        if "M02*" not in content:
            errors.append(f"{name}: Missing end-of-file M02*")
        if "%LPD*%" not in content:
            errors.append(f"{name}: Missing polarity %LPD*%")

        # Check for aperture definitions
        if "%ADD" not in content:
            errors.append(f"{name}: No aperture definitions found")

        # Check for drawing commands
        has_d01 = "D01*" in content
        has_d03 = "D03*" in content
        if not has_d01 and not has_d03:
            warnings.append(f"{name}: No draw (D01) or flash (D03) commands")

        # Count apertures
        ap_count = content.count("%ADD")
        cmd_count = content.count("D01*") + content.count("D02*") + content.count("D03*")

        if "Edge_Cuts" in name and "D01*" not in content:
            errors.append(f"{name}: Edge cuts must have line draws (D01)")

    # Check drill file
    drl_file = out_dir / f"{PREFIX}.drl"
    if drl_file.exists():
        content = drl_file.read_text()
        if "M48" not in content:
            errors.append(f"{drl_file.name}: Missing M48 header")
        if "METRIC" not in content:
            errors.append(f"{drl_file.name}: Missing METRIC specification")
        if "M30" not in content:
            errors.append(f"{drl_file.name}: Missing M30 end-of-file")
        if content.count("T") < 2:
            warnings.append(f"{drl_file.name}: Very few tool definitions")
    else:
        errors.append("Drill file missing!")

    # Check required layer files
    required = ["F_Cu", "B_Cu", "In1_Cu", "In2_Cu", "F_Mask", "B_Mask", "F_SilkS", "Edge_Cuts"]
    for layer in required:
        if not (out_dir / f"{PREFIX}-{layer}.gbr").exists():
            errors.append(f"Missing required layer: {layer}")

    return errors, warnings


def main():
    print("=" * 65)
    print("Koe Pro v2 -- Production Gerber Generator")
    print(f"  Board:  {BOARD_W}x{BOARD_H}mm, 4-layer FR-4")
    print(f"  Parts:  {len(PARTS)} components")
    print(f"  Traces: {len(ROUTES)} routes")
    print(f"  Vias:   {len(VIAS)} positions")
    print(f"  Output: {OUT_DIR}")
    print("=" * 65)

    # Generate
    print("\nGenerating manufacturing files...")
    files, zip_path = generate_all()

    # Validate
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

    # Summary
    print("\n" + "=" * 65)
    print("Output files:")
    for f in sorted(OUT_DIR.iterdir()):
        print(f"  {f.name:40s} {f.stat().st_size:>8,} bytes")
    print(f"\nJLCPCB upload: {zip_path.name}")
    print("  1. Go to https://www.jlcpcb.com/")
    print("  2. Click 'Order Now' -> 'Add gerber file'")
    print(f"  3. Upload {zip_path.name}")
    print("  4. Select 4 layers, 1.6mm thickness, HASL finish")
    print(f"  5. For assembly: upload BOM + CPL CSVs")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
