# CLAUDE.md — Koe Device

## プロジェクト概要
ESP32-S3 + Raspberry Pi CM5 の音声デバイスエコシステム。
- **koe.live** — 製品サイト + OTA APIサーバー (Fly.io `koe-live`, nrt)
- **firmware/** — ESP32-S3 Rust ファームウェア。bin名=`koe`・8モジュール
  (`main.rs` `audio.rs`(ADPCM) `es8388.rs`(コーデックI2C) `led.rs` `network.rs`(WiFi/NTP) `ota.rs` `power.rs`)
- **hub/** — Koe Hub ソフトウェア (Pi CM5, 8ch mixer, EQ/reverb/comp, SRT/RTMP)
- **server/** — koe.live の Axum サーバー (静的配信 + OTA API + WebRTC signaling)
- **stage/** `amp/` `stone/` — 筐体/フォームファクタ別アセット

> ⚠ かつて文書にあった `firmware/src/pro.rs` / `uwb.rs` / `firmware/coin-lite/` は
> **現コードには存在しない**（UWB同期・Pro送信機・C3受信専用ファームは未実装）。

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

## 動作モード（現状）
NVS読み込みは `power.rs::DeviceMode::load` が **TODO（未実装）**で、実際は
**コンパイル時フィーチャー**で切替：
- 既定（feature無し）= **COIN**: 双方向。Mic→ADPCM→UDP `239.42.42.1:4242` 送信 + 受信再生
- `--features guide` = **GUIDE**: 受信専用・低消費電力（イヤホン向け）
- `--features low_latency` = 32サンプル/パケット + raw PCM16（〜8ms）

## ボタン操作（実装は1ボタンのみ）
| btn (GPIO33) | 動作 |
|-----|------|
| 押すたび | 録音ON/OFF トグル（COINモードのTXのみ） |

> モード切替・ピッチシフト・factory reset・音量±・拍手検出・ウェイクワード等は
> **現ファームに未実装**（過去文書の記述は実体と不一致だった）。

## ピン配置 (ESP32-S3 / main.rs と一致)
| 用途 | GPIO |
|------|------|
| I2S BCLK（双方向・ES8388経由） | 14 |
| I2S WS | 15 |
| I2S DOUT（→DAC→スピーカー/ジャック） | 25 |
| I2S DIN（←ADC←マイク） | 32 |
| ES8388 I2C SDA | 18 |
| ES8388 I2C SCL | 23 |
| Amp/Jack SD（ミュート制御） | 21 |
| Button | 33 |
| LED (RGB) | 2 |

## 既知の未実装・要修正（コードと文書の整合のため記録）
- `power.rs::set_cpu_80mhz()` は構造体を作って捨てるだけで `esp_pm_configure` を**呼んでいない** → 80MHz化が効いていない
- `power.rs::enable_modem_sleep()` は定義のみで `main.rs` から**未呼出**
- `DeviceMode::load()` の NVS 読み込みが TODO（モードは再ビルドでしか変えられない）
