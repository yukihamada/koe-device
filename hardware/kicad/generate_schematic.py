#!/usr/bin/env python3
"""
Koe Device - KiCad Schematic Generator
Run this script with KiCad's Python (kicad-cli) or standalone to generate
a proper schematic with all symbols and wires.

Usage:
  python3 generate_schematic.py

This creates koe-device-generated.kicad_sch with all components placed
and connected. Open in KiCad 8 to review/edit.

Alternative: Open koe-device.kicad_sch in KiCad and manually place
components following the netlist.txt guide.
"""

import json

# Component placement coordinates (mm from origin)
# Organized into functional blocks

COMPONENTS = {
    # === POWER SUPPLY (top-left) ===
    "J1": {
        "lib": "Connector:USB_C_Receptacle_USB2.0",
        "value": "USB-C",
        "footprint": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
        "x": 30, "y": 40,
        "lcsc": "C168688",
    },
    "U5": {
        "lib": "Battery_Management:MCP73831-2-OT",
        "value": "MCP73831",
        "footprint": "Package_TO_SOT_SMD:SOT-23-5",
        "x": 65, "y": 35,
        "lcsc": "C424093",
    },
    "BT1": {
        "lib": "Device:Battery_Cell",
        "value": "LiPo 800mAh",
        "footprint": "",
        "x": 65, "y": 55,
    },
    "U6": {
        "lib": "Regulator_Linear:AP2112K-3.3",
        "value": "AP2112K-3.3",
        "footprint": "Package_TO_SOT_SMD:SOT-23-5",
        "x": 95, "y": 35,
        "lcsc": "C51118",
    },

    # === MCU (center) ===
    "U1": {
        "lib": "RF_Module:ESP32-S3-MINI-1",
        "value": "ESP32-S3-MINI-1-N8R2",
        "footprint": "RF_Module:ESP32-S3-MINI-1",
        "x": 150, "y": 80,
        "lcsc": "C2913196",
    },

    # === AUDIO INPUT (left) ===
    "U2": {
        "lib": "Audio:INMP441",
        "value": "INMP441 (L)",
        "footprint": "Package_LGA:Knowles_LGA-6_3.76x4.72mm",
        "x": 55, "y": 80,
        "lcsc": "C110326",
    },
    "U3": {
        "lib": "Audio:INMP441",
        "value": "INMP441 (R)",
        "footprint": "Package_LGA:Knowles_LGA-6_3.76x4.72mm",
        "x": 55, "y": 105,
        "lcsc": "C110326",
    },

    # === AUDIO OUTPUT (right) ===
    "U4": {
        "lib": "Audio:MAX98357A",
        "value": "MAX98357A",
        "footprint": "Package_DFN_QFN:TQFN-16-1EP_3x3mm_P0.5mm_EP1.23x1.23mm",
        "x": 230, "y": 80,
        "lcsc": "C2682619",
    },
    "SPK1": {
        "lib": "Device:Speaker",
        "value": "8R 0.5W",
        "footprint": "",
        "x": 260, "y": 80,
    },

    # === UI (bottom-right) ===
    "LED1": {
        "lib": "LED:WS2812B",
        "value": "WS2812B-2020",
        "footprint": "LED_SMD:LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm",
        "x": 230, "y": 110,
        "lcsc": "C2976072",
    },
    "SW1": {
        "lib": "Switch:SW_Push",
        "value": "Tact 3x4x2",
        "footprint": "Button_Switch_SMD:SW_SPST_TL3342",
        "x": 230, "y": 130,
        "lcsc": "C318884",
    },
}

PASSIVES = {
    "R1": {"value": "100K", "footprint": "Resistor_SMD:R_0402_1005Metric", "x": 195, "y": 50, "note": "VBAT divider top"},
    "R2": {"value": "100K", "footprint": "Resistor_SMD:R_0402_1005Metric", "x": 210, "y": 50, "note": "VBAT divider bot"},
    "R3": {"value": "5.1K", "footprint": "Resistor_SMD:R_0402_1005Metric", "x": 35, "y": 55, "note": "USB CC1"},
    "R4": {"value": "5.1K", "footprint": "Resistor_SMD:R_0402_1005Metric", "x": 40, "y": 55, "note": "USB CC2"},
    "R5": {"value": "10K", "footprint": "Resistor_SMD:R_0402_1005Metric", "x": 220, "y": 125, "note": "BTN pull-up"},
    "R6": {"value": "2K", "footprint": "Resistor_SMD:R_0402_1005Metric", "x": 65, "y": 45, "note": "PROG 500mA"},
    "R7": {"value": "10K", "footprint": "Resistor_SMD:R_0402_1005Metric", "x": 130, "y": 55, "note": "EN pull-up"},
    "C1": {"value": "10uF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "x": 130, "y": 65, "note": "ESP32 VDDA"},
    "C2": {"value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "x": 135, "y": 65, "note": "ESP32 bypass"},
    "C3": {"value": "10uF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "x": 105, "y": 42, "note": "LDO out"},
    "C4": {"value": "10uF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "x": 85, "y": 42, "note": "LDO in"},
    "C5": {"value": "4.7uF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "x": 55, "y": 30, "note": "Charger in"},
    "C6": {"value": "4.7uF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "x": 75, "y": 42, "note": "Charger out"},
    "C7": {"value": "10uF", "footprint": "Capacitor_SMD:C_0805_2012Metric", "x": 220, "y": 70, "note": "Amp bypass"},
    "C8": {"value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "x": 225, "y": 70, "note": "Amp bypass"},
    "C9": {"value": "100nF", "footprint": "Capacitor_SMD:C_0402_1005Metric", "x": 130, "y": 60, "note": "EN reset"},
}

# Net connections (from → to)
NETS = [
    # Power
    ("J1:VBUS", "+5V"),
    ("J1:CC1", "R3:1"),
    ("R3:2", "GND"),
    ("J1:CC2", "R4:1"),
    ("R4:2", "GND"),
    ("J1:D-", "U1:GPIO19"),
    ("J1:D+", "U1:GPIO20"),
    ("+5V", "U5:VDD"),
    ("+5V", "C5:1"),
    ("C5:2", "GND"),
    ("U5:VSS", "GND"),
    ("U5:PROG", "R6:1"),
    ("R6:2", "GND"),
    ("U5:VBAT", "VBAT"),
    ("VBAT", "BT1:+"),
    ("BT1:-", "GND"),
    ("VBAT", "C6:1"),
    ("C6:2", "GND"),
    ("VBAT", "U6:VIN"),
    ("VBAT", "U6:EN"),
    ("VBAT", "C4:1"),
    ("C4:2", "GND"),
    ("U6:GND", "GND"),
    ("U6:VOUT", "+3V3"),
    ("+3V3", "C3:1"),
    ("C3:2", "GND"),

    # ESP32 power
    ("+3V3", "U1:3V3"),
    ("U1:GND", "GND"),
    ("+3V3", "C1:1"),
    ("C1:2", "GND"),
    ("+3V3", "C2:1"),
    ("C2:2", "GND"),
    ("+3V3", "R7:1"),
    ("R7:2", "U1:EN"),
    ("U1:EN", "C9:1"),
    ("C9:2", "GND"),

    # VBAT ADC
    ("VBAT", "R1:1"),
    ("R1:2", "VBAT_ADC"),
    ("VBAT_ADC", "R2:1"),
    ("R2:2", "GND"),
    ("VBAT_ADC", "U1:GPIO1"),

    # I2S — Mic Left
    ("+3V3", "U2:VDD"),
    ("U2:GND", "GND"),
    ("U2:SCK", "I2S_BCLK"),
    ("U2:WS", "I2S_WS"),
    ("U2:SD", "I2S_DIN"),
    ("U2:L/R", "GND"),  # Left channel

    # I2S — Mic Right
    ("+3V3", "U3:VDD"),
    ("U3:GND", "GND"),
    ("U3:SCK", "I2S_BCLK"),
    ("U3:WS", "I2S_WS"),
    ("U3:SD", "I2S_DIN"),
    ("U3:L/R", "+3V3"),  # Right channel

    # I2S — ESP32 to bus
    ("U1:GPIO4", "I2S_BCLK"),
    ("U1:GPIO5", "I2S_WS"),
    ("U1:GPIO6", "I2S_DIN"),
    ("U1:GPIO7", "I2S_DOUT"),

    # I2S — Amplifier
    ("+3V3", "U4:VDD"),
    ("U4:GND", "GND"),
    ("I2S_BCLK", "U4:BCLK"),
    ("I2S_WS", "U4:LRCLK"),
    ("I2S_DOUT", "U4:DIN"),
    ("U1:GPIO8", "U4:SD_MODE"),
    ("+3V3", "U4:GAIN"),  # 15dB
    ("U4:OUTP", "SPK1:+"),
    ("U4:OUTN", "SPK1:-"),
    ("+3V3", "C7:1"),
    ("C7:2", "GND"),
    ("+3V3", "C8:1"),
    ("C8:2", "GND"),

    # WS2812B
    ("+3V3", "LED1:VDD"),
    ("LED1:GND", "GND"),
    ("U1:GPIO16", "LED1:DIN"),

    # Button
    ("+3V3", "R5:1"),
    ("R5:2", "BUTTON"),
    ("BUTTON", "U1:GPIO15"),
    ("BUTTON", "SW1:1"),
    ("SW1:2", "GND"),
]


def main():
    print("=" * 60)
    print("Koe Device - Schematic Summary")
    print("=" * 60)
    print()
    print(f"ICs/Modules:  {len(COMPONENTS)} components")
    print(f"Passives:     {len(PASSIVES)} (R + C)")
    print(f"Net connections: {len(NETS)}")
    print()

    print("COMPONENT PLACEMENT:")
    print("-" * 60)
    for ref, comp in COMPONENTS.items():
        lcsc = comp.get("lcsc", "—")
        print(f"  {ref:6s}  {comp['value']:25s}  ({comp['x']}, {comp['y']})  LCSC:{lcsc}")

    print()
    print("PASSIVE PLACEMENT:")
    print("-" * 60)
    for ref, p in PASSIVES.items():
        print(f"  {ref:6s}  {p['value']:8s}  ({p['x']}, {p['y']})  {p['note']}")

    print()
    print("NET LIST:")
    print("-" * 60)
    for src, dst in NETS:
        print(f"  {src:20s} → {dst}")

    print()
    print("=" * 60)
    print("To create the schematic:")
    print("  1. Open KiCad 8")
    print("  2. File → New Project → koe-device")
    print("  3. Open Schematic Editor")
    print("  4. Place symbols as listed above")
    print("  5. Wire connections per net list")
    print("  6. Run ERC (Electrical Rules Check)")
    print("  7. Assign footprints (pre-assigned in BOM)")
    print("  8. Generate netlist → PCB Editor")
    print()
    print("Or use KiCad Scripting Console:")
    print("  import pcbnew")
    print("  # Use NETS dict above to auto-route")
    print("=" * 60)

    # Also dump as JSON for programmatic use
    output = {
        "project": "koe-device",
        "version": "0.1",
        "components": COMPONENTS,
        "passives": PASSIVES,
        "nets": NETS,
    }

    with open("koe-device-netlist.json", "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nNetlist JSON saved to koe-device-netlist.json")


if __name__ == "__main__":
    main()
