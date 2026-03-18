# ドメイン整理計画

## 現状

| ドメイン | 現在の用途 | ホスト先 |
|---------|-----------|---------|
| koe.elio.love | Koeソフトウェア配布 | Lovable (66.241.124.27) |
| elio.love | Elioアプリ | Cloudflare Pages (elio-love.pages.dev) |
| solun.art | Solunaプロジェクト | Lovable (66.241.124.10) |
| relay.solun.art | Solunaリレーサーバー | Hetzner VPS (46.225.77.119) |
| yukihamada.github.io/koe-device | Koeデバイスサイト | GitHub Pages |

## 新構成

### 取得するドメイン
| ドメイン | 年額 | 用途 |
|---------|------|------|
| **koe.live** | $25 | Koeデバイス メインドメイン |
| **koe.cc** | $8 | 短縮リダイレクト → koe.live |

### 統合後の構成

```
koe.live                         ← メインサイト (GitHub Pages)
├── koe.live/                    ← EN トップ
├── koe.live/ja                  ← JA トップ
├── koe.live/soluna-edition      ← Soluna Edition
├── koe.live/dashboard           ← 管理画面デモ
├── koe.live/docs                ← ドキュメント一覧
│
├── api.koe.live                 ← デバイスAPI (Fly.io or Lambda)
│   ├── /v1/device/audio         ← 音声送信
│   ├── /v1/device/status        ← ステータス
│   └── /v1/soluna/channels      ← チャンネル管理
│
├── app.koe.live                 ← Koeソフトウェア (現koe.elio.love を移行)
│
└── status.koe.live              ← アップタイムモニター

koe.cc → 301 redirect → koe.live (全パス維持)

solun.art                        ← Solunaプロジェクト全体 (変更なし)
├── solun.art/soluna              ← Solunaプロジェクトページ
├── relay.solun.art               ← リレーサーバー (変更なし)
└── send.solun.art                ← メール送信 (変更なし)

elio.love                        ← Elioアプリ (変更なし)
└── api.elio.love                 ← Elio API (変更なし)
```

### DNS設定 (koe.live 取得後に設定)

```
# koe.live → GitHub Pages
koe.live          CNAME  yukihamada.github.io
www.koe.live      CNAME  yukihamada.github.io

# API → Fly.io (or Lambda)
api.koe.live      CNAME  koe-api.fly.dev        (将来)

# ソフトウェア → 現koe.elio.loveと同じ先
app.koe.live      A      66.241.124.27
app.koe.live      AAAA   2a09:8280:1::de:7a0e:0

# koe.cc → リダイレクト (Cloudflare Page Rules)
koe.cc            A      192.0.2.1 (proxied, redirect rule)
*.koe.cc          CNAME  koe.cc (proxied, redirect rule)
```

### 移行手順

1. Cloudflareダッシュボードで koe.live + koe.cc を購入
2. koe.live のDNSレコードを設定 (GitHub Pages CNAME)
3. GitHub Pages の CNAME ファイルを koe.live に設定 (済み)
4. koe.cc に 301 リダイレクトルールを設定
5. solun.art/soluna のページ内リンクを koe.live に更新
6. koe.elio.love → app.koe.live にリダイレクト設定 (将来)
7. 全サイトのURLを koe.live に更新

### 削除候補 (不要ドメイン)

elio.loveのサブドメイン koe.elio.love は koe.live 移行後に削除可能。
elio.love 自体と solun.art は独立プロジェクトなので維持。
