# Sync Demo - ESP32-S3 Synchronized Audio Playback

Minimal proof-of-concept: one ESP32-S3 captures audio from an I2S mic, sends it over UDP multicast with microsecond timestamps, and one or more receivers play it back through I2S speakers using a jitter buffer.

## Hardware

Each board needs:
- ESP32-S3 dev board
- I2S MEMS mic (e.g., INMP441): BCLK=GPIO4, WS=GPIO5, DIN=GPIO6
- I2S amplifier (e.g., MAX98357A): BCLK=GPIO14, WS=GPIO21, DOUT=GPIO7, SD_MODE=GPIO8
- WS2812B LED on GPIO16
- Button on GPIO15 (pulled HIGH by default, press to pull LOW)

## Prerequisites

```bash
# Install Rust ESP toolchain
cargo install espup
espup install
cargo install espflash
cargo install ldproxy
```

## Build & Flash

Set WiFi credentials as environment variables:

```bash
export WIFI_SSID="YourNetwork"
export WIFI_PASS="YourPassword"
```

Flash device A (sender) - hold GPIO15 button while flashing/booting:

```bash
cd demo
cargo espflash flash --monitor --port /dev/ttyUSB0
```

Flash device B (receiver) - do NOT hold button:

```bash
cargo espflash flash --monitor --port /dev/ttyUSB1
```

## How to Test

1. Flash both boards with the same firmware and WiFi credentials.
2. Power up device B (receiver) first. LED turns orange (waiting).
3. Power up device A while holding GPIO15 button. LED turns green (recording).
4. Device B LED turns orange (syncing), then cyan (playing audio).
5. Speak into device A's mic. You should hear audio from device B's speaker.
6. Add more receivers - they all join the same multicast group.

## LED States

| Color  | Meaning                      |
|--------|------------------------------|
| Green  | Sender: recording from mic   |
| Orange | Receiver: syncing/buffering  |
| Cyan   | Receiver: playing audio      |

## Packet Format

14-byte header + up to 1024 bytes PCM audio:

```
[0-1]   magic: 0x53 0x4C ("SL")
[2-5]   sequence: u32 LE
[6-9]   timestamp_us: u32 LE (lower 32 bits of esp_timer_get_time)
[10-13] reserved: 0
[14..]  audio: PCM s16le 16kHz mono
```

## Measuring Sync Accuracy

To verify that multiple receivers are synchronized:

1. Set up 2+ receiver boards, each with a speaker.
2. Place both speakers next to a stereo audio recorder (or use a 2-channel USB audio interface).
3. Connect speaker A to left channel, speaker B to right channel.
4. Record while the sender transmits audio.
5. Open the recording in Audacity or similar:
   - Zoom into a transient (e.g., a clap or click).
   - Measure the time offset between left and right channels.
   - Target: < 1ms offset between receivers on the same LAN.

Alternatively, use an oscilloscope on the I2S DOUT pins of both receivers to measure the sample-level alignment directly.

## Architecture

```
  [Mic] --> I2S RX --> [SENDER ESP32-S3]
                            |
                      UDP multicast
                      239.42.42.1:4242
                            |
                   +--------+--------+
                   |                 |
           [RECEIVER A]       [RECEIVER B]
           Jitter Buffer      Jitter Buffer
                |                    |
           I2S TX --> [Speaker] I2S TX --> [Speaker]
```

## Parameters

| Parameter     | Value          | Notes                          |
|--------------|----------------|--------------------------------|
| Sample rate  | 16 kHz         | Speech-quality                 |
| Bit depth    | 16-bit signed  | s16le                          |
| Channels     | 1 (mono)       |                                |
| Chunk size   | 512 samples    | 32ms per chunk                 |
| Jitter buf   | 8 slots        | ~256ms max, 40ms target        |
| Multicast    | 239.42.42.1    | Port 4242                      |
