#!/usr/bin/env python3
"""
Guitar → Babyface Pro → Raspberry Pi → UDP multicast → Koe devices

Usage:
  pip3 install sounddevice numpy
  python3 guitar-stream.py

Prerequisites:
  - Babyface Pro (or any USB audio interface) connected via USB
  - Same WiFi/LAN as Koe devices
"""

import socket
import struct
import time
import sys

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    print("Install: pip3 install sounddevice numpy")
    sys.exit(1)

# Config
SAMPLE_RATE = 48000      # Babyface Pro native rate
BLOCK_SIZE = 128         # 128 samples = 2.7ms @ 48kHz
CHANNELS = 1             # Mono (guitar)
MULTICAST_GROUP = "239.42.42.1"
MULTICAST_PORT = 4242

# Soluna protocol
MAGIC = b'\x53\x4c'     # "SL"
seq = 0

def make_packet(audio_bytes):
    global seq
    ts = int(time.monotonic() * 1_000_000) & 0xFFFFFFFF
    header = MAGIC + struct.pack('<III', seq, 0, ts)
    seq = (seq + 1) & 0xFFFFFFFF
    return header + audio_bytes

def main():
    # List devices
    print("Audio devices:")
    print(sd.query_devices())
    print()

    # Find Babyface / RME
    devices = sd.query_devices()
    bf_idx = None
    for i, d in enumerate(devices):
        name = d['name'].lower()
        if 'babyface' in name or 'rme' in name:
            bf_idx = i
            print(f"Found: [{i}] {d['name']}")
            break

    if bf_idx is None:
        print("Babyface not found, using default input.")
        bf_idx = sd.default.device[0]

    # UDP multicast socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    dest = (MULTICAST_GROUP, MULTICAST_PORT)

    packets_sent = 0
    start_time = time.time()

    print(f"\nStreaming: [{bf_idx}] → {MULTICAST_GROUP}:{MULTICAST_PORT}")
    print(f"Rate: {SAMPLE_RATE}Hz | Block: {BLOCK_SIZE} ({BLOCK_SIZE/SAMPLE_RATE*1000:.1f}ms)")
    print("Ctrl+C to stop\n")

    def callback(indata, frames, time_info, status):
        nonlocal packets_sent
        if status:
            print(f"! {status}")
        pcm = (indata[:, 0] * 32767).astype(np.int16).tobytes()
        sock.sendto(make_packet(pcm), dest)
        packets_sent += 1
        if packets_sent % (SAMPLE_RATE // BLOCK_SIZE * 5) == 0:
            elapsed = time.time() - start_time
            print(f"  {packets_sent} pkt | {packets_sent/elapsed:.0f}/s | {elapsed:.0f}s")

    try:
        with sd.InputStream(
            device=bf_idx,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            blocksize=BLOCK_SIZE,
            dtype='float32',
            callback=callback,
            latency='low'
        ):
            print("Play your guitar!")
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"\nDone. {packets_sent} packets in {time.time()-start_time:.1f}s")
    finally:
        sock.close()

if __name__ == "__main__":
    main()
