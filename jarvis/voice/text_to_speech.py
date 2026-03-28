"""
voice/text_to_speech.py
───────────────────────
Text-to-speech using pyttsx3.
Runs on a background thread to avoid blocking.
"""

from __future__ import annotations

import queue
import threading

from utils.config import CFG
from utils.logger import get_logger

log = get_logger(__name__)

try:
    import pyttsx3
    _TTS_LIB = True
except ImportError:
    _TTS_LIB = False


class TextToSpeech:
    """
    Thread-safe TTS engine.
    Enqueues text; a daemon thread processes it sequentially.
    """

    def __init__(self) -> None:
        cfg             = CFG.voice
        self.enabled    = cfg.get("tts_enabled", False) and _TTS_LIB
        self._rate:  int   = cfg.get("tts_rate",   175)
        self._volume: float = cfg.get("tts_volume", 0.9)
        self._queue  = queue.Queue()
        self._engine = None
        self._thread: threading.Thread | None = None

        if self.enabled:
            self._start()

    # ── Public ────────────────────────────────────────────
    def speak(self, text: str) -> None:
        """Non-blocking: enqueue text to be spoken."""
        if self.enabled and text.strip():
            self._queue.put(text)

    def enable(self) -> str:
        if not _TTS_LIB:
            return "pyttsx3 not installed — run: pip install pyttsx3"
        self.enabled = True
        self._start()
        return "Voice output enabled."

    def disable(self) -> str:
        self.enabled = False
        return "Voice output disabled."

    def toggle(self) -> str:
        if self.enabled:
            return self.disable()
        return self.enable()

    def set_rate(self, rate: int) -> str:
        self._rate = rate
        if self._engine:
            self._engine.setProperty("rate", rate)
        return f"Speech rate set to {rate}."

    # ── Internal ──────────────────────────────────────────
    def _start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate",   self._rate)
            self._engine.setProperty("volume", self._volume)
            self._thread = threading.Thread(
                target=self._worker, daemon=True, name="tts_worker"
            )
            self._thread.start()
            log.info("TTS engine started.")
        except Exception as e:
            log.error(f"TTS init failed: {e}")
            self.enabled = False

    def _worker(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:       # poison pill
                break
            try:
                if self._engine and self.enabled:
                    self._engine.say(text)
                    self._engine.runAndWait()
            except Exception as e:
                log.error(f"TTS error: {e}")
            finally:
                self._queue.task_done()


# Singleton
TTS = TextToSpeech()
