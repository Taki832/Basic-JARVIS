"""
ui/workers.py
─────────────
Background QThread workers for AI inference and voice capture.

Rules:
  • Workers NEVER touch the UI directly.
  • All results delivered via Qt signals (thread-safe by Qt's queued connection).
  • Every exception is caught, logged with full traceback, and emitted as error signal.
  • AI object is validated at construction time — fails fast with a clear message.

Streaming guarantee
───────────────────
chat_stream() delivers content in two ways:
  A. via on_token callback  → one token.emit() per chunk  (streaming mode)
  B. via return value only  → on_token never fires         (non-streaming fallback)

Case B must not silently drop the response. If collected is empty after
chat_stream() returns but final has content, we emit final as a single
token so the UI streaming bubble is created and filled before done fires.
The UI therefore always receives: ≥1 token.emit() → done.emit().
"""

from __future__ import annotations

import inspect
import traceback

from PyQt5.QtCore import QObject, pyqtSignal


# ════════════════════════════════════════════════════════════
#  AI OBJECT RESOLVER
# ════════════════════════════════════════════════════════════
def _resolve_ai(ai_obj):
    """
    Accept either an AIEngine instance or (as a fallback) the AIEngine
    class itself. Always return a usable instance.

    In production: AI = AIEngine() is exported from core.ai_engine,
    so ai_obj will always be an instance. The class-branch is a safety net.
    """
    if ai_obj is None:
        raise TypeError("AI backend is None — backend may not have loaded yet.")

    # Instance: has chat_stream as a bound method → use as-is
    if hasattr(ai_obj, "chat_stream") and callable(ai_obj.chat_stream):
        return ai_obj

    # Class: instantiate once with a warning
    if inspect.isclass(ai_obj):
        import logging
        logging.getLogger(__name__).warning(
            "AI was passed as a class, not an instance. "
            "Instantiating now. Verify bootstrap_backend() in main_window.py."
        )
        return ai_obj()

    raise TypeError(
        f"AI object of type {type(ai_obj)} is neither an AIEngine "
        "instance nor the AIEngine class."
    )


# ════════════════════════════════════════════════════════════
#  AI WORKER
# ════════════════════════════════════════════════════════════
class AIWorker(QObject):
    """
    Dispatches one text command through the JARVIS backend.

    Pipeline:
      1. Command router  → if matched, emits done immediately (no tokens)
      2. AI chat_stream  → tokens arrive via on_token callback
         2a. Streaming worked → N token signals, then done
         2b. No tokens came  → reply emitted as single token, then done
         2c. Empty reply     → error signal emitted

    Signals:
        token(str)  — one streaming token from the LLM
        done(str)   — full assembled reply (always follows ≥1 token for AI path)
        error(str)  — human-readable error; done is NOT emitted on error
    """

    token = pyqtSignal(str)
    done  = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, text: str, router, ai, memory, tts) -> None:
        super().__init__()
        self._text   = text
        self._router = router
        self._memory = memory
        self._tts    = tts

        # Validate AI at construction — fail before thread starts
        try:
            self._ai = _resolve_ai(ai)
        except TypeError as exc:
            self._ai         = None
            self._init_error = str(exc)
        else:
            self._init_error = None

    def run(self) -> None:
        # ── Construction-time error ───────────────────────
        if self._init_error:
            self.error.emit(f"⚠ AI init error: {self._init_error}")
            return

        try:
            text = self._text.strip()
            if not text:
                self.done.emit("")
                return

            # ── 1. Command router ──────────────────────────
            response, handled = self._router.dispatch(text)
            if handled and response is not None:
                try:
                    self._tts.speak(response)
                except Exception:
                    pass   # TTS failure must never abort the reply
                self.done.emit(response)
                return

            # ── 2. AI streaming ────────────────────────────
            context = self._memory.get_context()
            self._memory.add_turn("user", text)

            collected: list[str] = []

            def _on_token(tok: str) -> None:
                if tok:
                    collected.append(tok)
                    self.token.emit(tok)

            # chat_stream() blocks until the model finishes.
            # on_token fires for each chunk IF Ollama returns a stream.
            # If Ollama returns a single non-streaming response, on_token
            # may never fire — we handle that below.
            reply = self._ai.chat_stream(text, context, on_token=_on_token)

            # Assemble final text: prefer collected (streaming),
            # fall back to return value (non-streaming).
            final = "".join(collected) or (reply or "").strip()

            # ── Fallback: no tokens fired but we have text ─
            # Emit the full reply as a single token so the UI streaming
            # bubble is created and visible before done fires.
            if not collected and final:
                print(
                    f"[AIWorker] chat_stream returned content but emitted no tokens. "
                    f"Emitting reply as single token ({len(final)} chars)."
                )
                self.token.emit(final)

            # ── Guard: completely empty response ───────────
            if not final:
                self.error.emit(
                    "⚠ Model returned an empty response. "
                    "Check that Ollama is running and the model is loaded."
                )
                return

            # ── Persist to memory and speak ────────────────
            if not final.startswith("⚠"):
                self._memory.add_turn("assistant", final)
                try:
                    self._tts.speak(final)
                except Exception:
                    pass

            self.done.emit(final)

        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[AIWorker] Unhandled exception:\n{tb}")
            self.error.emit(f"⚠ Unexpected error: {exc}")


# ════════════════════════════════════════════════════════════
#  VOICE WORKER
# ════════════════════════════════════════════════════════════
class VoiceWorker(QObject):
    """
    Captures one spoken command on a background thread.

    Signals:
        result(str)  — transcribed text (empty string = nothing heard)
        error(str)   — human-readable error message
    """

    result = pyqtSignal(str)
    error  = pyqtSignal(str)

    def __init__(self, listen_fn) -> None:
        super().__init__()
        if not callable(listen_fn):
            raise TypeError(
                f"listen_fn must be callable, got {type(listen_fn)}"
            )
        self._listen = listen_fn

    def run(self) -> None:
        try:
            text = self._listen()
            self.result.emit(text or "")
        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[VoiceWorker] Error:\n{tb}")
            self.error.emit(f"⚠ Mic error: {exc}")
