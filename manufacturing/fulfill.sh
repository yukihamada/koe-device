#!/bin/bash
# Koe Seed Developer Edition — Fulfillment Pipeline
# Run this for each order to prepare and ship a unit.
#
# Prerequisites:
#   - fly CLI installed (for token retrieval)
#   - nRF Connect SDK installed (for firmware flash)
#   - curl, python3
#
# Usage:
#   ./fulfill.sh                  # Interactive pipeline
#   KOE_TOKEN=xxx ./fulfill.sh    # Skip token retrieval

set -e
echo "========================================"
echo "  Koe Seed — 出荷パイプライン"
echo "========================================"

# ---- Auth token ----
if [ -z "$KOE_TOKEN" ]; then
    echo ""
    echo "AUTH_TOKEN を取得中..."
    KOE_TOKEN=$(fly ssh console -a koe-live --command 'printenv AUTH_TOKEN' 2>/dev/null | tr -d '\r\n')
    if [ -z "$KOE_TOKEN" ]; then
        echo "  ERROR: AUTH_TOKEN を取得できませんでした"
        echo "  手動で設定してください: KOE_TOKEN=xxx ./fulfill.sh"
        exit 1
    fi
    echo "  OK"
fi

# Step 1: Check pending orders
echo ""
echo "[Step 1] 未発送の注文を確認..."
ORDERS=$(curl -sf "https://koe.live/admin/orders" -H "Authorization: Bearer $KOE_TOKEN" 2>/dev/null) || {
    echo "  ERROR: 注文一覧を取得できませんでした (認証エラーまたはサーバーダウン)"
    exit 1
}
PENDING=$(echo "$ORDERS" | python3 -c "
import sys,json
orders = json.load(sys.stdin).get('orders', [])
pending = [o for o in orders if o.get('status') in ('paid','confirmed')]
for o in pending:
    name = o.get('customer_name','') or o.get('shipping_name','')
    product = o.get('product','')
    status = o.get('status','')
    zip_code = o.get('shipping_zip','')
    state = o.get('shipping_state','')
    city = o.get('shipping_city','')
    addr = o.get('shipping_address','')
    print(f'  #{o[\"id\"]} {name} -- {product} -- {status}')
    print(f'     〒{zip_code} {state}{city} {addr}')
print(f'')
print(f'  未発送: {len(pending)}件')
")
echo "$PENDING"

PENDING_COUNT=$(echo "$ORDERS" | python3 -c "
import sys,json
orders = json.load(sys.stdin).get('orders', [])
print(len([o for o in orders if o.get('status') in ('paid','confirmed')]))
")

if [ "$PENDING_COUNT" = "0" ]; then
    echo ""
    echo "  未発送の注文はありません。"
    exit 0
fi

# Step 2: Flash firmware to DK
echo ""
echo "[Step 2] ファームウェア書込..."
echo "  nRF5340 Audio DK を USB-C で接続してください"
echo "  接続したら Enter を押してください..."
read -r

NCS_PATH="${NCS_PATH:-$HOME/ncs}"
if [ ! -d "$NCS_PATH/nrf" ]; then
    echo "  WARNING: nRF Connect SDK not found at $NCS_PATH"
    echo ""
    echo "  手動で flash してください:"
    echo "    cd $NCS_PATH/nrf/applications/nrf5340_audio"
    echo "    west build -b nrf5340_audio_dk/nrf5340/cpuapp -p -- -DCONFIG_TRANSPORT_BIS=y -DCONFIG_AUDIO_DEV=2"
    echo "    west flash"
    echo ""
    echo "  または flash-dk.sh を使ってください:"
    echo "    cd $(dirname "$0")/../firmware/demo"
    echo "    ./flash-dk.sh sink"
    echo ""
    echo "  flash 済みの場合は Enter を押してスキップ..."
    read -r
else
    cd "$NCS_PATH/nrf/applications/nrf5340_audio"
    echo "  Building Auracast Broadcast Sink..."
    west build -b nrf5340_audio_dk/nrf5340/cpuapp -p -- \
        -DCONFIG_TRANSPORT_BIS=y \
        -DCONFIG_AUDIO_DEV=2 2>&1 | tail -5

    echo "  Flashing..."
    west flash 2>&1 | tail -3

    echo "  ファームウェア書込完了"
fi

# Step 3: Test
echo ""
echo "[Step 3] 動作テスト..."
echo "  DK の電源を入れてください"
echo "  以下を確認:"
echo "    [ ] LED が点灯する"
echo "    [ ] nRF Connect app で BLE スキャン -> デバイスが見える"
echo "    [ ] (送信機があれば) 音が出る"
echo ""
echo -n "  テスト OK? (yes/no): "
read -r TEST_RESULT
if [ "$TEST_RESULT" != "yes" ]; then
    echo "  テスト失敗 -- 再 flash または DK 交換してください"
    exit 1
fi

# Step 4: Package
echo ""
echo "[Step 4] 梱包..."
echo "  [ ] DK をケースに入れる"
echo "  [ ] USB-C ケーブルを同梱"
echo "  [ ] クイックスタートカード (docs/quickstart.html を印刷) を同梱"
echo "  [ ] 静電気防止袋に入れる"
echo "  [ ] 緩衝材で包む"
echo "  [ ] 発送箱に入れる"
echo ""
echo -n "  梱包完了? (yes/no): "
read -r PACK_RESULT
if [ "$PACK_RESULT" != "yes" ]; then
    echo "  梱包を完了してから再実行してください"
    exit 1
fi

# Step 5: Select order and create shipping label
echo ""
echo "[Step 5] 発送ラベル作成..."
echo -n "  注文番号を入力: "
read -r ORDER_ID

# Validate input
if ! echo "$ORDER_ID" | grep -qE '^[0-9]+$'; then
    echo "  ERROR: 注文番号は数字で入力してください"
    exit 1
fi

# Get order details
ORDER_DETAIL=$(echo "$ORDERS" | python3 -c "
import sys,json
orders = json.load(sys.stdin).get('orders', [])
o = next((o for o in orders if o.get('id') == $ORDER_ID), None)
if o:
    ship_name = o.get('shipping_name','') or o.get('customer_name','')
    print(f'  宛先: {ship_name}')
    print(f'  〒{o.get(\"shipping_zip\",\"\")}')
    print(f'  {o.get(\"shipping_state\",\"\")}{o.get(\"shipping_city\",\"\")}')
    print(f'  {o.get(\"shipping_address\",\"\")}')
    country = o.get('shipping_country','')
    if country and country != 'JP':
        print(f'  国: {country}')
    print(f'  Email: {o.get(\"customer_email\",\"\")}')
    phone = o.get('phone','')
    if phone:
        print(f'  電話: {phone}')
else:
    print('  ERROR: 注文が見つかりません')
    import sys; sys.exit(1)
" 2>&1) || {
    echo "$ORDER_DETAIL"
    exit 1
}
echo "$ORDER_DETAIL"

echo ""
echo "  上記の宛先にラベルを作成してください。"
echo "  (DHL Express: https://mydhl.express.dhl/ )"
echo ""
echo -n "  追跡番号を入力 (発送後): "
read -r TRACKING

if [ -z "$TRACKING" ]; then
    echo "  WARNING: 追跡番号が空です"
    echo -n "  追跡番号なしで続行しますか? (yes/no): "
    read -r CONT
    if [ "$CONT" != "yes" ]; then
        echo "  追跡番号を取得してから再実行してください"
        exit 1
    fi
fi

# Step 6: Update order status
echo ""
echo "[Step 6] ステータス更新..."
UPDATE_BODY="{\"status\":\"shipped\""
if [ -n "$TRACKING" ]; then
    UPDATE_BODY="$UPDATE_BODY,\"tracking_number\":\"$TRACKING\""
fi
UPDATE_BODY="$UPDATE_BODY}"

RESULT=$(curl -sf -X PUT "https://koe.live/admin/orders/$ORDER_ID" \
    -H "Authorization: Bearer $KOE_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$UPDATE_BODY" 2>/dev/null) || {
    echo "  ERROR: ステータス更新に失敗しました"
    exit 1
}

echo "$RESULT" | python3 -c "
import sys,json
d=json.load(sys.stdin)
if d.get('ok'):
    print('  ステータス更新完了 -> shipped')
    print('  発送通知メールが自動送信されました')
else:
    print(f'  ERROR: {d}')
    sys.exit(1)
"

echo ""
echo "========================================"
echo "  出荷完了! 注文 #$ORDER_ID"
if [ -n "$TRACKING" ]; then
    echo "  追跡番号: $TRACKING"
fi
echo "========================================"
echo ""
echo "  次の注文がある場合は再度 ./fulfill.sh を実行してください"
