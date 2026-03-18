#!/usr/bin/env python3
"""
Soluna マルチキャスト OTA 配信ツール (Pi5 / STAGE サーバー用)

ファームウェアバイナリを1024Bチャンクに分割し、
UDPマルチキャストでカルーセル配信する。

使い方:
  python3 ota-broadcast.py firmware.bin [--loops 5] [--delay 2]

1台アップデートするのも1万台アップデートするのも帯域は同じ。
"""

import socket
import struct
import sys
import time
import hashlib

MULTICAST_ADDR = "239.42.42.1"
MULTICAST_PORT = 4242
CHUNK_SIZE = 1024
MAGIC = b"\x53\x4c"  # "SL"
FLAG_OTA = 0x20
OTA_CHANNEL = 0xFFFFFFFF
SENDER_HASH = 0xDEADBEEF  # Pi5のID

def fnv1a(data: bytes) -> int:
    h = 0x811c9dc5
    for b in data:
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def build_ota_packet(chunk_idx: int, total_chunks: int, fw_hash: int, data: bytes) -> bytes:
    # 19B Solunaヘッダ
    header = MAGIC
    header += struct.pack("<I", SENDER_HASH)     # device_hash
    header += struct.pack("<I", chunk_idx)        # seq (= chunk index)
    header += struct.pack("<I", OTA_CHANNEL)      # channel = 0xFFFFFFFF
    header += struct.pack("<I", total_chunks)     # ntp_ms field reused as total_chunks
    header += struct.pack("B", FLAG_OTA)          # flags

    # OTA拡張ヘッダ (12B)
    ext = struct.pack("<I", chunk_idx)
    ext += struct.pack("<I", total_chunks)
    ext += struct.pack("<I", fw_hash)

    return header + ext + data

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <firmware.bin> [--loops N] [--delay MS]")
        sys.exit(1)

    fw_path = sys.argv[1]
    loops = 5
    delay_ms = 2  # パケット間隔 (ms)

    for i, arg in enumerate(sys.argv[2:], 2):
        if arg == "--loops" and i + 1 < len(sys.argv):
            loops = int(sys.argv[i + 1])
        if arg == "--delay" and i + 1 < len(sys.argv):
            delay_ms = int(sys.argv[i + 1])

    # ファームウェア読み込み
    with open(fw_path, "rb") as f:
        firmware = f.read()

    total_size = len(firmware)
    total_chunks = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE
    fw_hash = fnv1a(firmware)

    print(f"=== Soluna Multicast OTA ===")
    print(f"  Firmware: {fw_path}")
    print(f"  Size: {total_size:,} bytes ({total_chunks} chunks)")
    print(f"  Hash: {fw_hash:#010x}")
    print(f"  Loops: {loops}")
    print(f"  Delay: {delay_ms}ms per packet")
    print(f"  Multicast: {MULTICAST_ADDR}:{MULTICAST_PORT}")
    print()

    # UDPソケット
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)

    # カルーセル配信
    for loop_num in range(1, loops + 1):
        print(f"Loop {loop_num}/{loops}...")

        for i in range(total_chunks):
            offset = i * CHUNK_SIZE
            chunk = firmware[offset:offset + CHUNK_SIZE]

            packet = build_ota_packet(i, total_chunks, fw_hash, chunk)
            sock.sendto(packet, (MULTICAST_ADDR, MULTICAST_PORT))

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

        print(f"  Sent {total_chunks} chunks ({total_size:,} bytes)")

        if loop_num < loops:
            # ループ間に少し間を空ける
            time.sleep(1.0)

    print()
    print(f"Done! {loops} loops × {total_chunks} chunks = {loops * total_chunks} packets sent")
    print(f"All devices on {MULTICAST_ADDR} should now have the firmware.")

    sock.close()

if __name__ == "__main__":
    main()
