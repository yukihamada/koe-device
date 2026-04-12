#!/bin/bash
# Koe Seed — 自動運用ループ
# 10分ごとに: 注文チェック → 在庫確認 → サイト監視 → テスト
# 人間が必要なことだけ通知する

set -e
cd "$(dirname "$0")"

AUTH=$(fly ssh console -a koe-live --command "printenv KOE_ADMIN_TOKEN" 2>/dev/null)
RESEND=$(fly ssh console -a enablerdao --command "printenv RESEND_API_KEY" 2>/dev/null)

notify() {
    echo "⚠️  人間が必要: $1"
    # Telegram通知
    BOT_TOKEN=$(fly ssh console -a koe-live --command "printenv TELEGRAM_BOT_TOKEN" 2>/dev/null || true)
    if [ -n "$BOT_TOKEN" ]; then
        curl -s "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
            -d "chat_id=1136442501" -d "text=🌱 Koe Seed: $1" > /dev/null 2>&1 || true
    fi
    # メール通知
    if [ -n "$RESEND" ]; then
        curl -s -X POST "https://api.resend.com/emails" \
            -H "Authorization: Bearer $RESEND" \
            -H "Content-Type: application/json" \
            -d "{\"from\":\"Koe <info@enablerdao.com>\",\"to\":[\"mail@yukihamada.jp\"],\"subject\":\"🌱 Koe Seed: $1\",\"html\":\"<p>$1</p><p><a href='https://koe.live/admin'>管理画面を開く</a></p>\"}" > /dev/null 2>&1 || true
    fi
}

check_pcbway() {
    echo "[$(date '+%H:%M')] PCBWay注文確認..."
    RESULT=$(python3 -c "
import json
from urllib.request import Request, urlopen
data = {'orderNo': 'W1046165AS1JP1'}
body = json.dumps(data).encode('utf-8')
req = Request('https://api-partner.pcbway.com/api/Pcb/QueryOrderProcess', data=body, method='POST')
req.add_header('Content-Type', 'application/json')
req.add_header('api-key', 'W1046165A 74D7895DE56D134C8063A54138502164')
with urlopen(req, timeout=15) as resp:
    r = json.loads(resp.read().decode('utf-8'))
    if r.get('Status') == 'ok' and r.get('AllProcess'):
        print('MANUFACTURING')
    elif 'not been arranged' in r.get('ErrorText',''):
        print('AWAITING_REVIEW')
    else:
        print(r.get('ErrorText','UNKNOWN'))
" 2>/dev/null)
    echo "  PCBWay W1046165AS1JP1: $RESULT"
    if [ "$RESULT" = "MANUFACTURING" ]; then
        notify "PCBWay基板が製造開始されました！"
    fi
}

check_orders() {
    echo "[$(date '+%H:%M')] 注文チェック..."
    ORDERS=$(curl -s "https://koe.live/admin/orders" -H "Authorization: Bearer $AUTH" 2>/dev/null)

    PAID=$(echo "$ORDERS" | python3 -c "
import sys,json
try:
    orders = json.load(sys.stdin).get('orders',[])
    paid = [o for o in orders if o['status'] in ('paid','confirmed')]
    shipped = [o for o in orders if o['status'] == 'shipped']
    delivered = [o for o in orders if o['status'] == 'delivered']
    total_revenue = sum(o.get('amount_jpy',0) or 0 for o in orders)
    print(f'PAID={len(paid)}')
    print(f'SHIPPED={len(shipped)}')
    print(f'DELIVERED={len(delivered)}')
    print(f'TOTAL={len(orders)}')
    print(f'REVENUE={total_revenue}')
    for o in paid:
        print(f'NEW_ORDER={o[\"id\"]}|{o[\"customer_name\"]}|{o[\"product\"]}|{o.get(\"amount_jpy\",0)}')
except:
    print('PAID=0')
    print('TOTAL=0')
    print('REVENUE=0')
" 2>/dev/null)

    eval "$PAID"

    echo "  注文: ${TOTAL}件 (未発送: ${PAID}, 発送済: ${SHIPPED}, 完了: ${DELIVERED})"
    echo "  売上: ¥${REVENUE}"

    if [ "$PAID" -gt 0 ]; then
        notify "新しい未発送注文が${PAID}件あります！ https://koe.live/admin"
    fi
}

check_site() {
    echo "[$(date '+%H:%M')] サイト監視..."
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://koe.live/health" 2>/dev/null || echo "000")
    if [ "$STATUS" = "200" ]; then
        echo "  koe.live: UP ✓"
    else
        echo "  koe.live: DOWN ✗ (HTTP $STATUS)"
        notify "koe.liveがダウンしています！HTTP $STATUS"
    fi

    # Checkout動作確認
    CHECKOUT=$(curl -s -X POST "https://koe.live/api/v1/checkout" \
        -H "Content-Type: application/json" \
        -d '{"product":"deposit","quantity":1}' 2>/dev/null)
    if echo "$CHECKOUT" | grep -q "checkout_url"; then
        echo "  Stripe Checkout: OK ✓"
    else
        echo "  Stripe Checkout: FAIL ✗"
        notify "Stripe Checkoutが動いていません！"
    fi
}

run_tests() {
    echo "[$(date '+%H:%M')] テスト実行..."
    if [ -f "tests/test_api.sh" ]; then
        RESULT=$(bash tests/test_api.sh 2>&1 | tail -3)
        echo "  $RESULT"
        if echo "$RESULT" | grep -q "FAILED"; then
            notify "E2Eテストが失敗しています！"
        fi
    fi
}

show_status() {
    echo ""
    echo "========================================"
    echo "  Koe Seed — 運用ステータス"
    echo "  $(date '+%Y-%m-%d %H:%M')"
    echo "========================================"
    check_orders
    check_pcbway
    check_site
    echo ""
    echo "  あなたがやること:"
    echo "  ─────────────────"
    if [ "$PAID" -gt 0 ]; then
        echo "  → 未発送${PAID}件: bash manufacturing/fulfill.sh"
    fi
    echo "  → DK在庫確認: 手元に何台ある？"
    echo "  → DK追加注文: open https://www.digikey.com/..."
    echo "  → デモ動画撮影+SNS投稿"
    echo "========================================"
}

# メインループ
echo "🌱 Koe Seed 自動運用ループ起動"
echo "   Ctrl+C で停止"
echo ""

while true; do
    show_status
    echo ""
    echo "次のチェック: 10分後..."
    sleep 600
done
