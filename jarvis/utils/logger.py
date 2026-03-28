"""
utils/logger.py
───────────────
Centralised logging setup.
Import and use:
    from utils.logger import get_logger
    log = get_logger(__name__)
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from utils.config import CFG


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger, configuring the root logger on first call.
    Subsequent calls return the already-configured child logger.
    """
    root = logging.getLogger()
    if not root.handlers:
        _configure_root_logger()
    return logging.getLogger(name)


def _configure_root_logger() -> None:
    cfg      = CFG.logging
    level    = getattr(logging, cfg.get("level", "INFO").upper(), logging.INFO)
    log_file = Path(cfg.get("file", "logs/jarvis.log"))
    log_file.parent.mkdir(parents=True, exist_ok=True)

    fmt     = "%(asctime)s  [%(levelname)-8s]  %(name)-25s  %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)

    # Rotating file handler (5 MB × 3 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=cfg.get("max_bytes", 5_242_880),
        backupCount=cfg.get("backup_count", 3),
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Console — only WARNING and above to keep terminal clean
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)
