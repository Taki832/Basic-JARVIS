"""
ui/styles.py
────────────
All colour tokens and Qt stylesheet strings for the JARVIS UI.
Import: from ui.styles import COLORS, CSS
"""

from __future__ import annotations

# ── Colour tokens ─────────────────────────────────────────
COLORS: dict[str, str] = {
    "dark":  "#0d0d0d",
    "panel": "#141414",
    "card":  "#1a1a1a",
    "bord":  "#2a2a2a",
    "cyan":  "#00e5ff",
    "green": "#00e676",
    "red":   "#ff1744",
    "amber": "#ffc400",
    "text":  "#e0e0e0",
    "muted": "#616161",
    "warn_bg": "#1a0f00",
    "warn_bord": "#ff6f00",
}

_C = COLORS   # local alias for CSS f-strings below


# ── Stylesheet strings ────────────────────────────────────
class CSS:
    GLOBAL = f"""
QWidget {{
    background: {_C['dark']};
    color: {_C['text']};
    font-family: "Segoe UI", "SF Pro Display", "Inter", sans-serif;
    font-size: 13px;
}}
QScrollBar:vertical {{
    background: {_C['panel']};
    width: 6px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical {{
    background: {_C['bord']};
    border-radius: 3px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollArea {{ border: none; }}
"""

    INPUT = f"""
QLineEdit {{
    background: {_C['card']};
    color: {_C['text']};
    border: 1px solid {_C['bord']};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
    selection-background-color: {_C['cyan']};
}}
QLineEdit:focus {{
    border: 1px solid {_C['cyan']};
}}
"""

    INPUT_CONFIRM = f"""
QLineEdit {{
    background: {_C['warn_bg']};
    color: {_C['amber']};
    border: 1px solid {_C['warn_bord']};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 13px;
}}
QLineEdit:focus {{
    border: 1px solid {_C['amber']};
}}
"""

    SEND = f"""
QPushButton {{
    background: {_C['cyan']};
    color: #000;
    border: none;
    border-radius: 8px;
    padding: 10px 22px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton:hover  {{ background: #26c6da; }}
QPushButton:pressed {{ background: #00acc1; }}
QPushButton:disabled {{ background: {_C['bord']}; color: {_C['muted']}; }}
"""

    MIC = f"""
QPushButton {{
    background: {_C['card']};
    color: {_C['cyan']};
    border: 1px solid {_C['bord']};
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 16px;
}}
QPushButton:hover  {{ border-color: {_C['cyan']}; background: #1e2a2a; }}
QPushButton:pressed {{ background: {_C['panel']}; }}
QPushButton:disabled {{ color: {_C['muted']}; border-color: {_C['bord']}; }}
"""

    MIC_ACTIVE = f"""
QPushButton {{
    background: #1a0a00;
    color: {_C['amber']};
    border: 1px solid {_C['amber']};
    border-radius: 8px;
    padding: 10px 16px;
    font-size: 16px;
}}
"""
