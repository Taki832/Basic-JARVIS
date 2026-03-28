"""
voice/speech_to_text.py
───────────────────────
Offline speech recognition using Vosk + sounddevice.

Architecture:
  • A daemon thread continuously reads mic audio into a bounded queue.
  • listen_for_command() drains that queue through Vosk until a sentence
    is finalised, printing partial results live.
  • listen() wraps both stages: passive wake-word scan → command capture.
  • The audio stream is opened once and shared across calls (no reopening).

Public API:
    from voice.speech_to_text import listen, listen_for_command

    text = listen()                  # wake word → command (default mode)
    text = listen_for_command()      # skip wake word, capture next sentence

Requirements:
    pip install vosk sounddevice
    Vosk model path: models/vosk-model/  (project root)
    Or override in config.json → voice.vosk_model_path
"""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Optional

from utils.config import CFG
from utils.logger import get_logger

log = get_logger(__name__)


# ════════════════════════════════════════════════════════════
#  OPTIONAL DEPENDENCIES  (graceful degradation)
# ════════════════════════════════════════════════════════════
try:
    from vosk import Model, KaldiRecognizer
    _VOSK_OK = True
except ImportError:
    _VOSK_OK = False
    log.warning("vosk not installed — run: pip install vosk")

try:
    import sounddevice as sd
    _SD_OK = True
except ImportError:
    _SD_OK = False
    log.warning("sounddevice not installed — run: pip install sounddevice")


# ════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════
_SAMPLERATE  = 16000
_BLOCKSIZE   = 4000   # smaller block = faster partial update latency
_QUEUE_MAX   = 50     # cap queue depth to prevent memory growth


# ════════════════════════════════════════════════════════════
#  MODULE-LEVEL STATE  (initialised lazily, shared across calls)
# ════════════════════════════════════════════════════════════
_vosk_model:    Optional["Model"]         = None
_audio_queue:   queue.Queue[bytes]        = queue.Queue(maxsize=_QUEUE_MAX)
_stream:        Optional["sd.RawInputStream"] = None
_stream_lock:   threading.Lock            = threading.Lock()
_stream_error:  Optional[str]             = None   # set by callback on PortAudio error


# ════════════════════════════════════════════════════════════
#  MODEL LOADER
# ════════════════════════════════════════════════════════════
def _get_model() -> Optional["Model"]:
    """Load Vosk model once; return cached instance on subsequent calls."""
    global _vosk_model
    if _vosk_model is not None:
        return _vosk_model
    if not _VOSK_OK:
        return None

    cfg_path   = CFG.voice.get("vosk_model_path", "")
    model_path = (
        Path(cfg_path)
        if cfg_path
        else Path(__file__).parent.parent / "models" / "vosk-model"
    )

    if not model_path.exists():
        log.error(f"Vosk model not found: {model_path}")
        print(
            f"\n[STT] ❌ Vosk model missing: {model_path}"
            f"\n      Download from https://alphacephei.com/vosk/models"
            f"\n      Extract and rename the folder to: models/vosk-model/\n"
        )
        return None

    try:
        import vosk
        vosk.SetLogLevel(-1)              # suppress Vosk's verbose C++ logs
        _vosk_model = Model(str(model_path))
        log.info(f"Vosk model loaded: {model_path}")
        return _vosk_model
    except Exception as exc:
        log.error(f"Vosk model load failed: {exc}")
        print(f"\n[STT] ❌ Failed to load Vosk model: {exc}\n")
        return None


# ════════════════════════════════════════════════════════════
#  AUDIO STREAM  (one shared stream, opened lazily)
# ════════════════════════════════════════════════════════════
def _audio_callback(
    indata,
    frames: int,        # noqa: ARG001
    time_info,          # noqa: ARG001
    status,
) -> None:
    """
    Called by sounddevice on its audio thread.
    Pushes raw PCM bytes into the queue; never blocks.
    """
    global _stream_error
    if status:
        # status is a CallbackFlags object; only log real errors
        status_str = str(status)
        if "error" in status_str.lower() or "overflow" in status_str.lower():
            log.warning(f"Audio callback status: {status_str}")
            _stream_error = status_str
    try:
        _audio_queue.put_nowait(bytes(indata))
    except queue.Full:
        # Queue is full (consumer is too slow) — drop oldest block
        try:
            _audio_queue.get_nowait()
            _audio_queue.put_nowait(bytes(indata))
        except queue.Empty:
            pass


def _open_stream(device_index: Optional[int] = None) -> bool:
    """
    Open the shared RawInputStream.
    Returns True on success, False on any hardware/driver error.
    """
    global _stream, _stream_error
    with _stream_lock:
        if _stream is not None and _stream.active:
            return True   # already open

        if not _SD_OK:
            print("[STT] ❌ sounddevice not installed — run: pip install sounddevice")
            return False

        # Resolve device index: config → argument → system default
        cfg_device = CFG.voice.get("mic_device_index", None)
        device     = device_index if device_index is not None else cfg_device

        try:
            _stream_error = None
            _stream = sd.RawInputStream(
                samplerate=_SAMPLERATE,
                blocksize=_BLOCKSIZE,
                dtype="int16",
                channels=1,
                device=device,
                callback=_audio_callback,
            )
            _stream.start()
            log.info(
                f"Audio stream opened — device: "
                f"{'default' if device is None else device}, "
                f"rate: {_SAMPLERATE} Hz"
            )
            return True

        except sd.PortAudioError as exc:
            log.error(f"PortAudio error opening stream: {exc}")
            print(
                f"\n[STT] ❌ Microphone error: {exc}"
                f"\n      Check that a microphone is connected and not in use.\n"
            )
            _stream = None
            return False

        except ValueError as exc:
            # Invalid device index
            log.error(f"Invalid audio device ({device}): {exc}")
            print(
                f"\n[STT] ❌ Invalid mic device index {device}: {exc}"
                f"\n      Run: python -c \"import sounddevice; print(sounddevice.query_devices())\"\n"
            )
            _stream = None
            return False

        except Exception as exc:
            log.error(f"Unexpected stream error: {exc}")
            print(f"\n[STT] ❌ Audio error: {exc}\n")
            _stream = None
            return False


def _drain_queue() -> None:
    """Discard all queued audio blocks (called before starting a new recognition pass)."""
    while not _audio_queue.empty():
        try:
            _audio_queue.get_nowait()
        except queue.Empty:
            break


def _new_recognizer() -> Optional["KaldiRecognizer"]:
    """Create a fresh KaldiRecognizer bound to the loaded model."""
    model = _get_model()
    if model is None:
        return None
    rec = KaldiRecognizer(model, _SAMPLERATE)
    rec.SetWords(False)   # word-level timestamps not needed; keeps output clean
    return rec


# ════════════════════════════════════════════════════════════
#  WAKE WORD DETECTION
# ════════════════════════════════════════════════════════════
def _wait_for_wake_word(wake_word: str) -> bool:
    """
    Passive listening loop.
    Scans Vosk partial results for the wake word substring.
    Returns True when detected, False on unrecoverable error.
    CPU-light: only processes partial results, no full-sentence decode needed.
    """
    rec = _new_recognizer()
    if rec is None:
        return False

    print(f"\n🎤 Waiting for wake word  [{wake_word}]...", flush=True)
    _drain_queue()

    while True:
        try:
            block = _audio_queue.get(timeout=2.0)
        except queue.Empty:
            # No audio for 2 s — check stream still alive
            if _stream is None or not _stream.active:
                log.warning("Audio stream died during wake word listening.")
                return False
            continue

        if _stream_error:
            log.error(f"Stream error during wake-word: {_stream_error}")
            return False

        try:
            if rec.AcceptWaveform(block):
                # Full sentence; check it too
                result_text = json.loads(rec.Result()).get("text", "").lower()
                if wake_word in result_text:
                    return True
                # Reset recogniser for next pass
                rec = _new_recognizer()
                if rec is None:
                    return False
            else:
                partial = json.loads(rec.PartialResult()).get("partial", "").lower()
                if wake_word in partial:
                    return True
        except (json.JSONDecodeError, Exception) as exc:
            log.debug(f"Wake word recognition error: {exc}")
            # Non-fatal — reset and keep going
            rec = _new_recognizer()
            if rec is None:
                return False


# ════════════════════════════════════════════════════════════
#  COMMAND CAPTURE
# ════════════════════════════════════════════════════════════
def listen_for_command(device_index: Optional[int] = None) -> str:
    """
    Capture one full spoken sentence and return it as text.
    Prints live partial results while the user is speaking.
    Always returns a string (empty string on failure).

    Args:
        device_index: sounddevice device index override (None = use config/default)
    """
    if not _VOSK_OK:
        print("[STT] vosk not installed.")
        return ""

    if not _open_stream(device_index):
        return ""

    rec = _new_recognizer()
    if rec is None:
        return ""

    _drain_queue()
    print("👂 Listening for command...", flush=True)

    last_partial = ""

    while True:
        try:
            block = _audio_queue.get(timeout=2.0)
        except queue.Empty:
            if _stream is None or not _stream.active:
                log.warning("Audio stream died during command capture.")
                return ""
            continue

        if _stream_error:
            log.error(f"Stream error during command capture: {_stream_error}")
            return ""

        try:
            if rec.AcceptWaveform(block):
                result = json.loads(rec.Result())
                text   = result.get("text", "").strip()
                if text:
                    print(f"\r[You said]: {text}                    ", flush=True)
                    log.info(f"STT command: {text}")
                    return text
                # Empty finalisation (silence burst) — keep listening
                # Reset so we don't carry stale state
                rec = _new_recognizer()
                if rec is None:
                    return ""
            else:
                partial = json.loads(rec.PartialResult()).get("partial", "").strip()
                if partial and partial != last_partial:
                    print(f"\r🎤 {partial}...", end="", flush=True)
                    last_partial = partial

        except (json.JSONDecodeError, Exception) as exc:
            log.debug(f"Command recognition error: {exc}")
            rec = _new_recognizer()
            if rec is None:
                return ""


# ════════════════════════════════════════════════════════════
#  PUBLIC: listen()  — wake word → command
# ════════════════════════════════════════════════════════════
def listen(device_index: Optional[int] = None) -> str:
    """
    Full interaction cycle:
      1. Passive scan for wake word ("jarvis" by default)
      2. On detection → capture the next spoken command
      3. Return command text

    If wake_word is empty in config → skip wake word stage,
    capture immediately (useful for PTT / blank-input mode).

    Always returns a string (empty on failure/silence).
    """
    if not _VOSK_OK or not _SD_OK:
        print("[STT] Required libraries missing (vosk / sounddevice).")
        return ""

    if not _open_stream(device_index):
        return ""

    wake_word = CFG.voice.get("wake_word", "jarvis").lower().strip()

    if wake_word:
        detected = _wait_for_wake_word(wake_word)
        if not detected:
            log.warning("Wake word detection ended without detection.")
            return ""
        print(f"\n👂 Wake word detected — go ahead!", flush=True)

    return listen_for_command(device_index)
