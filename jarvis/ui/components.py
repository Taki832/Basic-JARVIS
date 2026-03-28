"""
ui/components.py
────────────────
Reusable PyQt5 widgets for the JARVIS chat interface.

  ChatBubble       — finalised message bubble (user or jarvis)
  StreamingBubble  — jarvis bubble that grows token-by-token
  ThinkingBubble   — animated "🤖 Thinking..." placeholder
  StatusBar        — bottom bar: AI status, mic state, model name
"""

from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore  import Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QFrame, QSizePolicy,
)

from ui.styles import COLORS

_C = COLORS


# ════════════════════════════════════════════════════════════
#  CHAT BUBBLE
# ════════════════════════════════════════════════════════════
class ChatBubble(QWidget):
    """
    A single finalised message in the chat area.

    role: "user" | "jarvis" | "warning"
    """

    _ROLE_CFG: dict[str, dict] = {
        "user": {
            "label":    "You",
            "label_color": "#80deea",
            "bg":       "#1c2b2f",
            "align":    "right",
        },
        "jarvis": {
            "label":    "Jarvis",
            "label_color": _C["cyan"],
            "bg":       _C["card"],
            "align":    "left",
        },
        "warning": {
            "label":    "⚠ Jarvis",
            "label_color": _C["amber"],
            "bg":       _C["warn_bg"],
            "align":    "left",
        },
    }

    def __init__(self, role: str, text: str, parent=None) -> None:
        super().__init__(parent)
        cfg = self._ROLE_CFG.get(role, self._ROLE_CFG["jarvis"])

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("bubble")
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        frame.setMaximumWidth(700)

        bord_color = _C["warn_bord"] if role == "warning" else _C["bord"]
        frame.setStyleSheet(
            f"QFrame#bubble {{ background: {cfg['bg']}; border-radius: 10px;"
            f" border: 1px solid {bord_color}; }}"
        )

        inner = QVBoxLayout(frame)
        inner.setContentsMargins(12, 8, 12, 8)
        inner.setSpacing(3)

        role_lbl = QLabel(cfg["label"])
        role_lbl.setStyleSheet(
            f"color: {cfg['label_color']}; font-size: 11px; font-weight: 600;"
        )

        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        msg.setStyleSheet(
            f"color: {_C['text']}; font-size: 13px; line-height: 1.5;"
        )

        ts = QLabel(datetime.now().strftime("%H:%M"))
        ts.setStyleSheet(f"color: {_C['muted']}; font-size: 10px;")

        inner.addWidget(role_lbl)
        inner.addWidget(msg)
        inner.addWidget(ts)

        if cfg["align"] == "right":
            outer.addStretch()
            outer.addWidget(frame)
        else:
            outer.addWidget(frame)
            outer.addStretch()


# ════════════════════════════════════════════════════════════
#  STREAMING BUBBLE
# ════════════════════════════════════════════════════════════
class StreamingBubble(QWidget):
    """
    A Jarvis bubble whose text accumulates token-by-token.
    Call append_token() on each incoming token, finalise() when done.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(0)

        frame = QFrame()
        frame.setObjectName("bubble")
        frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Minimum)
        frame.setMaximumWidth(700)
        frame.setStyleSheet(
            f"QFrame#bubble {{ background: {_C['card']}; border-radius: 10px;"
            f" border: 1px solid {_C['bord']}; }}"
        )

        inner = QVBoxLayout(frame)
        inner.setContentsMargins(12, 8, 12, 8)
        inner.setSpacing(3)

        role_lbl = QLabel("Jarvis")
        role_lbl.setStyleSheet(
            f"color: {_C['cyan']}; font-size: 11px; font-weight: 600;"
        )

        self._msg = QLabel("▌")
        self._msg.setWordWrap(True)
        self._msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._msg.setStyleSheet(
            f"color: {_C['text']}; font-size: 13px; line-height: 1.5;"
        )

        self._ts = QLabel(datetime.now().strftime("%H:%M"))
        self._ts.setStyleSheet(f"color: {_C['muted']}; font-size: 10px;")

        inner.addWidget(role_lbl)
        inner.addWidget(self._msg)
        inner.addWidget(self._ts)

        outer.addWidget(frame)
        outer.addStretch()

        self._text = ""

    def append_token(self, tok: str) -> None:
        self._text += tok
        self._msg.setText(self._text + "▌")

    def finalise(self) -> None:
        self._msg.setText(self._text or "(no response)")


# ════════════════════════════════════════════════════════════
#  THINKING BUBBLE
# ════════════════════════════════════════════════════════════
class ThinkingBubble(QWidget):
    """
    Animated "🤖 Thinking..." indicator shown before AI streams.
    Automatically cycles through dot states.
    """

    _FRAMES = ["🤖 Thinking", "🤖 Thinking.", "🤖 Thinking..", "🤖 Thinking..."]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(0)

        self._lbl = QLabel(self._FRAMES[0])
        self._lbl.setStyleSheet(
            f"color: {_C['muted']}; font-size: 12px; font-style: italic; padding: 6px 0;"
        )
        outer.addWidget(self._lbl)
        outer.addStretch()

        self._frame_idx = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(400)

    def _tick(self) -> None:
        self._frame_idx = (self._frame_idx + 1) % len(self._FRAMES)
        self._lbl.setText(self._FRAMES[self._frame_idx])

    def stop(self) -> None:
        self._timer.stop()


# ════════════════════════════════════════════════════════════
#  STATUS BAR
# ════════════════════════════════════════════════════════════
class StatusBar(QWidget):
    """
    Fixed-height footer showing AI connection, mic state, and model name.
    """

    _MIC_STATES: dict[str, tuple[str, str]] = {
        "idle":       (_C["muted"], "Mic: Idle"),
        "listening":  (_C["amber"], "Mic: Listening…"),
        "processing": (_C["cyan"],  "Mic: Processing…"),
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setStyleSheet(
            f"background: {_C['panel']}; border-top: 1px solid {_C['bord']};"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 0, 16, 0)
        row.setSpacing(20)

        self._ai_dot  = QLabel("●")
        self._ai_lbl  = QLabel("AI: Connecting…")
        self._mic_dot = QLabel("●")
        self._mic_lbl = QLabel("Mic: Idle")
        self._model_lbl = QLabel("")

        for dot in (self._ai_dot, self._mic_dot):
            dot.setStyleSheet(f"color: {_C['muted']}; font-size: 10px;")
            dot.setFixedWidth(12)

        for lbl in (self._ai_lbl, self._mic_lbl):
            lbl.setStyleSheet(f"color: {_C['muted']}; font-size: 11px;")

        self._model_lbl.setStyleSheet(f"color: {_C['muted']}; font-size: 11px;")

        row.addWidget(self._ai_dot)
        row.addWidget(self._ai_lbl)
        row.addWidget(self._mic_dot)
        row.addWidget(self._mic_lbl)
        row.addStretch()
        row.addWidget(self._model_lbl)

    def set_ai(self, connected: bool) -> None:
        color = _C["green"] if connected else _C["red"]
        label = "AI: Connected" if connected else "AI: Error"
        self._ai_dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self._ai_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._ai_lbl.setText(label)

    def set_mic(self, state: str) -> None:
        color, text = self._MIC_STATES.get(state, (
            _C["muted"], "Mic: Idle"
        ))
        self._mic_dot.setStyleSheet(f"color: {color}; font-size: 10px;")
        self._mic_lbl.setStyleSheet(f"color: {color}; font-size: 11px;")
        self._mic_lbl.setText(text)

    def set_model(self, model: str) -> None:
        self._model_lbl.setText(model)
