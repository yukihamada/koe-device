#!/usr/bin/env python3
"""
Koe Hub v2 PCB — 140x120mm Pi CM5 Pro Audio Carrier
====================================================
Pro audio upgrade: ES9038Q2M quad DAC, nRF5340 BLE Audio,
ADAT optical I/O, TPA6120A2 headphone amp, M.2 NVMe SSD,
BNC word clock, DW3720 UWB sync.

Board: 140x120mm, 4-layer FR-4
Compute: Raspberry Pi CM5 (2x 100-pin Hirose DF40)
BLE: nRF5340 (QFN-94) — BLE Audio receiver (7 CIS)
UWB: DW3720 (Qorvo, QFN-48) — sync with Pro devices
DAC: ES9038Q2M (QFP-48) — quad DAC (129dB SNR)
ADC: 2x PCM1808 (stereo line input)
Headphone: TPA6120A2 (DIP-8, 120dB SNR, 6ohm drive)
Monitor: TPA3116D2 Class-D 2x50W
Network: RJ45 Ethernet with magnetics
Digital: ADAT Toslink IN/OUT, BNC word clock
Storage: M.2 2242 NVMe SSD slot
Connectors: USB-C PD, HDMI, 4x 6.35mm TRS, 2x XLR combo,
            2x Speakon NL4, headphone TRS, SD card
Controls: DIP switch (4-pos channel config)
LEDs: Power, Sync, Clip, Stream, BLE, UWB status
"""

import math
import zipfile
from pathlib import Path

BOARD_W = 140.0
BOARD_H = 120.0
TRACE, PWR, VIA_D, VIA_P = 0.2, 0.5, 0.3, 0.6

OUT = Path(__file__).parent / "kicad"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-hub-v2"


def in_rect(x, y, m=0.5):
    return m <= x <= BOARD_W - m and m <= y <= BOARD_H - m


# -- Footprints ---------------------------------------------------------------
FP = {}

# Raspberry Pi CM5 connector: 2x 100-pin Hirose DF40 (0.4mm pitch)
def _cm5_conn():
    p = []
    for i in range(50):
        p.append((i*2+1, -9.8 + i * 0.4, -0.85, 0.2, 0.7))
        p.append((i*2+2, -9.8 + i * 0.4,  0.85, 0.2, 0.7))
    return p

FP["CM5_CONN"] = {"pads": _cm5_conn(), "size": (21.0, 3.0)}

# nRF5340: QFN-94, 7x7mm, 0.4mm pitch (simplified as 4-side QFN)
def _nrf5340():
    p = []
    # 24 pins per side (96 total minus 2 = 94; we model 24 per side)
    for i in range(24):
        p.append((i+1,  -3.5, -4.6 + i * 0.4, 0.2, 0.8))   # Left
    for i in range(24):
        p.append((25+i, -4.6 + i * 0.4,  3.5, 0.8, 0.2))   # Bottom
    for i in range(24):
        p.append((49+i,  3.5,  4.6 - i * 0.4, 0.2, 0.8))   # Right
    for i in range(22):
        p.append((73+i,  4.2 - i * 0.4, -3.5, 0.8, 0.2))   # Top (22 = 94-72)
    p.append((95, 0, 0, 5.0, 5.0))  # Exposed pad
    return p

FP["NRF5340"] = {"pads": _nrf5340(), "size": (7.0, 7.0)}

# DW3720: QFN-48, 6.5x6.5mm, 0.5mm pitch
def _dw3720():
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

FP["DW3720"] = {"pads": _dw3720(), "size": (6.5, 6.5)}

# ES9038Q2M: QFP-48, 9x9mm body, 12 pins per side, 0.5mm pitch
def _es9038():
    p = []
    for i in range(12):
        p.append((i+1,  -5.3, -2.75 + i * 0.5, 0.25, 1.2))  # Left
    for i in range(12):
        p.append((13+i, -2.75 + i * 0.5,  5.3, 1.2, 0.25))  # Bottom
    for i in range(12):
        p.append((25+i,  5.3,  2.75 - i * 0.5, 0.25, 1.2))  # Right
    for i in range(12):
        p.append((37+i,  2.75 - i * 0.5, -5.3, 1.2, 0.25))  # Top
    return p

FP["ES9038"] = {"pads": _es9038(), "size": (9.0, 9.0)}

# PCM1808: SSOP-20, 7.5x6.2mm, 0.65mm pitch
def _pcm1808():
    p = []
    for i in range(10):
        p.append((i+1, -3.75, -2.925 + i * 0.65, 0.3, 1.2))
    for i in range(10):
        p.append((11+i, 3.75, -2.925 + i * 0.65, 0.3, 1.2))
    return p

FP["PCM1808"] = {"pads": _pcm1808(), "size": (7.5, 6.2)}

# TPA6120A2: DIP-8, 9.5x6.35mm, 2.54mm pitch
def _tpa6120():
    p = []
    for i in range(4):
        p.append((i+1, -3.81 + i * 2.54, -3.175, 1.5, 1.5))
    for i in range(4):
        p.append((5+i,  3.81 - i * 2.54,  3.175, 1.5, 1.5))
    return p

FP["TPA6120"] = {"pads": _tpa6120(), "size": (9.5, 6.35)}

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
    ("S1", -7.87, 0.0, 2.4, 2.4), ("S2", 7.87, 0.0, 2.4, 2.4),
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
    p.append(("S1", -7.0, 0.0, 2.0, 3.0))
    p.append(("S2",  7.0, 0.0, 2.0, 3.0))
    return p

FP["HDMI"] = {"pads": _hdmi(), "size": (15.0, 6.0)}

# Toslink optical connector
FP["TOSLINK"] = {"pads": [
    (1, -2.5, -3.0, 1.5, 1.5),   # Signal
    (2,  2.5, -3.0, 1.5, 1.5),   # GND
    ("M1", -5.0, 3.0, 2.5, 2.5), # Mount
    ("M2",  5.0, 3.0, 2.5, 2.5), # Mount
], "size": (12.0, 10.0)}

# BNC connector (through-hole, 50 ohm)
FP["BNC"] = {"pads": [
    (1, 0.0, 0.0, 1.5, 1.5),     # Center
    (2, -2.54, -2.54, 2.0, 2.0), # GND tab
    (3,  2.54, -2.54, 2.0, 2.0), # GND tab
    (4, -2.54,  2.54, 2.0, 2.0), # GND tab
    (5,  2.54,  2.54, 2.0, 2.0), # GND tab
], "size": (10.0, 10.0)}

# M.2 2242 socket (M-key, 75-pin)
def _m2_socket():
    p = []
    # 75 pins at 0.5mm pitch on key-M connector
    for i in range(38):
        p.append((i+1, -9.25 + i * 0.5, -1.5, 0.3, 1.0))
    for i in range(37):
        p.append((39+i, -8.75 + i * 0.5, 1.5, 0.3, 1.0))
    # Mount / standoff pads
    p.append(("M1", -11.0, 0.0, 2.5, 2.5))
    p.append(("M2",  11.0, 0.0, 2.5, 2.5))
    return p

FP["M2_SOCKET"] = {"pads": _m2_socket(), "size": (24.0, 5.0)}

# 6.35mm (1/4") TRS jack (through-hole)
FP["TRS_635MM"] = {"pads": [
    (1, -4.0, -4.0, 2.0, 2.0),   # Tip
    (2,  4.0, -4.0, 2.0, 2.0),   # Ring
    (3,  0.0,  5.0, 2.0, 2.0),   # Sleeve (GND)
    ("M1", -7.0, 0.0, 3.0, 3.0), # Mount
    ("M2",  7.0, 0.0, 3.0, 3.0), # Mount
], "size": (16.0, 12.0)}

# XLR combo jack (through-hole)
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

# DIP switch 4-position (2.54mm pitch)
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

# SMA connector (edge-mount, antenna)
FP["SMA"] = {"pads": [
    (1, 0.0, 0.0, 1.5, 1.5),
    (2, -2.54, 0.0, 2.0, 2.0),
    (3,  2.54, 0.0, 2.0, 2.0),
], "size": (6.35, 5.0)}

# Voltage regulator: LM2596 TO-263-5
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

# PCB antenna (chip, for BLE)
FP["ANT_CHIP"] = {"pads": [
    (1, -3.0, 0.0, 1.5, 1.0),
    (2,  3.0, 0.0, 1.5, 1.0),
], "size": (7.0, 2.0)}

# Crystal oscillator 3.2x2.5mm (for nRF5340)
FP["XTAL_3225"] = {"pads": [
    (1, -1.1, -0.8, 1.0, 0.8),
    (2,  1.1, -0.8, 1.0, 0.8),
    (3,  1.1,  0.8, 1.0, 0.8),
    (4, -1.1,  0.8, 1.0, 0.8),
], "size": (3.2, 2.5)}


# -- Components ---------------------------------------------------------------
PARTS = {
    # -- Pi CM5 connectors (center of board) --
    "J1": {"fp": "CM5_CONN", "x": 70.0, "y": 55.0, "rot": 0,
            "part": "DF40HC(3.0)-100DS-0.4V", "lcsc": "C2906057",
            "label": "CM5 Conn A", "color": "#006064"},
    "J2": {"fp": "CM5_CONN", "x": 70.0, "y": 62.0, "rot": 0,
            "part": "DF40HC(3.0)-100DS-0.4V", "lcsc": "C2906057",
            "label": "CM5 Conn B", "color": "#006064"},

    # -- nRF5340 BLE Audio (top-left) --
    "U2": {"fp": "NRF5340", "x": 25.0, "y": 20.0, "rot": 0,
            "part": "nRF5340-QKAA-R7", "lcsc": "C2676182",
            "label": "nRF5340\nBLE Audio", "color": "#0d47a1"},

    # -- DW3720 UWB (top-right) --
    "U3": {"fp": "DW3720", "x": 115.0, "y": 20.0, "rot": 0,
            "part": "DW3720 (Qorvo QFN-48)", "lcsc": "C5264783",
            "label": "DW3720\nUWB", "color": "#880e4f"},

    # -- ES9038Q2M Quad DAC (bottom, isolated analog section) --
    "U4": {"fp": "ES9038", "x": 55.0, "y": 100.0, "rot": 0,
            "part": "ES9038Q2M", "lcsc": "C5181918",
            "label": "ES9038Q2M\nQuad DAC", "color": "#4a148c"},

    # -- ADCs (2x PCM1808) --
    "U5": {"fp": "PCM1808", "x": 25.0, "y": 65.0, "rot": 0,
            "part": "PCM1808PWR", "lcsc": "C108818",
            "label": "PCM1808\nADC 1", "color": "#1a237e"},
    "U6": {"fp": "PCM1808", "x": 25.0, "y": 80.0, "rot": 0,
            "part": "PCM1808PWR", "lcsc": "C108818",
            "label": "PCM1808\nADC 2", "color": "#1a237e"},

    # -- TPA6120A2 headphone amp --
    "U7": {"fp": "TPA6120", "x": 75.0, "y": 108.0, "rot": 0,
            "part": "TPA6120A2", "lcsc": "C87345",
            "label": "TPA6120A2\nHP Amp", "color": "#e65100"},

    # -- TPA3116D2 monitor speaker amp --
    "U8": {"fp": "TPA3116", "x": 40.0, "y": 108.0, "rot": 0,
            "part": "TPA3116D2DADR", "lcsc": "C37833",
            "label": "TPA3116\n2x50W", "color": "#b71c1c"},

    # -- 5V Buck --
    "U9": {"fp": "TO263", "x": 120.0, "y": 15.0, "rot": 0,
            "part": "LM2596S-5.0/NOPB", "lcsc": "C29781",
            "label": "LM2596\n5V Buck", "color": "#4e342e"},

    # -- 3.3V LDO --
    "U10": {"fp": "SOT223", "x": 100.0, "y": 15.0, "rot": 0,
             "part": "AMS1117-3.3", "lcsc": "C6186",
             "label": "AMS1117\n3.3V", "color": "#4e342e"},

    # -- USB-C PD (top edge) --
    "J3": {"fp": "USBC", "x": 70.0, "y": 3.0, "rot": 0,
            "part": "TYPE-C-16PIN-2MD (PD 5V/12V)", "lcsc": "C2765186",
            "label": "USB-C\nPD", "color": "#78909c"},

    # -- RJ45 Ethernet (top edge) --
    "J4": {"fp": "RJ45", "x": 50.0, "y": 7.0, "rot": 0,
            "part": "HR911105A (10/100 w/ magnetics)", "lcsc": "C12084",
            "label": "RJ45\nEthernet", "color": "#263238"},

    # -- HDMI (top edge) --
    "J5": {"fp": "HDMI", "x": 90.0, "y": 3.0, "rot": 0,
            "part": "HDMI-A-19P", "lcsc": "C138388",
            "label": "HDMI\nDisplay", "color": "#37474f"},

    # -- Toslink ADAT IN (right edge) --
    "J6": {"fp": "TOSLINK", "x": 132.0, "y": 50.0, "rot": 0,
            "part": "PLT133/T10W Toslink RX", "lcsc": "C496841",
            "label": "ADAT\nIN", "color": "#1565c0"},

    # -- Toslink ADAT OUT (right edge) --
    "J7": {"fp": "TOSLINK", "x": 132.0, "y": 65.0, "rot": 0,
            "part": "PLR135/T10W Toslink TX", "lcsc": "C496842",
            "label": "ADAT\nOUT", "color": "#1565c0"},

    # -- BNC Word Clock IN (right edge) --
    "J8": {"fp": "BNC", "x": 132.0, "y": 82.0, "rot": 0,
            "part": "BNC-50ohm PCB mount", "lcsc": "C97583",
            "label": "WCLK\nIN", "color": "#6a1b9a"},

    # -- M.2 2242 NVMe (next to CM5) --
    "J9": {"fp": "M2_SOCKET", "x": 95.0, "y": 45.0, "rot": 0,
            "part": "M.2 M-key 2242 socket", "lcsc": "C5121839",
            "label": "M.2 NVMe\n2242", "color": "#37474f"},

    # -- 6.35mm TRS jacks (4x, left edge) --
    "J10": {"fp": "TRS_635MM", "x": 10.0, "y": 35.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "TRS 1\nInput", "color": "#263238"},
    "J11": {"fp": "TRS_635MM", "x": 10.0, "y": 52.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "TRS 2\nInput", "color": "#263238"},
    "J12": {"fp": "TRS_635MM", "x": 10.0, "y": 69.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "TRS 3\nInput", "color": "#263238"},
    "J13": {"fp": "TRS_635MM", "x": 10.0, "y": 86.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "TRS 4\nInput", "color": "#263238"},

    # -- XLR combo jacks (2x, bottom-left) --
    "J14": {"fp": "XLR_COMBO", "x": 10.0, "y": 108.0, "rot": 0,
             "part": "NCJ6FA-V XLR/TRS Combo", "lcsc": "",
             "label": "XLR 1", "color": "#1b5e20"},
    "J15": {"fp": "XLR_COMBO", "x": 35.0, "y": 108.0, "rot": 0,
             "part": "NCJ6FA-V XLR/TRS Combo", "lcsc": "",
             "label": "XLR 2", "color": "#1b5e20"},

    # -- Speakon NL4 outputs (2x, bottom edge) --
    "J16": {"fp": "SPEAKON", "x": 100.0, "y": 108.0, "rot": 0,
             "part": "NL4MP", "lcsc": "",
             "label": "Speakon\nMain", "color": "#263238"},
    "J17": {"fp": "SPEAKON", "x": 125.0, "y": 108.0, "rot": 0,
             "part": "NL4MP", "lcsc": "",
             "label": "Speakon\nMon", "color": "#263238"},

    # -- Headphone out (bottom edge) --
    "J18": {"fp": "TRS_635MM", "x": 85.0, "y": 113.0, "rot": 0,
             "part": "6.35mm TRS Stereo", "lcsc": "C381135",
             "label": "HP\nOut", "color": "#e65100"},

    # -- SD Card slot --
    "J19": {"fp": "SD_SLOT", "x": 35.0, "y": 5.0, "rot": 0,
             "part": "Micro-SD push-push", "lcsc": "C585353",
             "label": "SD Card", "color": "#455a64"},

    # -- SMA UWB antenna (top-right edge) --
    "J20": {"fp": "SMA", "x": 133.0, "y": 15.0, "rot": 0,
             "part": "SMA Edge-Mount", "lcsc": "C496549",
             "label": "SMA\nUWB", "color": "#ff6f00"},

    # -- BLE chip antenna (top-left edge) --
    "J21": {"fp": "ANT_CHIP", "x": 15.0, "y": 10.0, "rot": 0,
             "part": "2.4GHz chip antenna", "lcsc": "C318411",
             "label": "BLE\nAnt", "color": "#0d47a1"},

    # -- nRF5340 32MHz crystal --
    "Y1": {"fp": "XTAL_3225", "x": 18.0, "y": 25.0, "rot": 0,
            "part": "32MHz 3.2x2.5mm", "lcsc": "C255909",
            "label": "32M", "color": "#455a64"},

    # -- nRF5340 32.768kHz crystal --
    "Y2": {"fp": "0603", "x": 32.0, "y": 25.0, "rot": 0,
            "part": "32.768kHz", "lcsc": "C32346",
            "label": "32K", "color": "#455a64"},

    # -- Status LEDs (6x) --
    "LED1": {"fp": "WS2812B", "x": 55.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "PWR", "color": "#4caf50"},
    "LED2": {"fp": "WS2812B", "x": 60.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "SYNC", "color": "#2196f3"},
    "LED3": {"fp": "WS2812B", "x": 65.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "CLIP", "color": "#f44336"},
    "LED4": {"fp": "WS2812B", "x": 70.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "STRM", "color": "#ff9800"},
    "LED5": {"fp": "WS2812B", "x": 75.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "BLE", "color": "#0d47a1"},
    "LED6": {"fp": "WS2812B", "x": 80.0, "y": 10.0, "rot": 0,
              "part": "WS2812B-5050", "lcsc": "C114586",
              "label": "UWB", "color": "#880e4f"},

    # -- DIP Switch --
    "SW1": {"fp": "DIP4", "x": 115.0, "y": 35.0, "rot": 0,
             "part": "4-pos DIP switch", "lcsc": "C15781",
             "label": "CH CFG", "color": "#455a64"},

    # -- Reset button --
    "SW2": {"fp": "SW", "x": 130.0, "y": 35.0, "rot": 0,
             "part": "EVQP0N02B", "lcsc": "C2936178",
             "label": "RST", "color": "#455a64"},

    # -- Mounting holes --
    "MH1": {"fp": "M4_HOLE", "x": 4.0, "y": 4.0, "rot": 0,
              "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH2": {"fp": "M4_HOLE", "x": 136.0, "y": 4.0, "rot": 0,
              "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH3": {"fp": "M4_HOLE", "x": 4.0, "y": 116.0, "rot": 0,
              "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},
    "MH4": {"fp": "M4_HOLE", "x": 136.0, "y": 116.0, "rot": 0,
              "part": "M4 mounting hole", "lcsc": "", "label": "M4", "color": "#333"},

    # -- Buck converter external components --
    "D1": {"fp": "SMB", "x": 115.0, "y": 25.0, "rot": 0,
            "part": "SS34 (3A Schottky)", "lcsc": "C8678",
            "label": "D1", "color": "#263238"},
    "L1": {"fp": "IND_12MM", "x": 108.0, "y": 25.0, "rot": 0,
            "part": "33uH 3A", "lcsc": "C408428",
            "label": "33uH", "color": "#006064"},
    "C1": {"fp": "CAP_8MM", "x": 128.0, "y": 25.0, "rot": 0,
            "part": "680uF/35V", "lcsc": "C249462",
            "label": "680u", "color": "#1a237e"},
    "C2": {"fp": "CAP_8MM", "x": 98.0, "y": 25.0, "rot": 0,
            "part": "220uF/10V", "lcsc": "C65221",
            "label": "220u", "color": "#1a237e"},

    # -- Decoupling caps --
    # CM5 bypass
    "C3": {"fp": "0805", "x": 65.0, "y": 52.0, "rot": 0,
            "part": "100nF", "lcsc": "C49678", "label": "C3", "color": "#1a237e"},
    "C4": {"fp": "0805", "x": 75.0, "y": 52.0, "rot": 0,
            "part": "10uF", "lcsc": "C15850", "label": "C4", "color": "#1a237e"},
    # nRF5340 bypass
    "C5": {"fp": "0402", "x": 20.0, "y": 16.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C5", "color": "#1a237e"},
    "C6": {"fp": "0402", "x": 30.0, "y": 16.0, "rot": 0,
            "part": "10nF", "lcsc": "C15195", "label": "C6", "color": "#1a237e"},
    "C7": {"fp": "0402", "x": 20.0, "y": 28.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C7", "color": "#1a237e"},
    "C8": {"fp": "0402", "x": 30.0, "y": 28.0, "rot": 0,
            "part": "4.7uF", "lcsc": "C23733", "label": "C8", "color": "#1a237e"},
    # DW3720 bypass
    "C9": {"fp": "0402", "x": 110.0, "y": 16.0, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C9", "color": "#1a237e"},
    "C10": {"fp": "0402", "x": 120.0, "y": 28.0, "rot": 0,
             "part": "10nF", "lcsc": "C15195", "label": "C10", "color": "#1a237e"},
    # ES9038Q2M bypass (audiophile grade)
    "C11": {"fp": "0805", "x": 50.0, "y": 95.0, "rot": 0,
             "part": "100nF C0G", "lcsc": "C1808", "label": "C11", "color": "#4a148c"},
    "C12": {"fp": "0805", "x": 60.0, "y": 95.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C12", "color": "#4a148c"},
    "C13": {"fp": "0805", "x": 50.0, "y": 105.0, "rot": 0,
             "part": "100nF C0G", "lcsc": "C1808", "label": "C13", "color": "#4a148c"},
    "C14": {"fp": "0805", "x": 60.0, "y": 105.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C14", "color": "#4a148c"},
    # ADC bypass
    "C15": {"fp": "0805", "x": 20.0, "y": 62.0, "rot": 0,
             "part": "100nF", "lcsc": "C49678", "label": "C15", "color": "#1a237e"},
    "C16": {"fp": "0805", "x": 30.0, "y": 62.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C16", "color": "#1a237e"},
    "C17": {"fp": "0805", "x": 20.0, "y": 77.0, "rot": 0,
             "part": "100nF", "lcsc": "C49678", "label": "C17", "color": "#1a237e"},
    "C18": {"fp": "0805", "x": 30.0, "y": 77.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C18", "color": "#1a237e"},
    # TPA3116 bypass
    "C19": {"fp": "1206", "x": 35.0, "y": 104.0, "rot": 0,
             "part": "10uF/50V", "lcsc": "C13585", "label": "C19", "color": "#1a237e"},
    "C20": {"fp": "0805", "x": 45.0, "y": 104.0, "rot": 0,
             "part": "100nF", "lcsc": "C49678", "label": "C20", "color": "#1a237e"},
    # TPA6120 bypass
    "C21": {"fp": "0805", "x": 70.0, "y": 104.0, "rot": 0,
             "part": "100nF", "lcsc": "C49678", "label": "C21", "color": "#e65100"},
    "C22": {"fp": "0805", "x": 80.0, "y": 104.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C22", "color": "#e65100"},
    # LDO caps
    "C23": {"fp": "0805", "x": 95.0, "y": 18.0, "rot": 0,
             "part": "10uF", "lcsc": "C15850", "label": "C23", "color": "#1a237e"},
    "C24": {"fp": "0805", "x": 105.0, "y": 18.0, "rot": 0,
             "part": "22uF", "lcsc": "C45783", "label": "C24", "color": "#1a237e"},
    # ES9038 analog output filter caps
    "C25": {"fp": "0805", "x": 48.0, "y": 100.0, "rot": 90,
             "part": "2.2nF C0G", "lcsc": "C1809", "label": "C25", "color": "#4a148c"},
    "C26": {"fp": "0805", "x": 62.0, "y": 100.0, "rot": 90,
             "part": "2.2nF C0G", "lcsc": "C1809", "label": "C26", "color": "#4a148c"},

    # -- Resistors --
    # USB CC pull-down
    "R1": {"fp": "0402", "x": 66.0, "y": 6.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R1", "color": "#5d4037"},
    "R2": {"fp": "0402", "x": 74.0, "y": 6.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R2", "color": "#5d4037"},
    # TPA3116 gain set
    "R3": {"fp": "0805", "x": 35.0, "y": 112.0, "rot": 90,
            "part": "200k", "lcsc": "C17574", "label": "R3", "color": "#5d4037"},
    "R4": {"fp": "0805", "x": 45.0, "y": 112.0, "rot": 90,
            "part": "200k", "lcsc": "C17574", "label": "R4", "color": "#5d4037"},
    # LED data resistor
    "R5": {"fp": "0402", "x": 52.0, "y": 10.0, "rot": 0,
            "part": "330R", "lcsc": "C25104", "label": "R5", "color": "#5d4037"},
    # PCM1808 FMT pull (I2S mode)
    "R6": {"fp": "0402", "x": 25.0, "y": 59.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R6", "color": "#5d4037"},
    "R7": {"fp": "0402", "x": 25.0, "y": 74.0, "rot": 0,
            "part": "10k", "lcsc": "C25744", "label": "R7", "color": "#5d4037"},
    # ES9038 I2C address pull
    "R8": {"fp": "0402", "x": 55.0, "y": 93.0, "rot": 0,
            "part": "4.7k", "lcsc": "C25900", "label": "R8", "color": "#5d4037"},
    "R9": {"fp": "0402", "x": 55.0, "y": 107.0, "rot": 0,
            "part": "4.7k", "lcsc": "C25900", "label": "R9", "color": "#5d4037"},
    # TPA6120 gain resistors
    "R10": {"fp": "0805", "x": 70.0, "y": 112.0, "rot": 0,
             "part": "1k", "lcsc": "C17513", "label": "R10", "color": "#5d4037"},
    "R11": {"fp": "0805", "x": 80.0, "y": 112.0, "rot": 0,
             "part": "1k", "lcsc": "C17513", "label": "R11", "color": "#5d4037"},
    # BNC word clock termination
    "R12": {"fp": "0805", "x": 128.0, "y": 78.0, "rot": 90,
             "part": "75R", "lcsc": "C17760", "label": "R12", "color": "#5d4037"},
    # nRF5340 32MHz load caps (integrated into crystal pads)
    "R13": {"fp": "0402", "x": 18.0, "y": 30.0, "rot": 0,
             "part": "1M", "lcsc": "C26083", "label": "R13", "color": "#5d4037"},
}


# -- Routes --------------------------------------------------------------------
ROUTES = [
    # USB-C -> buck -> LDO -> 3.3V
    ("+5V_USB", PWR, [(70.0, 3.0), (70.0, 8.0), (120.0, 8.0), (120.0, 15.0)]),
    ("+5V", PWR, [(108.0, 25.0), (100.0, 25.0), (100.0, 15.0)]),          # Buck -> LDO
    ("+5V", PWR, [(100.0, 25.0), (70.0, 25.0), (70.0, 55.0)]),            # 5V -> CM5
    ("+3V3", TRACE, [(100.0, 18.25), (70.0, 18.0), (70.0, 35.0)]),        # LDO -> logic
    ("+3V3", TRACE, [(70.0, 18.0), (55.0, 10.0)]),                         # -> LED1
    ("+3V3", TRACE, [(70.0, 35.0), (25.0, 20.0)]),                         # -> nRF5340
    ("+3V3", TRACE, [(70.0, 35.0), (115.0, 20.0)]),                        # -> DW3720
    ("+3V3", TRACE, [(70.0, 35.0), (55.0, 100.0)]),                        # -> ES9038
    ("+3V3", TRACE, [(70.0, 35.0), (25.0, 65.0)]),                         # -> ADC1
    ("+3V3", TRACE, [(25.0, 65.0), (25.0, 80.0)]),                         # -> ADC2

    # I2S: CM5 -> ES9038Q2M (main quad DAC)
    ("I2S_MCLK",  TRACE, [(70.0-9.8, 55.0), (55.0-5.3, 98.5)]),           # CM5 -> ES9038
    ("I2S_BCK1",  TRACE, [(70.0-9.8+0.4, 55.0), (55.0-5.3, 99.0)]),
    ("I2S_LRCK1", TRACE, [(70.0-9.8+0.8, 55.0), (55.0-5.3, 99.5)]),
    ("I2S_DIN1",  TRACE, [(70.0-9.8+1.2, 55.0), (55.0-5.3, 100.0)]),

    # I2S: ADCs -> CM5
    ("I2S_BCK3",  TRACE, [(25.0-3.75, 63.5), (70.0-9.8+2.0, 55.0)]),     # ADC1 -> CM5
    ("I2S_LRCK3", TRACE, [(25.0-3.75, 64.15), (70.0-9.8+2.4, 55.0)]),
    ("I2S_DOUT3", TRACE, [(25.0-3.75, 64.8), (70.0-9.8+2.8, 55.0)]),
    ("I2S_BCK4",  TRACE, [(25.0-3.75, 78.5), (70.0-9.8+3.2, 55.0)]),     # ADC2 -> CM5
    ("I2S_LRCK4", TRACE, [(25.0-3.75, 79.15), (70.0-9.8+3.6, 55.0)]),
    ("I2S_DOUT4", TRACE, [(25.0-3.75, 79.8), (70.0-9.8+4.0, 55.0)]),

    # I2S: nRF5340 BLE Audio -> CM5
    ("BLE_I2S",   TRACE, [(25.0+3.5, 20.0), (45.0, 35.0), (70.0-9.8+5.0, 55.0)]),

    # Analog: ES9038 main L/R -> Speakon Main
    ("MAIN_L", TRACE, [(55.0-5.3, 101.0), (45.0, 101.0),
                        (45.0, 95.0), (100.0-5.0, 103.0)]),
    ("MAIN_R", TRACE, [(55.0-5.3, 101.5), (45.0, 102.0),
                        (45.0, 96.0), (100.0-5.0, 106.0)]),

    # Analog: ES9038 monitor L/R -> TPA3116 -> Speakon Mon
    ("MON_L", TRACE, [(55.0+5.3, 99.0), (55.0, 108.0), (40.0-5.35, 106.0)]),
    ("MON_R", TRACE, [(55.0+5.3, 99.5), (55.0, 109.0), (40.0-5.35, 107.0)]),
    ("SPK_MON+", PWR, [(40.0+5.35, 105.0), (60.0, 95.0), (125.0-5.0, 103.0)]),
    ("SPK_MON-", PWR, [(40.0+5.35, 107.0), (60.0, 97.0), (125.0-5.0, 106.0)]),

    # Analog: ES9038 HP L/R -> TPA6120A2 -> headphone jack
    ("HP_L", TRACE, [(55.0+5.3, 100.5), (65.0, 108.0), (75.0-3.81, 108.0-3.175)]),
    ("HP_R", TRACE, [(55.0+5.3, 101.0), (65.0, 109.0), (75.0-3.81+2.54, 108.0-3.175)]),
    ("HP_OUT_L", TRACE, [(75.0+3.81-2.54, 108.0+3.175), (85.0-4.0, 115.0-4.0)]),
    ("HP_OUT_R", TRACE, [(75.0+3.81, 108.0+3.175), (85.0+4.0, 115.0-4.0)]),

    # TRS inputs -> ADCs
    ("TRS1_TIP", TRACE, [(10.0-4.0, 35.0-4.0), (18.0, 30.0),
                          (25.0-3.75, 65.0-2.0)]),
    ("TRS2_TIP", TRACE, [(10.0-4.0, 52.0-4.0), (18.0, 48.0),
                          (25.0-3.75, 65.0+1.0)]),
    ("TRS3_TIP", TRACE, [(10.0-4.0, 69.0-4.0), (18.0, 66.0),
                          (25.0-3.75, 80.0-2.0)]),
    ("TRS4_TIP", TRACE, [(10.0-4.0, 86.0-4.0), (18.0, 83.0),
                          (25.0-3.75, 80.0+1.0)]),

    # XLR inputs -> ADCs (via summing)
    ("XLR1_HOT", TRACE, [(10.0, 108.0-5.0), (18.0, 100.0),
                          (20.0, 70.0), (25.0-3.75, 65.0+2.0)]),
    ("XLR2_HOT", TRACE, [(35.0, 108.0-5.0), (38.0, 100.0),
                          (20.0, 85.0), (25.0-3.75, 80.0+2.0)]),

    # ADAT: CM5 -> Toslink
    ("ADAT_TX", TRACE, [(70.0+9.8, 62.0), (100.0, 65.0), (132.0-5.0, 65.0)]),
    ("ADAT_RX", TRACE, [(132.0-5.0, 50.0), (100.0, 50.0), (70.0+9.8-0.4, 62.0)]),

    # Word clock: BNC -> CM5 (via buffer)
    ("WCLK_IN", TRACE, [(132.0, 82.0), (120.0, 82.0), (70.0+9.8-0.8, 62.0)]),

    # M.2 NVMe: PCIe from CM5
    ("PCIE_TX", TRACE, [(70.0+9.8-1.2, 62.0), (85.0, 45.0), (95.0-11.0, 45.0)]),
    ("PCIE_RX", TRACE, [(70.0+9.8-1.6, 62.0), (85.0, 43.0), (95.0-11.0, 43.0)]),

    # UWB antenna
    ("UWB_ANT", TRACE, [(115.0+3.25, 20.0-2.75), (125.0, 15.0), (133.0, 15.0)]),

    # SPI: CM5 -> DW3720
    ("SPI_DW", TRACE, [(70.0+9.8-2.0, 62.0), (100.0, 30.0), (115.0-3.25, 20.0)]),

    # SPI: CM5 -> nRF5340 (secondary link)
    ("SPI_NRF", TRACE, [(70.0-9.8+6.0, 55.0), (45.0, 40.0), (25.0+3.5, 24.6)]),

    # Ethernet: CM5 -> RJ45
    ("ETH", TRACE, [(70.0-9.8+7.0, 55.0), (50.0, 30.0), (50.0, 7.0)]),

    # HDMI: CM5 -> HDMI connector
    ("HDMI", TRACE, [(70.0+9.8-3.0, 62.0), (85.0, 30.0), (90.0, 3.0)]),

    # SD: CM5 -> SD slot
    ("SD_DAT", TRACE, [(70.0-9.8+8.0, 55.0), (45.0, 25.0), (35.0, 5.0)]),

    # LED chain
    ("LED_DIN",  TRACE, [(70.0-9.8+9.0, 55.0), (52.0, 10.0)]),
    ("LED_CH1",  TRACE, [(55.0+2.45, 10.0+1.6), (60.0-2.45, 10.0-1.6)]),
    ("LED_CH2",  TRACE, [(60.0+2.45, 10.0+1.6), (65.0-2.45, 10.0-1.6)]),
    ("LED_CH3",  TRACE, [(65.0+2.45, 10.0+1.6), (70.0-2.45, 10.0-1.6)]),
    ("LED_CH4",  TRACE, [(70.0+2.45, 10.0+1.6), (75.0-2.45, 10.0-1.6)]),
    ("LED_CH5",  TRACE, [(75.0+2.45, 10.0+1.6), (80.0-2.45, 10.0-1.6)]),

    # USB data (CM5)
    ("USB_D+", 0.2, [(70.0+0.25, 3.0), (70.0+1.0, 25.0), (70.0+0.4, 55.0)]),
    ("USB_D-", 0.2, [(70.0-0.25, 3.0), (70.0-1.0, 25.0), (70.0-0.4, 55.0)]),

    # USB CC
    ("CC1", TRACE, [(66.0, 6.0), (70.0-1.75, 3.0)]),
    ("CC2", TRACE, [(74.0, 6.0), (70.0+1.75, 3.0)]),

    # DIP switch -> CM5 GPIO
    ("DIP", TRACE, [(115.0, 35.0), (100.0, 40.0), (70.0+9.8-4.0, 62.0)]),

    # Reset
    ("RST", TRACE, [(130.0+3.25, 35.0), (70.0+9.8-5.0, 62.0)]),

    # I2C: CM5 -> ES9038 control
    ("I2C_SDA", TRACE, [(70.0-9.8+10.0, 55.0), (55.0+5.3, 98.0)]),
    ("I2C_SCL", TRACE, [(70.0-9.8+10.4, 55.0), (55.0+5.3, 98.5)]),

    # nRF5340 crystal connections
    ("XTAL_32M", TRACE, [(25.0-3.5, 20.0+2.0), (18.0, 25.0)]),
    ("XTAL_32K", TRACE, [(25.0+3.5, 20.0+2.0), (32.0, 25.0)]),

    # BLE antenna
    ("BLE_ANT", TRACE, [(25.0-3.5, 20.0-4.6), (15.0, 10.0)]),
]

VIAS = [
    # Grid pattern for ground stitching
    (10, 10), (30, 10), (50, 10), (70, 10), (90, 10), (110, 10), (130, 10),
    (10, 30), (30, 30), (50, 30), (70, 30), (90, 30), (110, 30), (130, 30),
    (10, 50), (30, 50), (50, 50), (70, 50), (90, 50), (110, 50), (130, 50),
    (10, 70), (30, 70), (50, 70), (70, 70), (90, 70), (110, 70), (130, 70),
    (10, 90), (30, 90), (50, 90), (70, 90), (90, 90), (110, 90), (130, 90),
    (10, 110), (30, 110), (50, 110), (70, 110), (90, 110), (110, 110), (130, 110),
    (20, 20), (40, 20), (60, 20), (80, 20), (100, 20), (120, 20),
    (20, 40), (40, 40), (60, 40), (80, 40), (100, 40), (120, 40),
    (20, 60), (40, 60), (60, 60), (80, 60), (100, 60), (120, 60),
    (20, 80), (40, 80), (60, 80), (80, 80), (100, 80), (120, 80),
    (20, 100), (40, 100), (60, 100), (80, 100), (100, 100), (120, 100),
    # Extra GND vias near TPA3116 thermal pad
    (38, 108), (40, 111), (42, 108), (40, 105),
    # Extra GND vias near DW3720
    (113, 20), (115, 23), (117, 20), (115, 17),
    # Extra GND vias near nRF5340
    (23, 20), (25, 23), (27, 20), (25, 17),
    # Extra GND vias near ES9038 analog section (critical)
    (53, 100), (55, 103), (57, 100), (55, 97),
    (50, 98), (60, 98), (50, 102), (60, 102),
]


# -- Helpers -------------------------------------------------------------------
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
            f.write(f"G04 Koe HUB v2 {s.name}*\n%LPD*%\n")
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
            f.write("M48\n; Koe HUB v2 140x120mm Pi CM5 Pro Audio Carrier\nFMAT,2\nMETRIC,TZ\n")
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
    th_refs = ("J4", "J10", "J11", "J12", "J13", "J14", "J15",
               "J16", "J17", "J18", "J6", "J7", "J8")
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

    # TPA6120 DIP-8 drills
    fp = FP["TPA6120"]
    c = PARTS["U7"]
    for p in fp["pads"]:
        pin, px, py, pw, ph = p
        ax, ay = xform(px, py, c["x"], c["y"], c.get("rot", 0))
        dr.hole(ax, ay, 0.9)

    # Ground copper pour (back copper = full GND)
    bc.rect(1, 1, BOARD_W - 1, BOARD_H - 1, 0.3)

    # Analog ground plane isolation slot (between digital and analog sections)
    # Narrow slot at y=92 to separate analog audio ground from digital ground
    ec.trace(35.0, 92.0, 90.0, 92.0, 0.05)

    pre = "koe-hub-v2"
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


# -- SVG -----------------------------------------------------------------------
def gen_svg():
    S = 5; pad = 60; img_w = int(BOARD_W * S + pad * 2); img_h = int(BOARD_H * S + pad * 2)
    ox, oy = pad, pad + 20

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{img_w}" height="{img_h + 220}">
<defs>
  <linearGradient id="pcb" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#0d5c0d"/><stop offset="100%" stop-color="#063806"/>
  </linearGradient>
  <linearGradient id="analog" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" stop-color="#1a0a2e"/><stop offset="100%" stop-color="#0d0520"/>
  </linearGradient>
  <filter id="sh"><feDropShadow dx="1" dy="2" stdDeviation="2" flood-opacity="0.4"/></filter>
</defs>
<rect width="{img_w}" height="{img_h + 220}" fill="#0d0d14"/>

<!-- Title -->
<text x="{img_w // 2}" y="22" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="16" font-weight="600">Koe Hub v2 -- Pi CM5 Pro Audio Carrier Board</text>
<text x="{img_w // 2}" y="40" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">140x120mm | 4-layer FR-4 | ES9038Q2M DAC | nRF5340 BLE Audio | ADAT | TPA6120A2 HP | M.2 NVMe | DW3720 UWB</text>

<!-- Board -->
<rect x="{ox - 2}" y="{oy - 2}" width="{BOARD_W * S + 4}" height="{BOARD_H * S + 4}" fill="#000" opacity="0.3" rx="3"/>
<rect x="{ox}" y="{oy}" width="{BOARD_W * S}" height="{BOARD_H * S}" fill="url(#pcb)" stroke="#c8a83e" stroke-width="1.5" rx="2"/>
'''

    # GND pour hint
    svg += f'<rect x="{ox + 4}" y="{oy + 4}" width="{BOARD_W * S - 8}" height="{BOARD_H * S - 8}" fill="none" stroke="#1a5c1a" stroke-width="0.5" stroke-dasharray="4,4" rx="1"/>\n'

    # Analog isolation zone (below y=92)
    analog_y = oy + 92 * S
    svg += f'<rect x="{ox + 30 * S}" y="{analog_y}" width="{65 * S}" height="{(BOARD_H - 92) * S}" fill="url(#analog)" opacity="0.25" rx="2"/>\n'
    svg += f'<text x="{ox + 62 * S}" y="{analog_y + 8}" text-anchor="middle" fill="#7c4dff" font-family="monospace" font-size="6" opacity="0.6">isolated analog ground plane</text>\n'

    # Amp thermal relief zone
    amp = PARTS["U8"]
    ax, ay = ox + amp["x"] * S, oy + amp["y"] * S
    svg += f'<rect x="{ax - 30}" y="{ay - 20}" width="60" height="40" fill="#4a2800" opacity="0.15" rx="3"/>\n'
    svg += f'<text x="{ax}" y="{ay + 28}" text-anchor="middle" fill="#8b4513" font-family="monospace" font-size="5" opacity="0.5">thermal relief</text>\n'

    # Traces
    net_colors = {
        "5V": "#ff7043", "3V3": "#66bb6a", "USB": "#ffca28",
        "I2S": "#42a5f5", "I2C": "#42a5f5", "SPI": "#42a5f5",
        "MAIN": "#ce93d8", "MON": "#ef9a9a", "SPK": "#ff5722",
        "HP": "#ff6d00", "TRS": "#80cbc4", "XLR": "#a5d6a7",
        "UWB": "#e91e63", "BLE": "#448aff", "LED": "#f9a825",
        "ETH": "#78909c", "HDMI": "#90a4ae", "SD": "#bcaaa4",
        "ADAT": "#7c4dff", "WCLK": "#7c4dff", "PCIE": "#ff4081",
        "DIP": "#b0bec5", "CC": "#78909c", "RST": "#78909c",
        "XTAL": "#78909c",
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
        rx = 3 if ref[0] in "UJY" else 1
        svg += f'<rect x="{-rw / 2}" y="{-rh / 2}" width="{rw}" height="{rh}" fill="{color}" stroke="#777" stroke-width="0.5" rx="{rx}"/>\n'
        if ref[0] == "U":
            svg += f'<circle cx="{-rw / 2 + 4}" cy="{-rh / 2 + 4}" r="1.5" fill="#aaa" opacity="0.4"/>\n'
        label = c.get("label", ref)
        lines = label.split('\n')
        for li, line in enumerate(lines):
            fy = 4 + (li - len(lines) / 2) * 10
            fs = 5 if ref[0] in "RCLDLY" else 7
            if ref.startswith("LED") or ref.startswith("SW"): fs = 6
            svg += f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="{fs}">{line}</text>\n'
        svg += '</g>\n'

    # Legend
    ly = img_h + 15
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="9">140x120mm | 4-layer | {len(PARTS)} parts | Pi CM5 + nRF5340 BLE + DW3720 UWB + ES9038Q2M DAC + ADAT + NVMe</text>\n'

    # Signal flow (analog)
    ly += 22
    flow_items = [
        ("Inputs", "#80cbc4"), ("PCM1808", "#1a237e"), ("I2S", "#42a5f5"),
        ("Pi CM5", "#006064"), ("I2S", "#42a5f5"), ("ES9038Q2M", "#4a148c"),
        ("TPA6120A2", "#e65100"), ("HP Out", "#ff6d00"),
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

    # Signal flow (digital/wireless)
    ly += 22
    flow_items2 = [
        ("BLE Audio", "#0d47a1"), ("nRF5340", "#0d47a1"), ("I2S", "#42a5f5"),
        ("Pi CM5", "#006064"), ("ADAT", "#7c4dff"), ("Toslink", "#1565c0"),
    ]
    total_w2 = sum(len(t) * 6.5 + 20 for t, _ in flow_items2)
    fx = (img_w - total_w2) / 2
    for i, (text, col) in enumerate(flow_items2):
        tw = len(text) * 6.5 + 10
        svg += f'<rect x="{fx}" y="{ly - 10}" width="{tw}" height="16" fill="{col}" rx="3" opacity="0.7"/>\n'
        svg += f'<text x="{fx + tw / 2}" y="{ly + 2}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="8">{text}</text>\n'
        fx += tw + 5
        if i < len(flow_items2) - 1:
            svg += f'<text x="{fx - 2}" y="{ly + 2}" text-anchor="middle" fill="#888" font-family="monospace" font-size="10">&#8594;</text>\n'

    # Power flow
    ly += 28
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#ef5350" font-family="monospace" font-size="9" font-weight="bold">USB-C PD 5V/12V &#8594; LM2596 5V (Pi CM5) &#8594; AMS1117 3.3V (logic/audio)</text>\n'
    ly += 16
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">4x TRS + 2x XLR in | ADAT 8ch I/O | BNC word clock | M.2 NVMe | 2x Speakon + HP out</text>\n'

    # Price
    ly += 22
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#c8a83e" font-family="monospace" font-size="9">HUB v2 ~$52 BOM | ES9038Q2M 129dB SNR | TPA6120A2 120dB HP | nRF5340 7x BLE Audio | NVMe recording</text>\n'

    # v1 vs v2 comparison
    ly += 20
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#666" font-family="monospace" font-size="7">v1: 2x PCM5102A + DW3000 | v2: ES9038Q2M + nRF5340 BLE + ADAT + TPA6120A2 HP + M.2 NVMe + BNC WCLK</text>\n'

    svg += '</svg>\n'
    path = GBR / "koe-hub-v2-layout.svg"
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
        print(f"DRC: All components within {BOARD_W:.0f}x{BOARD_H:.0f}mm board -- OK")
    return len(errs) == 0


def main():
    print("=" * 72)
    print("Koe Hub v2 -- 140x120mm Pi CM5 Pro Audio Carrier Board")
    print(f"  {len(PARTS)} parts | Pi CM5 + nRF5340 BLE + DW3720 UWB | Pro Audio")
    print(f"  ES9038Q2M Quad DAC (129dB SNR) | 2x PCM1808 ADC")
    print(f"  TPA6120A2 Headphone Amp (120dB SNR) | TPA3116D2 2x50W")
    print(f"  ADAT 8ch I/O | BNC Word Clock | M.2 NVMe SSD")
    print(f"  4x TRS + 2x XLR in | 2x Speakon + HP out | HDMI | Ethernet")
    print("=" * 72)
    check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()
    print(f"\nSignal chain (analog):")
    print(f"  Inputs: 4x 6.35mm TRS + 2x XLR combo")
    print(f"  --> 2x PCM1808 ADC --> I2S --> Pi CM5 (DSP/mixing)")
    print(f"  --> I2S --> ES9038Q2M Quad DAC (main L/R + monitor L/R)")
    print(f"  --> Main L/R: direct to Speakon")
    print(f"  --> Monitor L/R: TPA3116D2 amp --> Speakon")
    print(f"  --> HP L/R: TPA6120A2 --> 6.35mm headphone out")
    print(f"\nSignal chain (digital):")
    print(f"  ADAT Toslink IN (8ch) --> Pi CM5 --> ADAT Toslink OUT (8ch)")
    print(f"  BNC Word Clock IN --> Pi CM5 (sample-accurate sync)")
    print(f"  M.2 NVMe --> multi-track recording direct to SSD")
    print(f"\nWireless:")
    print(f"  nRF5340 BLE Audio (7 CIS) --> I2S --> Pi CM5")
    print(f"  DW3720 UWB <--> SPI <--> Pi CM5 (sub-us sync with Pro devices)")
    print(f"\nPower:")
    print(f"  USB-C PD 5V/12V --> LM2596 5V (Pi CM5)")
    print(f"  5V --> AMS1117 --> 3.3V (logic, audio, wireless)")
    print(f"\nUpgrades from v1:")
    print(f"  DAC: 2x PCM5102A --> ES9038Q2M (129dB SNR quad DAC)")
    print(f"  NEW: nRF5340 BLE Audio receiver (7 Koe Pro devices)")
    print(f"  NEW: ADAT Toslink IN/OUT (8ch digital I/O)")
    print(f"  NEW: TPA6120A2 headphone amp (120dB SNR, 6ohm drive)")
    print(f"  NEW: M.2 2242 NVMe SSD slot (multi-track recording)")
    print(f"  NEW: BNC word clock IN (pro studio sync)")
    print(f"  UWB: DW3000 --> DW3720 (improved)")
    print(f"  BOM: ~$120 --> ~$52 (optimized)")


if __name__ == "__main__":
    main()
