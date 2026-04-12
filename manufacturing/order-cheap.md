# Koe Device 最安発注プラン

> はんだ付けゼロ。届いたらカチッと組むだけ。

## 設計変更: はんだ付け不要化

全ボードのバッテリー・スピーカーを **JST-PHコネクタ** に統一。
JLCPCBがコネクタまで機械実装 → 届いたら差し込むだけ。

| 変更点 | Before | After |
|--------|--------|-------|
| COIN Lite バッテリー | ワイヤー直付け（はんだ要） | JST-PH 2Pコネクタ（差し込み） |
| COIN Lite スピーカー | ワイヤー直付け（はんだ要） | JST-PH 2Pコネクタ（差し込み） |
| Pro v2 | 既にJSTコネクタ | 変更なし |

---

## プランA: 最安（COIN Lite + Pro v2のみ、15台） — **$380**

Hub v2は後回し（Pi CM5代$275がデカい）。

### 1. JLCPCB PCB+SMT実装

| ボード | 数量 | PCB | 部品 | 組立 | 小計 |
|--------|------|-----|------|------|------|
| COIN Lite | 10 | $8 | $60 | $30 | **$98** |
| Pro v2 | 5 | $28 | $125 | $50 | **$203** |
| DHL送料 | | | | | **$20** |
| **JLCPCB計** | | | | | **$321** |

### 2. AliExpress 部品（JST付きを買う = はんだ不要）

| 部品 | スペック | 数量 | 単価 | 合計 | 検索 |
|------|---------|------|------|------|------|
| バッテリー | 802535 3.7V 800mAh **JST-PH付き** | 7 | $3 | $21 | `802535 lipo JST PH 2.0` |
| バッテリー小 | 301020 3.7V 300mAh **JST-PH付き** | 12 | $2 | $24 | `301020 lipo JST PH` |
| スピーカー | 1510 8ohm **JST-PHケーブル付き** | 15 | $1 | $15 | `1510 speaker JST PH` |
| **AliExpress計** | | | | **$60** |

> JST-PH 2.0mmコネクタ付きバッテリーを指定して買う。
> スピーカーにJSTが無い場合、JST-PHケーブル($3/10本)を別途買ってスピーカーにクリンプ。

### 3. JLCPCB 3Dプリント筐体

| 製品 | 素材 | 数量 | 単価 | 合計 |
|------|------|------|------|------|
| COIN Lite | SLA 8001 Resin Black | 10 | $1.50 | $15 |
| Pro v2 | SLA 8001 Resin Black | 5 | $3 | $15 |
| 送料（PCBと同梱） | | | | $0 |
| **3Dプリント計** | | | | **$30** |

> JLCPCB 3DプリントはPCB注文と同時発注で送料まとめられる

### プランA合計

| カテゴリ | 金額 |
|---------|------|
| JLCPCB PCB+SMT | $321 |
| AliExpress部品 | $60 |
| JLCPCB 3Dプリント | $30 |
| **合計** | **~$411** |
| **1台あたり** | **~$27** |

**PCBWayターンキー($900)の半額以下。**

---

## プランB: さらに安く（COIN Liteのみ10台） — **$160**

Pro v2も後回しにして、まずCOIN Liteだけで検証。

| カテゴリ | 金額 |
|---------|------|
| JLCPCB COIN Lite x10 (PCB+SMT) | $98 |
| AliExpress（バッテリー12個+スピーカー15個） | $39 |
| JLCPCB 3Dプリント x10 | $15 |
| DHL送料 | $15 |
| **合計** | **~$167** |
| **1台あたり** | **~$17** |

---

## 届いた後やること（はんだ不要、道具不要）

**1台あたり5分:**
1. バッテリーのJSTプラグをPCBのBT1コネクタに差す（カチッ）
2. スピーカーのJSTプラグをPCBのSPK1コネクタに差す（カチッ）
3. PCBを底ケースのスタンドオフに載せる
4. バッテリーを底の空間に入れる
5. スピーカーを上に置く
6. 上ケースをパチッとスナップ
7. USB-Cでファームウェア書込（PCに繋いでコマンド1つ）

```
所要時間: 5分/台 × 15台 = 1時間15分
道具: なし（素手で組める）
はんだ: 不要
```

---

## 発注手順（メール不要、全部Webで完結）

### Step 1: JLCPCB（10分）
1. https://cart.jlcpcb.com/quote
2. COIN Lite:
   - `manufacturing/gerbers/koe-coin-lite-production/koe-coin-lite-gerbers.zip` アップロード
   - 2層、1.0mm、ENIG、10枚
   - SMT Assembly ON → BOM + CPL アップロード
3. Pro v2:
   - `manufacturing/gerbers/koe-pro-v2-production/koe-pro-v2-gerbers.zip` アップロード
   - **4層**、1.6mm、ENIG、5枚
   - SMT Assembly ON → BOM + CPL アップロード
4. 3Dプリント追加:
   - https://jlcpcb.com/3d-printing
   - `hardware/cases/coin-lite-case.stl` x10, SLA 8001 Resin Black
   - `hardware/cases/pro-v2-case.stl` x5, SLA 8001 Resin Black
5. 同じカートでまとめて決済 → DHL Express

### Step 2: AliExpress（5分）
以下を検索してカートに入れる:

**COIN Lite用:**
- `301020 3.7V 300mAh lipo battery JST PH 2.0mm` × 12個
- `1510 speaker 8ohm 0.5W` × 15個 + `JST PH 2.0mm 2pin cable` × 15本

**Pro v2用:**
- `802535 3.7V 800mAh lipo battery JST PH 2.0mm` × 7個
- `20mm speaker 8ohm 1W JST` × 7個

決済。

### Step 3: 待つ
- JLCPCB: 10-12日で届く
- AliExpress: 15-20日で届く

### Step 4: 組む（道具なし、はんだなし）
全部届いたらプラグ差してケースにパチッ。以上。

---

## 比較表

| プラン | 台数 | 費用 | 1台 | はんだ | 組立時間 |
|--------|------|------|-----|--------|---------|
| **B: COIN Liteのみ** | 10 | **$167** | $17 | 不要 | 5分/台 |
| **A: COIN+Pro** | 15 | **$411** | $27 | 不要 | 5分/台 |
| PCBWayターンキー | 20 | $900 | $45 | 不要 | 0分 |
| 旧プラン（手はんだ） | 20 | $1,217 | $61 | 必要 | 30分/台 |
