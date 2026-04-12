#!/usr/bin/env python3
"""
koe-amp.py — Koe Amp recording service for Raspberry Pi 5 + ReSpeaker USB

Listens continuously on the ReSpeaker USB mic array, detects audio onsets using
an EMA background floor (ported from firmware/amp/src/audio.rs), and reports
sessions + heartbeats to koe.live.

Design:
  - sounddevice reads 16kHz mono frames of 512 samples (~32 ms each)
  - OnsetDetector mirrors the Rust EMA algorithm from audio.rs exactly
  - 5-second ring buffer captures pre-onset audio
  - A session starts on onset and ends after 5 seconds of continuous silence
  - Heartbeat POST every 5 seconds regardless of session state
  - Graceful SIGTERM shutdown: ends any open session before exiting

Usage:
  python3 /usr/local/bin/koe-amp.py

Config files:
  /etc/koe/device_id  — e.g. koe-amp-hawaii-01
  /etc/koe/room       — e.g. living_room
"""

import collections
import logging
import math
import os
import signal
import socket
import sys
import threading
import time
import uuid

import numpy as np
import requests
import sounddevice as sd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SAMPLE_RATE    = 16_000          # Hz
FRAME_SAMPLES  = 512             # samples per callback frame (~32 ms)
LOOKBACK_SECS  = 5               # ring-buffer depth
BUF_SAMPLES    = SAMPLE_RATE * LOOKBACK_SECS

ONSET_RATIO_DB = 8.0             # dB above floor to trigger onset

# EMA floor time constants (mirror audio.rs)
FLOOR_ATTACK   = 0.95            # fast rise when loud
FLOOR_RELEASE  = 0.9995          # very slow decay
FLOOR_MIN      = 50.0            # minimum floor (LSB RMS units, i16 scale)
FLOOR_INIT     = 100.0           # starting floor
REFRACTORY_FRAMES = 48           # ~1.5 s at 32 ms/frame

SILENCE_END_SECS   = 5.0         # seconds of silence before session ends
HEARTBEAT_INTERVAL = 5.0         # seconds between heartbeat POSTs
LEVEL_INTERVAL     = 0.1         # seconds between audio-level POSTs (100ms)

KOE_API_BASE = "https://koe.live"
FIRMWARE_VER = "python-1.0.0"
DEVICE_TYPE  = "amp"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("koe-amp")

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _read_file(path: str, default: str) -> str:
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def load_config() -> tuple[str, str]:
    device_id = _read_file("/etc/koe/device_id", socket.gethostname())
    room      = _read_file("/etc/koe/room", "living_room")
    return device_id, room


# ---------------------------------------------------------------------------
# Onset detector (port of firmware/amp/src/audio.rs OnsetDetector)
# ---------------------------------------------------------------------------

class OnsetDetector:
    """
    EMA-based onset detector that mirrors the Rust implementation in audio.rs.

    Internal floor is tracked in linear i16-scale RMS units (0–32767).
    Inputs are numpy float32 arrays in the range [-1.0, 1.0] from sounddevice;
    we scale them to i16 units before computing RMS.
    """

    def __init__(self) -> None:
        self._floor: float       = FLOOR_INIT
        self._refractory: int    = 0

    # -- public ----------------------------------------------------------------

    def process_frame(self, samples_f32: np.ndarray) -> bool:
        """
        Process one frame of float32 samples (range -1..1).
        Returns True if an onset is detected this frame.
        """
        # Scale to i16 range so thresholds match firmware constants
        samples_i16_scale = samples_f32 * 32767.0
        current_rms = _rms(samples_i16_scale)

        # Update background floor only outside refractory window
        if self._refractory == 0:
            if current_rms > self._floor:
                # Fast attack
                self._floor = FLOOR_ATTACK * self._floor + (1.0 - FLOOR_ATTACK) * current_rms
            else:
                # Slow release
                self._floor = FLOOR_RELEASE * self._floor + (1.0 - FLOOR_RELEASE) * current_rms
            if self._floor < FLOOR_MIN:
                self._floor = FLOOR_MIN

        # Decrement refractory
        if self._refractory > 0:
            self._refractory -= 1
            return False

        # Onset condition: current RMS must exceed floor by ONSET_RATIO_DB dB
        db_above = _ratio_to_db(current_rms / max(self._floor, 1.0))
        if db_above >= ONSET_RATIO_DB:
            log.info(
                "onset detected: rms=%.1f floor=%.1f db_above=%.1f",
                current_rms, self._floor, db_above,
            )
            self._refractory = REFRACTORY_FRAMES
            return True

        return False

    @property
    def floor_rms(self) -> float:
        return self._floor


def _rms(samples: np.ndarray) -> float:
    if samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))


def _ratio_to_db(ratio: float) -> float:
    if ratio <= 0.0:
        return -math.inf
    return 20.0 * math.log10(ratio)


# ---------------------------------------------------------------------------
# Ring buffer (numpy-backed)
# ---------------------------------------------------------------------------

class RingBuffer:
    """5-second circular buffer of float32 mono audio frames."""

    def __init__(self) -> None:
        self._buf   = collections.deque(maxlen=BUF_SAMPLES)

    def push(self, samples: np.ndarray) -> None:
        self._buf.extend(samples.tolist())

    def recent(self, n: int) -> np.ndarray:
        data = list(self._buf)
        if len(data) >= n:
            return np.array(data[-n:], dtype=np.float32)
        return np.array(data, dtype=np.float32)


# ---------------------------------------------------------------------------
# LED indicator (optional — best-effort, never crashes the main loop)
# ---------------------------------------------------------------------------

def _blink_led_violet() -> None:
    """
    Optional violet blink.  Uses /sys/class/leds if available.
    Silently no-ops if no LED device is found.
    """
    try:
        led_path = "/sys/class/leds/led0/brightness"
        if os.path.exists(led_path):
            with open(led_path, "w") as f:
                f.write("255\n")
            time.sleep(0.1)
            with open(led_path, "w") as f:
                f.write("0\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# API client (with retry on network errors)
# ---------------------------------------------------------------------------

_HTTP_TIMEOUT = 8  # seconds
_MAX_RETRIES  = 3
_RETRY_DELAY  = 2  # seconds


def _post(url: str, payload: dict) -> bool:
    """POST JSON payload; returns True on 2xx, False otherwise."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=payload, timeout=_HTTP_TIMEOUT)
            if 200 <= resp.status_code < 300:
                return True
            log.warning("POST %s → %d (attempt %d)", url, resp.status_code, attempt)
        except requests.exceptions.ConnectionError as e:
            log.warning("POST %s connection error (attempt %d): %s", url, attempt, e)
        except requests.exceptions.Timeout:
            log.warning("POST %s timed out (attempt %d)", url, attempt)
        except Exception as e:
            log.warning("POST %s unexpected error (attempt %d): %s", url, attempt, e)
        if attempt < _MAX_RETRIES:
            time.sleep(_RETRY_DELAY)
    return False


def send_heartbeat(device_id: str, room: str, audio_level: float, is_recording: bool) -> None:
    payload = {
        "device_id":    device_id,
        "room":         room,
        "device_type":  DEVICE_TYPE,
        "firmware_ver": FIRMWARE_VER,
        "audio_level":  round(audio_level, 4),
        "is_recording": is_recording,
        "battery_pct":  100,   # RPi runs from wall power; always 100
    }
    ok = _post(f"{KOE_API_BASE}/api/v1/device/heartbeat", payload)
    if ok:
        log.debug("heartbeat ok device=%s room=%s rec=%s", device_id, room, is_recording)
    else:
        log.warning("heartbeat FAILED for device=%s", device_id)


def send_session_start(session_id: str, device_id: str, room: str) -> None:
    payload = {
        "device_id": device_id,
        "room":      room,
        "source":    "device",
        "tracks":    1,
        "instruments": "[]",
    }
    ok = _post(f"{KOE_API_BASE}/api/v1/sessions/{session_id}/start", payload)
    if ok:
        log.info("session_start: %s device=%s room=%s", session_id, device_id, room)
    else:
        log.warning("session_start FAILED: %s", session_id)


def send_session_end(
    session_id: str,
    device_id: str,
    room: str,
    audio_rms: float,
    duration_secs: float,
) -> None:
    payload = {
        "device_id":      device_id,
        "room":           room,
        "audio_rms":      round(audio_rms, 4),
        "duration_secs":  round(duration_secs, 1),
        "loop_count":     0,
    }
    ok = _post(f"{KOE_API_BASE}/api/v1/sessions/{session_id}/end", payload)
    if ok:
        log.info(
            "session_end: %s device=%s duration=%.1fs rms=%.1f",
            session_id, device_id, duration_secs, audio_rms,
        )
    else:
        log.warning("session_end FAILED: %s", session_id)


# ---------------------------------------------------------------------------
# Audio-level streaming thread
# ---------------------------------------------------------------------------

def _level_thread(device_id: str, room: str, state: dict) -> None:
    """Posts audio level every 100ms for live /room display."""
    while not state['shutdown'].is_set():
        level  = state.get('current_level', 0.0)
        is_rec = state.get('is_recording', False)
        try:
            requests.post(
                f"{KOE_API_BASE}/api/v1/room/audio-level",
                json={
                    "device_id":    device_id,
                    "room":         room,
                    "level":        round(float(level), 3),
                    "is_recording": is_rec,
                },
                timeout=0.5,
            )
        except Exception:
            pass
        time.sleep(LEVEL_INTERVAL)


# ---------------------------------------------------------------------------
# Heartbeat background thread
# ---------------------------------------------------------------------------

class HeartbeatThread(threading.Thread):
    """Sends a heartbeat every HEARTBEAT_INTERVAL seconds until stopped."""

    def __init__(self, device_id: str, room: str) -> None:
        super().__init__(daemon=True, name="heartbeat")
        self._device_id   = device_id
        self._room        = room
        self._stop_event  = threading.Event()
        self._audio_level = 0.0
        self._is_recording = False
        self._lock        = threading.Lock()

    def update_state(self, audio_level: float, is_recording: bool) -> None:
        with self._lock:
            self._audio_level  = audio_level
            self._is_recording = is_recording

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        log.info("heartbeat thread started (interval=%.0fs)", HEARTBEAT_INTERVAL)
        while not self._stop_event.wait(timeout=HEARTBEAT_INTERVAL):
            with self._lock:
                level = self._audio_level
                rec   = self._is_recording
            send_heartbeat(self._device_id, self._room, level, rec)
        log.info("heartbeat thread stopped")


# ---------------------------------------------------------------------------
# Audio callback + session state machine
# ---------------------------------------------------------------------------

class AmpService:
    """
    Core service: opens a sounddevice input stream on the ReSpeaker USB mic,
    runs OnsetDetector on each frame, manages session state, and drives the
    HeartbeatThread.
    """

    def __init__(self, device_id: str, room: str) -> None:
        self._device_id    = device_id
        self._room         = room

        self._detector     = OnsetDetector()
        self._ring         = RingBuffer()

        # Session state
        self._session_id:    str | None  = None
        self._session_start: float       = 0.0
        self._last_sound:    float       = 0.0
        self._session_rms_acc: float     = 0.0
        self._session_frame_count: int   = 0

        # Shared state for heartbeat thread (written from audio callback)
        self._current_rms   = 0.0
        self._is_recording  = False
        self._state_lock    = threading.Lock()

        self._heartbeat     = HeartbeatThread(device_id, room)
        self._shutdown      = threading.Event()

        # Shared state dict for the level-streaming thread.
        # Python GIL makes single float/bool writes atomic, but we store them
        # in a dict to pass by reference to the thread function.
        self._level_state: dict = {
            'shutdown':      self._shutdown,
            'current_level': 0.0,
            'is_recording':  False,
        }

    # -- public ----------------------------------------------------------------

    def run(self) -> None:
        self._heartbeat.start()
        threading.Thread(
            target=_level_thread,
            args=(self._device_id, self._room, self._level_state),
            daemon=True,
            name="audio-level",
        ).start()
        log.info(
            "starting audio capture device_id=%s room=%s rate=%d frame=%d",
            self._device_id, self._room, SAMPLE_RATE, FRAME_SAMPLES,
        )
        # Find ReSpeaker device index (falls back to default)
        device_index = _find_respeaker()
        log.info("using audio device index: %s", device_index)

        try:
            with sd.InputStream(
                device=device_index,
                channels=1,
                samplerate=SAMPLE_RATE,
                blocksize=FRAME_SAMPLES,
                dtype="float32",
                callback=self._audio_callback,
            ):
                log.info("audio stream open — listening")
                self._shutdown.wait()
        except sd.PortAudioError as e:
            log.error("PortAudio error: %s", e)
        except Exception as e:
            log.error("unexpected stream error: %s", e)
        finally:
            self._close()

    def request_shutdown(self) -> None:
        log.info("shutdown requested")
        self._shutdown.set()

    # -- internal --------------------------------------------------------------

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            log.debug("sounddevice status: %s", status)

        samples = indata[:, 0]  # mono
        self._ring.push(samples)

        is_onset = self._detector.process_frame(samples)
        current_rms = _rms(samples * 32767.0)

        # Update heartbeat state (thread-safe)
        is_recording = self._session_id is not None
        normalized_level = current_rms / 32767.0  # normalise to 0..1 for API
        with self._state_lock:
            self._current_rms  = current_rms
            self._is_recording = is_recording
        self._heartbeat.update_state(normalized_level, is_recording)

        # Update level-streaming state (atomic float write — GIL-safe)
        self._level_state['current_level'] = normalized_level
        self._level_state['is_recording']  = is_recording

        now = time.monotonic()

        # --- Session state machine ---
        if self._session_id is None:
            # Idle: waiting for onset
            if is_onset:
                self._start_session(now)
        else:
            # Recording: accumulate RMS for energy profile
            self._session_rms_acc += current_rms
            self._session_frame_count += 1

            if current_rms > self._detector.floor_rms * 0.5:
                self._last_sound = now

            # End session after SILENCE_END_SECS of quiet
            if now - self._last_sound > SILENCE_END_SECS:
                self._end_session(now)

        # Blink LED on every onset (best-effort, non-blocking)
        if is_onset:
            threading.Thread(target=_blink_led_violet, daemon=True).start()

    def _start_session(self, now: float) -> None:
        sid = str(uuid.uuid4())
        self._session_id          = sid
        self._session_start       = now
        self._last_sound          = now
        self._session_rms_acc     = 0.0
        self._session_frame_count = 0
        log.info("session starting: %s", sid)
        threading.Thread(
            target=send_session_start,
            args=(sid, self._device_id, self._room),
            daemon=True,
        ).start()

    def _end_session(self, now: float) -> None:
        sid      = self._session_id
        duration = now - self._session_start
        avg_rms  = (
            self._session_rms_acc / self._session_frame_count
            if self._session_frame_count > 0
            else 0.0
        )
        self._session_id          = None
        self._session_rms_acc     = 0.0
        self._session_frame_count = 0
        log.info("session ending: %s duration=%.1fs", sid, duration)
        threading.Thread(
            target=send_session_end,
            args=(sid, self._device_id, self._room, avg_rms, duration),
            daemon=True,
        ).start()

    def _close(self) -> None:
        """End any open session and stop the heartbeat thread before exit."""
        if self._session_id:
            now = time.monotonic()
            self._end_session(now)
            time.sleep(1.0)   # give the session_end POST a moment to fire
        self._heartbeat.stop()
        self._heartbeat.join(timeout=3.0)
        log.info("koe-amp shutdown complete")


# ---------------------------------------------------------------------------
# Device discovery helpers
# ---------------------------------------------------------------------------

RESPEAKER_KEYWORDS = ("respeaker", "seeed", "usb microphone", "usb audio")


def _find_respeaker() -> int | None:
    """
    Scan sounddevice device list for a ReSpeaker USB mic array.
    Returns the device index if found, or None to use the system default.
    """
    try:
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            name_lower = dev["name"].lower()
            if any(kw in name_lower for kw in RESPEAKER_KEYWORDS):
                if dev["max_input_channels"] > 0:
                    log.info("found ReSpeaker: [%d] %s", i, dev["name"])
                    return i
    except Exception as e:
        log.warning("device scan failed: %s", e)
    log.info("ReSpeaker not found — using system default input device")
    return None


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

_service: AmpService | None = None


def _handle_signal(signum: int, frame: object) -> None:
    log.info("received signal %d — initiating graceful shutdown", signum)
    if _service is not None:
        _service.request_shutdown()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    global _service

    log.info("koe-amp starting (firmware=%s)", FIRMWARE_VER)

    device_id, room = load_config()
    log.info("device_id=%s room=%s api=%s", device_id, room, KOE_API_BASE)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    _service = AmpService(device_id, room)
    _service.run()


if __name__ == "__main__":
    main()
