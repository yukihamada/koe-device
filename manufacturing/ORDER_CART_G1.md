# 発注カート — G1 実機プロト（ポチるだけ）

> 目的: 設計v4 G1（XIAOで E2E green ＋ 10h/ソーラー実測）に必要な実機部品。
> **購入は人手**（Amazonアカウント）。価格は概算（2026-06-08時点・税送料別・最新は各リンクで要確認）。
> 全ASINは amazon.co.jp で実在確認済み。技適が要る無線は XIAO(ESP32-S3-WROOM系=TELEC取得済)のみ。

## ほぼ1クリック（まとめてカート投入）
下のURLを開くと主要5点がカートに入る（要ログイン・在庫により一部入らない場合は下の個別リンクで）:

`https://www.amazon.co.jp/gp/aws/cart/add.html?ASIN.1=B0C3M8FCNS&Quantity.1=1&ASIN.2=B074Z4THWJ&Quantity.2=1&ASIN.3=B0DS1LQJMT&Quantity.3=1&ASIN.4=B09WMDVXSQ&Quantity.4=1&ASIN.5=B07KC4Z6LD&Quantity.5=1`

## 個別リンク（確実）
| # | 部品 | 役割 | 概算 | リンク(ASIN) |
|---|------|------|------|------|
| 1 | **Seeed XIAO ESP32-S3 Sense** | コア・**マイク内蔵**・WiFi/BLE・電池充電回路付・技適済 | ~¥3,000 | https://www.amazon.co.jp/dp/B0C3M8FCNS |
| 2 | **MAX98357A I2Sアンプ (Adafruit)** | 再生(聴く)用アンプ | ~¥1,500 | https://www.amazon.co.jp/dp/B074Z4THWJ |
| 3 | **1S LiPo 3.7V 1000mAh (JST-PH2.0)** | 主電源(10h検証) | ~¥900 | https://www.amazon.co.jp/dp/B0DS1LQJMT |
| 4 | **CN3791 MPPT ソーラー充電 (6V版)** | ソーラー→LiPo MPPT充電 | ~¥1,700 | https://www.amazon.co.jp/dp/B09WMDVXSQ |
| 5 | **6V 2W ソーラーパネル (uxcell 136×110mm)** | 充電源 | ~¥1,200 | https://www.amazon.co.jp/dp/B07KC4Z6LD |
| 6 | 8Ω 0.5–1W 小型スピーカー | 再生用(commodity) | ~¥300 | 検索: `8ohm 1W スピーカー 小型 28mm` |
| 7 | (任意) USB電流計 | 消費電流の実測精度UP | ~¥1,000 | 検索: `USB 電流計 テスター Type-C` |

**必須(1–5)合計: 約¥8,300 / スピーカー込み ~¥8,600 / 計測込み ~¥9,600**

## 注意
- XIAO Sense は **マイク内蔵**なので「押して話す→焚き火に薪」(G1の録音側)は本体だけで可。聴く側は #2+#6。
- CN3791 は **6V版**を選ぶ（パネル#5の6Vと整合）。12V版は不可。
- LiPo は **JST-PH2.0** コネクタ品を選ぶ（極性は購入前に要確認）。
- 届いたら配線は `manufacturing/prototype-10h-solar.md` §2、実測は §3 手順。

## 届いた後の最短手順
1. XIAO に G1 ファーム書込（`takibi.rs`＝別途実装・署名OTA/creds撤廃込み）
2. 「長押し→喋る→atsm.wtf に薪→クローン声」E2E green（動画＋レイテンシ実測）
3. INA226/USB電流計で idle/受信/送信の平均mA→稼働時間算出、屋外で `充電−消費>0` を実証
4. 実測値を仕様へ反映（それまで「10h/ソーラー連続」は概算表記）
