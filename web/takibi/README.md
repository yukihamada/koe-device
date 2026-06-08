# 焚き火 — オープンソース静的クライアント

ATSM の焚き火（atsm.wtf）に**声で薪をくべ、声で聴ける**単機能Webクライアント。
公開API `https://mcp.koe.live/api/takibi/*`（CORS許可）を叩く自己完結の静的HTML。
誰でもフォークして自分のサイトに置けます。

- 正準版（PWA・サインイン・Service Worker込み）: https://mcp.koe.live/takibi
- 本ディレクトリ: その正準クライアントを**別オリジンでも動くよう絶対API化したスナップショット**

## 使い方
`index.html` を任意の静的ホスト（GitHub Pages 等）に置くだけ。ビルド不要。
- 聴く・🔥リアクション・実機予約は匿名でOK
- 声でくべるにはサインイン鍵が必要（`?...#k=<KEY>` で渡すか、正準版でサインイン）

## 再生成
正準版が更新されたら同期:
```bash
bash regenerate.sh   # mcp.koe.live/takibi を取得し相対パスを絶対APIへ書換
```

## API（公開・CORS *）
| メソッド | パス | 用途 |
|---|---|---|
| GET | /api/takibi/feed | 焚き火の薪一覧＋火の強さ |
| POST | /api/takibi/speak {id} | 薪をクローン声mp3に |
| POST | /api/takibi/log {text\|audio_base64} | 薪をくべる（要鍵） |
| POST | /api/takibi/react {id,r,v} | 🔥/🙏 リアクション |
| GET/POST | /api/takibi/reserve | 実機の予約・予約者数 |

ライセンス: 本リポジトリの LICENSE に従う。
