# 今すぐ買うもの

## Phase 1: ブレッドボードで動作確認 (今日注文 → 明日届く)

### Amazon.co.jp

| # | 品名 | 数量 | URL | 価格 |
|---|------|------|-----|------|
| 1 | ESP32-S3-DevKitC-1 x3個入 | 1セット | [AITRIP 3個入](https://www.amazon.co.jp/AITRI3PCS-ESP32-S3-DevKitC-1-N8R2-ESP32-S3-MCU%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB-%E5%AE%8C%E5%85%A8%E3%81%AAWi-Fi%E3%81%A8BLE%E6%A9%9F%E8%83%BD%E3%82%92%E7%B5%B1%E5%90%88%E3%80%82/dp/B0BX31WGQG) | ~¥3,000 |
| 2 | INMP441 I2Sマイクモジュール x2個入 | 1セット | [ACEIRMC 2個入](https://www.amazon.co.jp/-/en/ACEIRMC-Omnidirectional-Microphone-Interface-Compatible/dp/B09222JFBX) | ~¥1,000 |
| 3 | MAX98357A I2Sアンプモジュール x2個入 | 1セット | [DAOKAI 2個入](https://www.amazon.co.jp/DAOKAI-MAX98357-%E3%83%96%E3%83%AC%E3%83%BC%E3%82%AF%E3%82%A2%E3%82%A6%E3%83%88-%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%82%A4%E3%82%B9-Arduino/dp/B0B2NSMV55) | ~¥1,200 |
| 4 | 小型スピーカー 8Ω 20-23mm x2 | 2個 | Amazon「小型スピーカー 8Ω 20mm」検索 | ~¥500 |
| 5 | ブレッドボード + ジャンパワイヤ | 1セット | (手持ちあれば不要) | ~¥500 |

**合計: ~¥6,200** (ESP32 x3、マイク x2、アンプ x2、スピーカー x2)

→ これで同期デモ(2台)が作れる。1台予備。

### 配線 (2台分)

```
ボードA (送信):                     ボードB (受信):
ESP32-S3     INMP441                ESP32-S3     MAX98357A    Speaker
 3V3 ─────── VDD                     3V3 ─────── VIN
 GND ─────── GND                     GND ─────── GND
 GPIO4 ───── SCK                     GPIO14 ──── BCLK
 GPIO5 ───── WS                      GPIO21 ──── LRC
 GPIO6 ───── SD                      GPIO7 ────── DIN
             L/R → GND               GPIO8 ────── SD
                                                 OUT+ ───── Speaker+
                                                 OUT- ───── Speaker-
```

### フラッシュ

```bash
cargo install espup && espup install
cargo install espflash ldproxy

cd firmware/demo
WIFI_SSID="あなたのWiFi" WIFI_PASS="パスワード" cargo espflash flash --monitor
```

---

## Phase 2: Coin プロトタイプ (Phase 1 が動いたら)

### JLCPCB 発注

| 項目 | 数量 | コスト |
|------|------|--------|
| カスタム丸基板 26mm + SMT実装 | 5枚 | ~$50 |
| 手動部品 (バッテリー200mAh + スピーカー20mm) | 5セット | ~$15 |
| 3Dプリントケース | 5個 | ~$25 |
| **合計** | | **~$90 (~¥14,000)** |

→ `manufacturing/` フォルダの手順で発注

### Coin BOM ($22/台)

| 部品 | コスト |
|------|--------|
| ESP32-S3-MINI-1 | $3.50 |
| INMP441 マイク | $1.20 |
| MAX98357A アンプ | $1.80 |
| スピーカー 20mm | $1.00 |
| WS2812B LED | $0.08 |
| MCP73831 充電IC | $0.45 |
| AP2112K LDO | $0.15 |
| LiPo 200mAh | $2.00 |
| USB-C | $0.25 |
| ボタン + BME280 | $1.02 |
| パッシブ部品 | $1.00 |
| PCB + 組立 | $8.00 |
| ケース | $2.00 |
| **合計** | **~$22** |

GPS不要 — STAGEのNTPで時刻同期。

---

## Phase 3: Lantern STAGE (Coinが動いたら)

### Amazon.co.jp / Pi Shop

| # | 品名 | 価格 |
|---|------|------|
| 1 | Raspberry Pi 5 (4GB) | ~¥10,000 |
| 2 | Intel BE200 WiFi 7 M.2カード | ~¥3,000 |
| 3 | Pi 5 PCIe M.2 HAT | ~¥1,500 |
| 4 | HiFiBerry DAC+ Pro | ~¥5,000 |
| 5 | u-blox NEO-M9N GPS モジュール | ~¥3,000 |
| 6 | TPA3255 アンプモジュール | ~¥2,000 |
| 7 | 130mm 同軸ドライバー | ~¥3,500 |
| 8 | 電源 24V + ケース | ~¥3,000 |
| **合計** | | **~¥31,000** |

### セットアップ

```bash
# Pi 5 に Raspberry Pi OS Lite をインストール後:
cd stage/
chmod +x setup.sh
./setup.sh
sudo reboot
python3 soluna-server.py
```

---

## Phase 4: ギター配信テスト (手持ちの機材で)

Babyface Pro (手持ち) + Raspberry Pi (Phase 3で購入済み)

```bash
pip3 install sounddevice numpy
python3 tools/guitar-stream.py
# → Coin デバイスから音が出る (22ms遅延)
```

---

## 全Phase合計

| Phase | 何が手に入る | コスト |
|-------|------------|--------|
| 1 | ブレッドボード同期デモ 2台 + デモ動画 | ¥6,200 |
| 2 | Coin プロトタイプ 5台 | ¥14,000 |
| 3 | Lantern STAGE 1台 (GPS原子時計+WiFi 7) | ¥31,000 |
| 4 | ギター配信 (手持ちBabyface Pro) | ¥0 |
| **合計** | **Coin x5 + STAGE x1 + ギター配信** | **~¥51,200** |

---

## 買い物チェックリスト

### Phase 1 (今日)
- [ ] ESP32-S3-DevKitC x3個入
- [ ] INMP441 x2個入
- [ ] MAX98357A x2個入
- [ ] 小型スピーカー x2
- [ ] ブレッドボード (なければ)

### Phase 2 (1週間後)
- [ ] JLCPCB 丸基板発注 (manufacturing/ 参照)
- [ ] AliExpress: LiPo 200mAh x5
- [ ] AliExpress: 20mmスピーカー x5

### Phase 3 (2週間後)
- [ ] Raspberry Pi 5
- [ ] Intel BE200 + M.2 HAT
- [ ] HiFiBerry DAC+ Pro
- [ ] GPS モジュール
- [ ] アンプ + スピーカー + ケース

### Phase 4 (Phase 3と同時)
- [ ] Babyface Pro CC モード確認
- [ ] guitar-stream.py テスト
