#!/usr/bin/env python3
"""
Koe Soluna STAGE Server
Runs on Raspberry Pi 5. Provides:
1. Audio streaming (mic/line in → UDP multicast)
2. LED control (WebSocket → UDP multicast)
3. Web dashboard API
4. Smartphone WebSocket for visual sync
"""

import asyncio
import json
import socket
import struct
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

try:
    import websockets
except ImportError:
    print("pip3 install websockets")
    exit(1)

# Config
AUDIO_MULTICAST = ("239.42.42.1", 4242)
LED_MULTICAST = ("239.42.42.1", 4243)
WS_PORT = 8765
HTTP_PORT = 8080

# State
state = {
    "mode": "idle",
    "pattern": "off",
    "color": [0, 0, 0],
    "speed": 128,
    "intensity": 200,
    "bpm": 0,
    "devices": [],
    "uptime": 0,
}

start_time = time.time()

# UDP socket for LED commands
led_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
led_sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

PATTERNS = {"off": 0, "solid": 1, "pulse": 2, "rainbow": 3,
            "wave_lr": 4, "wave_rl": 5, "strobe": 6, "breathe": 7}

def send_led(pattern, r=0, g=0, b=0, speed=128, intensity=200):
    pat_id = PATTERNS.get(pattern, 0)
    packet = b'\x4c\x45' + struct.pack('<IBBBBB', 0, pat_id, r, g, b, speed) + bytes([intensity])
    led_sock.sendto(packet, LED_MULTICAST)
    state["pattern"] = pattern
    state["color"] = [r, g, b]
    state["speed"] = speed
    state["intensity"] = intensity

# WebSocket handler
connected_clients = set()

async def ws_handler(websocket):
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            try:
                cmd = json.loads(message)
                action = cmd.get("action", "")

                if action == "led":
                    send_led(
                        cmd.get("pattern", "off"),
                        cmd.get("r", 0),
                        cmd.get("g", 0),
                        cmd.get("b", 0),
                        cmd.get("speed", 128),
                        cmd.get("intensity", 200),
                    )
                    # Broadcast to all connected smartphones
                    await broadcast(json.dumps({"type": "led", **cmd}))

                elif action == "get_state":
                    state["uptime"] = int(time.time() - start_time)
                    await websocket.send(json.dumps({"type": "state", **state}))

                elif action == "bpm":
                    state["bpm"] = cmd.get("bpm", 0)

            except json.JSONDecodeError:
                pass
    finally:
        connected_clients.discard(websocket)

async def broadcast(message):
    if connected_clients:
        await asyncio.gather(
            *[c.send(message) for c in connected_clients],
            return_exceptions=True
        )

# Status broadcast every 2 seconds
async def status_loop():
    while True:
        state["uptime"] = int(time.time() - start_time)
        state["devices"] = len(connected_clients)
        await broadcast(json.dumps({"type": "status", **state}))
        await asyncio.sleep(2)

# HTTP server for static files (dashboard)
class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="/opt/koe-stage/web", **kwargs)

    def log_message(self, format, *args):
        pass  # Quiet

def run_http():
    import os
    os.makedirs("/opt/koe-stage/web", exist_ok=True)
    server = HTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    print(f"HTTP: http://0.0.0.0:{HTTP_PORT}")
    server.serve_forever()

async def main():
    print("=== Koe Soluna STAGE Server ===")
    print(f"WebSocket: ws://0.0.0.0:{WS_PORT}")
    print(f"HTTP:      http://0.0.0.0:{HTTP_PORT}")
    print(f"LED UDP:   {LED_MULTICAST[0]}:{LED_MULTICAST[1]}")
    print()

    # HTTP in background thread
    http_thread = threading.Thread(target=run_http, daemon=True)
    http_thread.start()

    # WebSocket server
    async with websockets.serve(ws_handler, "0.0.0.0", WS_PORT):
        await status_loop()

if __name__ == "__main__":
    asyncio.run(main())
