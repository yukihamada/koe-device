# Koe Seed -- 物流代行サービス

## なぜ必要か
DKを自分でflash→梱包→発送するのは10台までが限界。
100台以上は物流代行に委託する。

## 推奨サービス（日本）

### 1. オープンロジ (openlogi.com)
- 月額固定費: 0円（従量課金のみ）
- 入庫: 15-30円/個
- 保管: 5,000円/坪/月
- 出荷: 550円~/個（60サイズ）
- API連携: あり（注文自動取込可能）
- 小ロットOK

### 2. ロジモプロ (logi-mo.jp)
- 個人・スタートアップ向け
- 出荷: 500円~/個
- Shopify/BASE連携

### 3. Amazon FBA (MCF)
- Amazonに在庫を送る → Amazonが発送
- 出荷: 434円~/個
- Prime配送で翌日届く

## 推奨フロー

```
PCBWay完成品 → オープンロジ倉庫 → 注文Webhook → 自動出荷
     (1回)         (1回送る)        (koe.live)     (API連携)
```

1. PCBWayから完成品100台が届く
2. 全台まとめてオープンロジの倉庫に送る
3. koe.liveで注文が入る
4. Webhook → オープンロジAPI → 自動出荷
5. 追跡番号がkoe.live/adminに自動反映

## API連携 (オープンロジ)

### 出荷依頼
```bash
curl -X POST https://api.openlogi.com/api/shipments \
  -H "Authorization: Bearer $OPENLOGI_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "SEED-0001",
    "shipping_name": "山田太郎",
    "shipping_zip": "150-0001",
    "shipping_address": "東京都渋谷区...",
    "shipping_phone": "090-0000-0000",
    "items": [{"sku": "KOE-SEED-DK", "quantity": 1}]
  }'
```

### koe.live側の実装（server/src/main.rs に追加）
```rust
// 注文完了時にオープンロジへ出荷依頼を送信
async fn create_shipment(order: &Order) -> Result<String> {
    let client = reqwest::Client::new();
    let resp = client.post("https://api.openlogi.com/api/shipments")
        .bearer_auth(&std::env::var("OPENLOGI_TOKEN")?)
        .json(&serde_json::json!({
            "order_id": order.id,
            "shipping_name": order.name,
            "shipping_zip": order.zip,
            "shipping_address": order.address,
            "items": [{"sku": "KOE-SEED-DK", "quantity": order.quantity}]
        }))
        .send().await?;
    let tracking: serde_json::Value = resp.json().await?;
    Ok(tracking["tracking_number"].as_str().unwrap_or("").to_string())
}
```

## コスト試算（100台出荷）

| 項目 | 単価 | 合計 |
|------|------|------|
| 入庫 | 30円 x 100 | 3,000円 |
| 保管（1ヶ月） | ~500円 | 500円 |
| 出荷 | 550円 x 100 | 55,000円 |
| **合計** | | **58,500円** |

販売価格 12,800円 x 100 = 1,280,000円 に対して物流費 4.6%。十分なマージン。

## 海外発送

オープンロジはEMS/DHL連携あり。
- EMS: 2,000円~（アジア）/ 3,000円~（北米/欧州）
- DHL: 3,500円~

koe.liveの注文フォームで国を選択 → API側で自動振り分け。

## 次のアクション

1. [ ] オープンロジに無料アカウント作成
2. [ ] SKU "KOE-SEED-DK" を登録
3. [ ] テスト出荷（自分宛に1台送る）
4. [ ] koe.live注文Webhookと接続
5. [ ] 追跡番号のメール自動送信を設定
