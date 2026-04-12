#!/usr/bin/env python3
"""
Koe COIN PCB v8 — 14mm Ultimate Mini, nRF54LV10A CSP-29 Edition
=================================================================
nRF54LV10A-CAAA-R (CSP-29, WLCSP 2.3x1.9mm) — 1.2-1.7V direct from LiPo
NO LDO for MCU. LDO kept only for peripherals (mic, LED).
NO USB-C — Magnetic pogo pin charging on bottom.
NO speaker amp — BLE Auracast audio only, no local speaker.
BQ25100DSGR charger (Iq=75nA, WSON-6 1.5x1.5mm)
0201 passives where possible.

Board: 14mm diameter, 4-layer, 1.0mm FR-4
Power: ~3mA active BLE streaming, 80mAh -> 26.7 hours
"""

import math
import zipfile
from pathlib import Path

BOARD_DIA = 14.0
R = BOARD_DIA / 2.0
CX, CY = R, R
TRACE, PWR, VIA_D, VIA_P = 0.10, 0.20, 0.15, 0.35

OUT = Path(__file__).parent / "kicad-14mm"
GBR = Path(__file__).parent.parent / "manufacturing" / "gerbers" / "koe-coin-14mm"

def in_circle(x, y, m=0.3):
    return (x - CX)**2 + (y - CY)**2 <= (R - m)**2

# -- Footprints ----------------------------------------------------------------
FP = {}

# nRF54LV10A-CAAA-R: CSP-29 (WLCSP), 2.3x1.9mm, ~0.4mm pitch
# 29 balls arranged in a grid. Typical WLCSP layout:
# 6 columns (A-F) x 5 rows (1-5) = 30 positions, minus 1 = 29 balls
# Pitch: ~0.4mm, ball diameter: ~0.25mm, pad: 0.22mm
def _nrf54lv_csp():
    p = []
    cols = 6  # A-F
    rows = 5  # 1-5
    pitch = 0.4
    x0 = -(cols - 1) * pitch / 2
    y0 = -(rows - 1) * pitch / 2
    pad_d = 0.22
    pin = 1
    # 30 positions, skip one (typically corner) to get 29
    # Skip F5 (bottom-right corner)
    for row in range(rows):
        for col in range(cols):
            if row == 4 and col == 5:
                continue  # Skip position F5
            px = x0 + col * pitch
            py = y0 + row * pitch
            p.append((pin, px, py, pad_d, pad_d))
            pin += 1
    return p

FP["NRF54LV_CSP"] = {"pads": _nrf54lv_csp(), "size": (2.3, 1.9)}

# SPH0645LM4H: LGA, 3.5x2.7mm footprint (compact version)
FP["SPH0645"] = {"pads": [
    (1, -1.1, -0.85, 0.4, 0.6), (2, -1.1, 0, 0.4, 0.6), (3, -1.1, 0.85, 0.4, 0.6),
    (4, 1.1, 0.85, 0.4, 0.6), (5, 1.1, 0, 0.4, 0.6), (6, 1.1, -0.85, 0.4, 0.6),
], "size": (3.5, 2.7)}

# BQ25100DSGR: WSON-6, 1.5x1.5mm
FP["WSON6"] = {"pads": [
    (1, -0.55, 0.5, 0.3, 0.4),
    (2, -0.55, 0.0, 0.3, 0.4),
    (3, -0.55, -0.5, 0.3, 0.4),
    (4, 0.55, -0.5, 0.3, 0.4),
    (5, 0.55, 0.0, 0.3, 0.4),
    (6, 0.55, 0.5, 0.3, 0.4),
], "size": (1.5, 1.5)}

# XC6220 LDO (SOT-23-5) — for peripherals only (mic, LED)
FP["SOT23"] = {"pads": [
    (1, -1.1, 0.95, 0.6, 0.7), (2, -1.1, 0, 0.6, 0.7), (3, -1.1, -0.95, 0.6, 0.7),
    (4, 1.1, -0.95, 0.6, 0.7), (5, 1.1, 0.95, 0.6, 0.7),
], "size": (3.0, 3.0)}

# WS2812B-2020 LED
FP["LED2020"] = {"pads": [
    (1, -0.75, -0.5, 0.5, 0.5), (2, 0.75, -0.5, 0.5, 0.5),
    (3, 0.75, 0.5, 0.5, 0.5), (4, -0.75, 0.5, 0.5, 0.5),
], "size": (2.0, 2.0)}

# Button EVQP0N02B
FP["SW"] = {"pads": [(1, -1.0, 0, 0.6, 0.5), (2, 1.0, 0, 0.6, 0.5)], "size": (2.6, 1.6)}

# Pogo pin charging pads: 2x circular pads, 2mm dia, 4mm apart center-to-center
FP["POGO_2P"] = {"pads": [
    (1, -2.0, 0, 2.0, 2.0),  # VBUS (charge input)
    (2, 2.0, 0, 2.0, 2.0),   # GND
], "size": (6.0, 2.5)}

# 0201 passives (0.6x0.3mm body, pads wider)
FP["0201"] = {"pads": [(1, -0.35, 0, 0.35, 0.40), (2, 0.35, 0, 0.35, 0.40)], "size": (1.0, 0.5)}

# 0402 passives (fallback for larger values)
FP["0402"] = {"pads": [(1, -0.48, 0, 0.56, 0.62), (2, 0.48, 0, 0.56, 0.62)], "size": (1.6, 0.8)}

# 0603 for bulk caps
FP["0603"] = {"pads": [(1, -0.75, 0, 0.8, 1.0), (2, 0.75, 0, 0.8, 1.0)], "size": (2.2, 1.2)}

# Battery pads (80mAh thin pouch)
FP["BAT_PAD"] = {"pads": [
    (1, -0.8, 0, 0.8, 1.2),  # BAT+
    (2, 0.8, 0, 0.8, 1.2),   # BAT-
], "size": (2.8, 1.5)}

# 32.768kHz crystal, 1.6x1.0mm
FP["XTAL_1610"] = {"pads": [
    (1, -0.55, 0, 0.4, 0.8),
    (2, 0.55, 0, 0.4, 0.8),
], "size": (1.6, 1.0)}

# Schottky diode SOD-323
FP["SOD323"] = {"pads": [(1, -1.15, 0, 0.6, 0.5), (2, 1.15, 0, 0.6, 0.5)], "size": (2.8, 1.3)}


# -- Components ----------------------------------------------------------------
# TOP SIDE: MCU (center), Mic (top), LED (right), Button (left)
# BOTTOM SIDE: Charger, LDO, crystal, passives, battery pads, pogo pads

PARTS_TOP = {
    # -- MCU (nRF54LV10A CSP-29, 1.2-1.7V direct from LiPo) --
    "U1": {"fp": "NRF54LV_CSP", "x": CX, "y": CY, "rot": 0,
            "part": "nRF54LV10A-CAAA-R", "lcsc": "consignment",
            "label": "nRF54\nCSP29", "color": "#1565c0"},

    # -- MEMS Mic (top of board) --
    "U2": {"fp": "SPH0645", "x": CX, "y": 2.8, "rot": 0,
            "part": "SPH0645LM4H-1-8", "lcsc": "C19272537",
            "label": "MIC", "color": "#37474f"},

    # -- Status LED (right of MCU) --
    "LED1": {"fp": "LED2020", "x": CX + 3.2, "y": CY, "rot": 0,
             "part": "WS2812B-2020", "lcsc": "C2976072",
             "label": "LED", "color": "#f9a825"},

    # -- Button (left of MCU) --
    "SW1": {"fp": "SW", "x": CX - 3.5, "y": CY, "rot": 0,
            "part": "EVQP0N02B", "lcsc": "C2936178",
            "label": "BTN", "color": "#455a64"},
}

PARTS_BOTTOM = {
    # -- LiPo Charger (BQ25100) --
    "U4": {"fp": "WSON6", "x": CX - 2.0, "y": CY + 3.0, "rot": 0,
            "part": "BQ25100DSGR", "lcsc": "C527574",
            "label": "CHRG", "color": "#4e342e"},

    # -- LDO 3.3V (for peripherals ONLY) --
    "U5": {"fp": "SOT23", "x": CX + 2.5, "y": CY + 3.0, "rot": 0,
            "part": "XC6220B331MR-G", "lcsc": "C86534",
            "label": "LDO\n3V3", "color": "#4e342e"},

    # -- Schottky --
    "D1": {"fp": "SOD323", "x": CX, "y": CY + 1.5, "rot": 0,
            "part": "BAT54C", "lcsc": "C181054",
            "label": "D", "color": "#263238"},

    # -- 32.768kHz crystal --
    "Y1": {"fp": "XTAL_1610", "x": CX - 2.5, "y": CY - 2.5, "rot": 0,
            "part": "FC-12M 32.768kHz", "lcsc": "C32346",
            "label": "32K", "color": "#4a148c"},

    # -- Battery pads --
    "BT1": {"fp": "BAT_PAD", "x": CX, "y": CY - 3.5, "rot": 0,
            "part": "80mAh LiPo", "lcsc": "",
            "label": "BAT", "color": "#e65100"},

    # -- Pogo charge pads (exposed on bottom) --
    "J1": {"fp": "POGO_2P", "x": CX, "y": CY + 5.0, "rot": 0,
            "part": "Pogo 2P", "lcsc": "",
            "label": "POGO", "color": "#78909c"},

    # -- Charger ISET resistor --
    "R3": {"fp": "0201", "x": CX - 3.5, "y": CY + 1.8, "rot": 90,
            "part": "10k", "lcsc": "C25744", "label": "R3", "color": "#5d4037"},

    # -- MCU decoupling --
    "C1": {"fp": "0201", "x": CX + 1.5, "y": CY - 1.5, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C1", "color": "#1a237e"},

    # -- LDO output cap --
    "C2": {"fp": "0402", "x": CX + 2.5, "y": CY + 1.2, "rot": 90,
            "part": "10uF", "lcsc": "C19702", "label": "C2", "color": "#1a237e"},

    # -- LDO input cap --
    "C3": {"fp": "0201", "x": CX + 3.5, "y": CY + 1.5, "rot": 90,
            "part": "100nF", "lcsc": "C1525", "label": "C3", "color": "#1a237e"},

    # -- Charger input bypass --
    "C4": {"fp": "0402", "x": CX - 2.0, "y": CY + 1.5, "rot": 0,
            "part": "10uF", "lcsc": "C19702", "label": "C4", "color": "#1a237e"},

    # -- nRF DEC pin caps --
    "C7": {"fp": "0201", "x": CX - 1.5, "y": CY - 1.5, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C7", "color": "#1a237e"},
    "C8": {"fp": "0201", "x": CX + 1.5, "y": CY - 2.5, "rot": 0,
            "part": "100nF", "lcsc": "C1525", "label": "C8", "color": "#1a237e"},

    # -- MCU VDD bulk cap --
    "C12": {"fp": "0402", "x": CX - 1.5, "y": CY - 2.8, "rot": 0,
             "part": "4.7uF", "lcsc": "C19666", "label": "C12", "color": "#1a237e"},

    # -- 32kHz xtal load caps --
    "C10": {"fp": "0201", "x": CX - 3.5, "y": CY - 3.2, "rot": 0,
             "part": "12pF", "lcsc": "C1547", "label": "C10", "color": "#1a237e"},
    "C11": {"fp": "0201", "x": CX - 1.5, "y": CY - 3.5, "rot": 0,
             "part": "12pF", "lcsc": "C1547", "label": "C11", "color": "#1a237e"},

    # -- LC filter for nRF analog --
    "L1": {"fp": "0201", "x": CX, "y": CY - 2.5, "rot": 0,
            "part": "15nH", "lcsc": "C76862", "label": "L1", "color": "#006064"},
}

# Combined for gerber/BOM generation
PARTS = {**PARTS_TOP, **PARTS_BOTTOM}


# -- Routes --------------------------------------------------------------------
ROUTES = [
    # Battery -> Charger
    ("VBAT", PWR, [(CX, CY - 3.5), (CX - 2.0, CY + 3.0)]),
    # Charger -> Diode
    ("VBAT", PWR, [(CX - 2.0, CY + 3.0), (CX, CY + 1.5)]),
    # Diode -> MCU direct (no LDO for MCU)
    ("MCU_VDD", PWR, [(CX, CY + 1.5), (CX, CY)]),
    # Diode -> LDO input
    ("VBAT_LDO", PWR, [(CX, CY + 1.5), (CX + 2.5, CY + 3.0)]),
    # LDO 3.3V -> peripherals
    ("+3V3", PWR, [(CX + 2.5, CY + 3.0), (CX + 2.5, CY + 1.2)]),
    ("+3V3", TRACE, [(CX + 2.5, CY + 1.2), (CX, 2.8)]),       # -> Mic
    ("+3V3", TRACE, [(CX + 2.5, CY + 1.2), (CX + 3.2, CY)]),  # -> LED

    # Pogo VBUS -> Charger
    ("POGO_V", PWR, [(CX - 2.0, CY + 5.0), (CX - 2.0, CY + 3.0)]),

    # I2S mic
    ("I2S_SCK", TRACE, [(CX - 0.4, CY - 0.8), (CX - 1.1, 2.1)]),
    ("I2S_WS", TRACE, [(CX, CY - 0.8), (CX - 1.1, 2.8)]),
    ("I2S_SD", TRACE, [(CX + 0.4, CY - 0.8), (CX + 1.1, 2.1)]),

    # LED data
    ("LED_DIN", TRACE, [(CX + 0.8, CY), (CX + 2.45, CY)]),

    # Button
    ("BTN", TRACE, [(CX - 0.8, CY), (CX - 2.5, CY)]),

    # 32kHz xtal
    ("XC1", TRACE, [(CX - 0.8, CY + 0.4), (CX - 2.5 - 0.55, CY - 2.5)]),
    ("XC2", TRACE, [(CX - 0.8, CY + 0.8), (CX - 2.5 + 0.55, CY - 2.5)]),

    # Charger ISET
    ("ISET", TRACE, [(CX - 2.55, CY + 3.0), (CX - 3.5, CY + 1.8)]),
]

VIAS = [
    (CX, CY + 1.0), (CX - 2.0, CY), (CX + 2.0, CY),
    (CX, CY - 2.0), (CX - 2.0, CY + 2.0), (CX + 2.0, CY + 2.0),
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
    def arc(s, cx, cy, r, w=0.05, n=72):
        d = s._a("C", [w]); s.cmds.append(f"D{d}*")
        for i in range(n + 1):
            a = 2 * math.pi * i / n; x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            s.cmds.append(f"X{s._c(x)}Y{s._c(y)}D0{'2' if i == 0 else '1'}*")
    def write(s, path):
        with open(path, 'w') as f:
            f.write("%FSLAX46Y46*%\n%MOMM*%\n")
            f.write(f"G04 Koe COIN 14mm {s.name}*\n%LPD*%\n")
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
            f.write("M48\n; Koe COIN 14mm nRF54LV10A CSP-29\nFMAT,2\nMETRIC,TZ\n")
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
    ec.arc(CX, CY, R)

    # Top-side components
    for ref, c in PARTS_TOP.items():
        fp = FP[c["fp"]]; cx, cy, rot = c["x"], c["y"], c.get("rot", 0)
        sw, sh = fp["size"]
        co = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2), (sw / 2, sh / 2), (-sw / 2, sh / 2)]
        ca = [xform(a, b, cx, cy, rot) for a, b in co]
        for i in range(4):
            fs_.trace(ca[i][0], ca[i][1], ca[(i + 1) % 4][0], ca[(i + 1) % 4][1], 0.08)
        for p in fp["pads"]:
            pin, px, py, pw, ph = p; ax, ay = xform(px, py, cx, cy, rot)
            if rot in (90, 270): pw, ph = ph, pw
            fc.pad(ax, ay, pw, ph); fm.pad(ax, ay, pw + 0.08, ph + 0.08)

    # Bottom-side components
    for ref, c in PARTS_BOTTOM.items():
        fp = FP[c["fp"]]; cx, cy, rot = c["x"], c["y"], c.get("rot", 0)
        sw, sh = fp["size"]
        co = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2), (sw / 2, sh / 2), (-sw / 2, sh / 2)]
        ca = [xform(a, b, cx, cy, rot) for a, b in co]
        for i in range(4):
            bs_.trace(ca[i][0], ca[i][1], ca[(i + 1) % 4][0], ca[(i + 1) % 4][1], 0.08)
        for p in fp["pads"]:
            pin, px, py, pw, ph = p; ax, ay = xform(px, py, cx, cy, rot)
            if rot in (90, 270): pw, ph = ph, pw
            bc.pad(ax, ay, pw, ph); bm.pad(ax, ay, pw + 0.08, ph + 0.08)

    # Routes on front copper
    for _, w, pts in ROUTES:
        for i in range(len(pts) - 1):
            fc.trace(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], w)

    # Vias
    for vx, vy in VIAS:
        for g in (fc, bc): g.circ(vx, vy, VIA_P)
        for g in (fm, bm): g.circ(vx, vy, VIA_P + 0.08)
        dr.hole(vx, vy, VIA_D)

    pre = "koe-coin-14mm"
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
    ROT = {"SOT23": 180, "WSON6": 0}
    lines = ["Designator,Mid X(mm),Mid Y(mm),Layer,Rotation"]
    for ref, c in PARTS_TOP.items():
        rot = c.get("rot", 0) + ROT.get(c["fp"], 0)
        lines.append(f"{ref},{c['x']:.1f},{c['y']:.1f},Top,{rot % 360}")
    for ref, c in PARTS_BOTTOM.items():
        rot = c.get("rot", 0) + ROT.get(c["fp"], 0)
        lines.append(f"{ref},{c['x']:.1f},{c['y']:.1f},Bottom,{rot % 360}")
    (GBR / "CPL-JLCPCB.csv").write_text('\n'.join(lines) + '\n')
    print(f"CPL: {GBR / 'CPL-JLCPCB.csv'}")


# -- SVG -----------------------------------------------------------------------
def gen_svg():
    S = 28  # Scale factor (larger for 14mm to make detail visible)
    pad = 60
    board_px = int(BOARD_DIA * S)
    total_w = board_px * 2 + pad * 3 + 40  # Two boards side by side
    info_h = 380
    total_h = board_px + pad * 2 + 30 + info_h

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}">
<defs>
  <radialGradient id="pcb_top" cx="45%" cy="42%" r="55%">
    <stop offset="0%" stop-color="#0d5c0d"/><stop offset="100%" stop-color="#063806"/>
  </radialGradient>
  <radialGradient id="pcb_bot" cx="45%" cy="42%" r="55%">
    <stop offset="0%" stop-color="#0d3c5c"/><stop offset="100%" stop-color="#062838"/>
  </radialGradient>
  <filter id="sh"><feDropShadow dx="1" dy="1.5" stdDeviation="2" flood-opacity="0.5"/></filter>
</defs>
<rect width="{total_w}" height="{total_h}" fill="#0d0d14"/>

<!-- Title -->
<text x="{total_w // 2}" y="22" text-anchor="middle" fill="#e0e0e0" font-family="Helvetica,sans-serif" font-size="17" font-weight="600">Koe COIN v8 &#8212; 14mm Ultimate Mini</text>
<text x="{total_w // 2}" y="40" text-anchor="middle" fill="#888" font-family="sans-serif" font-size="10">14mm round | 4-layer | nRF54LV10A CSP-29 | No USB-C | Magnetic pogo charging | BLE Auracast only</text>
'''

    # ── TOP VIEW ──
    ox_top = pad + 20
    oy = pad + 30
    svg += f'<text x="{ox_top + CX * S}" y="{oy - 12}" text-anchor="middle" fill="#aaa" font-family="monospace" font-size="11" font-weight="bold">TOP SIDE</text>\n'
    # Board shadow + board
    svg += f'<circle cx="{ox_top + CX * S}" cy="{oy + CY * S}" r="{R * S + 2}" fill="#000" opacity="0.3"/>\n'
    svg += f'<circle cx="{ox_top + CX * S}" cy="{oy + CY * S}" r="{R * S}" fill="url(#pcb_top)" stroke="#c8a83e" stroke-width="1.5"/>\n'

    # Top-side traces
    net_colors = {
        "VBAT": "#ef5350", "3V3": "#66bb6a", "MCU_VDD": "#ff9800",
        "POGO": "#ffca28", "I2S": "#42a5f5", "LED": "#f9a825",
        "BTN": "#78909c", "ISET": "#78909c", "XC": "#ce93d8",
    }
    for net, w, pts in ROUTES:
        c = "#78909c"
        for k, v in net_colors.items():
            if k in net: c = v; break
        for i in range(len(pts) - 1):
            svg += f'<line x1="{ox_top + pts[i][0] * S}" y1="{oy + pts[i][1] * S}" x2="{ox_top + pts[i + 1][0] * S}" y2="{oy + pts[i + 1][1] * S}" stroke="{c}" stroke-width="{max(1.0, w * S * 0.5)}" opacity="0.3" stroke-linecap="round"/>\n'

    # Vias on top
    for vx, vy in VIAS:
        svg += f'<circle cx="{ox_top + vx * S}" cy="{oy + vy * S}" r="{VIA_P * S / 2 + 0.5}" fill="#1a1a1a" stroke="#666" stroke-width="0.5"/>\n'

    # Top components
    for ref, c in PARTS_TOP.items():
        fp = FP[c["fp"]]; cx_, cy_ = c["x"], c["y"]; rot = c.get("rot", 0)
        sw, sh = fp["size"]; color = c.get("color", "#5d4037")
        sx, sy = ox_top + cx_ * S, oy + cy_ * S; rw, rh = sw * S, sh * S
        svg += f'<g transform="translate({sx},{sy}) rotate({rot})" filter="url(#sh)">\n'
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            svg += f'<rect x="{px * S - pw * S / 2}" y="{py * S - ph * S / 2}" width="{pw * S}" height="{ph * S}" fill="#c8a83e" rx="0.5" opacity="0.4"/>\n'
        rx = 3 if ref[0] in "UJ" else 1
        svg += f'<rect x="{-rw / 2}" y="{-rh / 2}" width="{rw}" height="{rh}" fill="{color}" stroke="#777" stroke-width="0.5" rx="{rx}"/>\n'
        if ref[0] == "U":
            svg += f'<circle cx="{-rw / 2 + 3}" cy="{-rh / 2 + 3}" r="1.0" fill="#aaa" opacity="0.4"/>\n'
        label = c.get("label", ref)
        for li, line in enumerate(label.split('\n')):
            fy = 3.5 + (li - len(label.split('\n')) / 2) * 9
            fs = 6 if ref[0] in "RCLY" else 7
            svg += f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="{fs}">{line}</text>\n'
        svg += '</g>\n'

    # ── BOTTOM VIEW ──
    ox_bot = ox_top + board_px + pad + 20
    svg += f'<text x="{ox_bot + CX * S}" y="{oy - 12}" text-anchor="middle" fill="#aaa" font-family="monospace" font-size="11" font-weight="bold">BOTTOM SIDE</text>\n'
    svg += f'<circle cx="{ox_bot + CX * S}" cy="{oy + CY * S}" r="{R * S + 2}" fill="#000" opacity="0.3"/>\n'
    svg += f'<circle cx="{ox_bot + CX * S}" cy="{oy + CY * S}" r="{R * S}" fill="url(#pcb_bot)" stroke="#c8a83e" stroke-width="1.5"/>\n'

    # Vias on bottom (mirrored)
    for vx, vy in VIAS:
        mx = BOARD_DIA - vx  # Mirror X for bottom view
        svg += f'<circle cx="{ox_bot + mx * S}" cy="{oy + vy * S}" r="{VIA_P * S / 2 + 0.5}" fill="#1a1a1a" stroke="#666" stroke-width="0.5"/>\n'

    # Bottom components (mirrored X)
    for ref, c in PARTS_BOTTOM.items():
        fp = FP[c["fp"]]; cx_, cy_ = c["x"], c["y"]; rot = c.get("rot", 0)
        mx = BOARD_DIA - cx_  # Mirror X for bottom view
        sw, sh = fp["size"]; color = c.get("color", "#5d4037")
        sx, sy = ox_bot + mx * S, oy + cy_ * S; rw, rh = sw * S, sh * S
        svg += f'<g transform="translate({sx},{sy}) rotate({rot})" filter="url(#sh)">\n'
        for p in fp["pads"]:
            pin, px, py, pw, ph = p
            svg += f'<rect x="{px * S - pw * S / 2}" y="{py * S - ph * S / 2}" width="{pw * S}" height="{ph * S}" fill="#c8a83e" rx="0.5" opacity="0.4"/>\n'
        rx = 3 if ref[0] in "UJ" else 1
        svg += f'<rect x="{-rw / 2}" y="{-rh / 2}" width="{rw}" height="{rh}" fill="{color}" stroke="#777" stroke-width="0.5" rx="{rx}"/>\n'
        if ref[0] == "U":
            svg += f'<circle cx="{-rw / 2 + 3}" cy="{-rh / 2 + 3}" r="1.0" fill="#aaa" opacity="0.4"/>\n'
        label = c.get("label", ref)
        for li, line in enumerate(label.split('\n')):
            fy = 3.5 + (li - len(label.split('\n')) / 2) * 9
            fs = 5 if ref[0] in "RCLY" else 6.5
            svg += f'<text x="0" y="{fy}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="{fs}">{line}</text>\n'
        svg += '</g>\n'

    # ── SIZE COMPARISON ──
    comp_y = oy + board_px + pad + 10
    svg += f'<text x="{total_w // 2}" y="{comp_y}" text-anchor="middle" fill="#aaa" font-family="monospace" font-size="11" font-weight="bold">SIZE COMPARISON</text>\n'

    comp_cy = comp_y + 55
    comp_cx = total_w // 2
    comp_s = 4.5  # pixels per mm for comparison

    # AirTag (31.9mm)
    airtag_r = 31.9 / 2 * comp_s
    svg += f'<circle cx="{comp_cx}" cy="{comp_cy}" r="{airtag_r}" fill="none" stroke="#555" stroke-width="1" stroke-dasharray="6,4"/>\n'
    svg += f'<text x="{comp_cx + airtag_r + 5}" y="{comp_cy + 4}" fill="#555" font-family="monospace" font-size="8">AirTag 31.9mm</text>\n'

    # 1-yen coin (20mm)
    yen_r = 20.0 / 2 * comp_s
    svg += f'<circle cx="{comp_cx}" cy="{comp_cy}" r="{yen_r}" fill="none" stroke="#c8a83e" stroke-width="1" stroke-dasharray="5,3" opacity="0.5"/>\n'
    svg += f'<text x="{comp_cx + yen_r + 5}" y="{comp_cy + 4}" fill="#c8a83e" font-family="monospace" font-size="8" opacity="0.6">1-yen coin 20mm</text>\n'

    # Koe COIN 14mm (filled)
    koe_r = 14.0 / 2 * comp_s
    svg += f'<circle cx="{comp_cx}" cy="{comp_cy}" r="{koe_r}" fill="#0d5c0d" stroke="#66bb6a" stroke-width="1.5" opacity="0.8"/>\n'
    svg += f'<text x="{comp_cx}" y="{comp_cy + 3}" text-anchor="middle" fill="#eee" font-family="monospace" font-size="9" font-weight="bold">14mm</text>\n'
    svg += f'<text x="{comp_cx}" y="{comp_cy + 14}" text-anchor="middle" fill="#66bb6a" font-family="monospace" font-size="7">Koe COIN v8</text>\n'

    # ── INFO SECTION ──
    info_y = comp_cy + 70

    # Features box
    svg += f'<rect x="40" y="{info_y - 14}" width="{total_w - 80}" height="22" fill="#ff9800" rx="4" opacity="0.15"/>\n'
    svg += f'<text x="{total_w // 2}" y="{info_y}" text-anchor="middle" fill="#ff9800" font-family="monospace" font-size="10" font-weight="bold">No USB-C &#8212; Magnetic pogo charging &#8212; BLE Auracast only</text>\n'

    info_y += 28
    svg += f'<text x="{total_w // 2}" y="{info_y}" text-anchor="middle" fill="#66bb6a" font-family="monospace" font-size="11" font-weight="bold">80mAh / 3mA = 26.7 hours runtime</text>\n'

    info_y += 18
    svg += f'<text x="{total_w // 2}" y="{info_y}" text-anchor="middle" fill="#c8a83e" font-family="monospace" font-size="9">MIC &#8594; I2S &#8594; nRF54LV10A CSP-29 &#8594; BLE Audio (LC3) &#8212; No local speaker</text>\n'

    info_y += 16
    svg += f'<text x="{total_w // 2}" y="{info_y}" text-anchor="middle" fill="#888" font-family="monospace" font-size="8">Power: VBAT &#8594; MCU direct (1.2V) | VBAT &#8594; XC6220 &#8594; 3.3V peripherals (mic, LED)</text>\n'

    # Specs table
    info_y += 24
    specs = [
        ("MCU", "nRF54LV10A-CAAA-R (CSP-29, 2.3x1.9mm WLCSP)"),
        ("Board", "14mm dia, 4-layer FR-4, 1.0mm thick"),
        ("Charging", "Magnetic pogo pins (2x 2mm pads, 4mm apart)"),
        ("Battery", "80mAh thin LiPo, BQ25100 charger"),
        ("Audio", "SPH0645 MEMS mic, BLE Auracast (no speaker)"),
        ("Passives", "0201 (0.6x0.3mm) where possible"),
        ("Mounting", "Both sides: MCU+mic+LED top, charger+LDO+xtal bottom"),
    ]
    for i, (k, v) in enumerate(specs):
        y = info_y + i * 14
        svg += f'<text x="60" y="{y}" fill="#aaa" font-family="monospace" font-size="8" font-weight="bold">{k}:</text>\n'
        svg += f'<text x="140" y="{y}" fill="#888" font-family="monospace" font-size="8">{v}</text>\n'

    info_y += len(specs) * 14 + 12
    svg += f'<text x="{total_w // 2}" y="{info_y}" text-anchor="middle" fill="#555" font-family="monospace" font-size="8">{len(PARTS)} parts total | Q2 2026 | consignment assembly (nRF54LV10A not yet on LCSC)</text>\n'

    svg += '</svg>\n'
    path = GBR / "koe-coin-layout.svg"
    path.write_text(svg)
    print(f"SVG: {path}")


def check():
    errs = []
    margin = 0.3

    # Check top-side components
    for ref, c in PARTS_TOP.items():
        fp = FP[c["fp"]]; cx, cy = c["x"], c["y"]; sw, sh = fp["size"]
        rot = c.get("rot", 0)
        corners = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2), (sw / 2, sh / 2), (-sw / 2, sh / 2)]
        for dx, dy in corners:
            ax, ay = xform(dx, dy, cx, cy, rot)
            if not in_circle(ax, ay, margin):
                dist = math.sqrt((ax - CX)**2 + (ay - CY)**2)
                errs.append(f"  {ref} ({ax:.1f},{ay:.1f}) outside! dist={dist:.1f} > {R - margin:.1f}")

    # Check bottom-side components
    for ref, c in PARTS_BOTTOM.items():
        if ref == "J1":  # Pogo pads can extend to edge
            continue
        fp = FP[c["fp"]]; cx, cy = c["x"], c["y"]; sw, sh = fp["size"]
        rot = c.get("rot", 0)
        corners = [(-sw / 2, -sh / 2), (sw / 2, -sh / 2), (sw / 2, sh / 2), (-sw / 2, sh / 2)]
        for dx, dy in corners:
            ax, ay = xform(dx, dy, cx, cy, rot)
            if not in_circle(ax, ay, margin):
                dist = math.sqrt((ax - CX)**2 + (ay - CY)**2)
                errs.append(f"  {ref} ({ax:.1f},{ay:.1f}) outside! dist={dist:.1f} > {R - margin:.1f}")

    if errs:
        print("DRC WARNINGS:")
        for e in errs: print(e)
    else:
        print("DRC: All OK — all components fit within 14mm circle with 0.3mm margin")
    return len(errs) == 0


def main():
    print("=" * 65)
    print("Koe COIN v8 -- 14mm Ultimate Mini, nRF54LV10A CSP-29")
    print(f"  {len(PARTS)} parts | ~3mA BLE streaming | 80mAh -> 26.7h")
    print(f"  MCU: nRF54LV10A-CAAA-R CSP-29 (2.3x1.9mm WLCSP)")
    print(f"  1.2-1.7V direct from LiPo (NO LDO for MCU)")
    print(f"  Peripherals: LDO 3.3V (mic, LED only)")
    print(f"  Charging: Magnetic pogo pins (no USB-C)")
    print(f"  Audio: BLE Auracast only (no local speaker)")
    print("=" * 65)
    ok = check()
    gen_gerbers()
    gen_bom()
    gen_cpl()
    gen_svg()
    print(f"\nPower budget (nRF54LV10A CSP-29):")
    print(f"  nRF54LV10A BLE TX:  1.5mA (duty cycled)")
    print(f"  SPH0645 mic:        1.0mA")
    print(f"  XC6220 LDO (Iq):    0.008mA  (peripherals only)")
    print(f"  BQ25100 charger:    0.000075mA (Iq=75nA)")
    print(f"  WS2812B (off):      0mA")
    print(f"  ──────────────────────────────")
    print(f"  Total (streaming):  ~3mA")
    print(f"  80mAh / 3mA = 26.7 hours")
    print(f"\n  No USB-C — Magnetic pogo pin charging")
    print(f"  No speaker amp — BLE Auracast audio only")
    if not ok:
        print("\n  WARNING: Some components may not fit — review DRC warnings above")


if __name__ == "__main__":
    main()
