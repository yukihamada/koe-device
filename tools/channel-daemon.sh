#!/bin/bash
# Soluna Channel Daemon — 全チャンネル自動配信
# 66プレイリスト、646曲
#
# Usage:
#   ./channel-daemon.sh          # 全チャンネル起動
#   ./channel-daemon.sh avicii   # 1チャンネルだけ
#   ./channel-daemon.sh stop     # 全停止

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="/tmp/soluna-channels.pids"

if [ "$1" = "stop" ]; then
    if [ -f "$PID_FILE" ]; then
        kill $(cat "$PID_FILE") 2>/dev/null || true
        rm "$PID_FILE"
        echo "All channels stopped."
    fi
    exit 0
fi

echo "=== Soluna Channel Daemon ==="
echo "66 channels, 646 tracks"
echo ""

PIDS=""
COUNT=0

start() {
    local ch="$1"
    local playlist="$DIR/playlists/${ch}.txt"
    if [ -f "$playlist" ]; then
        python3 "$DIR/channel-dj.py" --channel "$ch" --playlist "$playlist" --loop > "/tmp/soluna-${ch}.log" 2>&1 &
        PIDS="$PIDS $!"
        COUNT=$((COUNT + 1))
        echo "  [$COUNT] $ch"
    fi
}

if [ -n "$1" ] && [ "$1" != "stop" ]; then
    start "$1"
else
    for playlist in "$DIR"/playlists/*.txt; do
        ch=$(basename "$playlist" .txt)
        start "$ch"
    done
fi

echo ""
echo "$COUNT channels running"
echo "$PIDS" > "$PID_FILE"
echo "Logs: /tmp/soluna-*.log"
echo "Stop: $0 stop"

wait
