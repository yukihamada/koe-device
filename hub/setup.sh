#!/bin/bash
# setup.sh — One-shot Koe Amp setup for Raspberry Pi OS Lite (64-bit)
#
# Run as root on a freshly imaged Pi 5 that already has network access:
#   sudo bash setup.sh
#
# What this does:
#   1. Installs Python dependencies (sounddevice, numpy, requests)
#   2. Writes /etc/koe/device_id and /etc/koe/room
#   3. Installs koe-amp.py to /usr/local/bin
#   4. Creates and enables koe-amp.service (systemd)
#
# To customise device_id / room, edit the variables below before running,
# or set them as environment variables:
#   DEVICE_ID=koe-amp-hawaii-02 ROOM=rehearsal_room sudo bash setup.sh

set -euo pipefail

DEVICE_ID="${DEVICE_ID:-koe-amp-hawaii-01}"
ROOM="${ROOM:-living_room}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOE_AMP_SRC="${SCRIPT_DIR}/koe-amp.py"
KOE_AMP_DEST="/usr/local/bin/koe-amp.py"
SERVICE_FILE="/etc/systemd/system/koe-amp.service"

# ---------------------------------------------------------------------------
log() { echo "[koe-amp setup] $*"; }

require_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        echo "ERROR: run this script as root (sudo bash setup.sh)" >&2
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
install_packages() {
    log "updating package list..."
    apt-get update -qq

    log "installing python3, pip, portaudio..."
    apt-get install -y -qq \
        python3 \
        python3-pip \
        python3-numpy \
        libportaudio2 \
        portaudio19-dev

    log "installing Python packages..."
    pip3 install --quiet --break-system-packages sounddevice requests
}

# ---------------------------------------------------------------------------
# 2. Device identity
# ---------------------------------------------------------------------------
write_identity() {
    log "writing device identity..."
    mkdir -p /etc/koe
    printf '%s' "${DEVICE_ID}" > /etc/koe/device_id
    printf '%s' "${ROOM}"      > /etc/koe/room
    chmod 644 /etc/koe/device_id /etc/koe/room
    log "  device_id = ${DEVICE_ID}"
    log "  room      = ${ROOM}"
}

# ---------------------------------------------------------------------------
# 3. Install service script
# ---------------------------------------------------------------------------
install_script() {
    if [[ ! -f "${KOE_AMP_SRC}" ]]; then
        echo "ERROR: ${KOE_AMP_SRC} not found. Run setup.sh from the hub/ directory." >&2
        exit 1
    fi
    log "installing koe-amp.py → ${KOE_AMP_DEST}"
    cp "${KOE_AMP_SRC}" "${KOE_AMP_DEST}"
    chmod 755 "${KOE_AMP_DEST}"
}

# ---------------------------------------------------------------------------
# 4. systemd service
# ---------------------------------------------------------------------------
install_service() {
    log "writing systemd service ${SERVICE_FILE}..."
    cat > "${SERVICE_FILE}" << 'EOF'
[Unit]
Description=Koe Amp Recording Service
Documentation=https://koe.live
After=network-online.target sound.target
Wants=network-online.target

[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/koe-amp.py
Restart=always
RestartSec=5
User=root
StandardOutput=journal
StandardError=journal
SyslogIdentifier=koe-amp
# Give the audio subsystem a moment on boot before we try to open it
ExecStartPre=/bin/sleep 3

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable koe-amp
    systemctl restart koe-amp || true   # best-effort start; may fail if no mic yet
}

# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
require_root
install_packages
write_identity
install_script
install_service

log ""
log "Done!  Koe Amp installed as koe-amp.service"
log ""
log "  Status:  systemctl status koe-amp"
log "  Logs:    journalctl -u koe-amp -f"
log "  Restart: systemctl restart koe-amp"
log ""
log "Reboot recommended to confirm auto-start:"
log "  sudo reboot"
