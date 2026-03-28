"""
uii.py
─────
JARVIS Desktop UI — entry point.

Run from the project root:
    python ui.py

Requirements:
    pip install PyQt5
"""

from __future__ import annotations

import sys

try:
    from PyQt5.QtCore    import Qt
    from PyQt5.QtGui     import QColor, QPalette
    from PyQt5.QtWidgets import QApplication
except ImportError:
    print("[ERROR] PyQt5 not installed — run: pip install PyQt5")
    sys.exit(1)

from ui.main_window import JarvisWindow
from ui.styles      import COLORS, CSS

_C = COLORS


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")
    app.setStyle("Fusion")
    app.setStyleSheet(CSS.GLOBAL)

    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(_C["dark"]))
    pal.setColor(QPalette.WindowText,      QColor(_C["text"]))
    pal.setColor(QPalette.Base,            QColor(_C["card"]))
    pal.setColor(QPalette.AlternateBase,   QColor(_C["panel"]))
    pal.setColor(QPalette.Text,            QColor(_C["text"]))
    pal.setColor(QPalette.ButtonText,      QColor(_C["text"]))
    pal.setColor(QPalette.Highlight,       QColor(_C["cyan"]))
    pal.setColor(QPalette.HighlightedText, QColor("#000000"))
    app.setPalette(pal)

    window = JarvisWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
