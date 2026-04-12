# Koe Seed — Stripe Pre-Order Setup

## 1分で完了する手順

### Step 1: Stripe Dashboardで商品を作る
https://dashboard.stripe.com/products にアクセス

4つの商品を作成:

| 商品名 | 価格 | 説明 |
|--------|------|------|
| Koe Seed (単品) | ¥5,000 ($35) | Auracast対応ワイヤレスオーディオレシーバー |
| Koe Seed Studio Pack | ¥430,000 ($2,900) | 100台 + Hub 1台 + 充電トレイ |
| Koe Seed Festival Pack | ¥2,850,000 ($19,000) | 1,000台 + Hub 2台 + 充電トレイ |
| Koe Seed Orchestra Pack | ¥1,425,000 ($9,500) | 100台 Pro + Hub 4台 |

### Step 2: Payment Linkを作る
https://dashboard.stripe.com/payment-links
各商品の「Payment Link」を作成 → URLをコピー

### Step 3: サイトに貼る
order.html, business.html, orchestra.html, gallery.html の
`STRIPE_SEED_SINGLE` / `STRIPE_STUDIO_PACK` / `STRIPE_FESTIVAL_PACK` / `STRIPE_ORCHESTRA_PACK` を実際のURLに置換:

```bash
find docs/ -name "*.html" -exec sed -i '' 's|STRIPE_SEED_SINGLE|https://buy.stripe.com/YOUR_LINK|g' {} \;
find docs/ -name "*.html" -exec sed -i '' 's|STRIPE_STUDIO_PACK|https://buy.stripe.com/YOUR_LINK|g' {} \;
find docs/ -name "*.html" -exec sed -i '' 's|STRIPE_FESTIVAL_PACK|https://buy.stripe.com/YOUR_LINK|g' {} \;
find docs/ -name "*.html" -exec sed -i '' 's|STRIPE_ORCHESTRA_PACK|https://buy.stripe.com/YOUR_LINK|g' {} \;
```

### Step 4: デプロイ
```bash
fly deploy --remote-only -a koe-live
```

## プレースホルダー一覧

| プレースホルダー | 使用ページ | 商品 |
|------------------|------------|------|
| `STRIPE_SEED_SINGLE` | order.html, gallery.html | Koe Seed 単品 ¥5,000 |
| `STRIPE_STUDIO_PACK` | business.html | Studio Pack ¥435,000 |
| `STRIPE_FESTIVAL_PACK` | business.html | Festival Pack ¥2,850,000 |
| `STRIPE_ORCHESTRA_PACK` | orchestra.html | Orchestra Pack ¥1,425,000 |
