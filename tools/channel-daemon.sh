#!/bin/bash
# Soluna Channel Daemon — 全チャンネルを同時配信
# Pi 5のSTAGEで実行。各チャンネルをバックグラウンドで起動。
#
# Usage: ./channel-daemon.sh
# Stop:  kill $(cat /tmp/soluna-channels.pid)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="/tmp/soluna-channels.pid"

echo "=== Soluna Channel Daemon ==="
echo "Starting channels..."
echo ""

PIDS=""

# Free channels (playlists loop)
start_channel() {
    local ch="$1"
    local playlist="$2"
    if [ -f "$SCRIPT_DIR/playlists/$playlist" ]; then
        python3 "$SCRIPT_DIR/channel-dj.py" --channel "$ch" --playlist "$SCRIPT_DIR/playlists/$playlist" --loop &
        PIDS="$PIDS $!"
        echo "  Started: $ch (playlist: $playlist)"
    fi
}

# YouTube search channels (loop search results)
start_search() {
    local ch="$1"
    local query="$2"
    python3 "$SCRIPT_DIR/channel-dj.py" --channel "$ch" --search "$query" --loop &
    PIDS="$PIDS $!"
    echo "  Started: $ch (search: $query)"
}

# Artist channels
start_channel "avicii" "avicii.txt"
start_channel "fkj" "fkj.txt"
start_channel "sunset-chill" "sunset-chill.txt"

# Genre channels (search-based)
start_search "jazz" "jazz lounge music live"
start_search "ambient" "ambient music for focus 2024"
start_search "lo-fi" "lofi hip hop radio beats"
start_search "classical" "classical music orchestra live"
start_search "electronic" "electronic music mix 2024"

# DJ Mix channels
start_search "solomun-live" "Solomun live DJ set 2024"
start_search "tale-of-us" "Tale Of Us Afterlife mix"
start_search "amelie-lens" "Amelie Lens techno set"
start_search "ben-bohmer" "Ben Böhmer live set"
start_search "carl-cox" "Carl Cox DJ set 2024"

echo ""
echo "Running $(echo $PIDS | wc -w | tr -d ' ') channels"
echo "PIDs: $PIDS"
echo "$PIDS" > "$PID_FILE"
echo "Stop: kill \$(cat $PID_FILE)"
echo ""

# Wait for all
wait
