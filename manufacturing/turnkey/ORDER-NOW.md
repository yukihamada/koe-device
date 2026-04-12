# 発注手順: Koe Seed 10台（完成品で届く）

## 検証結果

| チェック項目 | 結果 |
|------------|------|
| Gerber (9ファイル: 銅層/マスク/シルク/外形/ドリル) | OK |
| BOM (25部品種 / 36部品点数, PCBWayフォーマット, Manufacturer PN付き) | OK |
| CPL (全エントリ, BOM designator全一致) | OK |
| ファームウェア (nRF5340 app core + net core .hex) | OK |
| 筐体STL (32mm x 18.5mm, 2-piece snap-fit) | OK |
| 組立図・テスト仕様・書込手順 | OK |
| サイト(koe.live)との整合性 | OK (nRF5340 + nRF21540, 28mm, Auracast receive, BOM ~$12) |
| JST-PHコネクタ (BT1, SPK1) | OK (はんだ不要化済み) |

---

## PCBWay発注フォーム入力ガイド

### Step 1: https://www.pcbway.com/QuickOrderOnline.aspx にアクセス

### Step 2: PCBスペック入力
| フィールド | 値 |
|-----------|-----|
| Board type | Single PCB |
| Layers | 2 |
| Dimensions | 28 x 28 mm |
| Quantity | 10 |
| Thickness | 1.0 mm |
| Surface Finish | ENIG |
| Solder Mask | Green |
| Silkscreen | White |

### Step 3: Assembly Service 有効化
| フィールド | 値 |
|-----------|-----|
| Assembly | Yes |
| Assembly type | **Turnkey** (PCBWay supply parts) |
| Assembly side | Top side |
| Unique parts | 25 |
| SMD parts | 36 |
| BGA/QFP parts | 3 (nRF5340 QFN-94 + nRF21540 QFN-16 + MAX98357A QFN-16) |
| Through-hole parts | 0 |

### Step 4: Advanced Services チェック
- [x] **Box build assembly**
- [x] **Firmware loading**
- [ ] Function test -> メモ欄に書く

### Step 5: Special Request 欄に以下を貼る
```
BOX BUILD ASSEMBLY - FULLY ASSEMBLED UNITS REQUIRED

SoC: Nordic nRF5340 + nRF21540 (BLE 5.3 Auracast receiver)

Per-unit scope:
1. PCB fab + full SMT assembly (36 components / 25 unique parts, incl. QFN-94 and QFN-16)
2. CRITICAL: nRF5340 (U1) is QFN-94 7x7mm, 0.4mm pitch — requires stencil
   alignment check and post-reflow X-ray or AOI inspection for solder bridges.
3. nRF21540 (U2) is QFN-16 — verify antenna path pins (no bridges)
4. Source & plug in: LiPo battery 301020 3.7V 300mAh with JST-PH 2.0mm → BT1
5. Source & plug in: Speaker 15x10mm 8ohm 0.5W with JST-PH 2.0mm → SPK1
6. 3D print enclosure: SLA Black Resin, file: enclosure.stl (2-piece snap-fit, 32mm dia)
7. Assemble: battery + PCB + speaker into enclosure
8. Flash firmware via SWD (J-Link): see flash-instructions.md
   - Network core: nrfjprog --program net_core_firmware.hex --coprocessor CP_NETWORK
   - App core: nrfjprog --program app_core_firmware.hex --coprocessor CP_APPLICATION
   NOTE: This is NOT an ESP32. Do NOT use esptool. SWD debugger (J-Link) required.
9. Test: Power on → LED lights up, BLE scan shows "Koe-Seed-XXXX", button press → LED changes
10. Package each unit in anti-static bag

Battery/speaker connectors are JST-PH 2.0mm plug-in. NO soldering needed for assembly.
SWD pogo-pin jig recommended for batch firmware flashing.
```

### Step 6: ファイルアップロード
| ファイル | 場所 |
|---------|------|
| Gerber | `coin-lite/gerbers.zip` |
| BOM | `coin-lite/BOM.csv` |
| CPL | `coin-lite/CPL.csv` |

### Step 7: メール添付 (フォームに入らないファイル)
見積もり確認メールへの返信時に添付:
- `enclosure.stl` — 筐体3Dモデル (32mm diameter)
- `app_core_firmware.hex` — nRF5340 アプリコア ファームウェア
- `net_core_firmware.hex` — nRF5340 ネットワークコア ファームウェア
- `assembly-drawing.md` — 組立図
- `test-spec.md` — テスト仕様
- `flash-instructions.md` — 書込手順 (SWD/nrfjprog)

**または** koe-seed-complete.zip をまるごと添付。

---

## 見積もり目安

| 項目 | 金額 |
|------|------|
| PCB製造 (10枚, 2層, ENIG, 28mm) | $18 |
| SMT実装 (36部品 x 10枚, QFN-94含む) | $90 |
| 部品代 (Turnkey調達) | $140 |
| --- nRF5340 @$4.50 x10 | ($45) |
| --- nRF21540 @$1.50 x10 | ($15) |
| --- MAX98357A + passives + crystals | ($40) |
| --- USB-C + JST + LED + switch | ($30) |
| バッテリー+スピーカー調達 | $35 |
| 3Dプリント筐体 x10 | $22 |
| Box Build組立 x10 | $35 |
| ファームウェア書込 (SWD, 2 cores) x10 | $25 |
| DHL送料 (Japan) | $20 |
| **合計** | **~$385** |
| **1台あたり** | **~$39** |

### コスト比較 (v1 ESP32-C3 vs Koe Seed nRF5340)
| 項目 | v1 (ESP32-C3) | v2 (nRF5340) | 差分 |
|------|--------------|-------------|------|
| MCU | $1.50 | $4.50 | +$3.00 |
| RF PA/LNA | なし | $1.50 | +$1.50 |
| Crystals | 内蔵 | $0.80 | +$0.80 |
| SMT実装 (複雑さ) | $50 | $80 | +$30 |
| FW書込 (SWD 2コア) | $15 | $25 | +$10 |
| **1台あたり合計** | **~$25** | **~$39** | **+$14** |

Auracast対応 + 長距離(nRF21540) の付加価値で +$14/台。

---

## 添付ファイル

```
manufacturing/turnkey/koe-seed-complete.zip
├── BOM.csv                  ← PCBWay BOMフォーマット (25部品種 / 33点, Manufacturer PN付き)
├── CPL.csv                  ← 部品配置 (BOMと完全一致)
├── gerbers.zip              ← Gerber + ドリル (28mm round, 2-layer)
├── enclosure.stl            ← 筐体STL (32x18.5mm, 2-piece snap-fit)
├── app_core_firmware.hex    ← nRF5340 アプリコア FW
├── net_core_firmware.hex    ← nRF5340 ネットワークコア FW (BLE 5.3 Auracast)
├── assembly-drawing.md      ← 組立手順図
├── test-spec.md             ← テスト仕様 (7項目 + optional range test)
├── flash-instructions.md    ← SWD書込手順 (nrfjprog)
└── BOM-FULL.csv             ← 参考: 全部品リスト (SMT+プラグイン+機械)
```

## タイムライン
- 見積もり: 1-3営業日
- 製造+組立: 15-20営業日 (QFN-94 は要AOI/X-ray検査のため若干長め)
- 配送 DHL: 3-5日
- **合計: 約3-4週間で完成品10台が届く**

## 注意事項
- nRF5340 QFN-94 は高精度実装が必要。PCBWayのQFN実装実績を確認すること
- ファームウェア書込にはSWDデバッガ(J-Link)が必要 — esptoolは使えない
- 2コア(app + net)それぞれ別hexファイルを書き込む必要あり
- nRF21540のアンテナマッチングネットワーク(L1=3.9nH, C16=1.5pF)とチップアンテナ(ANT1)が欠品の場合、RF性能が大幅低下する
