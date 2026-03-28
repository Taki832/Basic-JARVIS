"""
core/ai_engine.py
─────────────────
Ollama wrapper for JARVIS.

Fixes vs previous version:
  • _check_ollama() runs on a daemon thread — never blocks __init__
  • chat_stream() does NOT hold the lock during streaming (deadlock fix)
  • Console print only fires when no on_token callback (UI-mode clean)
  • Full traceback on every exception
  • Defensive chunk access throughout
"""

from __future__ import annotations

import inspect
import threading
import traceback
from typing import Callable, Optional

from utils.config import CFG
from utils.logger import get_logger

log = get_logger(__name__)


class AIEngine:
    """
    Wraps Ollama chat completions.

    Singleton is exported as:  AI = AIEngine()
    Always an instance — never call AI() again.
    """

    def __init__(self) -> None:
        ai_cfg             = CFG.ai
        self.model         = ai_cfg.get("model",         "qwen3:4b")
        self.max_tokens    = ai_cfg.get("max_tokens",    1024)
        self.temperature   = ai_cfg.get("temperature",   0.7)
        self.system_prompt = ai_cfg.get("system_prompt", "You are JARVIS.")
        self._lock         = threading.Lock()
        self.ollama_ready  = False   # set True by _check_ollama thread

        # Non-blocking: probe Ollama on a daemon thread so __init__ returns fast
        t = threading.Thread(
            target=self._check_ollama,
            daemon=True,
            name="ollama_probe",
        )
        t.start()
        log.info(f"AIEngine initialised — model: {self.model}")

    # ── Public: blocking chat ─────────────────────────────
    def chat(
        self,
        user_message:    str,
        context:         Optional[list[dict]] = None,
        system_override: Optional[str]        = None,
    ) -> str:
        """Blocking call; returns the full reply string."""
        messages = self._build_messages(user_message, context, system_override)
        try:
            import ollama
            with self._lock:
                response = ollama.chat(
                    model=self.model,
                    messages=messages,
                    options={
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                )
            reply = response.get("message", {}).get("content", "") \
                if isinstance(response, dict) \
                else getattr(getattr(response, "message", None), "content", "")
            log.info(f"AI reply ({len(reply)} chars)")
            return reply or "⚠ Empty response from model."
        except Exception as exc:
            log.error(f"Ollama chat error: {exc}\n{traceback.format_exc()}")
            return f"⚠ AI engine error: {exc}"

    # ── Public: streaming chat ────────────────────────────
    def chat_stream(
        self,
        user_message: str,
        context:      Optional[list[dict]] = None,
        on_token:     Optional[Callable[[str], None]] = None,
    ) -> str:
        """
        Streams response token-by-token.

        Critical design:
          • Lock is acquired ONLY to start the generator, then released.
            Streaming itself is lock-free — prevents deadlocks.
          • Console output suppressed when on_token is provided (UI mode).
          • Always returns a non-None string.
        """
        messages   = self._build_messages(user_message, context)
        full_reply = ""

        try:
            import ollama

            ui_mode = on_token is not None

            if not ui_mode:
                print("Jarvis: ", end="", flush=True)

            # Acquire lock only to create the generator, then release
            with self._lock:
                stream = ollama.chat(
                    model=self.model,
                    messages=messages,
                    stream=True,
                    options={
                        "temperature": self.temperature,
                        "num_predict": self.max_tokens,
                    },
                )

            # Iterate outside the lock — stream holds its own connection
            for chunk in stream:
                # Safe access for both dict and response-object chunk formats
                if isinstance(chunk, dict):
                    token = chunk.get("message", {}).get("content", "")
                else:
                    msg   = getattr(chunk, "message", None)
                    token = getattr(msg, "content", "") if msg else ""

                if not token:
                    continue

                full_reply += token

                if ui_mode:
                    on_token(token)
                else:
                    print(token, end="", flush=True)

            if not ui_mode:
                print()  # terminal newline

            log.info(f"AI stream reply ({len(full_reply)} chars)")
            return full_reply if full_reply else "⚠ Model returned an empty response."

        except Exception as exc:
            log.error(f"Ollama stream error: {exc}\n{traceback.format_exc()}")
            if not on_token:
                print()
            # Return partial reply if we got something before the error
            return full_reply if full_reply else f"⚠ AI engine error: {exc}"

    # ── Public: async (fire-and-callback) ────────────────
    def chat_async(
        self,
        user_message: str,
        context:      Optional[list[dict]] = None,
        on_done:      Optional[Callable[[str], None]] = None,
        on_error:     Optional[Callable[[Exception], None]] = None,
    ) -> threading.Thread:
        """Non-blocking: runs chat() on a daemon thread."""
        def _run():
            try:
                reply = self.chat(user_message, context)
                if on_done:
                    on_done(reply)
            except Exception as exc:
                log.error(f"chat_async error: {exc}\n{traceback.format_exc()}")
                if on_error:
                    on_error(exc)

        t = threading.Thread(target=_run, daemon=True, name="ai_async")
        t.start()
        return t

    # ── Private ───────────────────────────────────────────
    def _build_messages(
        self,
        user_message:    str,
        context:         Optional[list[dict]],
        system_override: Optional[str] = None,
    ) -> list[dict]:
        sys_text = system_override or self.system_prompt
        msgs     = [{"role": "system", "content": sys_text}]
        if context:
            msgs.extend(context)
        msgs.append({"role": "user", "content": user_message})
        return msgs

    def _check_ollama(self) -> None:
        """
        Probe Ollama for reachability and model availability.
        Runs on a daemon thread — never blocks the caller.
        Sets self.ollama_ready = True on success.
        """
        try:
            import ollama
            response  = ollama.list()
            raw_models = (
                response.get("models", [])
                if isinstance(response, dict)
                else getattr(response, "models", [])
            )
            names: list[str] = []
            for m in raw_models:
                if isinstance(m, dict):
                    name = m.get("name") or m.get("model") or ""
                else:
                    name = getattr(m, "name", None) or getattr(m, "model", None) or ""
                if name:
                    names.append(str(name))

            if any(self.model in n for n in names):
                self.ollama_ready = True
                log.info(f"Ollama ready. Model '{self.model}' found.")
            else:
                log.warning(
                    f"Model '{self.model}' not in local list: {names}. "
                    f"Run: ollama pull {self.model}"
                )
                print(
                    f"[WARN] Model '{self.model}' not found locally. "
                    f"Run: ollama pull {self.model}"
                )
        except Exception as exc:
            log.error(f"Ollama probe failed: {exc}\n{traceback.format_exc()}")
            print(f"[WARN] Ollama not reachable: {exc}")


# ── Module-level singleton ────────────────────────────────
# AI is ALWAYS an instance of AIEngine.
# Import as:  from core.ai_engine import AI
# Use as:     AI.chat(...)  or  AI.chat_stream(...)
# NEVER call: AI()  — it is not a class at this point.
AI = AIEngine()
