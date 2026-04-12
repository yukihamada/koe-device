#!/usr/bin/env python3
"""
Koe COIN PCB — 20mm Round, nRF54L15-QFAA Edition
===================================================
nRF54L15 (BLE 5.4 + Channel Sounding, I2S, USB, PDM)
+ SPH0645 Mic + MAX98357A Amp + BQ25100 Charger
Battery: 150mAh LiPo pouch (402025) in case

Board: 20mm diameter, 4-layer, 1.0mm FR-4
Power: ~5mA active BLE streaming (nRF54L15 is more efficient)
"""

import math
import zipfile
from pathlib import Path

BOARD_DIA = 20.0
R = BOARD_DIA / 2.0
CX, CY = R, R
TRACE, PWR, VIA_D, VIA_P = 0.15, 0.3, 0.2, 0.45

OUT = Path(__file__).parent / "kicad"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-coin"

def in_circle(x, y, m=0.5):
    return (x - CX) ** 2 + (y - CY) ** 2 <= (R - m) ** 2


# ── Footprints ────────────────────────────────────────────────────────
FP = {}

# nRF54L15-QFAA: QFN-48, 6x6mm, 0.4mm pitch
# 12 pins per side + exposed pad 4.0x4.0mm
def _nrf54():
    p = []
    # Pins are arranged 12 per side, pitch 0.4mm
    # Total span = 11 * 0.4 = 4.4mm, first pin at -2.2mm from center
    for i in range(12):
        p.append((i + 1,  -3.0, 2.2 - i * 0.4,  0.2, 0.7))   # Left
    for i in range(12):
        p.append((13 + i, -2.2 + i * 0.4, 3.0,   0.7, 0.2))   # Bottom
    for i in range(12):
        p.append((25 + i, 3.0, -2.2 + i * 0.4,   0.2, 0.7))   # Right
    for i in range(12):
        p.append((37 + i, 2.2 - i * 0.4, -3.0,   0.7, 0.2))   # Top
    p.append((49, 0, 0, 4.0, 4.0))  # Exposed GND pad
    return p

FP["NRF54L15"] = {"pads": _nrf54(), "size": (6.0, 6.0)}

# MAX98357A: TQFN-16, 3x3mm
def _max98():
    p = []
    for i in range(4):
        p.append((i + 1,  -1.45, 0.75 - i * 0.5,  0.25, 0.7))
    for i in range(4):
        p.append((5 + i,  -0.75 + i * 0.5, 1.45,  0.7, 0.25))
    for i in range(4):
        p.append((9 + i,  1.45, -0.75 + i * 0.5,  0.25, 0.7))
    for i in range(4):
        p.append((13 + i, 0.75 - i * 0.5, -1.45,  0.7, 0.25))
    p.append((17, 0, 0, 1.23, 1.23))
    return p

FP["MAX98"] = {"pads": _max98(), "size": (3.0, 3.0)}

# SPH0645LM4H I2S MEMS mic (bottom-port, LGA-7, 4.72 x 3.76mm)
FP["SPH0645"] = {"pads": [
    (1, -1.27, -1.2, 0.5, 0.76), (2, -1.27, 0, 0.5, 0.76), (3, -1.27, 1.2, 0.5, 0.76),
    (4,  1.27,  1.2, 0.5, 0.76), (5,  1.27, 0, 0.5, 0.76), (6,  1.27, -1.2, 0.5, 0.76),
], "size": (4.72, 3.76)}

# BQ25100DSGR: WSON-6, 1.5x1.5mm, ultra-low Iq=75nA
FP["WSON6"] = {"pads": [
    (1, -0.625, 0.5,  0.3, 0.5),   # PGND
    (2, -0.625, 0.0,  0.3, 0.5),   # IN
    (3, -0.625, -0.5, 0.3, 0.5),   # TS
    (4,  0.625, -0.5, 0.3, 0.5),   # ISET
    (5,  0.625, 0.0,  0.3, 0.5),   # OUT
    (6,  0.625, 0.5,  0.3, 0.5),   # /CHG
], "size": (1.5, 1.5)}

# XC6220B331MR-G LDO: SOT-23-5
FP["SOT23"] = {"pads": [
    (1, -1.1, 0.95, 0.6, 0.7), (2, -1.1, 0, 0.6, 0.7), (3, -1.1, -0.95, 0.6, 0.7),
    (4,  1.1, -0.95, 0.6, 0.7), (5, 1.1, 0.95, 0.6, 0.7),
], "size": (3.0, 3.0)}

# WS2812B-2020
FP["LED2020"] = {"pads": [
    (1, -0.75, -0.5, 0.5, 0.5), (2, 0.75, -0.5, 0.5, 0.5),
    (3,  0.75,  0.5, 0.5, 0.5), (4, -0.75, 0.5, 0.5, 0.5),
], "size": (2.0, 2.0)}

# EVQP0N02B button
FP["SW"] = {"pads": [(1, -1.0, 0, 0.6, 0.5), (2, 1.0, 0, 0.6, 0.5)], "size": (2.6, 1.6)}

# TYPE-C-16PIN-2MD USB-C
FP["USBC"] = {"pads": [
    ("V1", -2.4, -1.0, 0.5, 1.0), ("V2", 2.4, -1.0, 0.5, 1.0),
    ("D-", -0.8, -1.0, 0.3, 1.0), ("D+", -0.4, -1.0, 0.3, 1.0),
    ("C1", -1.6, -1.0, 0.3, 1.0), ("C2", 1.6, -1.0, 0.3, 1.0),
    ("G1", -3.2, -1.0, 0.5, 1.0), ("G2", 3.2, -1.0, 0.5, 1.0),
    ("S1", -3.65, 0.0, 0.6, 1.2), ("S2", 3.65, 0.0, 0.6, 1.2),
], "size": (7.35, 3.2)}

FP["0402"] = {"pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)], "size": (1.6, 0.8)}
FP["0603"] = {"pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)], "size": (2.2, 1.2)}
FP["SPK_PAD"] = {"pads": [(1, -0.75, 0, 1.2, 1.5), (2, 0.75, 0, 1.2, 1.5)], "size": (3.0, 2.0)}

# Battery pads for 150mAh LiPo
FP["BAT_PAD"] = {"pads": [
    (1, -1.0, 0, 1.0, 1.5),  # BAT+
    (2,  1.0, 0, 1.0, 1.5),  # BAT-
], "size": (3.5, 2.0)}

# FC-12M 32.768kHz crystal, 1.6x1.0mm
FP["XTAL_1610"] = {"pads": [
    (1, -0.55, 0, 0.4, 0.8),
    (2,  0.55, 0, 0.4, 0.8),
], "size": (1.6, 1.0)}


# ── Components ────────────────────────────────────────────────────────
# nRF54L15 needs: 32.768kHz xtal, decoupling caps, DC-DC inductor
# Using internal HFXO for BLE (no external 32MHz xtal needed)

PARTS = {
    # ── MCU ──
    "U1": {"fp": "NRF54L15", "x": CX, "y": CY, "rot": 0,
            "part": "nRF54L15-QFAA-R", "lcsc": "C42458750",
            "label": "nRF54L15", "color": "#0d47a1"},

    # ── MEMS Mic (top, outside antenna keepout) ──
    "U2": {"fp": "SPH0645", "x": CX, "y": 3.5, "rot": 0,
            "part": "SPH0645LM4H", "lcsc": "C19272537",
            "label": "MIC", "color": "#37474f"},

    # ── Speaker amp (right side) ──
    "U3": {"fp": "MAX98", "x": 15.5, "y": 6.5, "rot": 0,
            "part": "MAX98357AETE+T", "lcsc": "C2682619",
            "label": "AMP", "color": "#b71c1c"},

    # ── LiPo Charger BQ25100 (left side) ──
    "U4": {"fp": "WSON6", "x": 4.0, "y": 13.5, "rot": 0,
            "part": "BQ25100DSGR", "lcsc": "C527574",
            "label": "CHRG", "color": "#4e342e"},

    # ── LDO 3.3V (left side, below MCU) ──
    "U5": {"fp": "SOT23", "x": 4.5, "y": 8.5, "rot": 0,
            "part": "XC6220B331MR-G", "lcsc": "C86534",
            "label": "LDO", "color": "#4e342e"},

    # ── Status LED (near top) ──
    "LED1": {"fp": "LED2020", "x": CX, "y": 6.5, "rot": 0,
             "part": "WS2812B-2020", "lcsc": "C2976072",
             "label": "LED", "color": "#f9a825"},

    # ── USB-C (bottom edge) ──
    "J1": {"fp": "USBC", "x": CX, "y": 18.8, "rot": 0,
            "part": "TYPE-C-16PIN-2MD", "lcsc": "C2765186",
            "label": "USB-C", "color": "#78909c"},

    # ── Button (left edge) ──
    "SW1": {"fp": "SW", "x": 3.5, "y": CX, "rot": 0,
            "part": "EVQP0N02B", "lcsc": "C2936178",
            "label": "BTN", "color": "#455a64"},

    # ── Speaker pads (right side) ──
    "SP1": {"fp": "SPK_PAD", "x": 16.5, "y": 14.5, "rot": 0,
            "part": "Speaker pads", "lcsc": "",
            "label": "SPK", "color": "#880e4f"},

    # ── Battery pads (bottom-left) ──
    "BT1": {"fp": "BAT_PAD", "x": 6.5, "y": 16.5, "rot": 0,
            "part": "150mAh LiPo 402025", "lcsc": "",
            "label": "BAT", "color": "#e65100"},

    # ── 32.768kHz crystal ──
    "Y1": {"fp": "XTAL_1610", "x": 15.0, "y": 12.5, "rot": 0,
            "part": "FC-12M 32.768kHz", "lcsc": "C32346",
            "label": "32K", "color": "#4a148c"},

    # ── USB CC resistors (5.1k) ──
    "R1": {"fp": "0402", "x": 7.5, "y": 17.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R1", "color": "#5d4037"},
    "R2": {"fp": "0402", "x": 12.5, "y": 17.0, "rot": 0,
            "part": "5.1k", "lcsc": "C25905", "label": "R2", "color": "#5d4037"},

    # ── Charger PROG resistor (BQ25100: R_ISET = 1040 / I_CHG(mA))
    #    100mA charge: R = 1040/100 = 10.4k, use 10k → ~104mA
    "R3": {"fp": "0402", "x": 5.0, "y": 12.0, "rot": 90,
            "part": "10k", "lcsc": "C25744", "label": "R3", "color": "#5d4037"},

    # ── Decoupling: 100nF x6 ──
    "C1": {"fp": "0402", "x": 7.5, "y": 7.5, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C1", "color": "#1a237e"},
    "C2": {"fp": "0402", "x": 12.5, "y": 7.5, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C2", "color": "#1a237e"},
    "C3": {"fp": "0402", "x": 7.5, "y": 12.5, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C3", "color": "#1a237e"},
    "C4": {"fp": "0402", "x": 12.5, "y": 12.5, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C4", "color": "#1a237e"},
    "C5": {"fp": "0402", "x": 13.5, "y": 3.5, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C5", "color": "#1a237e"},
    "C6": {"fp": "0402", "x": 17.0, "y": 5.5, "rot": 90,
            "part": "100nF", "lcsc": "C1525", "label": "C6", "color": "#1a237e"},

    # ── Bulk: 10uF x2 ──
    "C7": {"fp": "0603", "x": 6.0, "y": 5.5, "rot": 90,
            "part": "10uF", "lcsc": "C19702", "label": "C7", "color": "#1a237e"},
    "C8": {"fp": "0603", "x": 4.5, "y": 15.5, "rot": 0,
            "part": "10uF", "lcsc": "C19702", "label": "C8", "color": "#1a237e"},

    # ── 1uF (DCDC) ──
    "C9": {"fp": "0402", "x": 14.5, "y": 14.0, "rot": 90,
            "part": "1uF", "lcsc": "C52923", "label": "C9", "color": "#1a237e"},

    # ── 32kHz xtal load caps (12pF) ──
    "C10": {"fp": "0402", "x": 15.0, "y": 11.0, "rot": 0,
             "part": "12pF", "lcsc": "C1547", "label": "C10", "color": "#1a237e"},
    "C11": {"fp": "0402", "x": 15.0, "y": 14.0, "rot": 0,
             "part": "12pF", "lcsc": "C1547", "label": "C11", "color": "#1a237e"},

    # ── DC-DC inductor ──
    "L1": {"fp": "0402", "x": 8.0, "y": 13.5, "rot": 0,
            "part": "15nH", "lcsc": "C76862", "label": "L1", "color": "#006064"},
}


# ── Routes ────────────────────────────────────────────────────────────
ROUTES = [
    # Power
    ("+3V3", PWR, [(4.5, 8.5), (7.5, 8.5), (7.5, CY)]),
    ("+3V3", TRACE, [(7.5, 8.5), (7.5, 5.0), (CX + 1.27, 3.5)]),       # -> Mic
    ("+3V3", TRACE, [(7.5, 7.0), (CX - 0.75, 7.0)]),                     # -> LED
    ("+3V3", TRACE, [(7.5, 8.5), (15.5 - 1.45, 6.5)]),                   # -> AMP
    ("+5V",  PWR, [(CX, 18.8), (CX, 17.0), (6.5, 17.0), (4.0, 14.5)]),  # USB -> Charger IN
    ("VBAT", PWR, [(6.5, 16.5), (4.625, 13.5)]),                          # Bat -> Charger OUT
    ("VBAT", PWR, [(4.625, 13.5), (4.5, 11.0), (4.5, 8.5)]),             # Charger -> LDO

    # I2S mic (nRF54L15 -> SPH0645)
    ("I2S_SCK", TRACE, [(CX - 1.6, CY - 3.0), (CX - 1.27, 2.3)]),
    ("I2S_WS",  TRACE, [(CX - 1.2, CY - 3.0), (CX - 1.27, 3.5)]),
    ("I2S_SD",  TRACE, [(CX + 1.6, CY - 3.0), (CX + 1.27, 2.3)]),

    # I2S speaker (nRF54L15 -> MAX98357A)
    ("I2S1_BCLK", TRACE, [(CX + 3.0, CY - 1.0), (15.5 - 1.45, 6.1)]),
    ("I2S1_WS",   TRACE, [(CX + 3.0, CY - 0.6), (15.5, 6.5 + 1.45)]),
    ("I2S1_DIN",  TRACE, [(CX + 3.0, CY + 0.2), (15.5 + 1.45, 6.5)]),

    # AMP -> Speaker pads
    ("SPK+", TRACE, [(15.5 + 1.45, 6.5 + 0.25), (16.5 - 0.75, 14.5)]),
    ("SPK-", TRACE, [(15.5 + 1.45, 6.5 + 0.75), (16.5 + 0.75, 14.5)]),

    # LED
    ("LED_DIN", TRACE, [(CX + 3.0, CY + 1.0), (15.0, 8.0), (CX + 0.75, 7.0)]),

    # Button
    ("BTN", TRACE, [(CX - 3.0, CY), (4.5, CX)]),

    # USB D+/D-
    ("USB_D+", 0.15, [(CX - 0.4, CY + 3.0), (CX - 0.4, 17.8)]),
    ("USB_D-", 0.15, [(CX - 0.8, CY + 3.0), (CX - 0.8, 17.8)]),

    # CC resistors
    ("CC1", TRACE, [(7.5, 17.0), (CX - 1.6, 17.8)]),
    ("CC2", TRACE, [(12.5, 17.0), (CX + 1.6, 17.8)]),

    # Charger ISET resistor
    ("ISET", TRACE, [(4.625, 13.0), (5.0, 12.0)]),

    # 32kHz xtal
    ("XC1", TRACE, [(CX + 3.0, CY + 2.0), (15.0 - 0.55, 12.5)]),
    ("XC2", TRACE, [(CX + 3.0, CY + 2.4), (15.0 + 0.55, 12.5)]),
]

VIAS = [
    (5, 5), (CX, CY), (15, 5), (5, 15), (15, 15),
    (CX, 8), (CX, 14), (3.5, CX), (16.5, CX),
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

    def arc(s, cx, cy, r, w=0.05, n=72):
        d = s._a("C", [w])
        s.cmds.append(f"D{d}*")
        for i in range(n + 1):
            a = 2 * math.pi * i / n
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            s.cmds.append(f"X{s._c(x)}Y{s._c(y)}D0{'2' if i == 0 else '1'}*")

    def write(s, path):
        with open(path, 'w') as f:
            f.write("%FSLAX46Y46*%\n%MOMM*%\n")
            f.write(f"G04 Koe COIN {s.name}*\n%LPD*%\n")
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
            f.write("M48\n; Koe COIN 20mm nRF54L15\nFMAT,2\nMETRIC,TZ\n")
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
    ec.arc(CX, CY, R)

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

    for _, w, pts in ROUTES:
        for i in range(len(pts) - 1):
            fc.trace(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w)

    for vx, vy in VIAS:
        for g in (fc, bc):
            g.circ(vx, vy, VIA_P)
        for g in (fm, bm):
            g.circ(vx, vy, VIA_P + 0.1)
        dr.hole(vx, vy, VIA_D)

    pre = "koe-coin"
    for n, g in [("F_Cu", fc), ("B_Cu", bc), ("F_Mask", fm), ("B_Mask", bm),
                 ("F_SilkS", fs_), ("B_SilkS", bs_), ("Edge_Cuts", ec)]:
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
    ROT = {"SOT23": 180}
    lines = ["Designator,Mid X(mm),Mid Y(mm),Layer,Rotation"]
    for ref, c in PARTS.items():
        rot = c.get("rot", 0) + ROT.get(c["fp"], 0)
        lines.append(f"{ref},{c['x']:.1f},{c['y']:.1f},Top,{rot % 360}")
    (GBR / "CPL-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"CPL: {GBR / 'CPL-JLCPCB.csv'}")


# ── SVG ───────────────────────────────────────────────────────────────
def gen_svg():
    S = 20
    pad = 55
    img = int(BOARD_DIA * S + pad * 2)
    ox, oy = pad, pad + 15

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{img}" height="{img + 160}">
<defs>
  <radialGradient id="pcb" cx="45%" cy="42%" r="55%">
    <stop offset="0%" stop-color="#0d5c0d"/><stop offset="100%" stop-color="#063806"/>
  </radialGradient>
  <filter id="sh"><feDropShadow dx="1" dy="2" stdDeviation="3" flood-opacity="0.5"/></filter>
</defs>
<rect width="{img}" height="{img + 160}" fill="#0d0d14"/>

<!-- Title -->
<text x="{img // 2}" y="20" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="16" font-weight="600">Koe COIN v7 — nRF54L15 BLE 5.4 + Channel Sounding</text>
<text x="{img // 2}" y="38" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">20mm round | 4-layer | ~5mA BLE | 150mAh LiPo | ~30h runtime | BQ25100 Iq=75nA</text>

<!-- Board -->
<circle cx="{ox + CX * S}" cy="{oy + CY * S}" r="{R * S + 2}" fill="#000" opacity="0.3"/>
<circle cx="{ox + CX * S}" cy="{oy + CY * S}" r="{R * S}" fill="url(#pcb)" stroke="#c8a83e" stroke-width="1.5"/>
'''

    # Traces
    net_colors = {
        "5V": "#ef5350", "VBAT": "#ef5350", "3V3": "#66bb6a", "SPK": "#ff7043",
        "I2S": "#42a5f5", "USB": "#ffca28", "LED": "#f9a825",
        "CC": "#78909c", "BTN": "#78909c", "ISET": "#78909c", "XC": "#ce93d8",
    }
    for net, w, pts in ROUTES:
        c = "#78909c"
        for k, v in net_colors.items():
            if k in net:
                c = v
                break
        for i in range(len(pts) - 1):
            svg += (f'<line x1="{ox + pts[i][0] * S}" y1="{oy + pts[i][1] * S}" '
                    f'x2="{ox + pts[i + 1][0] * S}" y2="{oy + pts[i + 1][1] * S}" '
                    f'stroke="{c}" stroke-width="{max(1.2, w * S * 0.6)}" '
                    f'opacity="0.35" stroke-linecap="round"/>\n')

    # Vias
    for vx, vy in VIAS:
        svg += (f'<circle cx="{ox + vx * S}" cy="{oy + vy * S}" '
                f'r="{VIA_P * S / 2 + 1}" fill="#1a1a1a" stroke="#666" stroke-width="0.5"/>\n')

    # Components
    colors = {
        "U1": "#0d47a1", "U2": "#37474f", "U3": "#b71c1c", "U4": "#4e342e", "U5": "#4e342e",
        "LED1": "#f9a825", "J1": "#78909c", "SW1": "#455a64", "SP1": "#880e4f",
        "BT1": "#e65100", "Y1": "#4a148c", "L1": "#006064",
    }
    for ref, c in PARTS.items():
        fp = FP[c["fp"]]
        cx_, cy_ = c["x"], c["y"]
        rot = c.get("rot", 0)
        sw, sh = fp["size"]
        color = colors.get(ref, c.get("color", "#5d4037" if ref[0] == "R" else "#1a237e"))
        sx, sy = ox + cx_ * S, oy + cy_ * S
        rw, rh = sw * S, sh * S
        svg += f'<g transform="translate({sx},{sy}) rotate({rot})" filter="url(#sh)">\n'
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            svg += (f'<rect x="{px * S - pw * S / 2}" y="{py * S - ph * S / 2}" '
                    f'width="{pw * S}" height="{ph * S}" fill="#c8a83e" rx="0.5" opacity="0.5"/>\n')
        rx = 3 if ref[0] in "UJ" else 1
        svg += (f'<rect x="{-rw / 2}" y="{-rh / 2}" width="{rw}" height="{rh}" '
                f'fill="{color}" stroke="#777" stroke-width="0.5" rx="{rx}"/>\n')
        if ref[0] == "U":
            svg += f'<circle cx="{-rw / 2 + 3}" cy="{-rh / 2 + 3}" r="1.2" fill="#aaa" opacity="0.4"/>\n'
        label = c.get("label", ref)
        for li, line in enumerate(label.split('\n')):
            fy = 4 + (li - len(label.split('\n')) / 2) * 10
            fs = 6 if ref[0] in "RCLY" else 7
            svg += (f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" '
                    f'font-family="monospace" font-size="{fs}">{line}</text>\n')
        svg += '</g>\n'

    # 500 yen comparison ring
    svg += (f'<circle cx="{ox + CX * S}" cy="{oy + CY * S}" r="{13.25 * S}" '
            f'fill="none" stroke="#c8a83e" stroke-width="0.8" stroke-dasharray="6,4" opacity="0.2"/>\n')
    svg += (f'<text x="{ox + CX * S + 13.25 * S + 5}" y="{oy + CY * S + 4}" '
            f'fill="#c8a83e" font-family="monospace" font-size="8" opacity="0.5">500yen</text>\n')

    # Info bar
    ly = img + 10
    svg += (f'<text x="{img // 2}" y="{ly}" text-anchor="middle" fill="#888" '
            f'font-family="monospace" font-size="9">20mm | 4-layer | {len(PARTS)} parts | '
            f'nRF54L15 BLE 5.4 + Channel Sounding + USB + I2S + PDM</text>\n')

    # Power comparison bar: nRF52840 vs nRF54L15
    ly += 20
    bar_w = img - 120
    items = [
        ("nRF52840 (v6)",   8.0, "#ef5350"),
        ("nRF54L15 (v7)",   5.0, "#66bb6a"),
    ]
    max_ma = 10.0
    for i, (name, ma, col) in enumerate(items):
        y = ly + i * 22
        w = ma / max_ma * bar_w
        svg += (f'<rect x="60" y="{y - 8}" width="{w}" height="14" '
                f'fill="{col}" rx="2" opacity="0.7"/>\n')
        svg += (f'<text x="55" y="{y + 3}" text-anchor="end" fill="#aaa" '
                f'font-family="monospace" font-size="9">{name}</text>\n')
        svg += (f'<text x="{65 + w}" y="{y + 3}" fill="#eee" '
                f'font-family="monospace" font-size="9" font-weight="bold">{ma:.1f}mA</text>\n')

    ly += 55
    svg += (f'<text x="{img // 2}" y="{ly}" text-anchor="middle" fill="#66bb6a" '
            f'font-family="monospace" font-size="10" font-weight="bold">'
            f'150mAh / 5mA = 30 hours runtime (vs 18.8h nRF52840)</text>\n')
    svg += (f'<text x="{img // 2}" y="{ly + 18}" text-anchor="middle" fill="#c8a83e" '
            f'font-family="monospace" font-size="9">'
            f'MIC -> I2S -> nRF54L15 -> USB Audio / BLE 5.4 Audio (LC3)</text>\n')
    svg += (f'<text x="{img // 2}" y="{ly + 34}" text-anchor="middle" fill="#888" '
            f'font-family="monospace" font-size="8">'
            f'BQ25100 charger (Iq=75nA) + XC6220 LDO (Iq=8uA) + Channel Sounding</text>\n')

    svg += '</svg>\n'
    path = GBR / "koe-coin-layout.svg"
    path.write_text(svg)
    print(f"SVG: {path}")


def check():
    errs = []
    for ref, c in PARTS.items():
        if ref == "J1":
            continue  # USB-C extends to board edge by design
        fp = FP[c["fp"]]
        cx, cy = c["x"], c["y"]
        sw, sh = fp["size"]
        for dx, dy in [(-sw / 2, -sh / 2), (sw / 2, -sh / 2),
                       (sw / 2, sh / 2), (-sw / 2, sh / 2)]:
            if not in_circle(cx + dx, cy + dy, 0):
                errs.append(f"  {ref} ({cx + dx:.1f},{cy + dy:.1f}) outside!")
    if errs:
        print("DRC WARNINGS:")
        for e in errs:
            print(e)
    else:
        print("DRC: All OK — all parts fit in 20mm circle")
    return len(errs) == 0


def main():
    print("=" * 65)
    print("Koe COIN v7 — 20mm Round, nRF54L15 BLE 5.4 + Channel Sounding")
    print(f"  {len(PARTS)} parts | ~5mA BLE streaming | 150mAh -> 30h")
    print("=" * 65)
    check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()
    print(f"\nPower budget:")
    print(f"  nRF54L15 BLE TX:    3.5mA (BLE 5.4, duty cycled)")
    print(f"  SPH0645 mic:        1.4mA")
    print(f"  XC6220 LDO (Iq):    0.008mA")
    print(f"  BQ25100 (Iq):        0.000075mA")
    print(f"  WS2812B (off):      0mA")
    print(f"  MAX98357A (idle):   0.01mA")
    print(f"  ─────────────────────────────")
    print(f"  Total (streaming):  ~5mA")
    print(f"  150mAh / 5mA = 30 hours")
    print(f"\nKey upgrades vs v6 (nRF52840):")
    print(f"  - BLE 5.4 + Channel Sounding (indoor positioning)")
    print(f"  - 37% lower power (8mA -> 5mA)")
    print(f"  - 60% longer runtime (18.8h -> 30h)")
    print(f"  - Smaller MCU: 6x6mm vs 7x7mm (QFN-48 vs aQFN-73)")
    print(f"  - BQ25100 charger: Iq=75nA (vs MCP73831 55uA = 740x lower)")


if __name__ == "__main__":
    main()
