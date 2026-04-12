# Koe Pro v2 --- KiCad Project

nRF5340 + DW3720 UWB, 45x30mm 4-layer PCB.

## Open in KiCad
1. Install KiCad 8.0+
2. Open koe-pro-v2.kicad_pro
3. Install Nordic lib: Plugin Manager -> Add repo -> https://raw.githubusercontent.com/hlord2000/hlord2000-kicad-repository/main/repository.json

## Generate Manufacturing Files
1. Plot -> Gerber (F.Cu, B.Cu, In1.Cu, In2.Cu, F.Mask, B.Mask, F.SilkS, Edge.Cuts)
2. Drill -> Excellon
3. BOM -> KiCad BOM plugin
4. CPL -> Fabrication Outputs -> Footprint Position

## JLCPCB Order
1. Upload Gerber ZIP
2. Select 4-layer, 1.6mm, FR-4, HASL
3. Upload BOM + CPL for SMT assembly

## Key ICs
| Ref | Part | Function |
|-----|------|----------|
| U1 | nRF5340-QKAA | BLE 5.3 MCU (dual-core M33) |
| U2 | DW3720 | UWB transceiver |
| U3 | AK5720 | 24-bit ADC |
| U4 | PCM5102A | 32-bit DAC |
| U5 | MAX98357A | I2S speaker amp |
| U6 | nPM1300 | PMIC (LiPo charger + buck) |

## BOM Cost
~$23.05 per board (JLCPCB SMT assembly)
