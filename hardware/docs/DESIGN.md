# Koe Device — Hardware Design Specification

## Overview
常時録音・AI処理・音声応答ができる超小型ウェアラブルデバイス。
Koe (macOS/Windows音声入力アプリ) のスタンドアロンハードウェア版。

## Target Specs
| Spec | Target |
|------|--------|
| Size | 35 x 40 x 12mm (AirPodsケース以下) |
| Weight | < 25g (バッテリー込み) |
| Battery Life | 8-12時間 (常時録音) |
| Connectivity | WiFi 2.4GHz + BLE 5.0 + LTE-M (optional) |
| Audio Input | デュアルMEMSマイク (ビームフォーミング) |
| Audio Output | I2S DAC + 小型スピーカー or BT earbuds |
| Indicator | RGB LED x 1 (状態表示) |
| Button | タクトスイッチ x 1 (マルチファンクション) |
| Charging | USB-C (5V/500mA) |

## Architecture

```
                    ┌─────────────────────────────────┐
                    │        Koe Device PCB            │
                    │                                  │
  [MIC1 INMP441]───┤ GPIO/I2S                         │
  [MIC2 INMP441]───┤                                  │
                    │     ┌──────────────────┐         │
                    │     │   ESP32-S3-MINI  │         │
                    │     │                  │         │
  [USB-C]──────────┤─────│ USB              │         │
                    │     │                  │         │
  [LiPo 800mAh]───┤─────│ ADC (VBAT)       │         │
                    │     │                  │         │
                    │     │ I2S ─────────────┤───[MAX98357A]──[Speaker]
                    │     │                  │         │
                    │     │ GPIO ────────────┤───[WS2812B RGB LED]
                    │     │                  │         │
                    │     │ GPIO ────────────┤───[Button]
                    │     └──────────────────┘         │
                    │                                  │
                    │  [MCP73831] ← USB-C 5V           │
                    │  [AP2112K-3.3] → 3.3V rail       │
                    │                                  │
                    └─────────────────────────────────┘
```

## Key Component Selection

### 1. MCU: ESP32-S3-MINI-1 (N8R2)
- 8MB Flash, 2MB PSRAM
- Dual-core 240MHz Xtensa LX7
- WiFi 802.11 b/g/n + BLE 5.0
- USB OTG built-in
- Package: 15.4 x 20.5 x 2.4mm
- Why: 最小のESP32-S3モジュール。PSRAMで音声バッファ確保

### 2. Microphone: INMP441 x2
- I2S digital output (no ADC needed)
- SNR: 61dB, Sensitivity: -26dBFS
- Package: 4.72 x 3.76 x 1.0mm
- L/R select pin → 1本のI2Sバスでステレオ
- Why: デジタル出力でノイズ耐性高い、ESP32のI2Sと直結

### 3. Audio Output: MAX98357A
- I2S input, 3.2W Class D amp
- No MCLK required
- Package: 16-pin TQFN 1.6x1.6mm
- Why: I2S直結、外付け部品最少

### 4. Power: MCP73831 + AP2112K-3.3 + SS14 Schottky
- MCP73831: LiPo charger, 500mA, SOT-23-5
- AP2112K-3.3: LDO 3.3V/600mA, SOT-23-5
- SS14: Schottky diode for USB power path (VBUS → LDO)
- Battery: 802535 LiPo 800mAh (8x25x35mm)
- Power path: VBUS feeds MCP73831 (charging) AND AP2112K (operation) through Schottky diode, enabling use while charging. When USB disconnected, VBAT feeds LDO directly.
- Why: 最小部品数、実績あり、充電中も動作可能

### 5. LED: WS2812B-2020 (2x2mm)
- RGB, 1-wire control
- Why: 1 GPIOで制御、表現力十分

## Power Budget
> **Note:** All values below are CALCULATED estimates from datasheet typical values, NOT measured on actual hardware. Real-world consumption will vary depending on firmware, WiFi AP distance, ambient temperature, and battery age.

| Component | Active | Sleep |
|-----------|--------|-------|
| ESP32-S3 (WiFi active) | 120mA | 10uA |
| ESP32-S3 (recording, no WiFi) | 40mA | — |
| INMP441 x2 | 1.4mA | — |
| MAX98357A (idle) | 2mA | 0 (SD pin) |
| WS2812B | 1mA (dim) | 0 |
| LDO quiescent | 0.05mA | 0.05mA |
| VBAT ADC divider (10K+10K) | 0.21mA | 0.21mA |
| **Total (recording mode)** | **~45mA** | — |
| **Total (WiFi streaming)** | **~165mA** | — |

Battery life estimate (800mAh, calculated):
- Recording only: 800/45 = **~17 hours**
- Active streaming: 800/165 = **~4.8 hours**
- Mixed (80% record, 20% stream): **~12 hours**

## GPIO Assignment
ESP32-S3 has two independent I2S peripherals (I2S0, I2S1). Using separate buses for mic and speaker enables full-duplex operation (simultaneous recording and playback).

| GPIO | Function | Notes |
|------|----------|-------|
| GPIO 4 | I2S0_BCLK (MIC) | Mic bit clock |
| GPIO 5 | I2S0_WS (MIC) | Mic word select |
| GPIO 6 | I2S0_DIN (MIC data) | From INMP441 x2 |
| GPIO 14 | I2S1_BCLK (SPK) | Speaker bit clock |
| GPIO 21 | I2S1_WS (SPK) | Speaker word select |
| GPIO 7 | I2S1_DOUT (SPK data) | To MAX98357A |
| GPIO 8 | MAX98357A SD (enable) | HIGH=on |
| GPIO 15 | Button | Pull-up, active LOW |
| GPIO 16 | WS2812B data | NeoPixel |
| GPIO 1 | VBAT ADC | 10K/10K voltage divider |
| GPIO 19 | USB D- | USB-C |
| GPIO 20 | USB D+ | USB-C |

## PCB Design Rules
- 2-layer PCB, 1.0mm thickness
- Min trace: 0.15mm / Min space: 0.15mm
- Ground pour on both layers
- Keep analog (mic) traces short, away from digital/power
- USB impedance matching: 90 ohm differential
