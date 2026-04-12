#!/bin/bash
# Post to Twitter/X and open LinkedIn for manual posting
# Usage: bash scripts/post-sns.sh "投稿テキスト" [画像パス]

TEXT="${1:-Auracastワイヤレスオーディオレシーバーを開発中。nRF5340 DKで動作確認済み。28mmカスタム基板は設計中。オープンソース。 https://koe.live}"
IMAGE="$2"

echo "=== SNS投稿 ==="
echo "テキスト: $TEXT"
echo ""

# Twitter/X — use API if token available
TWITTER_TOKEN="${TWITTER_BEARER_TOKEN:-}"
if [ -n "$TWITTER_TOKEN" ]; then
    echo "[Twitter] API投稿中..."
    curl -s -X POST "https://api.twitter.com/2/tweets" \
        -H "Authorization: Bearer $TWITTER_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"$TEXT\"}" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if 'data' in d:
    print(f'  OK: https://twitter.com/i/web/status/{d[\"data\"][\"id\"]}')
else:
    print(f'  Error: {d}')
"
else
    echo "[Twitter] トークン未設定 -- ブラウザで開きます"
    # URL encode the text and open Twitter compose
    ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('''$TEXT'''))")
    open "https://twitter.com/intent/tweet?text=$ENCODED"
fi

# LinkedIn — no easy API, open browser
echo "[LinkedIn] ブラウザで開きます"
open "https://www.linkedin.com/feed/?shareActive=true"

# Hacker News
echo "[HN] ブラウザで開きます"
open "https://news.ycombinator.com/submit"

echo ""
echo "投稿テンプレート:"
echo "--------------------------------------------"
echo "Title: Show HN: Koe - Open-source Auracast audio receiver (nRF5340 DK, custom PCB in design)"
echo "URL: https://koe.live"
echo "--------------------------------------------"
