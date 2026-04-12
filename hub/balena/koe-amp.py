#!/usr/bin/env python3
"""
Koe Amp — passive multi-track session recording service.

Receives Soluna UDP audio streams (port 4242) and streams/records
them, reporting status back to koe.live.
"""

import os
import time
import socket
import struct
import threading
import requests
import numpy as np

KOE_API_URL = os.environ.get("KOE_API_URL", "https://koe.live")
KOE_ROOM    = os.environ.get("KOE_ROOM", "living_room")
SOLUNA_PORT = 4242
SOLUNA_ADDR = "239.42.42.1"
CHUNK_SIZE  = 1024
SAMPLE_RATE = 48000


def receive_udp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", SOLUNA_PORT))

    mreq = struct.pack("4sL", socket.inet_aton(SOLUNA_ADDR), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    print(f"[koe-amp] Listening on {SOLUNA_ADDR}:{SOLUNA_PORT} (room={KOE_ROOM})")
    pkt_count = 0
    while True:
        data, addr = sock.recvfrom(65536)
        pkt_count += 1
        if pkt_count % 500 == 0:
            print(f"[koe-amp] {pkt_count} packets from {addr[0]}")


def heartbeat():
    while True:
        try:
            requests.post(
                f"{KOE_API_URL}/api/v1/device/heartbeat",
                json={"room": KOE_ROOM, "service": "koe-amp"},
                timeout=5,
            )
        except Exception as e:
            print(f"[koe-amp] heartbeat failed: {e}")
        time.sleep(30)


if __name__ == "__main__":
    threading.Thread(target=heartbeat, daemon=True).start()
    receive_udp()
