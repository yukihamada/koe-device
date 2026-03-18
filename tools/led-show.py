#!/usr/bin/env python3
"""
Automated LED light show for Koe STAGE → CROWD devices.

Reads a show definition (JSON) and sends LED commands at timed intervals.

Usage:
  python3 led-show.py              # Run built-in 30-second demo
  python3 led-show.py show.json    # Run custom show from file
"""

import json
import os
import socket
import struct
import sys
import time

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

# ANSI color helpers
ANSI_RESET = "\033[0m"
ANSI_DIM   = "\033[2m"
ANSI_BOLD  = "\033[1m"


def rgb_ansi_bg(r: int, g: int, b: int) -> str:
    return f"\033[48;2;{r};{g};{b}m"


def rgb_ansi_fg(r: int, g: int, b: int) -> str:
    return f"\033[38;2;{r};{g};{b}m"


def build_packet(pattern: int, r: int, g: int, b: int,
                 speed: int, intensity: int) -> bytes:
    return struct.pack(">2sIBBBBBB",
                       b"LE",
                       0,  # timestamp = 0 (immediate)
                       pattern,
                       r, g, b,
                       speed,
                       intensity)


def send_packet(sock: socket.socket, packet: bytes) -> None:
    sock.sendto(packet, (MULTICAST_GROUP, MULTICAST_PORT))


def format_time(t: float) -> str:
    m = int(t) // 60
    s = t - m * 60
    return f"{m}:{s:05.2f}"


BUILTIN_SHOW = {
    "bpm": 120,
    "steps": [
        {"time": 0,    "pattern": "solid",   "color": [255, 0, 0],     "speed": 128},
        {"time": 2.0,  "pattern": "pulse",   "color": [255, 0, 0],     "speed": 180},
        {"time": 4.0,  "pattern": "solid",   "color": [0, 0, 255],     "speed": 128},
        {"time": 5.0,  "pattern": "pulse",   "color": [0, 0, 255],     "speed": 200},
        {"time": 7.0,  "pattern": "rainbow",                           "speed": 255},
        {"time": 10.0, "pattern": "wave_lr", "color": [255, 128, 0],   "speed": 160},
        {"time": 13.0, "pattern": "wave_rl", "color": [0, 255, 128],   "speed": 160},
        {"time": 16.0, "pattern": "strobe",  "color": [255, 255, 255], "speed": 255},
        {"time": 18.0, "pattern": "breathe", "color": [128, 0, 255],   "speed": 80},
        {"time": 22.0, "pattern": "pulse",   "color": [255, 64, 0],    "speed": 220},
        {"time": 25.0, "pattern": "solid",   "color": [0, 255, 255],   "speed": 128},
        {"time": 28.0, "pattern": "breathe", "color": [255, 255, 255], "speed": 60},
        {"time": 30.0, "pattern": "off"},
    ]
}


def run_show(show: dict) -> None:
    steps = sorted(show["steps"], key=lambda s: s["time"])
    bpm = show.get("bpm", 120)

    if not steps:
        print("No steps in show.")
        return

    total_time = steps[-1]["time"]
    print(f"{ANSI_BOLD}LED SHOW{ANSI_RESET}  "
          f"BPM={bpm}  steps={len(steps)}  duration={format_time(total_time)}")
    print(f"{'':─<60}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

    start = time.time()

    try:
        for i, step in enumerate(steps):
            target = step["time"]
            now = time.time() - start
            wait = target - now
            if wait > 0:
                time.sleep(wait)

            pattern_name = step["pattern"]
            pattern_id = PATTERNS.get(pattern_name, 0)
            color = step.get("color", [0, 0, 0])
            r, g, b = color[0] if len(color) > 0 else 0, \
                       color[1] if len(color) > 1 else 0, \
                       color[2] if len(color) > 2 else 0
            speed = step.get("speed", 128)
            intensity = step.get("intensity", 200)

            packet = build_packet(pattern_id, r, g, b, speed, intensity)
            send_packet(sock, packet)

            # Terminal output with color
            color_block = f"{rgb_ansi_bg(r, g, b)}    {ANSI_RESET}"
            color_text = f"{rgb_ansi_fg(r, g, b)}({r},{g},{b}){ANSI_RESET}"
            elapsed = time.time() - start
            step_num = f"[{i+1:2d}/{len(steps)}]"

            print(f"  {ANSI_DIM}{format_time(elapsed)}{ANSI_RESET}  "
                  f"{step_num}  {color_block} "
                  f"{ANSI_BOLD}{pattern_name:8s}{ANSI_RESET}  "
                  f"{color_text}  spd={speed}")

    except KeyboardInterrupt:
        # Send off on interrupt
        off_packet = build_packet(0, 0, 0, 0, 0, 0)
        send_packet(sock, off_packet)
        print(f"\n{ANSI_DIM}  interrupted - LEDs off{ANSI_RESET}")
    finally:
        sock.close()

    print(f"{'':─<60}")
    print(f"{ANSI_BOLD}SHOW COMPLETE{ANSI_RESET}")


def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if not os.path.isfile(path):
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        with open(path, "r") as f:
            show = json.load(f)
        print(f"Loading show: {path}")
    else:
        show = BUILTIN_SHOW
        print("Running built-in demo show")

    run_show(show)


if __name__ == "__main__":
    main()
