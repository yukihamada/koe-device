# CLAUDE.md — Koe Device

## プロジェクト概要
ESP32-S3 + Raspberry Pi CM5 の音声デバイスエコシステム。
- **koe.live** — 製品サイト + OTA APIサーバー (Fly.io `koe-live`, nrt)
- **firmware/** — ESP32-S3 Rust ファームウェア (Koe + Soluna + Pro)
- **firmware/src/pro.rs** — Koe Pro 低遅延オーディオ送信機 (UWB同期)
- **firmware/src/uwb.rs** — DW3000 UWBクロック同期
- **firmware/coin-lite/** — COIN Lite (ESP32-C3) 受信専用ファーム
- **hub/** — Koe Hub ソフトウェア (Pi CM5, 8ch mixer, EQ/reverb/comp, SRT/RTMP)
- **server/** — koe.live の Axum サーバー (静的配信 + OTA API + WebRTC signaling)

## Webページ (docs/)
| ページ | URL | 説明 |
|--------|-----|------|
| index.html | koe.live/ | ランディングページ |
| pro.html | koe.live/pro | Koe Pro + Hub 製品ページ |
| busker.html | koe.live/busker | ストリート演奏: 観客のスマホがスピーカーになる + 投げ銭 |
| classroom.html | koe.live/classroom | 先生/ガイドの声を全員のイヤホンへ、アプリ不要 |
| moji.html | koe.live/moji | リアルタイム音声翻訳 (JA/EN/ZH/KO/ES/FR) |
| soluna-os.html | koe.live/soluna-os | フェスティバル管理ダッシュボード |
| app/ | koe.live/app | P2P Webアプリ (Soluna)

## OTAファームウェア更新

### デプロイ手順（1コマンド）
```bash
cd firmware
./deploy-ota.sh --release --token $KOE_ADMIN_TOKEN
# または環境変数で:
export KOE_OTA_TOKEN=<token>
./deploy-ota.sh --release
```

### deploy-ota.sh がやること
1. `cargo build --release`
2. `espflash save-image --chip esp32s3 --merge` → `latest.bin` 生成
3. `curl POST https://koe.live/api/v1/device/firmware/upload?version=X.Y.Z&token=...`
4. デバイスは**次回起動時**に自動取得・書き込み・再起動

### OTA APIエンドポイント
| Method | URL | 説明 |
|--------|-----|------|
| GET | `/api/v1/device/firmware?version=X.Y.Z&device_id=koe-xxx` | 204=最新 / 200+binary=更新あり |
| POST | `/api/v1/device/firmware/upload?version=X.Y.Z&token=TOKEN` | バイナリアップロード (admin) |

### デバイス側の動作フロー
```
WiFi接続 → SNTP同期 → OTA check (koe.live)
  → 204: そのまま起動
  → 200: バイナリDL → esp_ota_write → esp_ota_set_boot_partition → 再起動
```

### 設定 (NVS) は OTA で絶対に消えない
- OTA は `ota_0`/`ota_1` パーティション (0x10000, 0x200000) にしか書き込まない
- WiFi設定・APIキー・デバイスID は NVS パーティション (0x9000) → **保持される**
- NVSが消えるのは factory_reset (btn長押し5秒) のみ

### Admin Token
```bash
# Fly.io secretsに保存済み
fly secrets list -a koe-live   # KOE_ADMIN_TOKEN を確認
fly ssh console -a koe-live --command "printenv KOE_ADMIN_TOKEN"  # 値を取得
```

## koe-live サーバーデプロイ
```bash
cd /Users/yuki/workspace/koe-device
fly deploy --remote-only -a koe-live
```

### 構成
- `server/` — Axum サーバー (Rust)
- `docs/` — 静的HTML (製品サイト)
- `/data/koe-firmware/` — Fly.io volume にファームウェア保存

## ファームウェアビルド
```bash
cd firmware
cargo build          # debug
cargo build --release  # release (OTA用)
```

## ボタン操作
| btn | 動作 |
|-----|------|
| 1 (short) | 録音ON/OFF |
| 2 | モード切替 (Koe ↔ Soluna) |
| 4 (double-tap) | ピッチシフトサイクル (0→+5→+12→-5→0半音) |
| 5 (long) | Factory reset (NVS全消去 + 再起動) |
| 6 | ボリューム↑ |
| 7 | ボリューム↓ |

## 4つの特殊機能
1. **ピッチシフター** — double-tap でサイクル、ビープ音でフィードバック
2. **拍手検出→LED閃光** — 拍手で全Solunaデバイスが同期フラッシュ (UDP multicast)
3. **自動ポジショニング** — ハッシュ順で左→右の送信遅延 (0〜8ms)、波エフェクト
4. **ウェイクワード** — ダブル拍手 (600ms以内) で録音強制ON + 黄色フラッシュ

## ピン配置 (ESP32-S3)
| 用途 | GPIO |
|------|------|
| Mic I2S BCLK | 14 |
| Mic I2S WS | 15 |
| Mic I2S DIN | 32 |
| Spk I2S BCLK | 26 |
| Spk I2S DOUT | 25 |
| Spk I2S WS | 27 |
| Spk Amp SD | 21 |
| Button | 33 |
| LED | 2 |
