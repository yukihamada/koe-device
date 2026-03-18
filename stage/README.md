# STAGE — Raspberry Pi 5 Server

Koe Soluna STAGE のサーバーソフトウェア。
Pi 5 + Intel BE200 (WiFi 7) + HiFiBerry DAC+ Pro で動作。

## セットアップ

```bash
# Pi 5 に Raspberry Pi OS Lite 64-bit をインストール後:
chmod +x setup.sh
./setup.sh
sudo reboot
```

## 起動

```bash
# Solunaサーバー (WebSocket + LED制御)
python3 soluna-server.py

# ギター配信 (Babyface Pro接続時)
python3 /opt/koe-stage/guitar-stream.py

# LEDコマンド送信
python3 /opt/koe-stage/led-send.py rainbow --speed 200

# ライトショー再生
python3 /opt/koe-stage/led-show.py demo-show.json
```

## ポート

| ポート | プロトコル | 用途 |
|--------|-----------|------|
| 4242/udp | Soluna音声 | UDP multicast 239.42.42.1 |
| 4243/udp | LED制御 | UDP multicast 239.42.42.1 |
| 8080/tcp | Web UI | ダッシュボード/LED制御画面 |
| 8765/tcp | WebSocket | スマホ連携/リアルタイム制御 |

## アーキテクチャ

```
soluna-server.py
├── WebSocket (8765) ← ブラウザ/スマホから制御
│   ├── LED制御コマンド受信
│   ├── ステータス配信 (2秒ごと)
│   └── スマホにビジュアル同期データ配信
├── UDP multicast (4243) → CROWDデバイスにLED制御送信
├── HTTP (8080) → 静的ファイル配信
└── guitar-stream.py → UDP multicast (4242) → 音声配信
```
