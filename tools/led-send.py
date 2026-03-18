#!/usr/bin/env python3
"""
LED command sender for Koe STAGE → CROWD devices.

Sends 12-byte LED control packets via UDP multicast.

Packet format:
  [0:2]  Magic "LE" (0x4C 0x45)
  [2:6]  Timestamp (uint32 big-endian, 0 = immediate)
  [6]    Pattern (0-7)
  [7]    Red   (0-255)
  [8]    Green (0-255)
  [9]    Blue  (0-255)
  [10]   Speed (0-255)
  [11]   Intensity (0-255)

Usage:
  python3 led-send.py solid 255 0 0          # All red
  python3 led-send.py rainbow --speed 128    # Rainbow at medium speed
  python3 led-send.py pulse 0 0 255 --bpm 120  # Blue pulse at 120 BPM
  python3 led-send.py wave_lr 255 128 0      # Orange wave left to right
  python3 led-send.py strobe 255 255 255     # White strobe
  python3 led-send.py off                    # All off
  python3 led-send.py breathe 0 255 128      # Teal breathe
"""

import argparse
import socket
import struct
import time
import sys

MULTICAST_GROUP = "239.42.42.1"
MULTICAST_PORT = 4243

PATTERNS = {
    "off":      0,
    "solid":    1,
    "pulse":    2,
    "rainbow":  3,
    "wave_lr":  4,
    "wave_rl":  5,
    "strobe":   6,
    "breathe":  7,
}

ANSI_RESET = "\033[0m"


def rgb_ansi(r: int, g: int, b: int) -> str:
    """Return ANSI escape for 24-bit foreground color."""
    return f"\033[38;2;{r};{g};{b}m"


def build_packet(pattern: int, r: int, g: int, b: int,
                 speed: int, intensity: int, timestamp: int = 0) -> bytes:
    """Build 12-byte LED control packet."""
    return struct.pack(">2sIBBBBBB",
                       b"LE",
                       timestamp,
                       pattern,
                       r, g, b,
                       speed,
                       intensity)


def send_packet(packet: bytes) -> None:
    """Send packet via UDP multicast."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.sendto(packet, (MULTICAST_GROUP, MULTICAST_PORT))
    sock.close()


def bpm_to_speed(bpm: int) -> int:
    """Convert BPM to speed byte (0-255). 300 BPM = 255."""
    return min(255, int(bpm * 255 / 300))


def main():
    parser = argparse.ArgumentParser(
        description="Send LED commands to CROWD devices via UDP multicast.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Patterns:
  off       All LEDs off
  solid     Solid color
  pulse     Pulsing color
  rainbow   Rainbow cycle (color args ignored)
  wave_lr   Wave sweep left to right
  wave_rl   Wave sweep right to left
  strobe    Strobe flash
  breathe   Slow breathe effect""")

    parser.add_argument("pattern", choices=PATTERNS.keys(),
                        help="LED pattern name")
    parser.add_argument("r", nargs="?", type=int, default=0,
                        help="Red (0-255)")
    parser.add_argument("g", nargs="?", type=int, default=0,
                        help="Green (0-255)")
    parser.add_argument("b", nargs="?", type=int, default=0,
                        help="Blue (0-255)")
    parser.add_argument("--speed", type=int, default=128,
                        help="Speed (0-255, default 128)")
    parser.add_argument("--intensity", type=int, default=200,
                        help="Intensity (0-255, default 200)")
    parser.add_argument("--bpm", type=int, default=None,
                        help="Set speed from BPM (overrides --speed)")
    parser.add_argument("--loop", action="store_true",
                        help="Repeat command every 100ms (Ctrl+C to stop)")

    args = parser.parse_args()

    # Clamp color values
    r = max(0, min(255, args.r))
    g = max(0, min(255, args.g))
    b = max(0, min(255, args.b))

    # Speed: BPM overrides --speed
    speed = bpm_to_speed(args.bpm) if args.bpm is not None else args.speed
    speed = max(0, min(255, speed))

    intensity = max(0, min(255, args.intensity))
    pattern_id = PATTERNS[args.pattern]

    packet = build_packet(pattern_id, r, g, b, speed, intensity)

    # Display info
    color_preview = rgb_ansi(r, g, b)
    print(f"LED >> {args.pattern} "
          f"{color_preview}({r},{g},{b}){ANSI_RESET} "
          f"speed={speed} intensity={intensity} "
          f"-> {MULTICAST_GROUP}:{MULTICAST_PORT}")
    print(f"     packet: {packet.hex()}")

    if args.loop:
        print("     looping every 100ms (Ctrl+C to stop)")
        try:
            while True:
                send_packet(packet)
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n     stopped.")
    else:
        send_packet(packet)
        print("     sent.")


if __name__ == "__main__":
    main()
