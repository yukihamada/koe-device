#!/bin/bash
# Koe Soluna STAGE — Raspberry Pi 5 Setup Script
# Run on a fresh Raspberry Pi OS Lite 64-bit
set -e

echo "=== Koe Soluna STAGE Setup ==="
echo "Pi 5 + Intel BE200 (WiFi 7) + HiFiBerry DAC+ Pro"
echo ""

# System update
sudo apt update && sudo apt upgrade -y

# Audio: ALSA + PipeWire
sudo apt install -y pipewire pipewire-alsa pipewire-pulse wireplumber
# HiFiBerry DAC+ Pro overlay
echo "dtoverlay=hifiberry-dacplus" | sudo tee -a /boot/firmware/config.txt

# GPS: gpsd + chrony for NTP
sudo apt install -y gpsd gpsd-clients chrony pps-tools
# GPS config (serial on /dev/ttyAMA0 or USB)
cat << 'GPS' | sudo tee /etc/default/gpsd
DEVICES="/dev/ttyAMA0"
GPSD_OPTIONS="-n"
USBAUTO="true"
GPS

# PTP: linuxptp for IEEE 1588
sudo apt install -y linuxptp
cat << 'PTP' | sudo tee /etc/ptp4l.conf
[global]
clockClass 248
clockAccuracy 0xFE
tx_timestamp_timeout 10
[eth0]
PTP

# GStreamer for audio/video pipeline
sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly gstreamer1.0-alsa

# Python deps for Soluna controller
sudo apt install -y python3-pip python3-numpy python3-flask python3-websockets
pip3 install sounddevice --break-system-packages

# WiFi 7 (Intel BE200) — driver should be built-in on kernel 6.6+
# Verify with: iwconfig wlan1

# mDNS
sudo apt install -y avahi-daemon avahi-utils

# Open Lighting Architecture (for DMX/ArtNet)
sudo apt install -y ola

# Firewall: allow Soluna ports
sudo apt install -y ufw
sudo ufw allow 4242/udp  # Soluna audio
sudo ufw allow 4243/udp  # Soluna LED
sudo ufw allow 8080/tcp  # Web dashboard
sudo ufw allow 5353/udp  # mDNS
sudo ufw enable

# Create service directory
sudo mkdir -p /opt/koe-stage
sudo chown $USER:$USER /opt/koe-stage

# Copy tools
cp -r ../tools/* /opt/koe-stage/

echo ""
echo "=== Setup Complete ==="
echo "Reboot to apply HiFiBerry overlay: sudo reboot"
echo ""
echo "After reboot:"
echo "  1. Check audio: aplay -l (should show HiFiBerry)"
echo "  2. Check GPS:   gpsmon (should show satellites)"
echo "  3. Check WiFi:  iwconfig (should show BE200 on wlan1)"
echo "  4. Start Soluna: python3 /opt/koe-stage/guitar-stream.py"
echo "  5. Start LED:    python3 /opt/koe-stage/led-send.py rainbow"
