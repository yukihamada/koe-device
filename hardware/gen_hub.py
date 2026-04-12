#!/usr/bin/env python3
"""
Koe Hub PCB — 120x100mm Pi CM5 Carrier for Audio Mixing/Routing
================================================================
Central hub for live performance: multi-channel audio I/O, UWB sync,
HDMI visual mixer output, and speaker drive.

Board: 120x100mm, 4-layer FR-4
Compute: Raspberry Pi CM5 (2x 100-pin Hirose DF40)
UWB: DW3000 (Qorvo, QFN-48) — sync with Pro devices
DAC: 2x PCM5102A (stereo main out + stereo monitor out)
ADC: 2x PCM1808 (stereo line input)
Amp: TPA3116D2 Class-D 2x50W (headphone/monitor amp)
Network: RJ45 Ethernet with magnetics
Connectors: USB-C (5V/3A), HDMI, 4x 6.35mm TRS, 2x XLR combo,
            2x Speakon NL4, SD card slot
Controls: DIP switch (4-pos channel config)
LEDs: Power, Sync, Clip, Stream status
"""

import math
import zipfile
from pathlib import Path

BOARD_W = 120.0
BOARD_H = 100.0
TRACE, PWR, VIA_D, VIA_P = 0.2, 0.5, 0.3, 0.6

OUT = Path(__file__).parent / "kicad"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-hub"


def in_rect(x, y, m=0.5):
    return m <= x <= BOARD_W - m and m <= y <= BOARD_H - m


# ── Footprints ────────────────────────────────────────────────────────
FP = {}

# Raspberry Pi CM5 connector: 2x 100-pin Hirose DF40 (0.4mm pitch)
def _cm5_conn():
    p = []
    for i in range(50):
        p.append((i*2+1, -9.8 + i * 0.4, -0.85, 0.2, 0.7))
        p.append((i*2+2, -9.8 + i * 0.4,  0.85, 0.2, 0.7))
    return p

FP["CM5_CONN"] = {"pads": _cm5_conn(), "size": (21.0, 3.0)}

# DW3000: QFN-48, 6.5x6.5mm, 0.5mm pitch
def _dw3000():
    p = []
    for i in range(12):
        p.append((i+1, -3.25, -2.75 + i * 0.5, 0.25, 0.8))
    for i in range(12):
        p.append((13+i, -2.75 + i * 0.5, 3.25, 0.8, 0.25))
    for i in range(12):
        p.append((25+i, 3.25, 2.75 - i * 0.5, 0.25, 0.8))
    for i in range(12):
        p.append((37+i, 2.75 - i * 0.5, -3.25, 0.8, 0.25))
    p.append((49, 0, 0, 4.0, 4.0))
    return p

FP["DW3000"] = {"pads": _dw3000(), "size": (6.5, 6.5)}

# PCM5102A: SSOP-20, 6.5x7.5mm, 0.65mm pitch
def _pcm5102():
    p = []
    for i in range(10):
        p.append((i+1, -3.75, -2.925 + i * 0.65, 0.4, 1.5))
    for i in range(10):
        p.append((11+i, 3.75, -2.925 + i * 0.65, 0.4, 1.5))
    return p

FP["PCM5102"] = {"pads": _pcm5102(), "size": (6.5, 7.5)}

# PCM1808: SSOP-20, 7.5x6.2mm, 0.65mm pitch
def _pcm1808():
    p = []
    for i in range(10):
        p.append((i+1, -3.75, -2.925 + i * 0.65, 0.3, 1.2))
    for i in range(10):
        p.append((11+i, 3.75, -2.925 + i * 0.65, 0.3, 1.2))
    return p

FP["PCM1808"] = {"pads": _pcm1808(), "size": (7.5, 6.2)}

# TPA3116D2: HTSSOP-32, 11x6.5mm, 0.65mm pitch
def _tpa3116():
    p = []
    for i in range(16):
        p.append((i+1, -5.35, -4.875 + i * 0.65, 0.3, 1.2))
    for i in range(16):
        p.append((17+i, 5.35, -4.875 + i * 0.65, 0.3, 1.2))
    p.append((33, 0, 0, 6.0, 4.5))
    return p

FP["TPA3116"] = {"pads": _tpa3116(), "size": (11.0, 6.5)}

# RJ45 with magnetics (through-hole)
FP["RJ45"] = {"pads": [
    (1, -4.445, -6.0, 1.0, 1.0), (2, -3.175, -6.0, 1.0, 1.0),
    (3, -1.905, -6.0, 1.0, 1.0), (4, -0.635, -6.0, 1.0, 1.0),
    (5,  0.635, -6.0, 1.0, 1.0), (6,  1.905, -6.0, 1.0, 1.0),
    (7,  3.175, -6.0, 1.0, 1.0), (8,  4.445, -6.0, 1.0, 1.0),
    # Shield/mount tabs
    ("S1", -7.87, 0.0, 2.4, 2.4), ("S2", 7.87, 0.0, 2.4, 2.4),
    # LEDs
    ("L1", -6.0, -6.0, 1.0, 1.0), ("L2", 6.0, -6.0, 1.0, 1.0),
], "size": (16.0, 13.5)}

# USB-C (16-pin SMD)
FP["USBC"] = {"pads": [
    ("V1", -2.75, -1.0, 0.6, 1.2), ("V2", 2.75, -1.0, 0.6, 1.2),
    ("D-", -0.25, -1.0, 0.3, 1.0), ("D+", 0.25, -1.0, 0.3, 1.0),
    ("C1", -1.75, -1.0, 0.3, 1.0), ("C2", 1.75, -1.0, 0.3, 1.0),
    ("G1", -3.5, -1.0, 0.5, 1.0),  ("G2", 3.5, -1.0, 0.5, 1.0),
    ("S1", -4.15, 0.5, 0.6, 1.6),  ("S2", 4.15, 0.5, 0.6, 1.6),
], "size": (9.0, 3.5)}

# HDMI Type-A (19-pin SMD)
def _hdmi():
    p = []
    for i in range(19):
        p.append((i+1, -4.5 + i * 0.5, -2.5, 0.25, 1.0))
    # Shield tabs
    p.append(("S1", -7.0, 0.0, 2.0, 3.0))
    p.append(("S2",  7.0, 0.0, 2.0, 3.0))
    return p

FP["HDMI"] = {"pads": _hdmi(), "size": (15.0, 6.0)}

# 6.35mm (1/4") TRS jack (through-hole)
FP["TRS_635MM"] = {"pads": [
    (1, -4.0, -4.0, 2.0, 2.0),   # Tip
    (2,  4.0, -4.0, 2.0, 2.0),   # Ring
    (3,  0.0,  5.0, 2.0, 2.0),   # Sleeve (GND)
    ("M1", -7.0, 0.0, 3.0, 3.0), # Mount
    ("M2",  7.0, 0.0, 3.0, 3.0), # Mount
], "size": (16.0, 12.0)}

# XLR combo jack (through-hole, simplified)
FP["XLR_COMBO"] = {"pads": [
    (1, -4.0, -5.0, 2.0, 2.0),   # Pin 1 (GND)
    (2,  0.0, -5.0, 2.0, 2.0),   # Pin 2 (Hot)
    (3,  4.0, -5.0, 2.0, 2.0),   # Pin 3 (Cold)
    (4, -4.0,  5.0, 2.0, 2.0),   # TRS Tip
    (5,  4.0,  5.0, 2.0, 2.0),   # TRS Sleeve
    ("M1", -9.0, 0.0, 3.0, 3.0), # Mount
    ("M2",  9.0, 0.0, 3.0, 3.0), # Mount
], "size": (20.0, 14.0)}

# Speakon NL4 (through-hole)
FP["SPEAKON"] = {"pads": [
    (1, -5.0, -5.0, 2.5, 2.5),
    (2,  5.0, -5.0, 2.5, 2.5),
    (3, -5.0,  5.0, 2.5, 2.5),
    (4,  5.0,  5.0, 2.5, 2.5),
    ("M1", -10.0, 0.0, 3.0, 3.0),
    ("M2",  10.0, 0.0, 3.0, 3.0),
], "size": (24.0, 14.0)}

# SD card slot (push-push type)
FP["SD_SLOT"] = {"pads": [
    (1, -5.5, -3.0, 0.7, 1.5), (2, -4.3, -3.0, 0.7, 1.5),
    (3, -3.1, -3.0, 0.7, 1.5), (4, -1.9, -3.0, 0.7, 1.5),
    (5, -0.7, -3.0, 0.7, 1.5), (6,  0.5, -3.0, 0.7, 1.5),
    (7,  1.7, -3.0, 0.7, 1.5), (8,  2.9, -3.0, 0.7, 1.5),
    (9,  4.1, -3.0, 0.7, 1.5),
    ("S1", -7.5, 1.0, 1.5, 2.0), ("S2", 7.5, 1.0, 1.5, 2.0),
], "size": (16.0, 7.0)}

# DIP switch 4-position (through-hole, 2.54mm pitch)
FP["DIP4"] = {"pads": [
    (1, -3.81, -2.0, 1.0, 1.6), (2, -1.27, -2.0, 1.0, 1.6),
    (3,  1.27, -2.0, 1.0, 1.6), (4,  3.81, -2.0, 1.0, 1.6),
    (5,  3.81,  2.0, 1.0, 1.6), (6,  1.27,  2.0, 1.0, 1.6),
    (7, -1.27,  2.0, 1.0, 1.6), (8, -3.81,  2.0, 1.0, 1.6),
], "size": (10.16, 5.08)}

# WS2812B-5050 (status LEDs)
FP["WS2812B"] = {"pads": [
    (1, -2.45, -1.6, 1.0, 1.0), (2, 2.45, -1.6, 1.0, 1.0),
    (3, 2.45, 1.6, 1.0, 1.0),   (4, -2.45, 1.6, 1.0, 1.0),
], "size": (5.0, 5.0)}

FP["SW"] = {"pads": [(1, -3.25, 0, 1.5, 1.0), (2, 3.25, 0, 1.5, 1.0)], "size": (6.0, 3.5)}

# SMA connector (edge-mount, UWB antenna)
FP["SMA"] = {"pads": [
    (1, 0.0, 0.0, 1.5, 1.5),
    (2, -2.54, 0.0, 2.0, 2.0),
    (3,  2.54, 0.0, 2.0, 2.0),
], "size": (6.35, 5.0)}

# Voltage regulator: LM2596 TO-263-5 (5V buck from USB)
FP["TO263"] = {"pads": [
    (1, -3.4, -5.0, 1.5, 2.5),
    (2, -1.7, -5.0, 1.5, 2.5),
    (3,  0.0, -5.0, 1.5, 2.5),
    (4,  1.7, -5.0, 1.5, 2.5),
    (5,  3.4, -5.0, 1.5, 2.5),
    (6,  0.0,  3.0, 10.0, 8.5),
], "size": (10.5, 15.3)}

# AMS1117-3.3: SOT-223
FP["SOT223"] = {"pads": [
    (1, -2.3, 3.25, 0.8, 1.5),
    (2,  0.0, 3.25, 0.8, 1.5),
    (3,  2.3, 3.25, 0.8, 1.5),
    (4,  0.0, -3.25, 3.0, 1.5),
], "size": (6.5, 7.0)}

# Passive components
FP["0402"] = {"pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)], "size": (1.6, 0.8)}
FP["0603"] = {"pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)], "size": (2.2, 1.2)}
FP["0805"] = {"pads": [(1, -0.95, 0, 1.0, 1.2), (2, 0.95, 0, 1.0, 1.2)], "size": (2.8, 1.5)}
FP["1206"] = {"pads": [(1, -1.4, 0, 1.2, 1.6), (2, 1.4, 0, 1.2, 1.6)], "size": (4.0, 2.0)}

# Electrolytic cap (8mm radial SMD)
FP["CAP_8MM"] = {"pads": [
    (1, -1.5, 0, 2.0, 2.0),
    (2,  1.5, 0, 2.0, 2.0),
], "size": (8.0, 8.0)}

# Power inductor 12mm
FP["IND_12MM"] = {"pads": [
    (1, -4.5, 0, 3.0, 3.0),
    (2,  4.5, 0, 3.0, 3.0),
], "size": (12.0, 12.0)}

# Schottky diode SMB
FP["SMB"] = {"pads": [
    (1, -2.0, 0, 2.0, 2.5),
    (2,  2.0, 0, 2.0, 2.5),
], "size": (5.3, 3.6)}

# Mounting hole M4
FP["M4_HOLE"] = {"pads": [
    (1, 0, 0, 5.5, 5.5),
], "size": (5.5, 5.5)}


# ── Components ────────────────────────────────────────────────────────
PARTS = {
    # ── Pi CM5 connectors (center of board) ──
    "J1": {"fp": "CM5_CONN", "x": 60.0, "y": 45.0, "rot": 0,
            "part": "DF40HC(3.0)-100DS-0.4V", "lcsc": "C2906057",
            "label": "CM5 Conn A", "color": "#006064"},
    "J2": {"fp": "CM5_CONN", "x": 60.0, "y": 52.0, "rot": 0,
            "part": "DF40HC(3.0)-100DS-0.4V", "lcsc": "C2906057",
            "label": "CM5 Conn B", "color": "#006064"},

    # ── UWB Module ──
    "U1": {"fp": "DW3000", "x": 60.0, "y": 35.0, "rot": 0,
            "part": "DW3000 (Qorvo QFN-48)", "lcsc": "C2843277",
            "label": "DW3000\nUWB", "color": "#880e4f"},

    # ── DACs (2x PCM5102A) ──
    "U2": {"fp": "PCM5102", "x": 30.0, "y": 50.0, "rot": 0,
            "part": "PCM5102APWR", "lcsc": "C107634",
            "label": "PCM5102A\nMain DAC", "color": "#4a148c"},
    "U3": {"fp": "PCM5102", "x": 30.0, "y": 65.0, "rot": 0,
            "part": "PCM5102APWR", "lcsc": "C107634",
            "label": "PCM5102A\nMon DAC", "color": "#4a148c"},

    # ── ADCs (2x PCM1808) ──
    "U4": {"fp": "PCM1808", "x": 90.0, "y": 50.0, "rot": 0,
            "part": "PCM1808PWR", "lcsc": "C108818",
            "label": "PCM1808\nADC L", "color": "#1a237e"},
    "U5": {"fp": "PCM1808", "x": 90.0, "y": 65.0, "rot": 0,
            "part": "PCM1808PWR", "lcsc": "C108818",
            "label": "PCM1808\nADC R", "color": "#1a237e"},

    # ── Class-D Amp (monitor/headphone) ──
    "U6": {"fp": "TPA3116", "x": 30.0, "y": 82.0, "rot": 0,
            "part": "TPA3116D2DADR", "lcsc": "C37833",
            "label": "TPA3116\n2x50W", "color": "#b71c1c"},

    # ── 5V Buck ──
    "U7": {"fp": "TO263", "x": 100.0, "y": 15.0, "rot": 0,
            "part": "LM2596S-5.0/NOPB", "lcsc": "C29781",
            "label": "LM2596\n5V Buck", "color": "#4e342e"},

    # ── 3.3V LDO ──
    "U8": {"fp": "SOT223", "x": 80.0, "y": 15.0, "rot": 0,
            "part": "AMS1117-3.3", "lcsc": "C6186",
            "label": "AMS1117\n3.3V", "color": "#4e342e"},

    # ── RJ45 Ethernet ──
    "J3": {"fp": "RJ45", "x": 110.0, "y": 92.0, "rot": 0,
            "part": "HR911105A (10/100 w/ magnetics)", "lcsc": "C12084",
            "label": "RJ45\nEthernet", "color": "#263238"},

    # ── USB-C ──
    "J4": {"fp": "USBC", "x": 60.0, "y": 3.0, "rot": 0,
            "part": "TYPE-C-16PIN-2MD (5V/3A)", "lcsc": "C2765186",
            "label": "USB-C\n5V/3A", "color": "#78909c"},

    # ── HDMI ──
    "J5": {"fp": "HDMI", "x": 40.0, "y": 3.0, "rot": 0,
            "part": "HDMI-A-19P", "lcsc": "C138388",
            "label": "HDMI\nDisplay", "color": "#37474f"},

    # ── 6.35mm TRS jacks (4x, left edge) ──
    "J6":  {"fp": "TRS_635MM", "x": 10.0, "y": 25.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "TRS 1\nInput", "color": "#263238"},
    "J7":  {"fp": "TRS_635MM", "x": 10.0, "y": 42.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "TRS 2\nInput", "color": "#263238"},
    "J8":  {"fp": "TRS_635MM", "x": 10.0, "y": 59.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "TRS 3\nInput", "color": "#263238"},
    "J9":  {"fp": "TRS_635MM", "x": 10.0, "y": 76.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "TRS 4\nInput", "color": "#263238"},

    # ── XLR combo jacks (2x, bottom-left) ──
    "J10": {"fp": "XLR_COMBO", "x": 10.0, "y": 92.0, "rot": 0,
             "part": "NCJ6FA-V XLR/TRS Combo", "lcsc": "",
             "label": "XLR 1", "color": "#1b5e20"},
    "J11": {"fp": "XLR_COMBO", "x": 35.0, "y": 92.0, "rot": 0,
             "part": "NCJ6FA-V XLR/TRS Combo", "lcsc": "",
             "label": "XLR 2", "color": "#1b5e20"},

    # ── Speakon NL4 outputs (2x, right edge) ──
    "J12": {"fp": "SPEAKON", "x": 107.0, "y": 50.0, "rot": 0,
             "part": "NL4MP", "lcsc": "",
             "label": "Speakon\nMain", "color": "#263238"},
    "J13": {"fp": "SPEAKON", "x": 107.0, "y": 70.0, "rot": 0,
             "part": "NL4MP", "lcsc": "",
             "label": "Speakon\nMon", "color": "#263238"},

    # ── SD Card slot ──
    "J14": {"fp": "SD_SLOT", "x": 80.0, "y": 5.0, "rot": 0,
             "part": "Micro-SD push-push", "lcsc": "C585353",
             "label": "SD Card", "color": "#455a64"},

    # ── SMA UWB antenna ──
    "J15": {"fp": "SMA", "x": 60.0, "y": 25.0, "rot": 0,
             "part": "SMA Edge-Mount", "lcsc": "C496549",
             "label": "SMA\nUWB", "color": "#ff6f00"},

    # ── Status LEDs ──
    "LED1": {"fp": "WS2812B", "x": 50.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "PWR", "color": "#4caf50"},
    "LED2": {"fp": "WS2812B", "x": 55.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "SYNC", "color": "#2196f3"},
    "LED3": {"fp": "WS2812B", "x": 60.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "CLIP", "color": "#f44336"},
    "LED4": {"fp": "WS2812B", "x": 65.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "STRM", "color": "#ff9800"},

    # ── DIP Switch ──
    "SW1": {"fp": "DIP4", "x": 75.0, "y": 10.0, "rot": 0,
             "part": "4-pos DIP switch", "lcsc": "C15781",
             "label": "CH CFG", "color": "#455a64"},

    # ── Reset button ──
    "SW2": {"fp": "SW", "x": 90.0, "y": 10.0, "rot": 0,
             "part": "EVQP0N02B", "lcsc": "C2936178",
             "label": "RST", "color": "#455a64"},

    # ── Mounting holes ──
    "MH1": {"fp": "M4_HOLE", "x": 4.0, "y": 4.0, "rot": 0,
              "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH2": {"fp": "M4_HOLE", "x": 116.0, "y": 4.0, "rot": 0,
              "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH3": {"fp": "M4_HOLE", "x": 4.0, "y": 96.0, "rot": 0,
              "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH4": {"fp": "M4_HOLE", "x": 116.0, "y": 96.0, "rot": 0,
              "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},

    # ── Buck converter external components ──
    "D1": {"fp": "SMB", "x": 95.0, "y": 23.0, "rot": 0,
            "part": "SS34 (3A Schottky)", "lcsc": "C8678",
            "label": "D1", "color": "#263238"},
    "L1": {"fp": "IND_12MM", "x": 88.0, "y": 23.0, "rot": 0,
            "part": "33uH 3A", "lcsc": "C408428",
            "label": "33uH", "color": "#006064"},
    "C1": {"fp": "CAP_8MM", "x": 108.0, "y": 23.0, "rot": 0,
            "part": "680uF/35V", "lcsc": "C249462",
            "label": "680u", "color": "#1a237e"},
    "C2": {"fp": "CAP_8MM", "x": 78.0, "y": 23.0, "rot": 0,
            "part": "220uF/10V", "lcsc": "C65221",
            "label": "220u", "color": "#1a237e"},

    # ── Decoupling caps ──
    # CM5 bypass
    "C3": {"fp": "0805", "x": 55.0, "y": 42.0, "rot": 0,
            "part": "100nF", "lcsc": "C49678", "label": "C3", "color": "#1a237e"},
    "C4": {"fp": "0805", "x": 65.0, "y": 42.0, "rot": 0,
            "part": "10uF", "lcsc": "C15850", "label": "C4", "color": "#1a237e"},
    # DW3000 bypass
    "C5": {"fp": "0402", "x": 55.0, "y": 33.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C5", "color": "#1a237e"},
    "C6": {"fp": "0402", "x": 65.0, "y": 33.0, "rot": 0,
            "part": "10nF", "lcsc": "C15195", "label": "C6", "color": "#1a237e"},
    # DAC bypass
    "C7": {"fp": "0805", "x": 25.0, "y": 46.0, "rot": 0,
            "part": "100nF", "lcsc": "C49678", "label": "C7", "color": "#1a237e"},
    "C8": {"fp": "0805", "x": 35.0, "y": 46.0, "rot": 0,
            "part": "10uF", "lcsc": "C15850", "label": "C8", "color": "#1a237e"},
    "C9": {"fp": "0805", "x": 25.0, "y": 61.0, "rot": 0,
            "part": "100nF", "lcsc": "C49678", "label": "C9", "color": "#1a237e"},
    "C10": {"fp": "0805", "x": 35.0, "y": 61.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C10", "color": "#1a237e"},
    # ADC bypass
    "C11": {"fp": "0805", "x": 85.0, "y": 46.0, "rot": 0,
             "part": "100nF", "lcsc": "C49678", "label": "C11", "color": "#1a237e"},
    "C12": {"fp": "0805", "x": 95.0, "y": 46.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C12", "color": "#1a237e"},
    "C13": {"fp": "0805", "x": 85.0, "y": 61.0, "rot": 0,
             "part": "100nF", "lcsc": "C49678", "label": "C13", "color": "#1a237e"},
    "C14": {"fp": "0805", "x": 95.0, "y": 61.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C14", "color": "#1a237e"},
    # TPA3116 bypass
    "C15": {"fp": "1206", "x": 25.0, "y": 78.0, "rot": 0,
             "part": "10uF/50V", "lcsc": "C13585", "label": "C15", "color": "#1a237e"},
    "C16": {"fp": "0805", "x": 35.0, "y": 78.0, "rot": 0,
             "part": "100nF", "lcsc": "C49678", "label": "C16", "color": "#1a237e"},
    # LDO caps
    "C17": {"fp": "0805", "x": 75.0, "y": 18.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C17", "color": "#1a237e"},
    "C18": {"fp": "0805", "x": 85.0, "y": 18.0, "rot": 0,
             "part": "22uF", "lcsc": "C45783", "label": "C18", "color": "#1a237e"},

    # ── Resistors ──
    # USB CC pull-down
    "R1": {"fp": "0402", "x": 56.0, "y": 6.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R1", "color": "#5d4037"},
    "R2": {"fp": "0402", "x": 64.0, "y": 6.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R2", "color": "#5d4037"},
    # TPA3116 gain set
    "R3": {"fp": "0805", "x": 25.0, "y": 85.0, "rot": 90,
            "part": "200k", "lcsc": "C17574", "label": "R3", "color": "#5d4037"},
    "R4": {"fp": "0805", "x": 35.0, "y": 85.0, "rot": 90,
            "part": "200k", "lcsc": "C17574", "label": "R4", "color": "#5d4037"},
    # LED data resistor
    "R5": {"fp": "0402", "x": 47.0, "y": 10.0, "rot": 0,
            "part": "330R", "lcsc": "C25104", "label": "R5", "color": "#5d4037"},
    # PCM5102 FLT/DEMP/XSMT pull
    "R6": {"fp": "0402", "x": 30.0, "y": 43.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R6", "color": "#5d4037"},
    "R7": {"fp": "0402", "x": 30.0, "y": 58.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R7", "color": "#5d4037"},
    # PCM1808 FMT pull (I2S mode)
    "R8": {"fp": "0402", "x": 90.0, "y": 43.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R8", "color": "#5d4037"},
    "R9": {"fp": "0402", "x": 90.0, "y": 58.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R9", "color": "#5d4037"},
}


# ── Routes ────────────────────────────────────────────────────────────
ROUTES = [
    # USB-C → buck → LDO → 3.3V
    ("+5V_USB", PWR, [(60.0, 3.0), (60.0, 8.0), (100.0, 8.0), (100.0, 15.0)]),
    ("+5V", PWR, [(88.0, 23.0), (80.0, 23.0), (80.0, 15.0)]),          # Buck → LDO
    ("+5V", PWR, [(80.0, 23.0), (60.0, 23.0), (60.0, 45.0)]),          # 5V → CM5
    ("+3V3", TRACE, [(80.0, 18.25), (60.0, 18.0), (60.0, 35.0)]),      # LDO → DW3000
    ("+3V3", TRACE, [(60.0, 18.0), (50.0, 10.0)]),                      # → LED1
    ("+3V3", TRACE, [(60.0, 35.0), (30.0, 50.0)]),                      # → DAC1
    ("+3V3", TRACE, [(30.0, 50.0), (30.0, 65.0)]),                      # → DAC2
    ("+3V3", TRACE, [(60.0, 35.0), (90.0, 50.0)]),                      # → ADC1
    ("+3V3", TRACE, [(90.0, 50.0), (90.0, 65.0)]),                      # → ADC2

    # I2S: CM5 → DACs (main + monitor)
    ("I2S_BCK1",  TRACE, [(60.0-9.8, 45.0), (30.0+3.75, 48.5)]),       # CM5 → DAC1
    ("I2S_LRCK1", TRACE, [(60.0-9.8+0.4, 45.0), (30.0+3.75, 49.15)]),
    ("I2S_DIN1",  TRACE, [(60.0-9.8+0.8, 45.0), (30.0+3.75, 49.8)]),
    ("I2S_BCK2",  TRACE, [(60.0-9.8+1.2, 45.0), (30.0+3.75, 63.5)]),   # CM5 → DAC2
    ("I2S_LRCK2", TRACE, [(60.0-9.8+1.6, 45.0), (30.0+3.75, 64.15)]),
    ("I2S_DIN2",  TRACE, [(60.0-9.8+2.0, 45.0), (30.0+3.75, 64.8)]),

    # I2S: ADCs → CM5
    ("I2S_BCK3",  TRACE, [(90.0-3.75, 48.5), (60.0+9.8, 45.0)]),       # ADC1 → CM5
    ("I2S_LRCK3", TRACE, [(90.0-3.75, 49.15), (60.0+9.8-0.4, 45.0)]),
    ("I2S_DOUT3", TRACE, [(90.0-3.75, 49.8), (60.0+9.8-0.8, 45.0)]),
    ("I2S_BCK4",  TRACE, [(90.0-3.75, 63.5), (60.0+9.8-1.2, 45.0)]),   # ADC2 → CM5
    ("I2S_LRCK4", TRACE, [(90.0-3.75, 64.15), (60.0+9.8-1.6, 45.0)]),
    ("I2S_DOUT4", TRACE, [(90.0-3.75, 64.8), (60.0+9.8-2.0, 45.0)]),

    # Analog: DAC1 → Speakon Main
    ("MAIN_L", TRACE, [(30.0-3.75, 50.0), (22.0, 50.0), (22.0, 50.0),
                        (107.0-5.0, 45.0)]),
    ("MAIN_R", TRACE, [(30.0-3.75, 51.0), (22.0, 51.0), (22.0, 51.0),
                        (107.0-5.0, 48.0)]),

    # Analog: DAC2 → TPA3116 → Speakon Mon
    ("MON_L", TRACE, [(30.0-3.75, 65.0), (30.0-5.35, 80.0)]),
    ("MON_R", TRACE, [(30.0-3.75, 66.0), (30.0-5.35, 81.0)]),
    ("SPK_MON1+", PWR, [(30.0+5.35, 78.0), (50.0, 70.0), (107.0-5.0, 65.0)]),
    ("SPK_MON1-", PWR, [(30.0+5.35, 80.0), (50.0, 73.0), (107.0-5.0, 68.0)]),

    # TRS inputs → ADCs
    ("TRS1_TIP", TRACE, [(10.0-4.0, 25.0-4.0), (20.0, 20.0),
                          (90.0-3.75, 50.0-2.0)]),
    ("TRS2_TIP", TRACE, [(10.0-4.0, 42.0-4.0), (20.0, 38.0),
                          (90.0-3.75, 50.0+1.0)]),
    ("TRS3_TIP", TRACE, [(10.0-4.0, 59.0-4.0), (20.0, 55.0),
                          (90.0-3.75, 65.0-2.0)]),
    ("TRS4_TIP", TRACE, [(10.0-4.0, 76.0-4.0), (20.0, 72.0),
                          (90.0-3.75, 65.0+1.0)]),

    # XLR inputs → ADCs (via summing)
    ("XLR1_HOT", TRACE, [(10.0, 92.0-5.0), (20.0, 87.0),
                          (85.0, 55.0), (90.0-3.75, 50.0+2.0)]),
    ("XLR2_HOT", TRACE, [(35.0, 92.0-5.0), (45.0, 87.0),
                          (85.0, 70.0), (90.0-3.75, 65.0+2.0)]),

    # UWB antenna
    ("UWB_ANT", TRACE, [(60.0+3.25, 35.0-2.75), (60.0, 28.0), (60.0, 25.0)]),

    # SPI: CM5 → DW3000
    ("SPI_DW", TRACE, [(60.0, 52.0), (60.0, 40.0), (60.0-3.25, 35.0)]),

    # Ethernet: CM5 → RJ45
    ("ETH", TRACE, [(60.0+9.8, 52.0), (85.0, 60.0), (110.0, 80.0), (110.0, 92.0)]),

    # HDMI: CM5 → HDMI connector
    ("HDMI", TRACE, [(60.0-9.8, 52.0), (40.0, 30.0), (40.0, 3.0)]),

    # SD: CM5 → SD slot
    ("SD_DAT", TRACE, [(60.0+9.8-2.0, 52.0), (75.0, 15.0), (80.0, 5.0)]),

    # LED chain
    ("LED_DIN",  TRACE, [(60.0-9.8-2.0, 52.0), (47.0, 10.0)]),
    ("LED_CH1",  TRACE, [(50.0+2.45, 10.0+1.6), (55.0-2.45, 10.0-1.6)]),
    ("LED_CH2",  TRACE, [(55.0+2.45, 10.0+1.6), (60.0-2.45, 10.0-1.6)]),
    ("LED_CH3",  TRACE, [(60.0+2.45, 10.0+1.6), (65.0-2.45, 10.0-1.6)]),

    # USB data (CM5)
    ("USB_D+", 0.2, [(60.0+0.25, 3.0), (60.0+1.0, 20.0), (60.0+0.4, 45.0)]),
    ("USB_D-", 0.2, [(60.0-0.25, 3.0), (60.0-1.0, 20.0), (60.0-0.4, 45.0)]),

    # USB CC
    ("CC1", TRACE, [(56.0, 6.0), (60.0-1.75, 3.0)]),
    ("CC2", TRACE, [(64.0, 6.0), (60.0+1.75, 3.0)]),

    # DIP switch → CM5 GPIO
    ("DIP", TRACE, [(75.0, 10.0), (70.0, 20.0), (60.0+9.8-3.0, 45.0)]),

    # Reset
    ("RST", TRACE, [(90.0+3.25, 10.0), (60.0+9.8-4.0, 45.0)]),
]

VIAS = [
    (10, 10), (30, 10), (60, 10), (90, 10), (110, 10),
    (10, 30), (30, 30), (60, 30), (90, 30), (110, 30),
    (10, 50), (30, 50), (60, 50), (90, 50), (110, 50),
    (10, 70), (30, 70), (60, 70), (90, 70), (110, 70),
    (10, 90), (30, 90), (60, 90), (90, 90), (110, 90),
    (20, 20), (40, 20), (80, 20), (100, 20),
    (20, 40), (40, 40), (80, 40), (100, 40),
    (20, 60), (40, 60), (80, 60), (100, 60),
    (20, 80), (40, 80), (80, 80), (100, 80),
    # Extra GND vias near amp thermal pad
    (28, 82), (30, 85), (32, 82), (30, 79),
    # Extra GND vias near DW3000
    (58, 35), (60, 38), (62, 35), (60, 32),
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
            f.write(f"G04 Koe HUB {s.name}*\n%LPD*%\n")
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
            f.write("M48\n; Koe HUB 120x100mm Pi CM5 Carrier\nFMAT,2\nMETRIC,TZ\n")
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

    # Through-hole component drills
    th_refs = ("J3", "J6", "J7", "J8", "J9", "J10", "J11", "J12", "J13")
    for ref in th_refs:
        c = PARTS[ref]
        fp = FP[c["fp"]]
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            ax, ay = xform(px, py, c["x"], c["y"], c.get("rot", 0))
            dr.hole(ax, ay, 1.2)

    # DIP switch drills
    fp = FP["DIP4"]
    c = PARTS["SW1"]
    for p in fp["pads"]:
        pin, px, py, pw, ph = p
        ax, ay = xform(px, py, c["x"], c["y"], c.get("rot", 0))
        dr.hole(ax, ay, 0.8)

    # Ground copper pour (back copper = full GND)
    bc.rect(1, 1, BOARD_W - 1, BOARD_H - 1, 0.3)

    pre = "koe-hub"
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
    S = 6; pad = 60; img_w = int(BOARD_W * S + pad * 2); img_h = int(BOARD_H * S + pad * 2)
    ox, oy = pad, pad + 20

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{img_w}" height="{img_h + 180}">
<defs>
  <linearGradient id="pcb" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#0d5c0d"/><stop offset="100%" stop-color="#063806"/>
  </linearGradient>
  <filter id="sh"><feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.4"/></filter>
</defs>
<rect width="{img_w}" height="{img_h + 180}" fill="#0d0d14"/>

<!-- Title -->
<text x="{img_w // 2}" y="22" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="16" font-weight="600">Koe Hub v1 -- Pi CM5 Audio Mixer/Router Carrier Board</text>
<text x="{img_w // 2}" y="40" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">120x100mm | 4-layer FR-4 | 2x PCM5102A DAC | 2x PCM1808 ADC | TPA3116D2 | DW3000 UWB | HDMI</text>

<!-- Board -->
<rect x="{ox - 2}" y="{oy - 2}" width="{BOARD_W * S + 4}" height="{BOARD_H * S + 4}" fill="#000" opacity="0.3" rx="3"/>
<rect x="{ox}" y="{oy}" width="{BOARD_W * S}" height="{BOARD_H * S}" fill="url(#pcb)" stroke="#c8a83e" stroke-width="1.5" rx="2"/>
'''

    # GND pour hint
    svg += f'<rect x="{ox + 4}" y="{oy + 4}" width="{BOARD_W * S - 8}" height="{BOARD_H * S - 8}" fill="none" stroke="#1a5c1a" stroke-width="0.5" stroke-dasharray="4,4" rx="1"/>\n'

    # Amp thermal relief zone
    amp = PARTS["U6"]
    ax, ay = ox + amp["x"] * S, oy + amp["y"] * S
    svg += f'<rect x="{ax - 30}" y="{ay - 20}" width="60" height="40" fill="#4a2800" opacity="0.15" rx="3"/>\n'
    svg += f'<text x="{ax}" y="{ay + 30}" text-anchor="middle" fill="#8b4513" font-family="monospace" font-size="6" opacity="0.5">thermal relief zone</text>\n'

    # Traces
    net_colors = {
        "5V": "#ff7043", "3V3": "#66bb6a", "USB": "#ffca28",
        "I2S": "#42a5f5", "SPI": "#42a5f5", "MAIN": "#ce93d8",
        "MON": "#ef9a9a", "SPK": "#ff5722", "TRS": "#80cbc4",
        "XLR": "#a5d6a7", "UWB": "#e91e63", "LED": "#f9a825",
        "ETH": "#78909c", "HDMI": "#90a4ae", "SD": "#bcaaa4",
        "DIP": "#b0bec5", "CC": "#78909c", "RST": "#78909c",
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
            fs = 5 if ref[0] in "RCLDL" else 7
            if ref.startswith("LED") or ref.startswith("SW"): fs = 6
            svg += f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="{fs}">{line}</text>\n'
        svg += '</g>\n'

    # Legend
    ly = img_h + 15
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="9">120x100mm | 4-layer | {len(PARTS)} parts | Pi CM5 carrier + DW3000 UWB + multi-channel audio</text>\n'

    # Signal flow
    ly += 22
    flow_items = [
        ("Inputs", "#80cbc4"), ("PCM1808", "#1a237e"), ("I2S", "#42a5f5"),
        ("Pi CM5", "#006064"), ("I2S", "#42a5f5"), ("PCM5102A", "#4a148c"),
        ("TPA3116", "#b71c1c"), ("Speakon", "#263238"),
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
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#ef5350" font-family="monospace" font-size="9" font-weight="bold">USB-C 5V/3A &#8594; LM2596 5V (Pi CM5) &#8594; AMS1117 3.3V (logic/audio)</text>\n'
    ly += 16
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">4x TRS + 2x XLR in | 2x Speakon out | HDMI display | Ethernet | DW3000 UWB sync</text>\n'

    # Price
    ly += 22
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#c8a83e" font-family="monospace" font-size="9">HUB $800 | Pi CM5 DSP | Multi-channel mixer | UWB sync with Pro devices</text>\n'

    svg += '</svg>\n'
    path = GBR / "koe-hub-layout.svg"
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
        print("DRC: All components within 120x100mm board -- OK")
    return len(errs) == 0


def main():
    print("=" * 65)
    print("Koe Hub v1 -- 120x100mm Pi CM5 Audio Carrier Board")
    print(f"  {len(PARTS)} parts | Pi CM5 + DW3000 UWB | Multi-channel Audio")
    print(f"  2x PCM5102A DAC | 2x PCM1808 ADC | TPA3116D2 2x50W")
    print(f"  4x TRS + 2x XLR in | 2x Speakon out | HDMI | Ethernet")
    print("=" * 65)
    check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()
    print(f"\nSignal chain:")
    print(f"  Inputs: 4x 6.35mm TRS + 2x XLR combo")
    print(f"  --> 2x PCM1808 ADC --> I2S --> Pi CM5 (DSP/mixing)")
    print(f"  --> I2S --> 2x PCM5102A DAC (main + monitor)")
    print(f"  --> Main: direct to Speakon")
    print(f"  --> Monitor: TPA3116D2 amp --> Speakon")
    print(f"\nSync:")
    print(f"  DW3000 UWB <--> SPI <--> Pi CM5 (sub-us sync with Pro devices)")
    print(f"\nPower:")
    print(f"  USB-C 5V/3A --> LM2596 5V (Pi CM5)")
    print(f"  5V --> AMS1117 --> 3.3V (logic, audio, UWB)")


if __name__ == "__main__":
    main()
