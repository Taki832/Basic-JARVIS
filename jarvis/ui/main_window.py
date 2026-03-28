"""
ui/main_window.py
─────────────────
JarvisWindow — the top-level PyQt5 window.

Responsibilities:
  • Build and wire all UI elements
  • Own the confirmation state machine (dangerous command guard)
  • Launch AI and Voice workers on QThreads
  • Route all signals back onto the main thread before touching widgets

Confirmation state machine
──────────────────────────
  _pending_cmd: str | None

  None      → normal dispatch mode
  str       → waiting for "yes" / "no" response

  On dangerous input:
    → set _pending_cmd = original_text
    → show warning bubble + colour the input field amber
    → lock the mic button (cannot voice-confirm, must type)

  On next send:
    → if "yes"  → execute _pending_cmd, clear state
    → anything else → cancel, clear state, show notice
    → either way: restore input to normal appearance

  Design guarantees:
    • One pending confirmation at a time (new dangerous cmd replaces old)
    • Confirmation loop cannot run indefinitely (any reply resolves it)
    • Mic disabled during confirmation (prevents accidental voice confirm)
    • Worker threads are never aware of the confirmation layer
"""

from __future__ import annotations

import threading
from typing import Optional

from PyQt5.QtCore    import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui     import QColor, QPalette
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QScrollArea, QSizePolicy, QFrame,
)

from ui.styles     import COLORS, CSS
from ui.components import ChatBubble, StreamingBubble, ThinkingBubble, StatusBar
from ui.workers    import AIWorker, VoiceWorker

_C = COLORS


# ════════════════════════════════════════════════════════════
#  DANGEROUS COMMAND DETECTOR
# ════════════════════════════════════════════════════════════
_DANGEROUS_KEYWORDS: frozenset[str] = frozenset({
    "shutdown", "restart", "reboot",
    "delete", "remove", "format",
    "kill",
})


def _is_dangerous(text: str) -> bool:
    """
    Returns True if the lowercased text contains a dangerous keyword.
    Checked BEFORE dispatching; does not interact with the command router.
    """
    lower = text.lower()
    return any(kw in lower for kw in _DANGEROUS_KEYWORDS)


# ════════════════════════════════════════════════════════════
#  BACKEND REGISTRY  (module-level, shared with entry point)
# ════════════════════════════════════════════════════════════
class _BackendHandle:
    """Thin container for backend singletons filled by bootstrap."""
    ai        = None
    router    = None
    memory    = None
    tts       = None
    listen_fn = None
    ready     = False


BE = _BackendHandle()


def bootstrap_backend() -> bool:
    """
    Import and initialise the JARVIS backend.
    Called once on a daemon thread at startup.
    Returns True on success.
    """
    try:
        import modules.system_control   # noqa: F401
        import modules.file_ops         # noqa: F401
        import modules.web_ops          # noqa: F401
        import modules.automation       # noqa: F401

        from core.ai_engine       import AI
        from core.command_router  import registry, ROUTER
        from core.memory          import MEMORY
        from voice.text_to_speech import TTS
        from voice.speech_to_text import listen_for_command
        from utils.config         import CFG

        _register_meta_commands(registry, TTS, CFG)
        registry.load_plugins()

        BE.ai        = AI
        BE.router    = ROUTER
        BE.memory    = MEMORY
        BE.tts       = TTS
        BE.listen_fn = listen_for_command
        BE.ready     = True
        return True

    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Backend bootstrap failed: {exc}")
        return False


def _register_meta_commands(registry, TTS, CFG) -> None:
    from core.command_router import registry as reg

    # Guard against re-registration if window is re-created
    existing = {c.description for c in reg._commands}

    if "Show all available commands" not in existing:
        @reg.register(
            triggers=["help", "commands", "what can you do", "show commands"],
            description="Show all available commands",
            category="Meta",
        )
        def show_help() -> str:
            return reg.help_text()

    if "Enable text-to-speech output" not in existing:
        @reg.register(
            triggers=["enable voice", "turn on voice", "voice on"],
            description="Enable text-to-speech output",
            category="Voice",
        )
        def enable_tts() -> str:
            return TTS.enable()

    if "Disable text-to-speech" not in existing:
        @reg.register(
            triggers=["disable voice", "turn off voice", "voice off"],
            description="Disable text-to-speech",
            category="Voice",
        )
        def disable_tts() -> str:
            return TTS.disable()

    if "JARVIS runtime status" not in existing:
        @reg.register(
            triggers=["status", "jarvis status"],
            description="JARVIS runtime status",
            category="Meta",
        )
        def jarvis_status() -> str:
            import datetime
            return "\n".join([
                "⚡  JARVIS Status",
                "─" * 30,
                f"Model    : {CFG.ai.get('model')}",
                f"Commands : {len(reg)}",
                f"TTS      : {'ON' if TTS.enabled else 'OFF'}",
                f"Time     : {datetime.datetime.now().strftime('%H:%M:%S')}",
            ])

    if "Reload config.json" not in existing:
        @reg.register(
            triggers=["reload config", "refresh config"],
            description="Reload config.json",
            category="Meta",
        )
        def reload_cfg() -> str:
            CFG.reload()
            return "Configuration reloaded."


# ════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ════════════════════════════════════════════════════════════
class JarvisWindow(QMainWindow):
    # All signals emitted by worker threads, consumed on main thread
    _sig_user_msg    = pyqtSignal(str)
    _sig_ai_token    = pyqtSignal(str)
    _sig_ai_done     = pyqtSignal(str)
    _sig_ai_error    = pyqtSignal(str)
    _sig_voice_done  = pyqtSignal(str)
    _sig_voice_error = pyqtSignal(str)
    _sig_backend_ready = pyqtSignal(bool)   # emitted from daemon thread → received on main thread

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JARVIS  ⚡  Local AI Assistant")
        self.resize(840, 660)
        self.setMinimumSize(560, 420)

        # Runtime state
        self._busy: bool                              = False
        self._pending_cmd: Optional[str]              = None  # confirmation guard
        self._ai_thread: Optional[QThread]            = None
        self._voice_thread: Optional[QThread]         = None
        self._streaming_bubble: Optional[StreamingBubble] = None
        self._thinking_bubble: Optional[ThinkingBubble]   = None

        self._build_ui()
        self._connect_signals()
        self._start_backend()

    # ════════════════════════════════════════════════════════
    #  UI CONSTRUCTION
    # ════════════════════════════════════════════════════════
    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._build_title_bar())
        layout.addWidget(self._build_chat_area(), stretch=1)
        layout.addWidget(self._build_input_row())
        layout.addWidget(self._build_status_bar())

    def _build_title_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(48)
        bar.setStyleSheet(
            f"background: {_C['panel']}; border-bottom: 1px solid {_C['bord']};"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 0, 20, 0)

        title = QLabel("⚡  JARVIS")
        title.setStyleSheet(
            f"color: {_C['cyan']}; font-size: 15px; font-weight: 700; letter-spacing: 2px;"
        )
        sub = QLabel("Local AI Assistant")
        sub.setStyleSheet(f"color: {_C['muted']}; font-size: 11px;")

        row.addWidget(title)
        row.addSpacing(10)
        row.addWidget(sub)
        row.addStretch()
        return bar

    def _build_chat_area(self) -> QScrollArea:
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._chat_container = QWidget()
        self._chat_layout    = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(0, 12, 0, 12)
        self._chat_layout.setSpacing(6)
        self._chat_layout.addStretch()

        self._scroll.setWidget(self._chat_container)
        self._add_system_notice("JARVIS online.  Type a message or press 🎤 to speak.")
        return self._scroll

    def _build_input_row(self) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet(
            f"background: {_C['panel']}; border-top: 1px solid {_C['bord']};"
        )
        wrap.setFixedHeight(64)

        row = QHBoxLayout(wrap)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(8)

        self._mic_btn = QPushButton("🎤")
        self._mic_btn.setFixedSize(44, 44)
        self._mic_btn.setStyleSheet(CSS.MIC)
        self._mic_btn.clicked.connect(self._on_voice)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Message JARVIS…")
        self._input.setStyleSheet(CSS.INPUT)
        self._input.returnPressed.connect(self._on_send)

        self._send_btn = QPushButton("Send")
        self._send_btn.setFixedSize(80, 44)
        self._send_btn.setStyleSheet(CSS.SEND)
        self._send_btn.clicked.connect(self._on_send)

        row.addWidget(self._mic_btn)
        row.addWidget(self._input, stretch=1)
        row.addWidget(self._send_btn)
        return wrap

    def _build_status_bar(self) -> StatusBar:
        self._status = StatusBar()
        return self._status

    # ════════════════════════════════════════════════════════
    #  SIGNAL WIRING
    # ════════════════════════════════════════════════════════
    def _connect_signals(self) -> None:
        self._sig_user_msg.connect(self._add_user_bubble)
        self._sig_ai_token.connect(self._on_ai_token)
        self._sig_ai_done.connect(self._on_ai_done)
        self._sig_ai_error.connect(self._on_ai_error)
        self._sig_voice_done.connect(self._on_voice_done)
        self._sig_voice_error.connect(self._on_voice_error)

    # ════════════════════════════════════════════════════════
    #  BACKEND STARTUP
    # ════════════════════════════════════════════════════════
    def _start_backend(self) -> None:
        """
        Bootstrap the backend on a daemon thread.

        We use a private pyqtSignal (_sig_backend_ready) to deliver
        the result safely to the main thread — QTimer.singleShot
        from a non-Qt thread is not guaranteed to fire on all platforms.
        """
        self._sig_backend_ready.connect(self._on_backend_ready)

        def _init() -> None:
            ok = bootstrap_backend()
            self._sig_backend_ready.emit(ok)

        threading.Thread(target=_init, daemon=True, name="backend_init").start()

    def _on_backend_ready(self, ok: bool) -> None:
        self._status.set_ai(ok)
        if ok:
            try:
                from utils.config import CFG
                self._status.set_model(CFG.ai.get("model", ""))
            except Exception:
                pass
            self._add_system_notice("Backend ready.")
        else:
            self._add_system_notice(
                "⚠ Backend failed to load. Check that Ollama is running."
            )

    # ════════════════════════════════════════════════════════
    #  CHAT HELPERS
    # ════════════════════════════════════════════════════════
    def _insert_widget(self, widget: QWidget) -> None:
        """Insert widget just before the terminal stretch item."""
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, widget)
        self._scroll_to_bottom()

    def _add_user_bubble(self, text: str) -> None:
        self._insert_widget(ChatBubble("user", text))

    def _add_jarvis_bubble(self, text: str) -> None:
        self._insert_widget(ChatBubble("jarvis", text))

    def _add_warning_bubble(self, text: str) -> None:
        self._insert_widget(ChatBubble("warning", text))

    def _add_system_notice(self, text: str) -> None:
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"color: {_C['muted']}; font-size: 11px; padding: 6px 0;"
        )
        self._insert_widget(lbl)

    def _begin_thinking(self) -> None:
        self._thinking_bubble = ThinkingBubble()
        self._insert_widget(self._thinking_bubble)

    def _end_thinking(self) -> None:
        if self._thinking_bubble:
            self._thinking_bubble.stop()
            self._thinking_bubble.setParent(None)
            self._thinking_bubble = None

    def _begin_streaming(self) -> None:
        self._end_thinking()
        self._streaming_bubble = StreamingBubble()
        self._insert_widget(self._streaming_bubble)

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(30, lambda: (
            self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()
            )
        ))

    # ════════════════════════════════════════════════════════
    #  CONFIRMATION STATE MACHINE
    # ════════════════════════════════════════════════════════
    def _enter_confirm_mode(self, original_text: str) -> None:
        """
        Store the dangerous command and prompt the user for confirmation.
        Replaces any previously pending confirmation (no infinite loop).
        """
        self._pending_cmd = original_text
        self._input.setStyleSheet(CSS.INPUT_CONFIRM)
        self._input.setPlaceholderText("Type YES to confirm, or anything else to cancel…")
        self._mic_btn.setEnabled(False)   # no voice confirmation allowed
        self._add_warning_bubble(
            f'⚠  Did you mean to run: "{original_text}"\n\n'
            f"Type  YES  to confirm  —  or anything else to cancel."
        )

    def _resolve_confirmation(self, reply: str) -> None:
        """
        Consume the pending confirmation.
        Called exactly once per confirmation cycle — cannot loop.
        """
        cmd = self._pending_cmd
        self._pending_cmd = None

        # Restore input appearance unconditionally
        self._input.setStyleSheet(CSS.INPUT)
        self._input.setPlaceholderText("Message JARVIS…")
        self._mic_btn.setEnabled(True)

        if reply.strip().lower() == "yes" and cmd:
            self._add_system_notice(f"✓ Confirmed. Executing: {cmd}")
            self._execute(cmd)
        else:
            self._add_system_notice("✗ Command cancelled.")
            # Re-enable controls that were locked before we got here
            self._busy = False
            self._set_controls_enabled(True)

    # ════════════════════════════════════════════════════════
    #  SEND HANDLER
    # ════════════════════════════════════════════════════════
    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text or self._busy:
            return
        self._input.clear()

        # ── Confirmation reply ────────────────────────────
        if self._pending_cmd is not None:
            self._sig_user_msg.emit(text)
            self._resolve_confirmation(text)
            return

        # ── Normal dispatch ───────────────────────────────
        self._sig_user_msg.emit(text)

        if _is_dangerous(text):
            self._enter_confirm_mode(text)
        else:
            self._execute(text)

    # ════════════════════════════════════════════════════════
    #  EXECUTE  (actual dispatch to backend)
    # ════════════════════════════════════════════════════════
    def _execute(self, text: str) -> None:
        if not BE.ready:
            self._add_system_notice("⚠ Backend not ready yet.")
            return

        self._busy = True
        self._set_controls_enabled(False)
        self._begin_thinking()

        worker = AIWorker(
            text   = text,
            router = BE.router,
            ai     = BE.ai,
            memory = BE.memory,
            tts    = BE.tts,
        )
        thread = QThread()
        worker.moveToThread(thread)

        worker.token.connect(self._sig_ai_token)
        worker.done.connect(self._sig_ai_done)
        worker.error.connect(self._sig_ai_error)

        thread.started.connect(worker.run)
        worker.done.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        self._ai_thread = thread
        thread.start()

    # ════════════════════════════════════════════════════════
    #  AI SIGNAL HANDLERS  (main thread only)
    # ════════════════════════════════════════════════════════
    def _on_ai_token(self, tok: str) -> None:
        if self._thinking_bubble:
            self._begin_streaming()
        if self._streaming_bubble:
            self._streaming_bubble.append_token(tok)
            self._scroll_to_bottom()

    def _on_ai_done(self, reply: str) -> None:
        self._end_thinking()
        if self._streaming_bubble:
            # Normal streaming path: finalise whatever tokens arrived
            self._streaming_bubble.finalise()
            self._streaming_bubble = None
        elif reply:
            # Non-streaming path: command router reply or fallback token
            # was emitted as a single token → _on_ai_token already created
            # _streaming_bubble, so we only land here for instant commands.
            self._add_jarvis_bubble(reply)
        # Empty reply: error was already shown via _on_ai_error — do nothing.
        self._busy = False
        self._set_controls_enabled(True)
        self._input.setFocus()
        self._scroll_to_bottom()

    def _on_ai_error(self, msg: str) -> None:
        self._end_thinking()
        if self._streaming_bubble:
            self._streaming_bubble.finalise()
            self._streaming_bubble = None
        self._add_jarvis_bubble(msg)
        self._status.set_ai(False)
        self._busy = False
        self._set_controls_enabled(True)

    # ════════════════════════════════════════════════════════
    #  VOICE
    # ════════════════════════════════════════════════════════
    def _on_voice(self) -> None:
        if self._busy or self._pending_cmd is not None:
            # Never allow voice during a confirmation prompt
            return
        if not BE.listen_fn:
            self._add_system_notice("⚠ Voice system not available.")
            return

        self._busy = True
        self._set_controls_enabled(False)
        self._mic_btn.setEnabled(True)    # visually keep mic lit while active
        self._mic_btn.setStyleSheet(CSS.MIC_ACTIVE)
        self._mic_btn.setText("⏺")
        self._status.set_mic("listening")
        self._add_system_notice("🎤 Listening…")

        worker = VoiceWorker(BE.listen_fn)
        thread = QThread()
        worker.moveToThread(thread)

        worker.result.connect(self._sig_voice_done)
        worker.error.connect(self._sig_voice_error)

        thread.started.connect(worker.run)
        worker.result.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        self._voice_thread = thread
        thread.start()

    def _on_voice_done(self, text: str) -> None:
        self._mic_btn.setStyleSheet(CSS.MIC)
        self._mic_btn.setText("🎤")
        self._status.set_mic("idle")

        if not text:
            self._add_system_notice("(No speech detected)")
            self._busy = False
            self._set_controls_enabled(True)
            return

        self._sig_user_msg.emit(text)
        self._status.set_mic("processing")

        if _is_dangerous(text):
            self._busy = False
            self._set_controls_enabled(True)
            self._enter_confirm_mode(text)
        else:
            self._execute(text)

    def _on_voice_error(self, msg: str) -> None:
        self._mic_btn.setStyleSheet(CSS.MIC)
        self._mic_btn.setText("🎤")
        self._status.set_mic("idle")
        self._add_jarvis_bubble(msg)
        self._busy = False
        self._set_controls_enabled(True)

    # ════════════════════════════════════════════════════════
    #  UTILITY
    # ════════════════════════════════════════════════════════
    def _set_controls_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        # Only re-enable mic when not in confirmation mode
        if enabled and self._pending_cmd is None:
            self._mic_btn.setEnabled(True)

    def closeEvent(self, event) -> None:
        for t in (self._ai_thread, self._voice_thread):
            if t and t.isRunning():
                t.quit()
                t.wait(500)
        event.accept()
