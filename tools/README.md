# Tools

## guitar-stream.py

ギター → Babyface Pro → Raspberry Pi → Koe デバイス群

### 接続

```
ギター ──シールド──→ Babyface Pro ──USB──→ Raspberry Pi
                                              │
                                         WiFi / LAN
                                              │
                                    ┌─────────┼─────────┐
                                    ▼         ▼         ▼
                                 Koe #1    Koe #2    Koe #3
                                (ESP32)   (ESP32)   (ESP32)
```

### Raspberry Pi セットアップ

```bash
# 1. Babyface Pro を USB で接続 (Class Compliant モードにしておく)
#    Babyface Pro 背面の "CC" ボタンを押しながら電源ON

# 2. 認識確認
arecord -l
# → card 1: BabyfacePro [Babyface Pro], device 0: USB Audio [USB Audio]

# 3. Python依存インストール
pip3 install sounddevice numpy

# 4. 実行
python3 guitar-stream.py
```

### Babyface Pro の設定

1. **Class Compliant モードを有効にする**
   - 背面の "CC" ボタンを押しながら電源ON
   - フロントパネルのLEDが青く光る
   - これでLinux/Piがドライバなしで認識する

2. **入力選択**
   - フロントパネルの Instrument 入力 (Hi-Z) にギターを挿す
   - ゲインノブで適切なレベルに調整

3. **サンプルレート**
   - CC モードでは 48kHz 固定
   - スクリプトもデフォルト 48kHz

### レイテンシ

| 区間 | 時間 |
|------|------|
| ギター → Babyface Pro (A/D) | ~0.5ms |
| USB → Pi (ALSA) | ~2.7ms (128 samples @ 48kHz) |
| Python処理 + UDP送信 | ~1ms |
| WiFi 伝送 | ~2ms |
| ESP32 受信 + ジッタバッファ | ~15ms |
| I2S → スピーカー | ~1ms |
| **合計** | **~22ms** |

### オプション

```bash
# ステレオで送信
python3 guitar-stream.py --channels 2

# 別のオーディオデバイスを使用
python3 guitar-stream.py --device 3

# ブロックサイズ変更 (小さい=低遅延, 大きい=安定)
python3 guitar-stream.py --block 64   # 1.3ms, 超低遅延
python3 guitar-stream.py --block 256  # 5.3ms, 安定
```

### Mac でテスト (Raspi なしでも動く)

Babyface Pro を Mac に繋いでも同じスクリプトが使える:

```bash
pip3 install sounddevice numpy
python3 tools/guitar-stream.py
# → 同じWiFi上の ESP32 Koe デバイスから音が出る
```

---

## led-send.py

STAGE (Raspberry Pi) から全 CROWD デバイスへ LED コマンドを送信する CLI ツール。

### プロトコル

- UDP マルチキャスト: `239.42.42.1:4243`
- パケット: 12 バイト固定長

```
Offset  Size  Field
0       2     Magic "LE" (0x4C 0x45)
2       4     Timestamp (uint32 BE, 0 = 即時実行)
6       1     Pattern ID (0-7)
7       1     Red   (0-255)
8       1     Green (0-255)
9       1     Blue  (0-255)
10      1     Speed (0-255)
11      1     Intensity (0-255)
```

### パターン一覧

| ID | Name     | 説明 |
|----|----------|------|
| 0  | off      | 全消灯 |
| 1  | solid    | 単色点灯 |
| 2  | pulse    | パルス (明滅) |
| 3  | rainbow  | レインボーサイクル (色指定不要) |
| 4  | wave_lr  | ウェーブ 左→右 |
| 5  | wave_rl  | ウェーブ 右→左 |
| 6  | strobe   | ストロボ |
| 7  | breathe  | ゆっくり明滅 |

### 使い方

```bash
python3 led-send.py solid 255 0 0          # 全デバイス赤
python3 led-send.py rainbow --speed 128    # レインボー (中速)
python3 led-send.py pulse 0 0 255 --bpm 120  # 青パルス 120 BPM
python3 led-send.py wave_lr 255 128 0      # オレンジ ウェーブ
python3 led-send.py strobe 255 255 255     # 白ストロボ
python3 led-send.py off                    # 全消灯
python3 led-send.py breathe 0 255 128      # ティール ブリーズ
python3 led-send.py solid 255 0 0 --loop   # 100ms 間隔で連続送信
```

### オプション

| フラグ | デフォルト | 説明 |
|--------|-----------|------|
| `--speed` | 128 | 速度 (0-255) |
| `--intensity` | 200 | 明るさ (0-255) |
| `--bpm` | - | BPM から速度を自動計算 (300BPM=255) |
| `--loop` | - | 100ms 間隔で連続送信 (Ctrl+C で停止) |

---

## led-show.py

LED ライトショーを JSON で定義し、タイミング通りに自動実行する。

### 使い方

```bash
python3 led-show.py              # 内蔵 30 秒デモショー
python3 led-show.py show.json    # カスタムショーファイル
```

### ショーファイル形式

```json
{
  "bpm": 120,
  "steps": [
    {"time": 0,   "pattern": "solid",   "color": [255, 0, 0], "speed": 128},
    {"time": 2.0, "pattern": "pulse",   "color": [0, 0, 255], "speed": 200},
    {"time": 4.0, "pattern": "rainbow", "speed": 255},
    {"time": 8.0, "pattern": "off"}
  ]
}
```

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `time` | Yes | 開始からの秒数 |
| `pattern` | Yes | パターン名 (led-send.py と同じ) |
| `color` | No | `[R, G, B]` (デフォルト `[0,0,0]`) |
| `speed` | No | 速度 (デフォルト 128) |
| `intensity` | No | 明るさ (デフォルト 200) |

### デモショーファイル

`demo-show.json` に 30 秒のサンプルショーが入っている:

```bash
python3 led-show.py demo-show.json
```

### 動作

- ステップを `time` 順にソートして順次実行
- 各ステップで ANSI カラー付きのログをターミナルに表示
- Ctrl+C で中断すると自動的に LED を消灯 (off 送信)
