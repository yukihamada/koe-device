#!/usr/bin/env python3
"""
Koe Pro v2 PCB — 45x30mm Compact Board (nRF5340 + DW3000)
==========================================================
Next-gen audio board: BLE 5.3 + UWB ranging, high-quality ADC/DAC, nPM1300 PMIC.

Board: 45x30mm, 4-layer FR-4 (signal-ground-power-signal for UWB impedance)
MCU: nRF5340-QKAA (BLE 5.3 + dual-core Cortex-M33)
UWB: DW3000 (Qorvo, QFN-48, 6x6mm) — sub-μs time sync + ranging
ADC: AK5720 (24-bit, SSOP-16) — guitar/mic line input
DAC: PCM5102A (32-bit, SSOP-20) — high-quality output
Amp: MAX98357A (I2S speaker monitor)
PMIC: nPM1300 (LiPo charger + buck + LDO integrated)
Connectors: USB-C, 3.5mm TRS, SMA (UWB antenna), PCB BLE antenna
BOM: ~$23.05
"""

import math
import zipfile
from pathlib import Path

BOARD_W = 45.0
BOARD_H = 30.0
TRACE, PWR, VIA_D, VIA_P = 0.15, 0.4, 0.25, 0.5

OUT = Path(__file__).parent / "kicad"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-pro-v2"


def in_rect(x, y, m=0.5):
    return m <= x <= BOARD_W - m and m <= y <= BOARD_H - m


# ── Footprints ────────────────────────────────────────────────────────
FP = {}

# nRF5340-QKAA: QFN-94, 7x7mm, 0.4mm pitch
# 24 pads per side (94 pads = 23+24+23+24 + exposed pad)
def _nrf5340():
    p = []
    pitch = 0.4
    # Left side: 24 pads
    for i in range(24):
        p.append((i+1, -3.5, -4.6 + i * pitch, 0.2, 0.7))
    # Bottom side: 23 pads
    for i in range(23):
        p.append((25+i, -4.4 + i * pitch, 3.5, 0.7, 0.2))
    # Right side: 24 pads
    for i in range(24):
        p.append((48+i, 3.5, 4.6 - i * pitch, 0.2, 0.7))
    # Top side: 23 pads
    for i in range(23):
        p.append((72+i, 4.4 - i * pitch, -3.5, 0.7, 0.2))
    # Exposed thermal pad
    p.append((95, 0, 0, 5.0, 5.0))
    return p

FP["NRF5340"] = {"pads": _nrf5340(), "size": (7.0, 7.0)}

# DW3000: QFN-48, 6x6mm, 0.5mm pitch
def _dw3000():
    p = []
    # 12 pads per side
    for i in range(12):
        p.append((i+1, -3.0, -2.75 + i * 0.5, 0.25, 0.8))    # Left
    for i in range(12):
        p.append((13+i, -2.75 + i * 0.5, 3.0, 0.8, 0.25))     # Bottom
    for i in range(12):
        p.append((25+i, 3.0, 2.75 - i * 0.5, 0.25, 0.8))      # Right
    for i in range(12):
        p.append((37+i, 2.75 - i * 0.5, -3.0, 0.8, 0.25))     # Top
    # Exposed thermal pad
    p.append((49, 0, 0, 4.0, 4.0))
    return p

FP["DW3000"] = {"pads": _dw3000(), "size": (6.0, 6.0)}

# AK5720: SSOP-16, 5.3x6.2mm, 0.65mm pitch
def _ak5720():
    p = []
    for i in range(8):
        p.append((i+1, -2.65, -2.275 + i * 0.65, 0.3, 1.2))
    for i in range(8):
        p.append((9+i, 2.65, -2.275 + i * 0.65, 0.3, 1.2))
    return p

FP["AK5720"] = {"pads": _ak5720(), "size": (5.3, 6.2)}

# PCM5102A: TSSOP-20, 4.4x6.5mm, 0.65mm pitch
def _pcm5102a():
    p = []
    for i in range(10):
        p.append((i+1, -2.2, -2.925 + i * 0.65, 0.3, 1.2))
    for i in range(10):
        p.append((11+i, 2.2, -2.925 + i * 0.65, 0.3, 1.2))
    return p

FP["PCM5102A"] = {"pads": _pcm5102a(), "size": (4.4, 6.5)}

# MAX98357A: QFN-16, 3x3mm, 0.5mm pitch
def _max98357():
    p = []
    for i in range(4):
        p.append((i+1, -1.5, -0.75 + i * 0.5, 0.25, 0.7))
    for i in range(4):
        p.append((5+i, -0.75 + i * 0.5, 1.5, 0.7, 0.25))
    for i in range(4):
        p.append((9+i, 1.5, 0.75 - i * 0.5, 0.25, 0.7))
    for i in range(4):
        p.append((13+i, 0.75 - i * 0.5, -1.5, 0.7, 0.25))
    p.append((17, 0, 0, 1.7, 1.7))  # Exposed pad
    return p

FP["MAX98357"] = {"pads": _max98357(), "size": (3.0, 3.0)}

# nPM1300: QFN-32, 5x5mm, 0.5mm pitch
def _npm1300():
    p = []
    # 8 pads per side
    for i in range(8):
        p.append((i+1, -2.5, -1.75 + i * 0.5, 0.25, 0.7))
    for i in range(8):
        p.append((9+i, -1.75 + i * 0.5, 2.5, 0.7, 0.25))
    for i in range(8):
        p.append((17+i, 2.5, 1.75 - i * 0.5, 0.25, 0.7))
    for i in range(8):
        p.append((25+i, 1.75 - i * 0.5, -2.5, 0.7, 0.25))
    # Exposed thermal pad
    p.append((33, 0, 0, 3.2, 3.2))
    return p

FP["NPM1300"] = {"pads": _npm1300(), "size": (5.0, 5.0)}

# 32MHz crystal: 2012 (2x1.2mm)
FP["XTAL_2012"] = {"pads": [
    (1, -0.7, 0, 0.5, 0.9),
    (2, 0.7, 0, 0.5, 0.9),
], "size": (2.0, 1.2)}

# 32.768kHz crystal: 1610 (1.6x1mm)
FP["XTAL_1610"] = {"pads": [
    (1, -0.55, 0, 0.4, 0.7),
    (2, 0.55, 0, 0.4, 0.7),
], "size": (1.6, 1.0)}

# USB-C (16-pin SMD, mid-mount)
FP["USBC"] = {"pads": [
    ("V1", -2.75, -1.0, 0.6, 1.2), ("V2", 2.75, -1.0, 0.6, 1.2),
    ("D-", -0.25, -1.0, 0.3, 1.0), ("D+", 0.25, -1.0, 0.3, 1.0),
    ("C1", -1.75, -1.0, 0.3, 1.0), ("C2", 1.75, -1.0, 0.3, 1.0),
    ("G1", -3.5, -1.0, 0.5, 1.0),  ("G2", 3.5, -1.0, 0.5, 1.0),
    ("S1", -4.15, 0.5, 0.6, 1.6),  ("S2", 4.15, 0.5, 0.6, 1.6),
], "size": (9.0, 3.5)}

# 3.5mm TRS jack (through-hole, PJ-320A)
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

# PCB BLE antenna (inverted-F, trace on layer 1)
FP["PCB_ANT"] = {"pads": [
    (1, 0.0, 0.0, 0.8, 0.8),     # Feed point
], "size": (8.0, 3.0)}

# WS2812B-2020: 2x2mm
FP["WS2812B"] = {"pads": [
    (1, -0.65, -0.55, 0.5, 0.5), (2,  0.65, -0.55, 0.5, 0.5),
    (3,  0.65,  0.55, 0.5, 0.5), (4, -0.65,  0.55, 0.5, 0.5),
], "size": (2.0, 2.0)}

# Tactile button: 3x3mm SMD
FP["SW"] = {"pads": [(1, -2.0, 0, 1.0, 0.8), (2, 2.0, 0, 1.0, 0.8)], "size": (3.0, 3.0)}

# JST-PH 2-pin (battery connector)
FP["JST_PH2"] = {"pads": [
    (1, -1.0, 0.0, 1.0, 1.5),
    (2,  1.0, 0.0, 1.0, 1.5),
], "size": (6.0, 4.5)}

# Speaker connector 2-pin
FP["SPK_CONN"] = {"pads": [
    (1, -1.0, 0.0, 1.0, 1.2),
    (2,  1.0, 0.0, 1.0, 1.2),
], "size": (4.0, 3.0)}

# Passive components
FP["0402"] = {"pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)], "size": (1.6, 0.8)}
FP["0603"] = {"pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)], "size": (2.2, 1.2)}
FP["0805"] = {"pads": [(1, -0.95, 0, 1.0, 1.2), (2, 0.95, 0, 1.0, 1.2)], "size": (2.8, 1.5)}

# Mounting hole M2
FP["M2_HOLE"] = {"pads": [
    (1, 0, 0, 3.5, 3.5),
], "size": (3.5, 3.5)}


# ── Components ────────────────────────────────────────────────────────
PARTS = {
    # ── MCU ──
    "U1": {"fp": "NRF5340", "x": 14.0, "y": 14.0, "rot": 0,
            "part": "nRF5340-QKAA-R7", "lcsc": "C2652073",
            "label": "nRF5340\nQFN-94", "color": "#0d47a1"},

    # ── UWB Module ──
    "U2": {"fp": "DW3000", "x": 33.0, "y": 8.0, "rot": 0,
            "part": "DW3000 (Qorvo QFN-48)", "lcsc": "C2843371",
            "label": "DW3000\nUWB", "color": "#880e4f"},

    # ── ADC (AK5720 24-bit) ──
    "U3": {"fp": "AK5720", "x": 10.0, "y": 25.0, "rot": 0,
            "part": "AK5720VT", "lcsc": "C2690387",
            "label": "AK5720\n24-bit ADC", "color": "#4a148c"},

    # ── DAC (PCM5102A 32-bit) ──
    "U4": {"fp": "PCM5102A", "x": 22.5, "y": 25.0, "rot": 0,
            "part": "PCM5102APWR", "lcsc": "C108774",
            "label": "PCM5102A\n32-bit DAC", "color": "#1b5e20"},

    # ── I2S Amplifier ──
    "U5": {"fp": "MAX98357", "x": 34.0, "y": 25.0, "rot": 0,
            "part": "MAX98357AETE+T", "lcsc": "C1506581",
            "label": "MAX98357\nAmp", "color": "#b71c1c"},

    # ── PMIC (nPM1300) ──
    "U6": {"fp": "NPM1300", "x": 22.5, "y": 5.0, "rot": 0,
            "part": "nPM1300-QEAA-R7", "lcsc": "C5303826",
            "label": "nPM1300\nPMIC", "color": "#e65100"},

    # ── 32MHz Crystal (nRF5340) ──
    "Y1": {"fp": "XTAL_2012", "x": 10.0, "y": 10.0, "rot": 0,
            "part": "32MHz 2012", "lcsc": "C2762297",
            "label": "Y1\n32M", "color": "#546e7a"},

    # ── 32.768kHz Crystal (RTC) ──
    "Y2": {"fp": "XTAL_1610", "x": 10.0, "y": 12.0, "rot": 0,
            "part": "32.768kHz 1610", "lcsc": "C2838510",
            "label": "Y2\n32k", "color": "#546e7a"},

    # ── USB-C ──
    "J1": {"fp": "USBC", "x": 22.5, "y": 1.5, "rot": 0,
            "part": "TYPE-C-16PIN-2MD", "lcsc": "C2765186",
            "label": "USB-C", "color": "#78909c"},

    # ── 3.5mm TRS Jack ──
    "J2": {"fp": "TRS_35MM", "x": 1.5, "y": 15.0, "rot": 90,
            "part": "PJ-320A (3.5mm TRS)", "lcsc": "C18438",
            "label": "3.5mm\nLine In", "color": "#263238"},

    # ── SMA Antenna (UWB) ──
    "J3": {"fp": "SMA", "x": 42.0, "y": 4.0, "rot": 0,
            "part": "SMA Edge-Mount", "lcsc": "C496549",
            "label": "SMA\nUWB", "color": "#ff6f00"},

    # ── PCB BLE Antenna (trace on layer 1) ──
    "J4": {"fp": "PCB_ANT", "x": 40.0, "y": 27.0, "rot": 0,
            "part": "PCB Antenna (BLE)", "lcsc": "",
            "label": "BLE\nAnt", "color": "#00838f"},

    # ── Status LEDs (WS2812B-2020) ──
    "D1": {"fp": "WS2812B", "x": 7.0, "y": 7.0, "rot": 0,
            "part": "WS2812B-2020", "lcsc": "C2976072",
            "label": "D1", "color": "#f9a825"},
    "D2": {"fp": "WS2812B", "x": 7.0, "y": 4.0, "rot": 0,
            "part": "WS2812B-2020", "lcsc": "C2976072",
            "label": "D2", "color": "#f9a825"},

    # ── Tactile button ──
    "SW1": {"fp": "SW", "x": 3.5, "y": 25.0, "rot": 0,
            "part": "3x3mm Tactile SMD", "lcsc": "C2936178",
            "label": "BTN", "color": "#455a64"},

    # ── Battery connector (JST-PH 2-pin) ──
    "BT1": {"fp": "JST_PH2", "x": 42.0, "y": 15.0, "rot": 0,
            "part": "JST-PH-2P (802535 800mAh)", "lcsc": "C131337",
            "label": "LiPo\n800mAh", "color": "#ff5722"},

    # ── Speaker connector ──
    "SPK1": {"fp": "SPK_CONN", "x": 42.0, "y": 21.0, "rot": 0,
             "part": "Speaker 20mm Conn 2-pin", "lcsc": "C160404",
             "label": "SPK", "color": "#795548"},

    # ── Mounting holes ──
    "MH1": {"fp": "M2_HOLE", "x": 2.5, "y": 2.5, "rot": 0,
             "part": "M2 mounting hole", "lcsc": "", "label": "M2", "color": "#333"},
    "MH2": {"fp": "M2_HOLE", "x": 42.5, "y": 2.5, "rot": 0,
             "part": "M2 mounting hole", "lcsc": "", "label": "M2", "color": "#333"},
    "MH3": {"fp": "M2_HOLE", "x": 2.5, "y": 27.5, "rot": 0,
             "part": "M2 mounting hole", "lcsc": "", "label": "M2", "color": "#333"},
    "MH4": {"fp": "M2_HOLE", "x": 42.5, "y": 27.5, "rot": 0,
             "part": "M2 mounting hole", "lcsc": "", "label": "M2", "color": "#333"},

    # ── Decoupling / filter caps ──
    # nRF5340 bypass (DECVDD, VDD, VDDH)
    "C1":  {"fp": "0402", "x": 11.0, "y": 16.5, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C1", "color": "#1a237e"},
    "C2":  {"fp": "0402", "x": 17.0, "y": 16.5, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C2", "color": "#1a237e"},
    "C3":  {"fp": "0603", "x": 11.0, "y": 18.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C3", "color": "#1a237e"},
    "C4":  {"fp": "0402", "x": 17.0, "y": 18.0, "rot": 0,
             "part": "1uF", "lcsc": "C14445", "label": "C4", "color": "#1a237e"},
    # DW3000 bypass
    "C5":  {"fp": "0402", "x": 30.0, "y": 4.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C5", "color": "#1a237e"},
    "C6":  {"fp": "0402", "x": 36.0, "y": 4.0, "rot": 0,
             "part": "10nF", "lcsc": "C15195", "label": "C6", "color": "#1a237e"},
    # AK5720 bypass
    "C7":  {"fp": "0402", "x": 7.5, "y": 23.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C7", "color": "#1a237e"},
    "C8":  {"fp": "0402", "x": 12.5, "y": 23.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C8", "color": "#1a237e"},
    # PCM5102A bypass
    "C9":  {"fp": "0402", "x": 20.0, "y": 22.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C9", "color": "#1a237e"},
    "C10": {"fp": "0402", "x": 25.0, "y": 22.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C10", "color": "#1a237e"},
    # MAX98357 bypass
    "C11": {"fp": "0402", "x": 31.5, "y": 23.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C11", "color": "#1a237e"},
    # nPM1300 input/output caps
    "C12": {"fp": "0603", "x": 19.0, "y": 3.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C12", "color": "#1a237e"},
    "C13": {"fp": "0603", "x": 26.0, "y": 3.0, "rot": 0,
             "part": "22uF", "lcsc": "C45783", "label": "C13", "color": "#1a237e"},
    # Crystal load caps (32MHz)
    "C14": {"fp": "0402", "x": 9.0, "y": 9.0, "rot": 0,
             "part": "12pF", "lcsc": "C1547", "label": "C14", "color": "#1a237e"},
    "C15": {"fp": "0402", "x": 11.0, "y": 9.0, "rot": 0,
             "part": "12pF", "lcsc": "C1547", "label": "C15", "color": "#1a237e"},

    # ── Resistors ──
    # USB CC pull-down (5.1k x2)
    "R1":  {"fp": "0402", "x": 19.5, "y": 5.0, "rot": 90,
             "part": "5.1k", "lcsc": "C25905", "label": "R1", "color": "#5d4037"},
    "R2":  {"fp": "0402", "x": 25.5, "y": 5.0, "rot": 90,
             "part": "5.1k", "lcsc": "C25905", "label": "R2", "color": "#5d4037"},
    # LED data resistor
    "R3":  {"fp": "0402", "x": 7.0, "y": 9.5, "rot": 90,
             "part": "330R", "lcsc": "C25104", "label": "R3", "color": "#5d4037"},
    # I2C pull-ups (nPM1300)
    "R4":  {"fp": "0402", "x": 14.0, "y": 8.0, "rot": 0,
             "part": "4.7k", "lcsc": "C25900", "label": "R4", "color": "#5d4037"},
    "R5":  {"fp": "0402", "x": 14.0, "y": 9.5, "rot": 0,
             "part": "4.7k", "lcsc": "C25900", "label": "R5", "color": "#5d4037"},
    # AK5720 format select
    "R6":  {"fp": "0402", "x": 7.5, "y": 27.0, "rot": 0,
             "part": "10k", "lcsc": "C25744", "label": "R6", "color": "#5d4037"},
    # PCM5102A FMT/DEMP pull-down
    "R7":  {"fp": "0402", "x": 20.0, "y": 28.0, "rot": 0,
             "part": "10k", "lcsc": "C25744", "label": "R7", "color": "#5d4037"},
    "R8":  {"fp": "0402", "x": 25.0, "y": 28.0, "rot": 0,
             "part": "10k", "lcsc": "C25744", "label": "R8", "color": "#5d4037"},
    # Button pull-up (internal in nRF5340, but add external for reliability)
    "R9":  {"fp": "0402", "x": 3.5, "y": 22.5, "rot": 0,
             "part": "10k", "lcsc": "C25744", "label": "R9", "color": "#5d4037"},

    # ── Inductors (nPM1300 buck) ──
    "L1":  {"fp": "0805", "x": 22.5, "y": 8.5, "rot": 0,
             "part": "10uH", "lcsc": "C408412", "label": "L1", "color": "#37474f"},
    "L2":  {"fp": "0805", "x": 27.5, "y": 8.5, "rot": 0,
             "part": "4.7uH", "lcsc": "C408335", "label": "L2", "color": "#37474f"},

    # ── DW3000 UWB support components ──
    # 38.4MHz TCXO for DW3000 (LFXTAL060655, 2.0x1.6mm)
    "Y3":  {"fp": "XTAL_1610", "x": 36.0, "y": 10.0, "rot": 0,
             "part": "38.4MHz TCXO", "lcsc": "C2838510", "label": "Y3\n38.4M", "color": "#546e7a"},
    # DW3000 decoupling caps (100nF x4, 0402)
    "C16": {"fp": "0402", "x": 30.0, "y": 6.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C16", "color": "#1a237e"},
    "C17": {"fp": "0402", "x": 36.0, "y": 6.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C17", "color": "#1a237e"},
    "C18": {"fp": "0402", "x": 30.0, "y": 10.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C18", "color": "#1a237e"},
    "C19": {"fp": "0402", "x": 36.0, "y": 12.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C19", "color": "#1a237e"},
    # RF matching inductor 15nH (0402)
    "L3":  {"fp": "0402", "x": 38.0, "y": 6.0, "rot": 0,
             "part": "15nH", "lcsc": "C76862", "label": "L3", "color": "#37474f"},
    # RF matching cap 1.5pF (0402)
    "C20": {"fp": "0402", "x": 38.0, "y": 8.0, "rot": 0,
             "part": "1.5pF", "lcsc": "C1546", "label": "C20", "color": "#1a237e"},
    # DW3000 RST pull-up 10k (0402)
    "R10": {"fp": "0402", "x": 30.0, "y": 12.0, "rot": 0,
             "part": "10k", "lcsc": "C25744", "label": "R10", "color": "#5d4037"},

    # ── PCM5102A support components ──
    # XSMT pull-up 10k (0402) — keeps DAC unmuted
    "R11": {"fp": "0402", "x": 20.0, "y": 27.0, "rot": 0,
             "part": "10k", "lcsc": "C25744", "label": "R11", "color": "#5d4037"},
    # Charge pump cap 1uF between CAPP and CAPM (0402)
    "C21": {"fp": "0402", "x": 25.0, "y": 27.0, "rot": 0,
             "part": "1uF", "lcsc": "C14445", "label": "C21", "color": "#1a237e"},
    # Output coupling caps 2.2uF on VOUTL/VOUTR (0603)
    "C22": {"fp": "0603", "x": 20.0, "y": 20.0, "rot": 0,
             "part": "2.2uF", "lcsc": "C12530", "label": "C22", "color": "#1a237e"},
    "C23": {"fp": "0603", "x": 25.0, "y": 20.0, "rot": 0,
             "part": "2.2uF", "lcsc": "C12530", "label": "C23", "color": "#1a237e"},
    # LDOO bypass cap 10uF (0603)
    "C24": {"fp": "0603", "x": 22.5, "y": 20.0, "rot": 0,
             "part": "10uF", "lcsc": "C15849", "label": "C24", "color": "#1a237e"},
    # CPVDD bypass cap 100nF (0402)
    "C25": {"fp": "0402", "x": 22.5, "y": 27.0, "rot": 0,
             "part": "100nF", "lcsc": "C1525", "label": "C25", "color": "#1a237e"},
}


# ── Routes ────────────────────────────────────────────────────────────
ROUTES = [
    # USB VBUS → nPM1300 PMIC
    ("+VBUS", PWR, [(22.5, 1.5), (22.5, 5.0)]),                            # USB → PMIC

    # PMIC → 3.3V rail
    ("+3V3", TRACE, [(22.5, 5.0), (22.5, 8.5)]),                           # PMIC → inductor
    ("+3V3", TRACE, [(22.5, 8.5), (14.0, 8.5), (14.0, 14.0)]),             # → nRF5340
    ("+3V3", TRACE, [(14.0, 14.0), (10.0, 14.0), (10.0, 25.0)]),           # → AK5720
    ("+3V3", TRACE, [(14.0, 14.0), (22.5, 14.0), (22.5, 25.0)]),           # → PCM5102A
    ("+3V3", TRACE, [(22.5, 14.0), (33.0, 14.0), (33.0, 8.0)]),            # → DW3000
    ("+3V3", TRACE, [(33.0, 14.0), (34.0, 14.0), (34.0, 25.0)]),           # → MAX98357
    ("+3V3", TRACE, [(10.0, 14.0), (7.0, 7.0)]),                           # → LED1
    ("+3V3", TRACE, [(7.0, 7.0), (7.0, 4.0)]),                             # → LED2

    # Battery connector → PMIC
    ("+VBAT", PWR, [(42.0, 15.0), (35.0, 10.0), (27.5, 8.5), (22.5, 5.0)]),

    # SPI3: nRF5340 → DW3000 (P0.13-P0.18)
    ("SPI_MOSI", TRACE, [(14.0+3.5, 14.0-1.0), (33.0-3.0, 8.0-1.5)]),     # P0.13 → MOSI
    ("SPI_MISO", TRACE, [(14.0+3.5, 14.0-0.6), (33.0-3.0, 8.0-1.0)]),     # P0.14 → MISO
    ("SPI_SCLK", TRACE, [(14.0+3.5, 14.0-0.2), (33.0-3.0, 8.0-0.5)]),     # P0.15 → SCLK
    ("SPI_CS",   TRACE, [(14.0+3.5, 14.0+0.2), (33.0-3.0, 8.0+0.0)]),     # P0.16 → CS
    ("UWB_IRQ",  TRACE, [(14.0+3.5, 14.0+0.6), (33.0-3.0, 8.0+0.5)]),     # P0.17 → IRQ
    ("UWB_RST",  TRACE, [(14.0+3.5, 14.0+1.0), (33.0-3.0, 8.0+1.0)]),     # P0.18 → RST

    # DW3000 TCXO connection (38.4MHz crystal)
    ("UWB_TCXO", TRACE, [(33.0+3.0, 8.0-2.75), (36.0, 10.0)]),           # DW3000 → Y3 TCXO
    # DW3000 RST pull-up (R10 to 3.3V)
    ("UWB_RST_PU", TRACE, [(30.0, 12.0), (33.0-3.0, 8.0+1.0)]),          # R10 → DW3000 RST
    # RF matching network: DW3000 → L3 → C20 → SMA
    ("UWB_RF_L", TRACE, [(33.0+3.0, 8.0-2.0), (38.0, 6.0)]),             # DW3000 RF → L3
    ("UWB_RF_C", TRACE, [(38.0, 6.0), (38.0, 8.0)]),                      # L3 → C20
    ("UWB_RF_OUT", TRACE, [(38.0, 6.0), (39.0, 4.0), (42.0, 4.0)]),      # L3 → SMA

    # I2S0 shared bus: nRF5340 → AK5720 + PCM5102A + MAX98357A
    # nRF5340 has ONLY ONE I2S peripheral. Full-duplex: SDIN (ADC) + SDOUT (DAC+Amp)
    # P0.04 = I2S0_SCK (shared BCLK to all 3 audio ICs)
    ("I2S0_SCK",  TRACE, [(14.0-3.5, 14.0-2.0), (10.0+2.65, 25.0-1.6)]),  # P0.04 → AK5720 BCLK
    ("I2S0_SCK",  TRACE, [(14.0-3.5, 14.0-2.0), (22.5-3.25, 25.0-1.3)]),  # P0.04 → PCM5102A BCK
    ("I2S0_SCK",  TRACE, [(22.5-3.25, 25.0-1.3), (34.0-1.5, 25.0-0.75)]), # → MAX98357A BCLK
    # P0.05 = I2S0_LRCK (shared LRCK to all 3 audio ICs)
    ("I2S0_LRCK", TRACE, [(14.0-3.5, 14.0-1.6), (10.0+2.65, 25.0-0.95)]), # P0.05 → AK5720 LRCK
    ("I2S0_LRCK", TRACE, [(14.0-3.5, 14.0-1.6), (22.5-3.25, 25.0-0.65)]), # P0.05 → PCM5102A LRCK
    ("I2S0_LRCK", TRACE, [(22.5-3.25, 25.0-0.65), (34.0-1.5, 25.0-0.25)]),# → MAX98357A LRCK
    # P0.06 = I2S0_SDIN (AK5720 SDOUT → nRF5340 only)
    ("I2S0_SDIN", TRACE, [(14.0-3.5, 14.0-1.2), (10.0+2.65, 25.0-0.3)]),  # P0.06 ← AK5720 SDOUT
    # P0.07 = I2S0_SDOUT (nRF5340 → PCM5102A DIN + MAX98357A DIN)
    ("I2S0_SDOUT", TRACE, [(14.0-3.5, 14.0-0.8), (22.5-3.25, 25.0+0.0)]), # P0.07 → PCM5102A DIN
    ("I2S0_SDOUT", TRACE, [(22.5-3.25, 25.0+0.0), (34.0-1.5, 25.0+0.25)]),# → MAX98357A DIN
    # P0.28 = I2S0_MCK (optional master clock to AK5720)
    ("I2S0_MCK",  TRACE, [(14.0+3.5, 14.0+2.6), (10.0+2.65, 25.0+0.35)]), # P0.28 → AK5720 MCLK

    # I2C1: nRF5340 → nPM1300 PMIC (P0.09-P0.10)
    ("I2C_SDA",  TRACE, [(14.0-3.5, 14.0+0.4), (22.5-2.5, 5.0-0.25)]),    # P0.09
    ("I2C_SCL",  TRACE, [(14.0-3.5, 14.0+0.8), (22.5-2.5, 5.0+0.25)]),    # P0.10

    # PCM5102A XSMT pull-up (R11 → 3.3V via PCM5102A XSMT pin)
    ("DAC_XSMT", TRACE, [(22.5-2.2, 25.0+0.65), (20.0, 27.0)]),           # PCM5102A XSMT → R11
    # PCM5102A SCK → GND (auto-clock detection mode)
    ("DAC_SCK_GND", TRACE, [(22.5-2.2, 25.0-1.625), (22.5-2.2, 25.0-2.925)]),  # SCK pin to GND via
    # PCM5102A charge pump (C21 between CAPP/CAPM)
    ("DAC_CAPP", TRACE, [(22.5+2.2, 25.0-0.325), (25.0, 27.0)]),           # CAPP → C21
    # PCM5102A output coupling (C22/C23 on VOUTL/VOUTR)
    ("DAC_VOUTL", TRACE, [(22.5+2.2, 25.0+0.975), (20.0, 20.0)]),          # VOUTL → C22
    ("DAC_VOUTR", TRACE, [(22.5+2.2, 25.0+1.625), (25.0, 20.0)]),          # VOUTR → C23
    # PCM5102A LDOO bypass (C24)
    ("DAC_LDOO", TRACE, [(22.5+2.2, 25.0+2.275), (22.5, 20.0)]),           # LDOO → C24
    # PCM5102A CPVDD bypass (C25)
    ("DAC_CPVDD", TRACE, [(22.5+2.2, 25.0-0.975), (22.5, 27.0)]),          # CPVDD → C25

    # Speaker amp → speaker connector
    ("SPK_OUT", TRACE, [(34.0+1.5, 25.0+0.75), (42.0, 21.0)]),             # MAX98357 → SPK

    # Speaker enable (P0.21 → MAX98357A SD_MODE pin, active HIGH)
    ("AMP_SD", TRACE, [(14.0-3.5, 14.0+0.0), (34.0-1.5, 25.0+0.75)]),     # P0.21 → MAX98357A SD

    # 3.5mm TRS → AK5720 analog input
    ("LINE_TIP", TRACE, [(1.5, 12.0), (5.0, 22.0), (10.0-2.65, 25.0-1.6)]),
    ("LINE_GND", TRACE, [(1.5, 18.0), (5.0, 28.0), (10.0-2.65, 25.0+1.6)]),

    # UWB antenna (DW3000 → SMA, via RF matching network L3/C20)
    # Main path routed through UWB_RF_L/UWB_RF_C/UWB_RF_OUT above

    # LED chain (P0.20)
    ("LED_DIN",   TRACE, [(14.0-3.5, 14.0+1.2), (7.0, 9.5)]),             # P0.20 → R3
    ("LED_R_OUT", TRACE, [(7.0, 9.5), (7.0, 7.0)]),                       # R3 → D1
    ("LED_CHAIN", TRACE, [(7.0+0.65, 7.0-0.55), (7.0-0.65, 4.0+0.55)]),   # D1 → D2

    # Button (P0.08)
    ("BTN", TRACE, [(14.0-3.5, 14.0+0.0), (3.5+2.0, 25.0)]),              # P0.08 → SW1

    # USB data
    ("USB_D+", 0.15, [(14.0-3.5, 14.0+2.4), (22.5+0.25, 1.5)]),
    ("USB_D-", 0.15, [(14.0-3.5, 14.0+2.8), (22.5-0.25, 1.5)]),

    # USB CC
    ("CC1", TRACE, [(19.5, 5.0), (22.5-1.75, 1.5)]),
    ("CC2", TRACE, [(25.5, 5.0), (22.5+1.75, 1.5)]),

    # Crystal connections
    ("XTAL_32M", TRACE, [(10.0, 10.0), (14.0-3.5, 14.0-3.2)]),            # 32MHz → nRF
    ("XTAL_32K", TRACE, [(10.0, 12.0), (14.0-3.5, 14.0-2.8)]),            # 32.768k → nRF

    # BLE antenna (nRF5340 → PCB trace antenna)
    ("BLE_ANT", TRACE, [(14.0+3.5, 14.0+4.6), (40.0, 27.0)]),
]

VIAS = [
    (5, 5), (22.5, 5), (40, 5),
    (5, 15), (22.5, 15), (40, 15),
    (5, 25), (22.5, 25), (40, 25),
    (14, 10), (33, 10), (14, 20), (33, 20),
    # Extra GND vias near DW3000 thermal pad
    (31, 8), (33, 6), (35, 8), (33, 10),
    # Extra GND vias near nRF5340 thermal pad
    (12, 14), (14, 12), (16, 14), (14, 16),
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
            f.write(f"G04 Koe PRO v2 {s.name}*\n%LPD*%\n")
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
            f.write("M48\n; Koe PRO v2 45x30mm nRF5340 + DW3000 UWB\nFMAT,2\nMETRIC,TZ\n")
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

    # Mounting holes (M2 = 2.2mm drill)
    for ref in ("MH1", "MH2", "MH3", "MH4"):
        c = PARTS[ref]
        dr.hole(c["x"], c["y"], 2.2)

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

    pre = "koe-pro-v2"
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
    ROT = {"NPM1300": 0, "NRF5340": 0}
    lines = ["Designator,Mid X(mm),Mid Y(mm),Layer,Rotation"]
    for ref, c in PARTS.items():
        rot = c.get("rot", 0) + ROT.get(c["fp"], 0)
        lines.append(f"{ref},{c['x']:.1f},{c['y']:.1f},Top,{rot % 360}")
    (GBR / "CPL-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"CPL: {GBR / 'CPL-JLCPCB.csv'}")


# ── SVG ───────────────────────────────────────────────────────────────
def gen_svg():
    S = 12; pad = 60; img_w = int(BOARD_W * S + pad * 2); img_h = int(BOARD_H * S + pad * 2)
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
<text x="{img_w // 2}" y="22" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="16" font-weight="600">Koe Pro v2 -- nRF5340 + DW3000 UWB Audio Board</text>
<text x="{img_w // 2}" y="40" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">45x30mm | 4-layer FR-4 | AK5720 ADC | PCM5102A DAC | MAX98357A Amp | nPM1300 PMIC</text>

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
        "AMP": "#ff8a65", "CC": "#78909c", "BTN": "#78909c",
        "I2C": "#26a69a", "XTAL": "#78909c", "BLE": "#00acc1",
        "SPK": "#ff8a65",
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
        svg += f'<circle cx="{mx}" cy="{my}" r="{2.2 * S / 2}" fill="#1a1a1a" stroke="#888" stroke-width="1"/>\n'
        svg += f'<circle cx="{mx}" cy="{my}" r="{1.1 * S}" fill="none" stroke="#c8a83e" stroke-width="0.5" opacity="0.4"/>\n'

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
            if ref.startswith("D") or ref == "SW1": fs = 6
            svg += f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="{fs}">{line}</text>\n'
        svg += '</g>\n'

    # Legend
    ly = img_h + 15
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="9">45x30mm | 4-layer | {len(PARTS)} parts | nRF5340 + DW3000 UWB + AK5720 ADC + PCM5102A DAC | BOM $23.05</text>\n'

    # Signal flow
    ly += 22
    flow_items = [
        ("Guitar/Mic", "#ce93d8"), ("AK5720", "#4a148c"), ("I2S", "#42a5f5"),
        ("nRF5340", "#0d47a1"), ("PCM5102A", "#1b5e20"), ("MAX98357", "#b71c1c"),
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

    # UWB flow
    ly += 24
    uwb_items = [
        ("nRF5340", "#0d47a1"), ("SPI", "#42a5f5"), ("DW3000", "#880e4f"),
        ("SMA", "#ff6f00"), ("UWB Sync", "#880e4f"),
    ]
    total_w = sum(len(t) * 6.5 + 20 for t, _ in uwb_items)
    fx = (img_w - total_w) / 2
    for i, (text, col) in enumerate(uwb_items):
        tw = len(text) * 6.5 + 10
        svg += f'<rect x="{fx}" y="{ly - 10}" width="{tw}" height="16" fill="{col}" rx="3" opacity="0.7"/>\n'
        svg += f'<text x="{fx + tw / 2}" y="{ly + 2}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="8">{text}</text>\n'
        fx += tw + 5
        if i < len(uwb_items) - 1:
            svg += f'<text x="{fx - 2}" y="{ly + 2}" text-anchor="middle" fill="#888" font-family="monospace" font-size="10">&#8594;</text>\n'

    # Power flow
    ly += 28
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#ef5350" font-family="monospace" font-size="9" font-weight="bold">USB-C 5V / LiPo 800mAh &#8594; nPM1300 PMIC (charger + buck + LDO) &#8594; 3.3V (all logic)</text>\n'
    ly += 16
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">DW3000 UWB for sub-us time sync + ranging | AK5720 24-bit ADC + PCM5102A 32-bit DAC</text>\n'

    # Pin assignment summary
    ly += 22
    svg += f'<text x="{img_w // 2}" y="{ly}" text-anchor="middle" fill="#c8a83e" font-family="monospace" font-size="9">I2S0(P0.04-07,28):Full-duplex(ADC+DAC+AMP) | SPI3(P0.13-18):UWB | I2C1(P0.09-10):PMIC | P0.20:LED | P0.08:BTN</text>\n'

    svg += '</svg>\n'
    path = GBR / "koe-pro-v2-layout.svg"
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
        print(f"DRC: All components within {BOARD_W}x{BOARD_H}mm board -- OK")
    return len(errs) == 0


def main():
    print("=" * 65)
    print("Koe Pro v2 -- 45x30mm nRF5340 + DW3000 UWB Audio Board")
    print(f"  {len(PARTS)} parts | nRF5340 BLE 5.3 + DW3000 UWB")
    print(f"  AK5720 24-bit ADC | PCM5102A 32-bit DAC | MAX98357A Amp")
    print(f"  nPM1300 PMIC | LiPo 802535 800mAh | BOM ~$23.05")
    print("=" * 65)
    check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()
    print(f"\nSignal chain (I2S0 full-duplex, single peripheral):")
    print(f"  Guitar/Mic 3.5mm --> AK5720 ADC --SDIN--> I2S0 --> nRF5340")
    print(f"  nRF5340 --> I2S0 --SDOUT--> PCM5102A DAC --> Line out")
    print(f"  nRF5340 --> I2S0 --SDOUT--> MAX98357A --> Monitor speaker")
    print(f"  (SCK/LRCK shared bus: AK5720 + PCM5102A + MAX98357A)")
    print(f"  nRF5340 <--> SPI3 <--> DW3000 UWB (sub-us sync + ranging)")
    print(f"\nPower:")
    print(f"  USB-C 5V / LiPo 800mAh --> nPM1300 PMIC --> 3.3V (all logic)")
    print(f"\nPin assignment (nRF5340):")
    print(f"  I2S0 (Full-duplex ADC+DAC+AMP):")
    print(f"    P0.04=SCK   P0.05=LRCK  --> shared bus to AK5720, PCM5102A, MAX98357A")
    print(f"    P0.06=SDIN  <-- AK5720 SDOUT (ADC capture)")
    print(f"    P0.07=SDOUT --> PCM5102A DIN + MAX98357A DIN (DAC/amp output)")
    print(f"    P0.28=MCK   --> AK5720 MCLK (master clock)")
    print(f"  SPI3 (UWB):  P0.13=MOSI P0.14=MISO  P0.15=SCLK  P0.16=CS")
    print(f"               P0.17=IRQ  P0.18=RST")
    print(f"  I2C1 (PMIC): P0.09=SDA  P0.10=SCL")
    print(f"  GPIO:        P0.08=BTN  P0.20=LED   P0.21=SPK_EN(MAX98357A SD)")


if __name__ == "__main__":
    main()
