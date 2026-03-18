#!/usr/bin/env python3
"""
Soluna Channel DJ — YouTube/ローカルファイルからチャンネルに音声配信

Usage:
  # YouTubeから再生
  python3 channel-dj.py --channel "avicii" --youtube "https://www.youtube.com/watch?v=IcrbM1l_BoI"

  # プレイリスト
  python3 channel-dj.py --channel "sunset-chill" --playlist sunset.txt

  # ローカルファイル
  python3 channel-dj.py --channel "jazz" --file ~/Music/jazz-mix.mp3

  # YouTube検索
  python3 channel-dj.py --channel "fkj" --search "FKJ live session"

Prerequisites:
  pip3 install yt-dlp sounddevice numpy
"""

import argparse
import socket
import struct
import time
import subprocess
import tempfile
import os
import sys
import signal

try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    print("pip3 install sounddevice numpy")
    sys.exit(1)

# Soluna protocol
MULTICAST_GROUP = "239.42.42.1"
MULTICAST_PORT = 4242
MAGIC = b'\x53\x4c'
SAMPLE_RATE = 48000
BLOCK_SIZE = 240  # 5ms @ 48kHz

seq = 0
running = True

def signal_handler(sig, frame):
    global running
    running = False
    print("\nStopping...")

signal.signal(signal.SIGINT, signal_handler)

def fnv1a(s):
    h = 0x811c9dc5
    for b in s.encode():
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

def make_packet(channel_hash, pcm_bytes):
    global seq
    ts = int(time.monotonic() * 1_000_000) & 0xFFFFFFFF
    header = MAGIC + struct.pack('<III', seq, channel_hash, ts)
    seq = (seq + 1) & 0xFFFFFFFF
    return header + pcm_bytes

def download_youtube(url):
    """yt-dlpでYouTubeから音声をダウンロード → wav"""
    print(f"Downloading: {url}")
    tmp = tempfile.mktemp(suffix='.wav')
    cmd = [
        'yt-dlp', '-x', '--audio-format', 'wav',
        '--audio-quality', '0',
        '-o', tmp.replace('.wav', '.%(ext)s'),
        '--no-playlist',
        url
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    # yt-dlp might add .wav or not
    if os.path.exists(tmp):
        return tmp
    # Find the downloaded file
    base = tmp.replace('.wav', '')
    for ext in ['.wav', '.opus', '.m4a', '.mp3']:
        if os.path.exists(base + ext):
            # Convert to wav
            wav_path = base + '.wav'
            subprocess.run(['ffmpeg', '-i', base + ext, '-ar', str(SAMPLE_RATE), '-ac', '1', wav_path],
                         capture_output=True)
            return wav_path
    raise FileNotFoundError(f"Download failed for {url}")

def search_youtube(query):
    """yt-dlpで検索してURLを返す"""
    cmd = ['yt-dlp', f'ytsearch1:{query}', '--get-url', '--get-title', '-f', 'bestaudio']
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    if len(lines) >= 2:
        title = lines[0]
        url = lines[1]
        print(f"Found: {title}")
        return url
    raise ValueError(f"No results for: {query}")

def load_audio(path):
    """wavファイルをf32 mono 48kHzで読み込み"""
    import wave
    # ffmpegで正規化
    tmp = tempfile.mktemp(suffix='.wav')
    subprocess.run(['ffmpeg', '-i', path, '-ar', str(SAMPLE_RATE), '-ac', '1',
                   '-acodec', 'pcm_f32le', tmp, '-y'], capture_output=True)

    with wave.open(tmp, 'r') as wf:
        frames = wf.readframes(wf.getnframes())
        samples = np.frombuffer(frames, dtype=np.float32)
    os.unlink(tmp)
    return samples

def stream_audio(samples, channel, sock, dest):
    """音声をSolunaプロトコルでストリーミング"""
    ch_hash = fnv1a(channel)
    total = len(samples)
    pos = 0
    start_time = time.time()

    print(f"Streaming to channel '{channel}' ({total/SAMPLE_RATE:.1f}s)")
    print(f"  Multicast: {MULTICAST_GROUP}:{MULTICAST_PORT}")
    print(f"  Channel hash: {ch_hash:#010x}")
    print()

    while pos < total and running:
        chunk = samples[pos:pos + BLOCK_SIZE]
        if len(chunk) < BLOCK_SIZE:
            chunk = np.pad(chunk, (0, BLOCK_SIZE - len(chunk)))

        # f32 → s16le
        pcm = (chunk * 32767).astype(np.int16).tobytes()
        packet = make_packet(ch_hash, pcm)
        sock.sendto(packet, dest)

        pos += BLOCK_SIZE

        # Real-time pacing
        elapsed = time.time() - start_time
        expected = pos / SAMPLE_RATE
        sleep_time = expected - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

        # Progress
        if pos % (SAMPLE_RATE * 10) == 0:
            pct = pos / total * 100
            mins = pos / SAMPLE_RATE / 60
            print(f"  {pct:.0f}% ({mins:.1f}min)")

    print(f"Done. {pos/SAMPLE_RATE:.1f}s streamed.")

def main():
    parser = argparse.ArgumentParser(description='Soluna Channel DJ')
    parser.add_argument('--channel', required=True, help='Channel name (e.g., avicii, sunset-chill)')
    parser.add_argument('--youtube', help='YouTube URL')
    parser.add_argument('--search', help='YouTube search query')
    parser.add_argument('--file', help='Local audio file')
    parser.add_argument('--playlist', help='Text file with YouTube URLs (one per line)')
    parser.add_argument('--loop', action='store_true', help='Loop playback')
    args = parser.parse_args()

    # UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    dest = (MULTICAST_GROUP, MULTICAST_PORT)

    urls = []
    if args.youtube:
        urls = [args.youtube]
    elif args.search:
        urls = [search_youtube(args.search)]
    elif args.playlist:
        with open(args.playlist) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    elif args.file:
        pass  # handled below

    print(f"=== Soluna Channel DJ ===")
    print(f"Channel: {args.channel}")
    print()

    while running:
        if args.file:
            samples = load_audio(args.file)
            stream_audio(samples, args.channel, sock, dest)
        else:
            for url in urls:
                if not running:
                    break
                try:
                    wav_path = download_youtube(url)
                    samples = load_audio(wav_path)
                    stream_audio(samples, args.channel, sock, dest)
                    os.unlink(wav_path)
                except Exception as e:
                    print(f"Error: {e}")
                    continue

        if not args.loop:
            break
        print("Looping...")

    sock.close()

if __name__ == "__main__":
    main()
