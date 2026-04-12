# Koe Device 全製品発注ガイド（修正版）

> 目標: 全部発注 → 届いたら最終組立30分/台で完成品

## 修正済み事項
- Pro v2 I2S設計: ファームウェア+PCBは正常（I2S0 full-duplex）。ドキュメント修正済み
- 筐体STL: PCB実寸+CPLコネクタ座標に基づいて再生成済み（0.3mmトレランス）
- 全3モデルのGerber+BOM+CPL+STLが揃っている

---

## 発注する3製品

| # | 製品 | PCBサイズ | 層数 | 筐体サイズ | 数量 |
|---|------|----------|------|----------|------|
| 1 | **COIN Lite** | Ø26mm | 2層 | Ø30x18.5mm | 10枚 |
| 2 | **Pro v2** | 45x30mm | 4層 | 49x34x21mm | 5枚 |
| 3 | **Hub v2** | 140x120mm | 2層 | 147x127x29mm | 5枚 |

**合計20台**

---

## 発注手順（全て同日に発注する）

### ORDER 1: AliExpress手配部品（最初に発注 — 15-30日かかる）

検索してカートに入れる:

| # | 部品 | 検索ワード | 数量 | 目安 |
|---|------|-----------|------|------|
| 1 | LiPoバッテリー大 | `802535 lipo 800mah JST` | 25個 | $62 |
| 2 | LiPoバッテリー小 | `301020 lipo 300mah` | 12個 | $18 |
| 3 | スピーカー15x10 | `1510 speaker 8 ohm 0.5W` | 25個 | $13 |
| 4 | スピーカー28mm | `28mm speaker 8ohm 1W` | 12個 | $18 |
| 5 | シリコンワイヤー | `30AWG silicone wire red black` | 1セット | $3 |
| 6 | Kaptonテープ | `kapton tape 10mm` | 1巻 | $2 |
| **合計** | | | | **~$116** |

> バッテリー極性注意: 赤=+、黒=- を必ず確認。JST PHコネクタの極性は製造元で異なる。

---

### ORDER 2: JLCPCB PCB+SMT組立（10-12日で届く）

https://cart.jlcpcb.com/quote にアクセスし、3つのボードを順番に注文:

#### 2-A: COIN Lite x10

| 設定項目 | 値 |
|---------|-----|
| Gerber ZIP | `manufacturing/gerbers/koe-coin-lite-production/koe-coin-lite-gerbers.zip` |
| Layers | 2 |
| Thickness | 1.0mm |
| Surface Finish | ENIG |
| Qty | 10 |
| SMT Assembly | Top Side |
| BOM | `koe-coin-lite-production/koe-coin-lite-BOM-JLCPCB.csv` |
| CPL | `koe-coin-lite-production/koe-coin-lite-CPL-JLCPCB.csv` |

見積: ~$98

#### 2-B: Pro v2 x5

| 設定項目 | 値 |
|---------|-----|
| Gerber ZIP | `manufacturing/gerbers/koe-pro-v2-production/koe-pro-v2-gerbers.zip` |
| Layers | **4** |
| Thickness | 1.6mm |
| Surface Finish | ENIG |
| Qty | 5 |
| SMT Assembly | Top Side |
| BOM | `koe-pro-v2-production/koe-pro-v2-BOM-JLCPCB.csv` |
| CPL | `koe-pro-v2-production/koe-pro-v2-CPL-JLCPCB.csv` |

見積: ~$203

#### 2-C: Hub v2 x5

| 設定項目 | 値 |
|---------|-----|
| Gerber ZIP | `manufacturing/gerbers/koe-hub-v2/koe-hub-v2.zip` |
| Layers | 2 |
| Thickness | 1.6mm |
| Surface Finish | HASL lead-free |
| Qty | 5 |
| SMT Assembly | Top Side |
| BOM | `koe-hub-v2/BOM-JLCPCB.csv` |
| CPL | `koe-hub-v2/CPL-JLCPCB.csv` |

見積: ~$155

**JLCPCB合計: ~$456 + 送料DHL ~$25 = ~$481**

> 重要: 部品マッチング画面で在庫切れ部品がないか確認。C168688(USB-C)は在庫切れの場合C2765186で代替可。

---

### ORDER 3: JLCPCB 3Dプリント筐体（PCBと同時発注で送料節約）

https://jlcpcb.com/3d-printing にアクセス:

| 製品 | STLファイル | 数量 | 素材 | 目安 |
|------|-----------|------|------|------|
| COIN Lite | `hardware/cases/coin-lite-case.stl` | 10個 | SLA Black Resin | ~$30 |
| Pro v2 | `hardware/cases/pro-v2-case.stl` | 5個 | SLA Black Resin | ~$20 |
| Hub v2 | `hardware/cases/hub-v2-case.stl` | 5個 | MJF Nylon PA12 Black | ~$50 |
| **合計** | | | | **~$100** |

---

### ORDER 4: Hub v2追加部品（DigiKey/Amazon — 3-5日で届く）

| 部品 | 型番 | 数量 | 単価 | 購入先 |
|------|------|------|------|--------|
| Raspberry Pi CM5 4GB WiFi | SC1657 | 5 | $55 | PiShop/DigiKey |
| CM5 IO Board | SC1674 | 5 | $25 | PiShop/DigiKey |
| microSD 32GB | — | 5 | $8 | Amazon |
| PCM5102A DAC Module | GY-PCM5102 | 10 | $8 | Amazon |

**Hub追加部品合計: ~$520**

---

## 費用総計

| カテゴリ | 金額 |
|---------|------|
| AliExpress手配部品 | $116 |
| JLCPCB PCB+SMT | $481 |
| JLCPCB 3Dプリント | $100 |
| Hub追加部品 | $520 |
| **合計** | **~$1,217** |
| **1台あたり** | **~$61** |

---

## タイムライン

```
Day 0:  全4注文を同日に発注
Day 3:  DigiKey/Amazon Hub部品到着
Day 10: JLCPCB PCB+筐体到着 (DHL Express)
Day 20: AliExpress手配部品到着 ← ボトルネック
Day 20: 最終組立開始
Day 21: 全20台完成
```

---

## 最終組立手順（PCB+筐体+部品が全て届いた後）

### 道具
- はんだこて（300-350°C、こて先0.5-0.8mm）
- 鉛フリーはんだ（0.5-0.8mm）
- テスター（極性確認用）
- ルーペ（はんだブリッジ確認）
- ホットグルーガン、ニッパー、ピンセット

### 各ユニット組立（30-45分/台）

1. **検品**: PCBを目視検査（はんだブリッジ、部品欠品、IC方向）
2. **通電テスト**: USB-C接続 → VCC=3.3V確認 → LED動作確認
3. **スピーカー接続**: 30AWGワイヤ40mmを2本はんだ付け（SPK+/SPK-パッド）
4. **バッテリー接続**: テスターで極性確認後、BT+/BT-パッドにはんだ付け
5. **バッテリーテスト**: ボタンON → LED点灯確認
6. **絶縁**: バッテリー裏面にKaptonテープ
7. **ケース組込**:
   - 底ケースにバッテリーを配置
   - スタンドオフにPCBを載せる（部品面を上）
   - スピーカーを上部に配置
   - 上ケースをスナップフィット
8. **ファームウェア**: USB-C接続 → `espflash flash` or OTA
9. **最終テスト**: 録音、再生、LED、ボタン、充電

### Hub v2追加手順
- Pi CM5をIO Boardに装着
- microSDにOS書き込み
- CM5ボードをHub PCBに接続
- DACモジュールをI2Sヘッダに接続

---

## ファイル場所

```
koe-device/
├── manufacturing/
│   ├── gerbers/
│   │   ├── koe-coin-lite-production/  ← Gerber+BOM+CPL
│   │   ├── koe-pro-v2-production/     ← Gerber+BOM+CPL
│   │   └── koe-hub-v2/               ← Gerber+BOM+CPL
│   ├── assembly-guide.md             ← 詳細組立手順
│   ├── manual-parts.md               ← 手配部品の購入先
│   └── order-all.md                  ← このファイル
├── hardware/
│   ├── cases/
│   │   ├── generate_cases.py         ← STL生成スクリプト
│   │   ├── coin-lite-case.stl        ← COIN Lite筐体 (64KB)
│   │   ├── pro-v2-case.stl           ← Pro v2筐体 (60KB)
│   │   └── hub-v2-case.stl           ← Hub v2筐体 (47KB)
│   ├── bom/                          ← 詳細BOM（原価計算用）
│   └── gen_pro_v2.py                 ← Pro v2 PCB生成（I2S修正済み）
└── enclosure/SPEC.md                 ← 筐体設計仕様
```
