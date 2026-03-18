# 今すぐ買うもの — プロトタイプ部品リスト

## Step 1: Amazon.co.jp で今日注文 (翌日届く)

### 必須 (同期デモに最低限必要)

| # | 品名 | 数量 | URL | 価格 |
|---|------|------|-----|------|
| 1 | ESP32-S3-DevKitC-1 (N8R2 or N16R8) | **2台** | [Espressif N8R2 ¥4,600](https://www.amazon.co.jp/Espressif-ESP32-S3-DevKitC-1-N8R2-%E9%96%8B%E7%99%BA%E3%83%9C%E3%83%BC%E3%83%89/dp/B09D3S7T3M) or [AITRIP 3個入 ¥3,000](https://www.amazon.co.jp/AITRI3PCS-ESP32-S3-DevKitC-1-N8R2-ESP32-S3-MCU%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB-%E5%AE%8C%E5%85%A8%E3%81%AAWi-Fi%E3%81%A8BLE%E6%A9%9F%E8%83%BD%E3%82%92%E7%B5%B1%E5%90%88%E3%80%82/dp/B0BX31WGQG) | ¥3,000-4,600 |
| 2 | INMP441 I2Sマイクモジュール | **2個** | [ACEIRMC 2個入](https://www.amazon.co.jp/-/en/ACEIRMC-Omnidirectional-Microphone-Interface-Compatible/dp/B09222JFBX) | ~¥1,000 |
| 3 | MAX98357A I2Sアンプモジュール | **2個** | [DAOKAI 2個入](https://www.amazon.co.jp/DAOKAI-MAX98357-%E3%83%96%E3%83%AC%E3%83%BC%E3%82%AF%E3%82%A2%E3%82%A6%E3%83%88-%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%82%A4%E3%82%B9-Arduino/dp/B0B2NSMV55) | ~¥1,200 |
| 4 | 小型スピーカー 8Ω 0.5-1W | **2個** | Amazon「小型スピーカー 8Ω」で検索 | ~¥500 |
| 5 | ブレッドボード + ジャンパワイヤ | **1セット** | 手持ちがあれば不要 | ~¥500 |
| 6 | USB-Cケーブル | **2本** | 手持ちがあれば不要 | ~¥0 |

### 合計: **約¥5,200-6,800**

> **推奨:** AITRIP 3個入(¥3,000)を買えばESP32が3台手に入る。1台予備。

## Step 2: 届いたらやること

### Day 1: 配線 (30分)

```
ボードA (送信側):                    ボードB (受信側):
ESP32-S3     INMP441                ESP32-S3     MAX98357A    Speaker
 3V3 ────── VDD                      3V3 ────── VIN
 GND ────── GND                      GND ────── GND
 GPIO4 ──── SCK                      GPIO14 ──── BCLK
 GPIO5 ──── WS                       GPIO21 ──── LRC
 GPIO6 ──── SD                       GPIO7 ───── DIN
            L/R → GND                GPIO8 ───── SD (enable)
                                                OUT+ ──── Speaker+
                                                OUT- ──── Speaker-
```

### Day 1: フラッシュ (10分)

```bash
# ESP Rust ツールチェーンインストール (初回のみ)
cargo install espup && espup install
cargo install espflash ldproxy

# ボードA (送信): GPIO15ボタンを押しながら起動
cd /Users/yuki/workspace/koe-device/firmware/demo
WIFI_SSID="あなたのWiFi" WIFI_PASS="パスワード" cargo espflash flash --monitor

# ボードB (受信): ボタン押さずに起動
WIFI_SSID="あなたのWiFi" WIFI_PASS="パスワード" cargo espflash flash --monitor
```

### Day 1: テスト (5分)

1. ボードBの電源を入れる → LED: オレンジ (待機)
2. ボードAの電源を入れる (GPIO15押しながら) → LED: 緑 (録音)
3. ボードAのマイクに向かって話す
4. ボードBのスピーカーから声が聞こえる → **成功!**

### Day 1: デモ動画撮影 (15分)

1. スマホで縦動画を撮る
2. 2台のボードとスピーカーを映す
3. 片方に話しかける → もう片方から聞こえる
4. 「これが同期再生のデモです」と説明
5. サイトに貼る / SNSに投稿

## Step 3: カスタムPCB発注 (翌週)

プロトタイプが動いたら:
→ `manufacturing/` フォルダの手順に従ってJLCPCBに発注
→ 5枚+組立で約$100 (¥15,000)
→ 2週間で届く

## 買い物チェックリスト

- [ ] ESP32-S3-DevKitC x2 (or 3個入)
- [ ] INMP441モジュール x2
- [ ] MAX98357Aモジュール x2
- [ ] 小型スピーカー x2
- [ ] ブレッドボード (なければ)
- [ ] ジャンパワイヤ (なければ)
