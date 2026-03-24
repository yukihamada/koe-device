# Koe/Soluna: 管理画面 + 全プラットフォーム対応

## 概要
1. 全デバイスの状態をリアルタイム可視化するダッシュボードを構築する
2. iPhone, Mac, ESP32, Raspberry Pi, Android, Windows が同一Solunaプロトコルで音声通信できるようにする

## 調査結果

### 既存コードベース

| プラットフォーム | パス | Soluna実装状況 |
|---|---|---|
| **ESP32** | `koe-device/firmware/src/soluna.rs` | 完全実装済み (ADPCM, Gossip, 音響測距, ChaCha20, Heartbeat, PLC, ジッタバッファ) |
| **iOS** | `Koe-swift/Koe-iOS/Sources/SolunaManager.swift` | 基本実装済み (送受信、LED受信、チャンネル切替)。但しADPCM未対応、SLヘッダ14B(ESP32は19B) |
| **macOS** | `Koe-swift/Sources/Koe/` | Soluna未実装。音声入力アプリのみ |
| **Windows** | `Koe-swift/Koe-windows/src/` | Soluna未実装。音声入力のみ |
| **Android** | なし | 未着手 |
| **Raspberry Pi** | `koe-device/stage/soluna-server.py` | Python STAGE Server (LED制御, WebSocket, HTTP) |
| **サイト** | `Koe-swift/site/` | axum Rust server (koe.live, 分析のみ) |

### プロトコル差異（重要な問題）

ESP32とiOSで**パケットフォーマットが不一致**:
- **ESP32 (soluna.rs)**: 19Bヘッダ `[magic 2B][device_id 4B][seq 4B][channel 4B][ntp_ms 4B][flags 1B][ADPCM audio]`
- **iOS (SolunaManager.swift)**: 14Bヘッダ `[magic 2B][seq 4B][channel 4B][ts 4B][raw PCM audio]` — device_idもflagsもない

両方ともマジック `0x53 0x4C` ("SL") を使用、マルチキャスト `239.42.42.1:4242`。
iOSはさらに `239.69.0.1:5004` (OSTP) も参照している形跡があるが、実際の送受信は `4242` ポート。

### 既存インフラ
- **koe.live**: Fly.io (`koe-live` app, nrt region, shared-cpu-1x, 256MB)
- 現在は nginx で docs/ を配信するだけ
- **Koe-swift/site/**: axum サーバー (koe.elio.love 向け、分析機能あり)
- **STAGE Server**: Raspberry Pi用 Python WebSocket + HTTP サーバー

### ドメイン計画 (DOMAIN_PLAN.md)
- `koe.live/dashboard` — 管理画面デモ
- `api.koe.live` — デバイスAPI (将来)

---

## アーキテクチャ設計

```
                        ┌──────────────────────┐
                        │    koe.live (Fly.io)  │
                        │    Rust axum server   │
                        │                       │
                        │  /dashboard  (SPA)    │◄── Mac/iPhone ブラウザ
                        │  /api/v1/status       │◄── デバイスが定期POST
                        │  /api/v1/relay        │◄── WAN音声リレー (WebSocket)
                        │  /api/v1/channels     │◄── チャンネル一覧
                        └──────────┬────────────┘
                                   │ WebSocket
                    ┌──────────────┼──────────────┐
                    ▼              ▼               ▼
              ┌──────────┐  ┌──────────┐   ┌──────────┐
              │  ESP32   │  │  iPhone  │   │   Mac    │
              │  (Rust)  │  │  (Swift) │   │  (Swift) │
              └────┬─────┘  └────┬─────┘   └────┬─────┘
                   │             │              │
                   └──── LAN UDP Multicast ─────┘
                        239.42.42.1:4242
                        (同一WiFi内は直接P2P)
```

### 設計方針
1. **サーバー (koe.live)**: ダッシュボードHTML + デバイスステータスAPI + WANリレー
2. **ダッシュボード**: サーバーサイドHTML + WebSocket でリアルタイム更新。SPA不要、シンプルに。
3. **プロトコル統一**: ESP32の19Bヘッダを正とし、iOS/Mac/Windows/Android全て合わせる
4. **LAN優先**: 同一WiFi内はUDPマルチキャスト直接。WAN時のみリレーサーバー経由

---

## 要件1: 管理画面 (ダッシュボード)

### 機能一覧

| 機能 | 優先度 | 説明 |
|------|--------|------|
| デバイス一覧 | P0 | 全接続デバイスのリスト (ID, 種別, チャンネル, 最終通信) |
| リアルタイム状態 | P0 | ピア数、チャンネル、音声レベル (WebSocket push) |
| チャンネルマップ | P1 | どのチャンネルに何台いるか可視化 |
| 距離マップ | P1 | 音響測距の結果を2D可視化 |
| 音声レベルメーター | P1 | 各デバイスの入出力レベル |
| LED制御パネル | P2 | パターン/色/速度をブラウザから送信 |
| 設定変更 | P2 | チャンネル切替、音量変更をリモートで |
| ログビューア | P3 | デバイスログのストリーミング表示 |

### 技術選定
- **サーバー**: Rust axum (既存 `Koe-swift/site/` を拡張 or 新規)
- **フロントエンド**: 単一HTML + vanilla JS + WebSocket。React不要。
- **データ永続化**: インメモリ (再起動で消えてOK)。将来的にSQLiteも可。
- **リアルタイム**: WebSocket (axum の `ws` 機能)
- **デプロイ**: Fly.io `koe-live` app

理由: KISSの原則。既存の `koe-site` が axum + include_str! パターンなので踏襲。
フロントエンドフレームワークは不要 — WebSocket + DOM操作で十分。

---

## 要件2: 全プラットフォーム対応

### プロトコル統一仕様 (Soluna Protocol v2)

```
パケットフォーマット (19 bytes header + audio):
┌───────┬───────────┬─────┬─────────┬────────┬───────┬──────────┐
│ magic │ device_id │ seq │ channel │ ntp_ms │ flags │ audio    │
│ 2B    │ 4B        │ 4B  │ 4B      │ 4B     │ 1B    │ variable │
└───────┴───────────┴─────┴─────────┴────────┴───────┴──────────┘
magic: 0x53 0x4C ("SL")
flags: 0x01=ADPCM, 0x02=Encrypted, 0x04=Heartbeat, 0x08=Chirp, 0x10=Gossip

マルチキャスト: 239.42.42.1:4242 (音声) / 239.42.42.1:4243 (LED)
サンプルレート: 16kHz mono
コーデック: IMA-ADPCM (4:1圧縮) — flagsで指定
暗号化: ChaCha20 (チャンネル名からキー派生) — flagsで指定
ピア発見: Heartbeat 5秒間隔、タイムアウト10秒
```

### 各プラットフォーム実装方針

| プラットフォーム | 言語 | 音声I/O | ネットワーク | 実装場所 |
|---|---|---|---|---|
| **ESP32** | Rust | I2S (INMP441/MAX98357A) | esp-idf UDP | 実装済み。変更不要 |
| **iOS** | Swift | AVAudioEngine | NWConnectionGroup | `Koe-iOS/Sources/SolunaManager.swift` を修正 |
| **macOS** | Swift | AVAudioEngine (CoreAudio) | NWConnectionGroup | 新規 `Sources/Koe/SolunaManager.swift` |
| **Windows** | Rust | cpal | std::net::UdpSocket | 新規 `Koe-windows/src/soluna.rs` |
| **Android** | Kotlin | AudioRecord/AudioTrack | DatagramSocket | 新規リポジトリ `Koe-android/` |
| **Raspberry Pi** | Rust or Python | ALSA / PyAudio | UDP socket | `stage/soluna-server.py` 拡張 or Rust新規 |

### 共通ライブラリ戦略
Rust 実装 (ESP32/Windows/RPi/サーバー) は `soluna-core` クレートとして共通化可能。
Swift 実装 (iOS/macOS) は共有 Swift パッケージ化可能。
ただし初期段階ではコピー&ペーストで進め、安定後にライブラリ化する。

---

## 実装ステップ (優先度順)

### Phase 1: 基盤整備 (1-2日)

- [ ] **Step 1.1**: プロトコル仕様書を `docs/SOLUNA_PROTOCOL.md` に正式化 (推定: 小)
- [ ] **Step 1.2**: iOS SolunaManager.swift のヘッダを 19B に修正し ESP32 と互換にする (推定: 小)
  - device_id (FNV-1a hash of UUID) 追加
  - flags フィールド追加
  - ADPCM エンコード/デコード追加 (Swift)
- [ ] **Step 1.3**: ESP32 <-> iOS の LAN 通信テスト (推定: 小)

### Phase 2: ダッシュボードサーバー (2-3日)

- [ ] **Step 2.1**: `koe-device/dashboard/` に axum サーバーを新規作成 (推定: 中)
  - `GET /` — ダッシュボードHTML
  - `GET /api/v1/devices` — デバイス一覧 JSON
  - `POST /api/v1/status` — デバイスからの状態報告
  - `WS /api/v1/ws` — リアルタイム更新
- [ ] **Step 2.2**: ダッシュボードHTML (推定: 中)
  - デバイス一覧テーブル (種別アイコン、状態、チャンネル)
  - チャンネルごとのピア数カード
  - 音声レベルバー (WebSocket push)
  - モバイル対応レスポンシブ (Mac Safari + iPhone Safari)
- [ ] **Step 2.3**: ESP32 ファームウェアにステータス報告機能追加 (推定: 小)
  - 既存 `cloud.rs` を拡張、`/api/v1/status` に定期POST
  - デバイスID、チャンネル、ピア数、バッテリー、音声レベル
- [ ] **Step 2.4**: Fly.io デプロイ (推定: 小)
  - `koe-live` app の Dockerfile を axum サーバーに変更
  - `fly deploy -a koe-live`

### Phase 3: macOS Soluna対応 (2-3日)

- [ ] **Step 3.1**: macOS用 `SolunaManager.swift` を作成 (推定: 中)
  - iOS版をベースにmacOS向けに調整 (AVAudioSession → AudioDevice選択)
  - 19Bヘッダ + ADPCM対応
- [ ] **Step 3.2**: macOS設定画面に Soluna タブ追加 (推定: 中)
  - チャンネル選択、状態表示、音量調整
- [ ] **Step 3.3**: macOS <-> ESP32 <-> iOS の3者通信テスト (推定: 小)

### Phase 4: Windows Soluna対応 (1-2日)

- [ ] **Step 4.1**: `Koe-windows/src/soluna.rs` 新規作成 (推定: 中)
  - ESP32の `soluna.rs` からポータブル部分を抽出
  - cpal で音声入出力
  - std::net::UdpSocket でマルチキャスト
- [ ] **Step 4.2**: トレイアイコンに Soluna モード追加 (推定: 小)
- [ ] **Step 4.3**: テスト (推定: 小)

### Phase 5: WANリレー (2-3日)

- [ ] **Step 5.1**: ダッシュボードサーバーに WebSocket リレー機能追加 (推定: 中)
  - クライアントがWebSocketで接続、チャンネルをsubscribe
  - 音声パケットをサーバー経由で転送 (同一チャンネルの他クライアントへ)
- [ ] **Step 5.2**: 各プラットフォームにWANフォールバック実装 (推定: 中)
  - LANマルチキャストで応答なし → WebSocket リレーに自動切替
- [ ] **Step 5.3**: E2Eテスト (異なるネットワーク間) (推定: 小)

### Phase 6: Android (3-4日)

- [ ] **Step 6.1**: `Koe-android/` Kotlin プロジェクト作成 (推定: 中)
- [ ] **Step 6.2**: Soluna プロトコル実装 (推定: 中)
  - AudioRecord/AudioTrack, DatagramSocket
  - ADPCM codec (Kotlin)
- [ ] **Step 6.3**: 最低限のUI (チャンネル選択、ON/OFF) (推定: 中)
- [ ] **Step 6.4**: テスト (推定: 小)

### Phase 7: 管理画面拡張 (1-2日)

- [ ] **Step 7.1**: 距離マップ (Canvas 2D描画) (推定: 中)
- [ ] **Step 7.2**: LED制御パネル (推定: 小)
- [ ] **Step 7.3**: 設定リモート変更 (推定: 小)

---

## テスト方針

- [ ] **ユニットテスト**: ADPCM codec のエンコード/デコード一致確認 (各言語)
- [ ] **プロトコルテスト**: 19B パケットのパース互換性 (ESP32 packet → iOS/Mac/Win で受信)
- [ ] **LAN統合テスト**: ESP32 + iPhone + Mac を同一WiFiに置き、全方向で音声が聞こえること
- [ ] **WANテスト**: 異なるネットワークのデバイス間でリレー経由で通信
- [ ] **ダッシュボード**: 3台以上接続時にリアルタイム表示が更新されること
- [ ] **ビルド確認**: 各プラットフォームでビルドが通ること

---

## リスク

1. **iOSマルチキャスト制限**: iOS ではバックグラウンドでのマルチキャスト受信が制限される。フォアグラウンド限定になる可能性
2. **ADPCM品質**: Swift での ADPCM 実装精度が ESP32 Rust 版と微妙に異なるとノイズが出る。テスト必須
3. **NAT越え**: WAN リレーがボトルネックになる可能性。初期は帯域を ADPCM で抑える
4. **Fly.io WebSocket**: shared-cpu-1x (256MB) で何人まで同時接続できるか未検証
5. **Android 音声遅延**: AudioTrack のバッファリング遅延がiOS/macOSより大きい傾向

---

## 完了条件

1. koe.live/dashboard でアクセスし、接続中のデバイス一覧がリアルタイム表示される
2. iPhone Safari と Mac Safari の両方で管理画面が正常に表示される
3. ESP32, iPhone, Mac の3台が同一チャンネルで音声送受信できる
4. Windows でも Soluna モードで音声送受信できる
5. 異なるWiFiのデバイス間で WAN リレー経由の通信ができる

---

## 技術選定の理由

| 選定 | 理由 |
|------|------|
| **axum (Rust)** | 既存の koe-site が axum。Fly.io デプロイ実績あり。WebSocket標準サポート |
| **vanilla HTML/JS** | KISS原則。ダッシュボードにReactは過剰。WebSocket + DOM操作で十分 |
| **インメモリ状態** | デバイス状態は揮発性データ。DB不要。再起動で消えて問題なし |
| **ADPCM** | ESP32で実績あり。75%帯域削減。Opus等は ESP32 に重すぎる |
| **UDP マルチキャスト** | LAN内のゼロコンフィグP2P。mDNSより軽量 |
| **WebSocket リレー** | WAN通過用。HTTP/2 SSE より双方向に強い。Fly.ioが標準サポート |
| **19B SLヘッダ** | ESP32の実装を正とする。device_idとflagsが必須 (ゴシップ、暗号化に使う) |
