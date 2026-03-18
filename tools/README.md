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
