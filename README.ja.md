<div align="center">

# 声 Koe

**群衆を楽器にするデバイス。**

1台は記憶。100台はオーケストラ。

[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/yukihamada/koe-device?style=flat-square)](https://github.com/yukihamada/koe-device)
[![Status](https://img.shields.io/badge/status-prototype-orange?style=flat-square)]()

**[ウェブサイト](https://yukihamada.github.io/koe-device/ja.html)** · **[English](README.md)** · **[Soluna Edition](https://yukihamada.github.io/koe-device/soluna-edition.html)** · **[ダッシュボードデモ](https://yukihamada.github.io/koe-device/dashboard.html)** · **[ドキュメント](https://yukihamada.github.io/koe-device/docs.html)**

</div>

---

> **[English version is here / 英語版はこちら](README.md)**

## Koe とは？

Koe は、音を通じて人と人をつなぐ、小さなオープンハードウェアデバイスです。聴いて、記憶し、つながりを生み出します。

- **ソロモード (Koe):** 常時オンのAI音声コンパニオン。一日の音声を記録し、文脈を理解し、イヤホンを通じて応答します。
- **群衆モード (Soluna):** P2P 音声メッシュネットワーク。同じ WiFi 上の複数デバイスが瞬時に同期。一台に話しかければ全員に聞こえます。フェスティバルでは、群衆そのものがスピーカーシステムになります。

### スマートフォンにはできない3つの体験

| | 体験 | 何が起きるか |
|---|---|---|
| 01 | **群衆オーケストラ** | 1000人がハミング → AIがリアルタイムでハーモニーを生成 → 全デバイスが足りないパートを演奏 |
| 02 | **サウンドメモリー** | 「あのレストランの名前なんだっけ？」→ その瞬間の音声を再生 |
| 03 | **空間群衆音響** | 1000本のマイクが会場全体のリアルタイム3Dサウンドマップを生成 |

## 5つのフォームファクター

| モデル | 形状 | サイズ | 用途 |
|-------|------|------|----------|
| **Pick** | ギターピック型ペンダント | 30 x 30 x 8mm | 日常使い、ミュージシャンのDNA |
| **Ear Cuff** | チタン製イヤーカフ | 20 x 8 x 5mm | 声に最も近い場所 |
| **Coin** | 完全な円形ディスク | 26mm径 x 6mm | ポケットサイズ、フィジェット |
| **Band** | リストバンド+スピーカーグリル | 40 x 18 x 11mm | アクティブ、フェスティバル |
| **Lantern** | 360°円筒形ステージユニット | 100 x 150mm | イベント、Pi CM5搭載 |

## アーキテクチャ

```
[デバイス] ESP32-S3 + MEMSマイク + スピーカー
    |
    |  WiFi / UDP マルチキャスト (Soluna P2P)
    |  WiFi / HTTPS (Koe AI)
    |
[クラウド] api.chatweb.ai
    |
    +-- エージェント1: リスナー (STT、コンテキスト)
    +-- エージェント2: シンカー (推論)
    +-- エージェント3: リサーチャー (Web検索)
    +-- エージェント4: レスポンダー (TTS)
    +-- エージェント5: メモリー (長期学習)
```

### Soluna 同期プロトコル

```
[GPS衛星] → 1PPS → [STAGE: Pi CM5 + TCXO]
                              |
                        PTP グランドマスター
                              |
              WiFi/4G マルチキャスト (Opus エンコード + GPSタイムスタンプ)
                              |
                     [CROWD x N: ESP32-S3]
                              |
                     GPS座標 → STAGEまでの距離
                              |
                     遅延 = 距離 / 音速(気温)
                              |
                     STAGE直接音の到着に合わせて再生同期
```

## クイックスタート

### パーツを購入する

プロトタイプに必要な部品リストは **[BUY_NOW.md](BUY_NOW.md)** を参照してください。Amazon.co.jp で約¥5,200〜6,800で揃います。

### 同期デモ (ESP32-S3ボード2台)

```bash
# ツールチェーンのインストール
cargo install espup && espup install
cargo install espflash ldproxy

# 送信側をフラッシュ (起動時にGPIO15ボタンを押しながら)
cd firmware/demo
WIFI_SSID="あなたのWiFi" WIFI_PASS="パスワード" cargo espflash flash --monitor

# 受信側をフラッシュ (ボタンを押さずに)
# 送信側に話しかける → 受信側から聞こえる
```

詳細は [firmware/demo/README.md](firmware/demo/README.md) を参照してください。

### フルファームウェア

```bash
cd firmware
cargo build --release
```

## プロジェクト構成

```
koe-device/
├── docs/                    # ウェブサイト (GitHub Pages)
│   ├── index.html           # 英語版
│   ├── ja.html              # 日本語版
│   ├── soluna-edition.html  # フェスティバル向け音響
│   ├── dashboard.html       # 管理ダッシュボードデモ
│   └── images/              # 製品レンダリング (Gemini AI)
├── firmware/
│   ├── src/                 # メインファームウェア (Koe + Soluna)
│   │   ├── main.rs          # エントリポイント、デュアルモード
│   │   ├── audio.rs         # I2S、VAD、DSP
│   │   ├── cloud.rs         # chatweb.ai へのHTTPS接続
│   │   ├── soluna.rs        # UDPマルチキャストP2Pプロトコル
│   │   └── led.rs           # WS2812Bステータス LED
│   └── demo/                # 最小同期デモ (2ボード)
├── hardware/
│   ├── kicad/               # 回路図 + ネットリスト
│   ├── bom/                 # 部品表: Mini ($12)、STAGE ($260)、CROWD ($52)
│   └── docs/                # 設計仕様、音響分析、ビジョン
├── enclosure/               # 3Dプリント用ケース仕様
├── LICENSE                  # MIT
└── CONTRIBUTING.md          # コントリビューションガイド
```

## ハードウェア部品表

| モデル | BOMコスト | 主要部品 |
|-------|----------|----------------|
| **Pick/Ear Cuff/Coin** | ~$12 | ESP32-S3、INMP441、MAX98357A、LiPo |
| **Band** | ~$52 | + GPS (MAX-M10S)、LTE-M (SIM7080G)、40mmドライバー |
| **Lantern STAGE** | ~$260 | Pi CM5、HiFiBerry DAC、TPA3255、130mm同軸、GPS (NEO-M9N)、4G |

完全な部品表: [hardware/bom/](hardware/bom/)

## ステータス

| 領域 | 進捗 | 備考 |
|------|----------|-------|
| ハードウェア設計 | 70% | 回路図完成、部品発注中 |
| ファームウェア | 40% | コンパイル済み、実機テストが必要 |
| Koe ソフトウェア | 100% | [koe.elio.love](https://koe.elio.love) (macOS/Windows) |
| プロトタイプ | 20% | 部品到着待ち |
| Soluna Edition | 30% | Pi CM5アーキテクチャ設計済み |

## ロードマップ

- [ ] **今週:** Amazon.co.jp で ESP32-S3 + INMP441 + MAX98357A を発注
- [ ] **来週:** 同期デモをフラッシュ、オシロスコープで同期精度を測定
- [ ] **2週間後:** デモ動画 → サイトに掲載
- [ ] **1ヶ月後:** Pi CM5 STAGEプロトタイプ + 実データ付きWebダッシュボード
- [ ] **3ヶ月後:** 30人イベントでフィールドテスト、技適事前相談
- [ ] **6ヶ月後:** カスタムPCB (JLCPCB)、射出成形金型
- [ ] **9ヶ月後:** パイロット: イベント会社1社に STAGE 4台 + CROWD 50台
- [ ] **12ヶ月後:** 初回バッチ販売開始

## リンク

- **ウェブサイト:** https://yukihamada.github.io/koe-device/ja.html
- **Koe ソフトウェア:** https://koe.elio.love
- **Soluna:** https://solun.art/soluna
- **EnablerDAO:** https://github.com/enablerdao
- **ドキュメント:** https://yukihamada.github.io/koe-device/docs.html

## ライセンス

MIT — [LICENSE](LICENSE) を参照

## コントリビューション

[CONTRIBUTING.md](CONTRIBUTING.md) を参照
