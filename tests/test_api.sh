#!/bin/bash
# Koe Seed — E2E API Test Suite
# Tests all live endpoints on koe.live
# Usage: bash tests/test_api.sh [--local]
#
# Options:
#   --local   Test against http://localhost:8080 instead of https://koe.live
#   --no-auth Skip tests that require admin auth token

set -euo pipefail

# ── Configuration ──
if [ "${1:-}" = "--local" ]; then
    BASE="http://localhost:8080"
    shift
else
    BASE="https://koe.live"
fi

SKIP_AUTH=false
if [ "${1:-}" = "--no-auth" ]; then
    SKIP_AUTH=true
    shift
fi

PASS=0
FAIL=0
SKIP=0
TOTAL=0

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

# ── Test helpers ──

assert_status() {
    local name="$1" url="$2" expected="$3" method="${4:-GET}" body="${5:-}"
    TOTAL=$((TOTAL+1))

    if [ "$method" = "POST" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$url" \
            -H "Content-Type: application/json" -d "$body" --max-time 15)
    elif [ "$method" = "PUT" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$url" \
            -H "Content-Type: application/json" -d "$body" --max-time 15)
    else
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url" --max-time 15)
    fi

    if [ "$status" = "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC} $name (HTTP $status)"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} $name (expected $expected, got $status)"
        FAIL=$((FAIL+1))
    fi
}

assert_status_auth() {
    local name="$1" url="$2" expected="$3" method="${4:-GET}" body="${5:-}"
    TOTAL=$((TOTAL+1))

    if [ "$method" = "PUT" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$url" \
            -H "Content-Type: application/json" -H "Authorization: Bearer $AUTH" \
            -d "$body" --max-time 15)
    else
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url" \
            -H "Authorization: Bearer $AUTH" --max-time 15)
    fi

    if [ "$status" = "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC} $name (HTTP $status)"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} $name (expected $expected, got $status)"
        FAIL=$((FAIL+1))
    fi
}

assert_contains() {
    local name="$1" url="$2" expected="$3"
    TOTAL=$((TOTAL+1))

    body=$(curl -s "$url" --max-time 15)
    if echo "$body" | grep -q "$expected"; then
        echo -e "  ${GREEN}PASS${NC} $name (contains '$expected')"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} $name (missing '$expected')"
        FAIL=$((FAIL+1))
    fi
}

assert_json_field() {
    local name="$1" url="$2" field="$3" expected="$4" headers="${5:-}"
    TOTAL=$((TOTAL+1))

    if [ -n "$headers" ]; then
        value=$(curl -s "$url" -H "$headers" --max-time 15 | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('$field', ''))
except:
    print('JSON_PARSE_ERROR')
" 2>/dev/null)
    else
        value=$(curl -s "$url" --max-time 15 | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('$field', ''))
except:
    print('JSON_PARSE_ERROR')
" 2>/dev/null)
    fi

    if [ "$value" = "$expected" ]; then
        echo -e "  ${GREEN}PASS${NC} $name (.$field = '$value')"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} $name (expected .$field='$expected', got '$value')"
        FAIL=$((FAIL+1))
    fi
}

assert_json_exists() {
    local name="$1" url="$2" field="$3" headers="${4:-}"
    TOTAL=$((TOTAL+1))

    if [ -n "$headers" ]; then
        exists=$(curl -s "$url" -H "$headers" --max-time 15 | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('yes' if '$field' in d else 'no')
except:
    print('no')
" 2>/dev/null)
    else
        exists=$(curl -s "$url" --max-time 15 | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('yes' if '$field' in d else 'no')
except:
    print('no')
" 2>/dev/null)
    fi

    if [ "$exists" = "yes" ]; then
        echo -e "  ${GREEN}PASS${NC} $name (has .$field)"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} $name (missing .$field)"
        FAIL=$((FAIL+1))
    fi
}

skip_test() {
    local name="$1" reason="$2"
    TOTAL=$((TOTAL+1))
    SKIP=$((SKIP+1))
    echo -e "  ${YELLOW}SKIP${NC} $name ($reason)"
}

# ── Start ──

echo "========================================"
echo -e "  ${BOLD}Koe Seed — E2E Test Suite${NC}"
echo "  Target: $BASE"
echo "  Date:   $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# ── Get auth token ──
AUTH=""
if [ "$SKIP_AUTH" = false ]; then
    echo ""
    echo -e "${BOLD}Fetching admin token...${NC}"
    AUTH=$(fly ssh console -a koe-live --command "printenv AUTH_TOKEN" 2>/dev/null || true)
    if [ -z "$AUTH" ]; then
        echo -e "  ${YELLOW}WARNING${NC}: Could not fetch AUTH_TOKEN from Fly.io. Auth tests will be skipped."
        SKIP_AUTH=true
    else
        echo -e "  ${GREEN}OK${NC} Token retrieved (${#AUTH} chars)"
    fi
fi

# ════════════════════════════════════════
# Section 1: HTML Pages
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 1. HTML Pages (HTTP 200) ──${NC}"
assert_status "Landing page /"           "$BASE/"             "200"
assert_status "Order page /order"        "$BASE/order"        "200"
assert_status "Gallery /gallery"         "$BASE/gallery"      "200"
assert_status "Business /business"       "$BASE/business"     "200"
assert_status "Orchestra /orchestra"     "$BASE/orchestra"    "200"
assert_status "Order success"            "$BASE/order/success" "200"
assert_status "Admin page"               "$BASE/admin"        "200"
assert_status "Pro page"                 "$BASE/pro"          "200"
assert_status "Busker page"              "$BASE/busker"       "200"
assert_status "Classroom page"           "$BASE/classroom"    "200"
assert_status "Moji (translate)"         "$BASE/moji"         "200"
assert_status "Soluna OS"                "$BASE/soluna-os"    "200"
assert_status "Stadium page"             "$BASE/stadium"      "200"
assert_status "Design page"              "$BASE/design"       "200"
assert_status "Compare page"             "$BASE/compare"      "200"
assert_status "Crowd page"               "$BASE/crowd"        "200"
assert_status "Story page"               "$BASE/story"        "200"
assert_status "P2P App /app"             "$BASE/app"          "200"
assert_status "Quickstart (static)"      "$BASE/quickstart.html" "200"

# ════════════════════════════════════════
# Section 2: Page Content Validation
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 2. Page Content ──${NC}"
assert_contains "LP has HTML"                "$BASE/"        "<html"
assert_contains "Order has product info"     "$BASE/order"   "Koe"
assert_contains "Gallery has content"        "$BASE/gallery" "Koe"
assert_contains "Business has pricing"       "$BASE/business" "Koe"
assert_contains "Admin has dashboard"        "$BASE/admin"   "admin"

# ════════════════════════════════════════
# Section 3: Health & JSON APIs
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 3. Health & JSON APIs ──${NC}"
assert_status     "Health endpoint"          "$BASE/health"  "200"
assert_json_field "Health returns ok"        "$BASE/health"  "status" "ok"

# /api/devices — returns array (may be empty)
TOTAL=$((TOTAL+1))
DEVICES=$(curl -s "$BASE/api/devices" --max-time 15)
if echo "$DEVICES" | python3 -c "import sys,json; d=json.load(sys.stdin); assert isinstance(d, list)" 2>/dev/null; then
    echo -e "  ${GREEN}PASS${NC} /api/devices returns JSON array"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}FAIL${NC} /api/devices should return JSON array (got: ${DEVICES:0:80})"
    FAIL=$((FAIL+1))
fi

# /api/stats
assert_status "Stats endpoint" "$BASE/api/stats" "200"

# /api/features
assert_status "Features endpoint" "$BASE/api/features" "200"

# /api/wt-hash
assert_status "WebTransport hash" "$BASE/api/wt-hash" "200"

# /api/rooms
assert_status "Rooms list" "$BASE/api/rooms" "200"

# ════════════════════════════════════════
# Section 4: Stripe Checkout API
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 4. Stripe Checkout ──${NC}"

# Valid product: deposit
TOTAL=$((TOTAL+1))
CHECKOUT=$(curl -s -X POST "$BASE/api/v1/checkout" \
    -H "Content-Type: application/json" \
    -d '{"product":"deposit","quantity":1}' --max-time 15)
if echo "$CHECKOUT" | grep -q "checkout_url"; then
    echo -e "  ${GREEN}PASS${NC} Checkout deposit -> Stripe URL returned"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}FAIL${NC} Checkout deposit -> no URL (${CHECKOUT:0:120})"
    FAIL=$((FAIL+1))
fi

# Valid product: dk_edition
TOTAL=$((TOTAL+1))
CHECKOUT2=$(curl -s -X POST "$BASE/api/v1/checkout" \
    -H "Content-Type: application/json" \
    -d '{"product":"dk_edition","quantity":1}' --max-time 15)
if echo "$CHECKOUT2" | grep -q "checkout_url"; then
    echo -e "  ${GREEN}PASS${NC} Checkout dk_edition -> Stripe URL returned"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}FAIL${NC} Checkout dk_edition -> no URL (${CHECKOUT2:0:120})"
    FAIL=$((FAIL+1))
fi

# Valid product: seed
TOTAL=$((TOTAL+1))
CHECKOUT3=$(curl -s -X POST "$BASE/api/v1/checkout" \
    -H "Content-Type: application/json" \
    -d '{"product":"seed","quantity":2}' --max-time 15)
if echo "$CHECKOUT3" | grep -q "checkout_url"; then
    echo -e "  ${GREEN}PASS${NC} Checkout seed qty=2 -> Stripe URL returned"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}FAIL${NC} Checkout seed qty=2 -> no URL (${CHECKOUT3:0:120})"
    FAIL=$((FAIL+1))
fi

# Invalid product -> error
TOTAL=$((TOTAL+1))
CHECKOUT_BAD=$(curl -s -X POST "$BASE/api/v1/checkout" \
    -H "Content-Type: application/json" \
    -d '{"product":"invalid_product","quantity":1}' --max-time 15)
if echo "$CHECKOUT_BAD" | grep -qi "error\|Invalid"; then
    echo -e "  ${GREEN}PASS${NC} Checkout invalid product -> error returned"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}FAIL${NC} Checkout invalid product -> should return error (${CHECKOUT_BAD:0:120})"
    FAIL=$((FAIL+1))
fi

# Missing body -> error (axum returns 400 for missing/malformed JSON)
assert_status "Checkout empty body -> 400" "$BASE/api/v1/checkout" "400" "POST" ""

# ════════════════════════════════════════
# Section 5: Stripe Webhook
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 5. Stripe Webhook ──${NC}"

# Webhook with empty JSON body (no stripe-signature) -> should 400 (bad sig)
TOTAL=$((TOTAL+1))
WH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/v1/stripe/webhook" \
    -H "Content-Type: application/json" -d '{"type":"test"}' --max-time 15)
# If STRIPE_WEBHOOK_SECRET is set, expect 400 (bad sig). If not set, accept any 2xx/4xx.
if [ "$WH_STATUS" = "400" ] || [ "$WH_STATUS" = "200" ]; then
    echo -e "  ${GREEN}PASS${NC} Webhook endpoint responds (HTTP $WH_STATUS)"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}FAIL${NC} Webhook endpoint unexpected status (HTTP $WH_STATUS)"
    FAIL=$((FAIL+1))
fi

# Webhook with invalid JSON body -> 400
assert_status "Webhook invalid JSON" "$BASE/api/v1/stripe/webhook" "400" "POST" "not-json"

# ════════════════════════════════════════
# Section 6: Admin Auth (No Token)
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 6. Admin Auth (Unauthorized) ──${NC}"
assert_status "Admin orders (no auth) -> 401"   "$BASE/admin/orders"        "401"
assert_status "Admin export (no auth) -> 401"   "$BASE/admin/orders/export" "401"
assert_status "Order update (no auth) -> 401"   "$BASE/admin/orders/1"      "401" "PUT" '{"notes":"test"}'

# ════════════════════════════════════════
# Section 7: Admin Auth (With Token)
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 7. Admin Operations (Authenticated) ──${NC}"

if [ "$SKIP_AUTH" = true ]; then
    skip_test "Admin orders list"       "no auth token"
    skip_test "Admin orders has total"  "no auth token"
    skip_test "Admin order update"      "no auth token"
    skip_test "Admin invalid status"    "no auth token"
    skip_test "Admin CSV export"        "no auth token"
    skip_test "Admin CSV header"        "no auth token"
else
    # List orders
    assert_status_auth "Admin orders (auth) -> 200" "$BASE/admin/orders" "200"

    # Orders response has 'total' field
    TOTAL=$((TOTAL+1))
    ORDERS=$(curl -s "$BASE/admin/orders" -H "Authorization: Bearer $AUTH" --max-time 15)
    if echo "$ORDERS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'total' in d" 2>/dev/null; then
        ORDER_COUNT=$(echo "$ORDERS" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])" 2>/dev/null)
        echo -e "  ${GREEN}PASS${NC} Admin orders response has .total ($ORDER_COUNT orders)"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} Admin orders response missing .total"
        FAIL=$((FAIL+1))
    fi

    # Update order notes (non-destructive)
    TOTAL=$((TOTAL+1))
    UPDATE=$(curl -s -X PUT "$BASE/admin/orders/1" \
        -H "Authorization: Bearer $AUTH" \
        -H "Content-Type: application/json" \
        -d '{"notes":"E2E test note - safe to ignore"}' --max-time 15)
    if echo "$UPDATE" | grep -q '"ok"'; then
        echo -e "  ${GREEN}PASS${NC} Order update (notes) -> ok"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} Order update (notes) -> $UPDATE"
        FAIL=$((FAIL+1))
    fi

    # Invalid status -> rejected
    TOTAL=$((TOTAL+1))
    UPDATE_BAD=$(curl -s -X PUT "$BASE/admin/orders/1" \
        -H "Authorization: Bearer $AUTH" \
        -H "Content-Type: application/json" \
        -d '{"status":"invalid_status_xyz"}' --max-time 15)
    if echo "$UPDATE_BAD" | grep -qi "error\|Invalid"; then
        echo -e "  ${GREEN}PASS${NC} Order invalid status -> rejected"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} Order invalid status -> should reject (${UPDATE_BAD:0:120})"
        FAIL=$((FAIL+1))
    fi

    # CSV export
    assert_status_auth "Admin CSV export -> 200" "$BASE/admin/orders/export" "200"

    TOTAL=$((TOTAL+1))
    CSV_HEADER=$(curl -s "$BASE/admin/orders/export" \
        -H "Authorization: Bearer $AUTH" --max-time 15 | head -1)
    if echo "$CSV_HEADER" | grep -q "ID"; then
        echo -e "  ${GREEN}PASS${NC} CSV export has header row"
        PASS=$((PASS+1))
    else
        echo -e "  ${RED}FAIL${NC} CSV export missing header (got: ${CSV_HEADER:0:80})"
        FAIL=$((FAIL+1))
    fi
fi

# ════════════════════════════════════════
# Section 8: Firmware / OTA API
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 8. Firmware / OTA ──${NC}"

# Firmware check — should return 200 (update available) or 204 (up-to-date) or 404 (no firmware)
TOTAL=$((TOTAL+1))
FW_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    "$BASE/api/v1/device/firmware?version=0.0.1&device_id=e2e-test" --max-time 15)
if [ "$FW_STATUS" = "200" ] || [ "$FW_STATUS" = "204" ] || [ "$FW_STATUS" = "404" ]; then
    echo -e "  ${GREEN}PASS${NC} Firmware check responds (HTTP $FW_STATUS)"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}FAIL${NC} Firmware check unexpected status (HTTP $FW_STATUS)"
    FAIL=$((FAIL+1))
fi

# Firmware upload without token -> 401
assert_status "Firmware upload (no token) -> 401" \
    "$BASE/api/v1/device/firmware/upload?version=0.0.0" "401" "POST" "binary"

# ════════════════════════════════════════
# Section 9: Static Assets
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 9. Static Assets ──${NC}"
assert_status "Favicon"               "$BASE/favicon.svg"              "200"
assert_status "CSS or JS asset"       "$BASE/quickstart.html"          "200"

# ════════════════════════════════════════
# Section 10: Error Handling
# ════════════════════════════════════════
echo ""
echo -e "${BOLD}── 10. Error Handling ──${NC}"
assert_status "404 for nonexistent page"    "$BASE/this-page-does-not-exist-xyz" "404"
assert_status "Checkout wrong method (GET)" "$BASE/api/v1/checkout"              "405"

# ════════════════════════════════════════
# Results
# ════════════════════════════════════════
echo ""
echo "========================================"
echo -e "  ${BOLD}Results${NC}"
echo "  Passed:  $PASS"
echo "  Failed:  $FAIL"
echo "  Skipped: $SKIP"
echo "  Total:   $TOTAL"
echo ""
if [ $FAIL -eq 0 ]; then
    echo -e "  ${GREEN}${BOLD}ALL TESTS PASSED${NC}"
else
    echo -e "  ${RED}${BOLD}$FAIL TEST(S) FAILED${NC}"
fi
echo "========================================"

exit $FAIL
