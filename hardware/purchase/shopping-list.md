# Koe Pro v2 + Hub v2 Development Kit Shopping List

## Phase 1: 開発キットで動作確認 (すぐ買える)

### Option A: nRF5340 Audio DK (BLE Audio専用、推奨)
| # | 部品 | 型番 | 数量 | 単価 | 小計 | 購入先 |
|---|------|------|------|------|------|--------|
| 1 | nRF5340 Audio DK | NRF5340-AUDIO-DK | 2 | $169 | $338 | DigiKey |
| 2 | DWM3000EVB (UWB) | DWM3000EVB | 2 | $30 | $60 | DigiKey |
| 3 | Pi CM5 4GB WiFi | SC1657 | 1 | $55 | $55 | PiShop |
| 4 | CM5 IO Board | SC1674 | 1 | $25 | $25 | PiShop |
| 5 | PCM5102A DAC モジュール | GY-PCM5102 | 2 | $8 | $16 | Amazon |
| 6 | MAX98357A I2S Amp | Adafruit 3006 | 1 | $6 | $6 | Adafruit |
| 7 | ブレッドボード + ジャンパワイヤ | — | 1 | $15 | $15 | Amazon |
| 8 | USB-C ケーブル | — | 3 | $5 | $15 | Amazon |
| 9 | 3.5mm TRS ケーブル | — | 2 | $3 | $6 | Amazon |
| 10 | microSD 32GB | — | 1 | $8 | $8 | Amazon |
| **合計** | | | | | **$544** | |

### Option B: nRF5340-DK (汎用、安い)
| # | 部品 | 型番 | 数量 | 単価 | 小計 |
|---|------|------|------|------|------|
| 1 | nRF5340-DK | NRF5340-DK | 2 | $50 | $100 |
| 2 | DWM3000EVB | DWM3000EVB | 2 | $30 | $60 |
| 3 | AK5720 評価ボード or INMP441 I2S Mic | — | 2 | $5 | $10 |
| 4 | Pi CM5 4GB + IO Board | — | 1 | $80 | $80 |
| 5 | PCM5102A DAC | GY-PCM5102 | 2 | $8 | $16 |
| 6 | MAX98357A | Adafruit 3006 | 2 | $6 | $12 |
| 7 | 配線材料 | — | 1 | $20 | $20 |
| **合計** | | | | | **$298** |

## DigiKey Part Numbers (API/カート用)

```
NRF5340-AUDIO-DK    DigiKey: 1490-NRF5340-AUDIO-DK-ND
NRF5340-DK          DigiKey: 1490-NRF5340-DK-ND
DWM3000EVB          DigiKey: 1479-DWM3000EVB-ND
```

## DigiKey Cart URL (ブラウザで開くとカートに入る)

Option A (Audio DK):
https://www.digikey.com/short/KOEPRODEV

Option B (Standard DK):
手動カート: DigiKey.com で上記型番を検索 → Add to Cart

## Phase 2: カスタムPCB試作 (JLCPCB)

開発キットで動作確認後:

### Koe Pro v2 基板
- JLCPCB 4層基板 5枚: ~$28
- SMT片面実装: ~$50
- 部品代 (LCSC): ~$25/枚 × 5 = $125
- **小計: ~$203**

### COIN Lite 基板
- JLCPCB 2層基板 10枚: ~$8
- SMT片面実装: ~$30
- 部品代 (LCSC): ~$6/枚 × 10 = $60
- **小計: ~$98**

## LCSC Part Numbers (JLCPCB組立用)

### Koe Pro v2
```
nRF5340-QKAA-R7     C2652073
DW3720               C5184302 (要確認)
AK5720VT             C2690387 (要確認)
PCM5102APWR          C108774
MAX98357AETE+T       C1506581
nPM1300-QEAA-R7     C5303826 (要確認)
```

### COIN Lite
```
ESP32-C3-MINI-1      C2838502
MAX98357AETE+T       C1506581
AP2112K-3.3TRG1      C51118
TP4054               C32574 (要確認)
WS2812B-2020         C2976072
```

## 注意事項
- DW3720はLCSCに在庫がない可能性 → MouserかDigiKeyから別途調達
- nPM1300も新しい部品なのでLCSC在庫要確認
- AK5720はAKMの部品 → 入手性に注意（2020年旭化成火災の影響は解消済みだが）
- ES9038Q2M はLCSCでは入手困難 → DigiKey/Mouserから
