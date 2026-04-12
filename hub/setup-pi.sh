#!/bin/bash
# Koe Hub — Raspberry Pi CM5 Setup
# Run on a fresh Raspbian installation:
#   curl -sSL https://koe.live/setup-pi.sh | bash

set -e
echo "=== Koe Hub Setup for Raspberry Pi CM5 ==="

# 1. Install Rust
if ! command -v cargo &>/dev/null; then
    echo "[1/6] Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source ~/.cargo/env
else
    echo "[1/6] Rust already installed ($(rustc --version))"
fi

# 2. Install dependencies
echo "[2/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq build-essential pkg-config libasound2-dev

# 3. Clone repo
echo "[3/6] Cloning Koe device repo..."
if [ ! -d ~/koe-device ]; then
    git clone https://github.com/yukihamada/koe-device.git ~/koe-device
else
    echo "     Repo already exists, pulling latest..."
    cd ~/koe-device && git pull --ff-only
fi
cd ~/koe-device/hub

# 4. Build
echo "[4/6] Building Koe Hub (this takes ~5 minutes on CM5)..."
cargo build --release

# 5. Create systemd service
echo "[5/6] Creating systemd service..."
CURRENT_USER=$(whoami)
sudo tee /etc/systemd/system/koe-hub.service > /dev/null << EOF
[Unit]
Description=Koe Hub Audio Mixer
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=/home/${CURRENT_USER}/koe-device/hub
ExecStart=/home/${CURRENT_USER}/koe-device/hub/target/release/koe-hub
Restart=always
RestartSec=5
Environment=RUST_LOG=info

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable koe-hub
sudo systemctl start koe-hub

# 6. Print status
echo "[6/6] Done!"
echo ""
echo "Koe Hub is running!"
echo "  Dashboard: http://$(hostname -I | awk '{print $1}'):3000"
echo "  Status:    sudo systemctl status koe-hub"
echo "  Logs:      sudo journalctl -u koe-hub -f"
