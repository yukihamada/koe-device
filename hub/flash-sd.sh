#!/bin/bash
# flash-sd.sh — Flash a pre-configured Koe Amp SD card image
#
# Usage:
#   sudo ./flash-sd.sh /dev/sdX DEVICE_ID ROOM WIFI_SSID WIFI_PASS
#
# Example:
#   sudo ./flash-sd.sh /dev/sda koe-amp-hawaii-01 living_room "Oki_Home" "wifi_pass_here"
#
# Requirements on the host machine (macOS or Linux):
#   macOS: brew install rpi-imager wget curl xz
#   Linux: apt-get install -y wget curl xz-utils
#
# What this does:
#   1. Downloads Raspberry Pi OS Lite 64-bit if not cached (~500 MB)
#   2. Writes the image to the target block device with dd
#   3. Mounts the boot partition and injects:
#        - wpa_supplicant.conf  (WiFi credentials)
#        - ssh                  (empty file enables SSH on first boot)
#        - firstrun.sh          (runs once at first boot via cmdline.txt)
#   4. firstrun.sh installs koe-amp service via setup.sh pulled from koe.live
#
# IMPORTANT: /dev/sdX is permanently overwritten. Double-check the device path.

set -euo pipefail

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
if [[ $# -lt 5 ]]; then
    echo "Usage: sudo $0 DEVICE DEVICE_ID ROOM WIFI_SSID WIFI_PASS"
    echo "  e.g: sudo $0 /dev/sda koe-amp-hawaii-01 living_room 'OkiHome' 's3cr3t'"
    exit 1
fi

TARGET_DEV="$1"
DEVICE_ID="$2"
ROOM="$3"
WIFI_SSID="$4"
WIFI_PASS="$5"

# ---------------------------------------------------------------------------
# Require root
# ---------------------------------------------------------------------------
if [[ "$(id -u)" -ne 0 ]]; then
    echo "ERROR: run as root (sudo $0 ...)" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
RPI_OS_URL="https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2024-11-19/2024-11-19-raspios-bookworm-arm64-lite.img.xz"
RPI_OS_XZ="$(basename "${RPI_OS_URL}")"
RPI_OS_IMG="${RPI_OS_XZ%.xz}"
CACHE_DIR="${HOME}/.cache/koe-sd-flash"
SETUP_SCRIPT_URL="https://raw.githubusercontent.com/yukihamada/koe-device/main/hub/setup.sh"
KOE_AMP_URL="https://raw.githubusercontent.com/yukihamada/koe-device/main/hub/koe-amp.py"

log() { echo "[flash-sd] $*"; }

# ---------------------------------------------------------------------------
# 1. Download image (cached)
# ---------------------------------------------------------------------------
mkdir -p "${CACHE_DIR}"
if [[ ! -f "${CACHE_DIR}/${RPI_OS_IMG}" ]]; then
    log "downloading RPi OS Lite 64-bit (~500 MB)..."
    wget -q --show-progress -O "${CACHE_DIR}/${RPI_OS_XZ}" "${RPI_OS_URL}"
    log "decompressing..."
    xz -d --keep "${CACHE_DIR}/${RPI_OS_XZ}"
    log "image ready: ${CACHE_DIR}/${RPI_OS_IMG}"
else
    log "cached image found: ${CACHE_DIR}/${RPI_OS_IMG}"
fi

# ---------------------------------------------------------------------------
# 2. Safety check — never overwrite macOS internal disk
# ---------------------------------------------------------------------------
if [[ "${TARGET_DEV}" == /dev/disk0 ]] || [[ "${TARGET_DEV}" == /dev/sda && "$(df / | tail -1 | awk '{print $1}')" == *"sda"* ]]; then
    echo "ERROR: '${TARGET_DEV}' looks like the system disk. Aborting." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 3. Flash
# ---------------------------------------------------------------------------
log "flashing ${CACHE_DIR}/${RPI_OS_IMG} → ${TARGET_DEV} ..."
log "THIS WILL ERASE ${TARGET_DEV}. Press Ctrl-C within 5 seconds to cancel."
sleep 5

# Detect OS for correct dd invocation
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS: use /dev/rdiskX for speed
    RAW_DEV="${TARGET_DEV/disk/rdisk}"
    diskutil unmountDisk "${TARGET_DEV}" 2>/dev/null || true
    dd if="${CACHE_DIR}/${RPI_OS_IMG}" of="${RAW_DEV}" bs=4m status=progress conv=sync
    diskutil mountDisk "${TARGET_DEV}"
    BOOT_MOUNT="$(diskutil info "${TARGET_DEV}s1" 2>/dev/null | awk '/Mount Point/ {print $3}')"
else
    # Linux
    dd if="${CACHE_DIR}/${RPI_OS_IMG}" of="${TARGET_DEV}" bs=4M status=progress conv=fsync
    sync
    # Re-read partition table
    partprobe "${TARGET_DEV}" 2>/dev/null || true
    sleep 2
    BOOT_PART="${TARGET_DEV}1"
    BOOT_MOUNT="/mnt/koe-boot-$$"
    mkdir -p "${BOOT_MOUNT}"
    mount "${BOOT_PART}" "${BOOT_MOUNT}"
fi

log "boot partition mounted at ${BOOT_MOUNT}"

# ---------------------------------------------------------------------------
# 4. Enable SSH
# ---------------------------------------------------------------------------
touch "${BOOT_MOUNT}/ssh"
log "SSH enabled"

# ---------------------------------------------------------------------------
# 5. WiFi credentials (wpa_supplicant.conf)
# ---------------------------------------------------------------------------
cat > "${BOOT_MOUNT}/wpa_supplicant.conf" << EOF
country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={
    ssid="${WIFI_SSID}"
    psk="${WIFI_PASS}"
    key_mgmt=WPA-PSK
}
EOF
log "WiFi config written (SSID=${WIFI_SSID})"

# ---------------------------------------------------------------------------
# 6. firstrun.sh — executed once at first boot
# ---------------------------------------------------------------------------
cat > "${BOOT_MOUNT}/firstrun.sh" << FIRSTRUN
#!/bin/bash
# Koe Amp first-boot provisioning
# Injected by flash-sd.sh — runs once via /etc/rc.local and then removes itself

set -euo pipefail
exec > /var/log/koe-firstrun.log 2>&1

echo "[firstrun] starting at \$(date)"

# Wait for network (up to 60 s)
for i in \$(seq 1 12); do
    if ping -c 1 -W 3 koe.live > /dev/null 2>&1; then
        echo "[firstrun] network up"
        break
    fi
    echo "[firstrun] waiting for network (\$i/12)..."
    sleep 5
done

# Download koe-amp.py and setup.sh from koe.live GitHub
mkdir -p /usr/local/share/koe
curl -sSL "${KOE_AMP_URL}"    -o /usr/local/share/koe/koe-amp.py
curl -sSL "${SETUP_SCRIPT_URL}" -o /usr/local/share/koe/setup.sh
chmod +x /usr/local/share/koe/setup.sh

# Run setup with device identity
export DEVICE_ID="${DEVICE_ID}"
export ROOM="${ROOM}"
bash /usr/local/share/koe/setup.sh

echo "[firstrun] done at \$(date)"

# Remove self from rc.local and delete this script
sed -i '/firstrun.sh/d' /etc/rc.local
rm -f /boot/firstrun.sh /boot/firmware/firstrun.sh
FIRSTRUN

chmod +x "${BOOT_MOUNT}/firstrun.sh"
log "firstrun.sh written (device_id=${DEVICE_ID} room=${ROOM})"

# ---------------------------------------------------------------------------
# 7. Hook firstrun.sh into /etc/rc.local via cmdline.txt
#    RPi OS boots with systemd but rc.local still runs if it exists.
#    We append a hook to cmdline.txt to call our script on first boot.
# ---------------------------------------------------------------------------
CMDLINE="${BOOT_MOUNT}/cmdline.txt"
if [[ -f "${CMDLINE}" ]]; then
    # Append systemd.run to execute firstrun.sh at first boot
    EXISTING="$(cat "${CMDLINE}")"
    # Only add if not already present
    if ! grep -q "firstrun.sh" "${CMDLINE}"; then
        printf '%s systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target\n' "${EXISTING}" > "${CMDLINE}"
        log "firstrun hook added to cmdline.txt"
    fi
fi

# ---------------------------------------------------------------------------
# 8. Unmount
# ---------------------------------------------------------------------------
sync
if [[ "$(uname)" == "Darwin" ]]; then
    diskutil unmountDisk "${TARGET_DEV}" 2>/dev/null || true
else
    umount "${BOOT_MOUNT}" 2>/dev/null || true
    rmdir  "${BOOT_MOUNT}" 2>/dev/null || true
fi

log ""
log "SD card ready!"
log "  Device ID : ${DEVICE_ID}"
log "  Room      : ${ROOM}"
log "  WiFi      : ${WIFI_SSID}"
log ""
log "Insert into Raspberry Pi 5 and apply power."
log "First boot will auto-install koe-amp service (~2 min)."
log "After first boot, confirm with:"
log "  curl https://koe.live/api/devices | python3 -m json.tool | grep ${DEVICE_ID}"
