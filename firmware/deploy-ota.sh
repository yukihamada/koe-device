#!/bin/bash
# Koe Device OTA デプロイスクリプト
# 使い方: ./deploy-ota.sh [--release] [--token ADMIN_TOKEN]
#
# 処理:
#   1. cargo build (release)
#   2. espflash save-image → latest.bin 生成
#   3. api.chatweb.ai/api/v1/device/firmware/upload にアップロード
#   デバイスは次回起動時に自動取得・書き込み・再起動

set -euo pipefail

cd "$(dirname "$0")"

# ─── 引数 ───────────────────────────────────────────────
BUILD_PROFILE="debug"
SERVER="https://koe.live"
ADMIN_TOKEN="${KOE_OTA_TOKEN:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --release) BUILD_PROFILE="release"; shift ;;
        --token)   ADMIN_TOKEN="$2"; shift 2 ;;
        --server)  SERVER="$2"; shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

if [[ -z "$ADMIN_TOKEN" ]]; then
    echo "ERROR: ADMIN_TOKEN required (--token TOKEN or KOE_OTA_TOKEN env)"
    exit 1
fi

# ─── バージョン取得 ──────────────────────────────────────
VERSION=$(grep '^version' Cargo.toml | head -1 | sed 's/.*= *"\(.*\)"/\1/')
echo "=== Koe OTA Deploy v${VERSION} ==="

# ─── ビルド ─────────────────────────────────────────────
echo "[1/3] Building firmware..."
if [[ "$BUILD_PROFILE" == "release" ]]; then
    cargo build --release 2>&1 | tail -5
    ELF="target/xtensa-esp32s3-espidf/release/koe-device"
else
    cargo build 2>&1 | tail -5
    ELF="target/xtensa-esp32s3-espidf/debug/koe-device"
fi

if [[ ! -f "$ELF" ]]; then
    echo "ERROR: ELF not found at $ELF"
    exit 1
fi

# ─── バイナリ生成 ────────────────────────────────────────
echo "[2/3] Generating firmware binary..."
BIN="latest.bin"
espflash save-image \
    --chip esp32s3 \
    --merge \
    "$ELF" \
    "$BIN"

BIN_SIZE=$(wc -c < "$BIN")
echo "  Binary: ${BIN} (${BIN_SIZE} bytes)"

# ─── アップロード ────────────────────────────────────────
echo "[3/3] Uploading to ${SERVER}..."
HTTP_STATUS=$(curl -s -o /tmp/ota_upload_resp.txt -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@${BIN}" \
    "${SERVER}/api/v1/device/firmware/upload?version=${VERSION}&token=${ADMIN_TOKEN}")

RESPONSE=$(cat /tmp/ota_upload_resp.txt)

if [[ "$HTTP_STATUS" == "200" ]]; then
    echo "  ✓ Upload OK: ${RESPONSE}"
else
    echo "  ✗ Upload failed (HTTP ${HTTP_STATUS}): ${RESPONSE}"
    exit 1
fi

echo ""
echo "=== OTA Deploy Complete ==="
echo "  Version:   v${VERSION}"
echo "  Size:      ${BIN_SIZE} bytes"
echo "  Endpoint:  ${SERVER}/api/v1/device/firmware"
echo ""
echo "Devices will auto-update on next boot."
