#!/bin/bash
# Koe Hub — Raspberry Pi setup (one-liner installer)
#
# Run on a fresh Raspberry Pi OS (Bullseye / Bookworm):
#   curl -sSL https://koe.live/setup-pi.sh | bash
#
# What this does:
#   1. Installs C build tools + PortAudio + libcurl
#   2. Clones / updates the koe-device repo
#   3. Compiles hub/koe-amp.c  (takes ~5 seconds on Pi 4)
#   4. Installs binary + systemd service → auto-starts on every boot
#   5. Prompts for device ID if not already configured
#
# After install:
#   koe.live/room shows live waveform from this Pi's mic
#   journalctl -u koe-amp -f   — live logs
#   sudo systemctl stop koe-amp — stop

set -euo pipefail

RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GRN}[koe]${NC} $*"; }
warn()  { echo -e "${YLW}[koe]${NC} $*"; }
error() { echo -e "${RED}[koe]${NC} $*" >&2; exit 1; }

# ── 1. System deps ────────────────────────────────────────────────────────────
info "Installing system dependencies…"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential \
    git \
    pkg-config \
    libportaudio2 \
    portaudio19-dev \
    libcurl4-openssl-dev

# ── 2. Clone / update repo ────────────────────────────────────────────────────
REPO_DIR="$HOME/koe-device"
if [ -d "$REPO_DIR/.git" ]; then
    info "Updating koe-device repo…"
    git -C "$REPO_DIR" pull --ff-only
else
    info "Cloning koe-device repo…"
    git clone https://github.com/yukihamada/koe-device.git "$REPO_DIR"
fi

# ── 3. Compile koe-amp.c ─────────────────────────────────────────────────────
info "Compiling koe-amp.c…"
make -C "$REPO_DIR/hub" clean all

# ── 4. Configure device ───────────────────────────────────────────────────────
sudo mkdir -p /etc/koe

if [ ! -f /etc/koe/device_id ]; then
    DEFAULT_ID="koe-amp-$(hostname | tr -dc 'a-z0-9' | head -c8)"
    read -rp "Device ID [$DEFAULT_ID]: " input_id
    DEVICE_ID="${input_id:-$DEFAULT_ID}"
    echo "$DEVICE_ID" | sudo tee /etc/koe/device_id > /dev/null
fi

if [ ! -f /etc/koe/room ]; then
    read -rp "Room name [main]: " input_room
    ROOM="${input_room:-main}"
    echo "$ROOM" | sudo tee /etc/koe/room > /dev/null
fi

if [ ! -f /etc/koe/server ]; then
    echo "https://koe.live" | sudo tee /etc/koe/server > /dev/null
fi

# ── 5. Install binary + service ───────────────────────────────────────────────
info "Installing koe-amp service…"
sudo make -C "$REPO_DIR/hub" install

# ── 6. Summary ────────────────────────────────────────────────────────────────
DEVICE_ID=$(cat /etc/koe/device_id)
ROOM=$(cat /etc/koe/room)

echo ""
echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GRN}  Koe Amp is running${NC}"
echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Device ID : $DEVICE_ID"
echo "  Room      : $ROOM"
echo "  Server    : $(cat /etc/koe/server)"
echo ""
echo "  Live room : https://koe.live/room"
echo ""
echo "  Logs      : journalctl -u koe-amp -f"
echo "  Status    : systemctl status koe-amp"
echo "  Restart   : sudo systemctl restart koe-amp"
echo ""
echo "  Plug in your mic and open koe.live/room — done."
echo ""
