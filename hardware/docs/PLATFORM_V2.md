# Soluna Edition v2 — 確定仕様

## アーキテクチャ (確定 2026-03-18)

- **STAGE:** Raspberry Pi 5 + Intel BE200 (WiFi 7) + HiFiBerry DAC + GPS
- **CROWD:** ESP32-S3 (WiFi 4) — コスト最適、音声帯域には十分

### なぜこの組み合わせか

| | STAGE (Pi 5) | CROWD (ESP32-S3) |
|---|---|---|
| **WiFi** | WiFi 7 (BE200, 2.4Gbps) | WiFi 4 (2.4GHz, 150Mbps) |
| **なぜ** | 500台のCROWDを捌く | 音声128kbpsに150Mbpsは十分 |
| **CPU** | Cortex-A76 x4 2.4GHz | Xtensa LX7 x2 240MHz |
| **RAM** | 4GB DDR4 | 8MB PSRAM |
| **価格** | ~$60 (Pi5) + $20 (BE200) | $3.50 |
| **台数** | 1-4台 / イベント | 100-1000台 |

### 音声に必要な帯域

| データ | 帯域 |
|--------|------|
| PCM 48kHz/16bit mono | 768 kbps |
| Opus 128kbps | 128 kbps |
| UDP multicast → 何台でも同じ | 128 kbps |

→ WiFi 4 (150Mbps) でも1000倍以上の余裕。WiFi 7はCROWDには不要。

## アーキテクチャ図

```
┌─────────────────────────────────────────────────────┐
│  STAGE (Raspberry Pi 5)                             │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Pi 5     │  │ HiFiBerry│  │ GPS HAT          │  │
│  │ WiFi 7   │  │ DAC+ Pro │  │ u-blox NEO-M9N   │  │
│  │(BE200    │  │ PCM5122  │  │ 1PPS → GPIO      │  │
│  │ M.2 HAT) │  │ 192kHz   │  │ TCXO 0.5ppm      │  │
│  │ GbE      │  │ -112dB   │  └──────────────────┘  │
│  │ 4GB RAM  │  │ SNR      │                         │
│  │ 32GB SD  │  └──────────┘  ┌──────────────────┐  │
│  └──────────┘                │ Quectel EC25-J    │  │
│                              │ 4G LTE Cat-4      │  │
│  OS: Linux (Raspberry Pi OS) │ USB接続            │  │
│  Audio: PipeWire + ALSA      └──────────────────┘  │
│  Sync: ptp4l (IEEE 1588)                           │
│  Stream: GStreamer + Opus/FLAC                      │
│  Dashboard: FastAPI + WebSocket                     │
│  GPS: gpsd                                          │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ TPA3255 Class-D 2ch (175W + 175W)           │   │
│  │ → 130mm同軸ドライバー (Bi-amp: LF + HF)     │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  CROWD (ESP32-S3 — コスト最適、十分な性能)          │
│                                                     │
│  ESP32-S3-MINI-1 (8MB/2MB)                          │
│  + MAX-M10S GPS (1PPS)                              │
│  + SIM7080G LTE-M                                   │
│  + MAX98357A → 40mm Full Range                      │
│  + BME280 (温度→音速補正)                            │
│  + LRA触覚モーター (サブベース体感)                   │
│                                                     │
│  NTP + GPS 1PPSで時刻同期                            │
│  STAGEのPTPクロックに従属                             │
│  音速補正ディレイ自動計算                              │
└─────────────────────────────────────────────────────┘
```

## なぜ Raspberry Pi CM5 か

| 要件 | ESP32-S3 | Pi CM5 | 理由 |
|------|----------|--------|------|
| WiFi 5GHz | NG | 802.11ac 2x2 | フェスで必須 |
| PTP (IEEE 1588) | 自前実装 | linuxptp (ptp4l) | カーネルレベルで<1μs |
| DAC品質 | I2S直、ノイズフロア高い | HiFiBerry DAC+ Pro (SNR -112dB) | プロ音響品質 |
| DSP処理 | Xtensa 240MHz、FPU弱い | Cortex-A76 2.4GHz x4、NEON SIMD | FIR EQ、AECがリアルタイムで余裕 |
| RAM | 8MB PSRAM | 4GB DDR4 | ジッターバッファ+DSP+Web UIが余裕 |
| Web UI | ESP32でHTTPサーバーは限界 | FastAPI + WebSocketでリアルタイムダッシュボード | 管理画面が本格的 |
| ストレージ | 8MB Flash | 32GB eMMC | ログ、録音、ファームウェアOTA |
| コスト | $3.50 | ~$45 (CM5 + IO board) | STAGEは数が少ないのでコスト許容 |

**CROWDはESP32-S3のまま。** 数百台必要で、$3.50と$45では勝負にならない。CROWDに求められるのは「安くて小さくて電池で動く」であり、ESP32-S3は最適解。

## STAGE ソフトウェアスタック

```
┌─────────────────────────────────┐
│          Web Dashboard          │  ← ブラウザからアクセス
│  (FastAPI + WebSocket + HTML)   │     全デバイス管理、EQ、ボリューム
├─────────────────────────────────┤
│        Soluna Controller        │  ← Pythonデーモン
│  - デバイス発見 (mDNS/Avahi)    │
│  - 音速補正計算 (GPS座標+温度)   │
│  - チャンネル管理               │
│  - 適応コーデック切替            │
├─────────────────────────────────┤
│    GStreamer Audio Pipeline      │  ← 音声処理
│  alsasrc → audioconvert         │
│  → DSP (EQ, compressor, limiter)│
│  → opusenc / flacenc            │
│  → udpsink (multicast)          │
│  + GPS timestamp injection      │
├─────────────────────────────────┤
│    PipeWire / ALSA              │  ← HALオーディオ
│  HiFiBerry DAC+ Pro (I2S)       │
├─────────────────────────────────┤
│    linuxptp (ptp4l + phc2sys)   │  ← IEEE 1588 PTP
│    gpsd + chrony                │  ← GPS 1PPS → システムクロック
├─────────────────────────────────┤
│    Linux Kernel (RT_PREEMPT)    │  ← リアルタイムカーネル
│    Raspberry Pi OS Lite 64-bit  │
└─────────────────────────────────┘
```

## 改訂BOMコスト

### STAGE (Pi CM5ベース)

| カテゴリ | 部品 | コスト |
|---------|------|--------|
| Compute | Pi CM5 4GB + IO Board | $55 |
| Audio DAC | HiFiBerry DAC+ Pro (PCM5122) | $35 |
| Amp | TPA3255EVM (175W x2) | $15 |
| Speaker | 130mm同軸ドライバー (Peerless) | $22 |
| GPS | u-blox NEO-M9N + active antenna | $22 |
| GPS clock | TCXO 0.5ppm + 1PPS interface | $5 |
| Cellular | Quectel EC25-J (4G Cat-4) USB | $18 |
| Temperature | BME280 | $1 |
| Power | 24V/5A PSU + 6S Li-ion 5Ah + BMS | $40 |
| Enclosure | アルミ筐体 + ガスケット | $22 |
| PCB/配線 | キャリアボード + ケーブル | $15 |
| Input | XLR + 3.5mm + USB-C | $5 |
| LED | WS2812B x5 | $0.40 |
| Misc | microSD, ファン、熱対策 | $5 |
| **合計** | | **~$260** |
| **小売想定 (2.5x)** | | **~$650** |

### CROWD (ESP32-S3ベース、変更なし + 改善追加)

| カテゴリ | 部品 | コスト |
|---------|------|--------|
| MCU | ESP32-S3-MINI-1 | $3.50 |
| Audio | MAX98357A + 40mm driver | $5.30 |
| GPS | u-blox MAX-M10S + chip antenna | $10.50 |
| Cellular | SIM7080G + chip antenna | $10.50 |
| Mic | INMP441 | $1.20 |
| Temperature | BME280 | $1.00 |
| Haptics | LRA motor + DRV2605L | $1.50 |
| Power | 2500mAh LiPo + MCP73831 + LDO | $5.00 |
| UI | WS2812B x5 + Button | $0.50 |
| PCB+組立 | 2層 JLCPCB | $10.00 |
| Enclosure | 射出成型 + TPUバンパー | $3.00 |
| **合計** | | **~$52** |
| **小売想定 (3x)** | | **~$156** |

## イベント構成例と総コスト

### 500人野外フェス
| 項目 | 数量 | 単価 | 小計 |
|------|------|------|------|
| STAGE | 4 | $650 | $2,600 |
| CROWD | 200 | $156 | $31,200 |
| WiFi 6 AP (業務用) | 4 | $300 | $1,200 |
| **合計** | | | **$35,000** |

d&b audiotechnikの同等システム: $150,000-300,000
→ **Koe Solunaは1/5-1/10のコスト**

### 50人カンファレンス
| 項目 | 数量 | 単価 | 小計 |
|------|------|------|------|
| STAGE | 2 | $650 | $1,300 |
| CROWD | 20 | $156 | $3,120 |
| **合計** | | | **$4,420** |

## 開発ロードマップ

### Phase 0: 今週 (デモ)
- ESP32-S3 x2台でUDP同期再生デモ
- 同期精度の実測 (オシロスコープ波形キャプチャ)
- デモ動画撮影

### Phase 1: 1ヶ月 (Pi CM5 STAGE プロトタイプ)
- Pi CM5 + HiFiBerry + GPS HAT組み立て
- ptp4l + GStreamer パイプライン構築
- Web管理ダッシュボード
- CROWD (ESP32-S3) ← STAGE (Pi CM5) の同期テスト

### Phase 2: 3ヶ月 (フィールドテスト)
- 小規模イベント (30-50人) でテスト
- 音速補正の実測検証
- 温度補正の精度検証
- 連続稼働8時間テスト
- 技適事前相談

### Phase 3: 6ヶ月 (量産準備)
- CROWD カスタムPCB → JLCPCB PCBA
- STAGE キャリアボード設計
- 射出成形金型
- 技適/FCC認証開始

### Phase 4: 9ヶ月 (パイロット)
- イベント会社1社にパイロット貸出 (STAGE x4 + CROWD x50)
- フィードバック → 改良

### Phase 5: 12ヶ月 (販売開始)
- 初回ロット: STAGE x50, CROWD x500
- サブスクリプション (ファームウェアOTA + ダッシュボードクラウド)
