# 今すぐ買うもの — Koe Soluna Festival System

## 全体像

```
4プロダクト:
  SUB   → 体で感じる低音 (15", 1000W, 130dB)
  FILL  → メインPA (8"+1"ホーン, 118dB, WiFi 7)
  COIN  → 近接+LED+マイク (20mm, 82dB)
  STAGE → 制御ブレイン (Pi 5)
```

---

## Phase 1: COIN 同期デモ — ¥6,200 (今日注文→明日届く)

まず2台で同期再生が動くことを証明する。

### Amazon.co.jp

| # | 品名 | URL | 価格 |
|---|------|-----|------|
| 1 | ESP32-S3-DevKitC-1 x3個入 | [AITRIP](https://www.amazon.co.jp/AITRI3PCS-ESP32-S3-DevKitC-1-N8R2-ESP32-S3-MCU%E3%83%A2%E3%82%B8%E3%83%A5%E3%83%BC%E3%83%AB-%E5%AE%8C%E5%85%A8%E3%81%AAWi-Fi%E3%81%A8BLE%E6%A9%9F%E8%83%BD%E3%82%92%E7%B5%B1%E5%90%88%E3%80%82/dp/B0BX31WGQG) | ¥3,000 |
| 2 | INMP441 マイク x2個入 | [ACEIRMC](https://www.amazon.co.jp/-/en/ACEIRMC-Omnidirectional-Microphone-Interface-Compatible/dp/B09222JFBX) | ¥1,000 |
| 3 | MAX98357A アンプ x2個入 | [DAOKAI](https://www.amazon.co.jp/DAOKAI-MAX98357-%E3%83%96%E3%83%AC%E3%83%BC%E3%82%AF%E3%82%A2%E3%82%A6%E3%83%88-%E3%82%A4%E3%83%B3%E3%82%BF%E3%83%BC%E3%83%95%E3%82%A7%E3%82%A4%E3%82%B9-Arduino/dp/B0B2NSMV55) | ¥1,200 |
| 4 | 小型スピーカー 8Ω 20mm x2 | Amazon検索 | ¥500 |
| 5 | ブレッドボード + ジャンパワイヤ | (手持ちあれば不要) | ¥500 |

**→ 同期デモ2台 + 予備1台。デモ動画撮影。**

### やること

```bash
cd firmware/demo
WIFI_SSID="WiFi名" WIFI_PASS="パスワード" cargo espflash flash --monitor
```

---

## Phase 2: COIN 量産基板 — ¥14,000 (Phase 1成功後)

### JLCPCB

| 項目 | 数量 | コスト |
|------|------|--------|
| 26mm丸基板 + SMT実装 | 10枚 | ~$60 |
| LiPo 200mAh + スピーカー 20mm | 10セット | ~$30 |
| 3Dプリントケース | 10個 | ~$25 |
| **合計** | | **~$115 (¥17,000)** |

BOM $22/台 × 10 = $220。基板+ケースで$115。
→ `manufacturing/` 参照

---

## Phase 3: FILL プロトタイプ — ¥75,000 (Phase 2と並行)

メインPAの心臓。プロ音質の検証。

### 購入部品

| # | 品名 | 購入先 | 価格 |
|---|------|--------|------|
| 1 | **Raspberry Pi 5 (4GB)** | Amazon/Pi Shop | ¥10,000 |
| 2 | **Intel BE200 WiFi 7 M.2** | Amazon | ¥3,000 |
| 3 | **PCIe M.2 HAT (Pi 5用)** | Amazon | ¥1,500 |
| 4 | **ES9038Q2M DAC ボード** | AliExpress | ¥2,500 |
| 5 | **ICEpower 125ASX2 アンプ** | eBay/AliExpress | ¥12,000 |
| 6 | **SB Acoustics 8" ウーファー** | Parts Express/AliExpress | ¥5,000 |
| 7 | **Celestion CDX1-1730 1" 圧縮ドライバー** | Parts Express | ¥6,000 |
| 8 | **90x50 定指向性ホーン** | AliExpress / 3Dプリント | ¥2,000 |
| 9 | **u-blox NEO-M9N GPS + アンテナ** | Mouser/DigiKey | ¥4,500 |
| 10 | **Quectel EC25-J 4G モジュール** | AliExpress | ¥3,000 |
| 11 | **AC電源 (24V 5A + 5V 3A)** | Amazon | ¥2,000 |
| 12 | **エンクロージャ材 (合板15mm + 吸音材)** | ホームセンター | ¥3,000 |
| 13 | **XLR + Speakon コネクタ** | Amazon | ¥1,500 |
| 14 | **microSD 32GB** | Amazon | ¥700 |
| 15 | **内部配線 + ファン + 金具** | Amazon | ¥1,500 |
| | **合計** | | **~¥58,200** |

### セットアップ

```bash
# Pi 5セットアップ
cd stage/
./setup.sh
sudo reboot

# Solunaサーバー起動
python3 soluna-server.py

# COIN群がFILLに同期して鳴る
```

---

## Phase 4: SUB プロトタイプ — ¥60,000 (Phase 3成功後)

フェスの低音。体で感じるサブベース。

### 購入部品

| # | 品名 | 購入先 | 価格 |
|---|------|--------|------|
| 1 | **Dayton Audio RSS390HF-4 15" ウーファー** | Parts Express | ¥18,000 |
| 2 | **ICEpower 1000ASP アンプモジュール** | eBay/ICEpower直販 | ¥28,000 |
| 3 | **miniDSP 2x4 (またはADAU1701ボード)** | miniDSP / AliExpress | ¥4,000 |
| 4 | **u-blox NEO-M9N GPS + アンテナ** | Mouser | ¥4,500 |
| 5 | **ESP32-S3-MINI-1** | LCSC | ¥500 |
| 6 | **エンクロージャ材 (18mm合板バーチ)** | ホームセンター | ¥5,000 |
| 7 | **バスレフポート管 (100mm径 x200mm)** | Amazon/ホームセンター | ¥500 |
| 8 | **Speakon NL4 x2 + XLR + IEC C14** | Amazon | ¥2,000 |
| 9 | **取っ手 x2 + ゴム脚 x4 + M20ポールマウント** | Amazon | ¥1,500 |
| 10 | **吸音材 + 内部配線** | Amazon | ¥1,500 |
| | **合計** | | **~¥65,500** |

### エンクロージャ製作

```
バスレフ 80L (内寸約430x430x430mm)
材料: 18mmバーチ合板
ポート: 100mm径 x 200mm (チューニング ~35Hz)
内部: 吸音材充填 (背面+側面)
仕上げ: 黒ペイント + 鬼目ナット
```

---

## Phase 5: ギター配信テスト — ¥0

手持ちのBabyface Proを使用。

```bash
# Phase 3のPi 5に接続
python3 tools/guitar-stream.py
# → 全COIN + FILLから音が出る (22ms)
```

---

## Phase 6: フィールドテスト — ¥10,000

30-50人の小規模イベントで実地テスト。

### 構成

| 機材 | 台数 | 用途 |
|------|------|------|
| SUB | 1 | 低音 |
| FILL | 2 | メインPA (ステレオ) |
| COIN | 10 | 観客の近接+LED |
| STAGE | 1 | 制御 (FILL内蔵) |

### 計測

- オシロスコープでSUB/FILL/COIN間の同期精度
- RTA (リアルタイムアナライザ) で周波数特性
- dBメーターで音圧分布マップ
- バッテリー持続時間 (COIN)
- WiFi接続安定性 (10台同時)

---

## 全Phase合計

| Phase | 内容 | コスト | 成果 |
|-------|------|--------|------|
| 1 | ブレッドボード同期デモ | **¥6,200** | デモ動画 |
| 2 | COIN 10台 | **¥17,000** | LED同期ショー |
| 3 | FILL 1台 (プロPA) | **¥58,200** | 本気の音 |
| 4 | SUB 1台 (サブウーファー) | **¥65,500** | 体で感じる低音 |
| 5 | ギター配信 | **¥0** | Babyface Pro活用 |
| 6 | フィールドテスト | **¥10,000** | 実測データ |
| **合計** | | **¥156,900** | フェス対応フルシステム |

**¥157,000 (約$1,050) で、L-Acoustics $488,000 と同じ構成のプロトタイプが手に入る。**

---

## 買い物チェックリスト

### Phase 1 (今日) — ¥6,200
- [ ] ESP32-S3-DevKitC x3個入
- [ ] INMP441 x2個入
- [ ] MAX98357A x2個入
- [ ] 小型スピーカー 20mm x2
- [ ] ブレッドボード (なければ)

### Phase 2 (1週後) — ¥17,000
- [ ] JLCPCB: 26mm丸基板 + PCBA 10枚
- [ ] AliExpress: LiPo 200mAh x10
- [ ] AliExpress: 20mmスピーカー x10
- [ ] JLCPCB: 3Dプリントケース x10

### Phase 3 (2週後) — ¥58,200
- [ ] Raspberry Pi 5 (4GB)
- [ ] Intel BE200 + M.2 HAT
- [ ] ES9038Q2M DAC ボード
- [ ] ICEpower 125ASX2
- [ ] SB Acoustics 8" ウーファー
- [ ] Celestion CDX1-1730 1" 圧縮ドライバー
- [ ] 90x50 ホーン
- [ ] u-blox NEO-M9N GPS + アンテナ
- [ ] Quectel EC25-J 4G
- [ ] AC電源 (24V+5V)
- [ ] エンクロージャ材 (合板+吸音材)
- [ ] コネクタ (XLR+Speakon)

### Phase 4 (1ヶ月後) — ¥65,500
- [ ] Dayton Audio RSS390HF-4 15" ウーファー
- [ ] ICEpower 1000ASP アンプ
- [ ] miniDSP 2x4
- [ ] u-blox NEO-M9N GPS + アンテナ
- [ ] ESP32-S3-MINI-1
- [ ] エンクロージャ材 (18mmバーチ合板)
- [ ] バスレフポート管 100mm
- [ ] コネクタ (Speakon+XLR+IEC)
- [ ] 取っ手+ゴム脚+ポールマウント
- [ ] 吸音材+内部配線
