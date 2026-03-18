# Koe Device — 今すぐ注文する部品リスト

## Amazon.co.jp (翌日配送)

### 必須 (プロトタイプ最小構成)

| # | 部品 | リンク | 数量 | 予算 |
|---|------|--------|------|------|
| 1 | **ESP32-S3-DevKitC-1 N8R2** | [Espressif公式 N8R2](https://www.amazon.co.jp/Espressif-ESP32-S3-DevKitC-1-N8R2-%E9%96%8B%E7%99%BA%E3%83%9C%E3%83%BC%E3%83%89/dp/B09D3S7T3M) | 1 | ~¥2,500 |
| 2 | **INMP441 I2Sマイクモジュール** | [ACEIRMC 2個入り](https://www.amazon.co.jp/-/en/ACEIRMC-Omnidirectional-Microphone-Interface-Compatible/dp/B09222JFBX) | 1セット(2個) | ~¥1,000 |
| 3 | **MAX98357A I2Sアンプモジュール** | [DAOKAI 2個入り](https://www.amazon.co.jp/DAOKAI-MAX98357-%E3%83%96%E3%83%AC%E3%83%BC%E3%82%AF%E3%82%A2%E3%82%A6%E3%83%88-%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%82%A4%E3%82%B9-Arduino/dp/B0B2NSMV55) | 1セット(2個) | ~¥1,200 |
| 4 | **小型スピーカー 8ohm** | Amazonで「8ohm 0.5W スピーカー 小型」検索 | 1 | ~¥300 |
| 5 | **ブレッドボード + ジャンパワイヤ** | 手持ちがなければ | 1セット | ~¥500 |

**合計: 約¥5,500** (翌日届く)

### あると便利 (Phase 2)

| 部品 | 用途 | 予算 |
|------|------|------|
| USB-Cブレイクアウト | 充電回路テスト | ~¥300 |
| LiPoバッテリー 3.7V 500-800mAh | バッテリー駆動テスト | ~¥800 |
| MCP73831 充電モジュール (TP4056でも可) | 充電回路 | ~¥300 |

## 注文後すぐやること

### Day 1: 部品到着 → 配線 → 音が出る

```
ESP32-S3-DevKitC    INMP441          MAX98357A        Speaker
 ┌──────────┐      ┌───────┐        ┌─────────┐     ┌─────┐
 │      3V3 ├──────┤ VDD   │   ┌────┤ VIN     │     │     │
 │      GND ├──┬───┤ GND   │   │ ┌──┤ GND     │     │     │
 │          │  │   │       │   │ │  │         │     │     │
 │    GPIO4 ├──┼───┤ SCK   │   │ │  │         │     │     │
 │    GPIO5 ├──┼───┤ WS    │   │ │  │         │     │     │
 │    GPIO6 ├──┼───┤ SD    │   │ │  │         │     │     │
 │          │  │   │ L/R→GND│   │ │  │         │     │     │
 │          │  │   └───────┘   │ │  │         │     │     │
 │          │  │               │ │  │         │     │     │
 │      3V3 ├──┼───────────────┘ │  │  BCLK ←├─GPIO14  │
 │      GND ├──┼─────────────────┘  │  LRC  ←├─GPIO21  │
 │   GPIO14 ├──┼────────────────────┤  DIN  ←├─GPIO7   │
 │   GPIO21 ├──┼────────────────────┤         │     │     │
 │    GPIO7 ├──┼────────────────────┤  OUT+ ──├─────┤ +   │
 │          │  │                    │  OUT- ──├─────┤ -   │
 │          │  │                    └─────────┘     └─────┘
 └──────────┘  │
               GND
```

### Day 1 のゴール: この3行で音が録れることを確認

```bash
cd /Users/yuki/workspace/koe-device/firmware
# ESP-IDF + Rust 環境がなければ:
cargo install espup && espup install
cargo install cargo-espflash

# ビルド & フラッシュ
cargo build --release
cargo espflash flash --release --monitor
# → シリアルモニタで "Voice detected!" が出ればOK
```
