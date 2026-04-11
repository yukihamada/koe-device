# Koe Launch Plan — 2026年7月3日発表 / 7月18日出荷

## 決定事項 (2026-04-11)

1. **29 kill. 1 name = `Koe`** ✅
2. **価格: $1,995 / ¥300,000 / Limited 100** ✅
3. **発表日: 2026-07-03 (原宿ギャラリー)**
4. **出荷日: 2026-07-18**
5. **ギタリスト: TBD (候補: Jack White / Rick Beato / 大村孝佳 / 押尾コータロー / 山岸竜之介)**

## 1行ポジショニング
**「22ms。ギターから1000人の耳まで。」**

---

## 12週スケジュール

### W0 (今週): 凍結
- [ ] `/3d` から29モデルを隠す → `/archive`に退避、`/3d`は`Koe`のみ
- [ ] `koe.live/` ランディングを1プロダクト仕様に書き換え
- [ ] `tasks/keynote.md` 台本確定
- [ ] `tasks/prd-koe.md` 1枚仕様書
- [ ] Nordic Design House 3社へRFP送付準備 (Silvair, Nordic partners)
- [ ] CNC工場候補リスト (山形/大田/東大阪の精密工作系 + Protolabs/Xometry)
- [ ] ギタリスト候補にエージェント経由で打診

### W1-2: 発注・契約
- [ ] Nordic Design House 1社決定 + 契約 ($40-60K)
- [ ] CNC工場 2社と試作見積契約
- [ ] ID freelance 契約 (Dribbble top or Takram若手, $5-15K)
- [ ] ギタリスト1名ブッキング (出演料$10-30K + 機材サンプル)
- [ ] Keynote映像制作会社 選定 ($20-40K)
- [ ] 原宿ギャラリー仮押さえ (表参道Rocket / G/P gallery / GYRE周辺)

### W3-6: 並行開発
- [ ] **HW**: nRF5340 Audio DK 小型化 PCB v1 (30×25mm 4層)
- [ ] **FW**: BLE Audio LE + LC3 + UWB同期アルゴ
- [ ] **筐体**: CNC 6061-T6 unibody プロト3世代
- [ ] **ID**: 3案→1案決定、CMF finalize (Space Gray anodize)
- [ ] **音響**: Knowles MEMS + 内蔵DSP tuning
- [ ] **キーノート動画**: 絵コンテ → ロケハン → 撮影

### W7-9: DVT
- [ ] プロト10台手組
- [ ] 22ms latency測定（SINAD, SNR, end-to-end）
- [ ] 落下1m × 6面 × 3回 (MIL-STD-810H簡易)
- [ ] 実機ライブ配信テスト (ギタリスト本番環境)
- [ ] FW OTA動作確認
- [ ] 技適ドキュメント (nRF5340 module継承)

### W10-11: PVT → MP
- [ ] PCBA 100枚 (JLCPCB SMT)
- [ ] CNCパーツ 100セット (unibody)
- [ ] 組立 日本国内工房 (週30-50台)
- [ ] QC全数 (通電+音出し+BLE pair+latency測定)
- [ ] シリアル刻印 001-100
- [ ] パッケージング (福永紙工 厚紙貼箱 + 織りケーブル + QR取説)

### W12: 発表・出荷
- [ ] 2026-07-03 原宿発表イベント (3日間、ギタリスト実演)
- [ ] プレス30媒体招待
- [ ] 動画公開 (YouTube + koe.live)
- [ ] 予約受付開始 (先着100, Stripe)
- [ ] 2026-07-18 初回出荷

---

## 予算

| カテゴリ | 金額 |
|---------|------|
| HW/FW 設計 (Nordic Design House) | $60K |
| ID (freelance) | $10K |
| CNC プロト + 量産 100台分 | $15K |
| PCBA 100枚 | $8K |
| 音響/DSP tuning | $8K |
| ギタリスト出演料 | $20K |
| キーノート動画制作 | $30K |
| ギャラリー3日貸切 + 運営 | $15K |
| パッケージ | $5K |
| 認証 (module継承で軽量) | $8K |
| PR仕込み (雑誌+メディア) | $10K |
| 知財 (意匠 + 商標) | $8K |
| 予備費 15% | $30K |
| **合計** | **$227K** |

**売上**: 100台 × $1,995 = $199.5K
**赤字 upfront**: $27.5K (PR/ブランド価値で吸収)

---

## 殺す29モデル (アーカイブ)

/archive ページに移動、/3d はKoeのみ:
- Koe Hub v2, Seed Core 5種(Stone/Drop/Lens/Seed/Plectrum)
- Music 3種(Capo/DrumKey/Pedalboard/Amp)
- Wearable 7種 (Pendant/Neckband/Ring/Watch/Headphone/Earphone/Glasses)
- Attach 5種 (Badge/Clip/HatClip/MicClip/Sticker)
- Sport 4種 (Shoe/Outdoor/Wristband/Bottle)
- Object 3種 (Ball/Card/Figurine)
- DK Edition (現行販売中 → 静かにEOL)

---

## ギタリスト候補比較

| 候補 | メリット | デメリット | 出演料目安 |
|------|---------|-----------|----------|
| **Jack White** | 世界的知名度、Third Man Records連携可 | 日本市場訴求弱、ブッキング困難 | $100K+ |
| **Rick Beato** | YouTube 500万登録、楽器技術者の聖地 | 演奏より解説キャラ | $30-50K |
| **大村孝佳** | 日本ロック界トップ技巧、BABYMETAL歴 | 海外知名度限定 | $10-20K |
| **押尾コータロー** | アコギ日本1位、海外アコギファン有 | ロック色弱 | $10-20K |
| **山岸竜之介** | 若手技巧派、SNS伸び盛り | 知名度成長中 | $5-10K |

**私の推し**: **大村孝佳** (ロック+日本+技巧+価格バランス) or **押尾コータロー** (アコギ静寂→ライブの対比が映像的)

---

## Keynote 1分動画 構成

詳細は `tasks/keynote.md` 参照

---

## RFP送付先 (W0中)

### Nordic Design House
1. **Silvair** (Poland, Nordic主要パートナー) — BLE Audio LE実績豊富
2. **Particle** (US) — HW+FW+クラウド統合
3. **Embedded Artists** (Sweden) — Nordic公認、小型モジュール得意

### CNC
1. **山形県小松精機工作所** (精密加工, 医療機器・光学機器実績)
2. **Protolabs Japan** (2週納期, 品質安定)
3. **Fictiv** (US, 見積自動化)
4. **大田区金型加工協同組合** (国内町工場ネットワーク)

### ID freelance
1. **Dribbble Industrial Design tier**
2. **Takram Jr.** (直接オファー)
3. **Nosigner OB**

### パッケージ
1. **福永紙工** (東京, 厚紙貼箱, hacoa提携)
2. **hacoa** (木箱, 楽器ケース高級感)
