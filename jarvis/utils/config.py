"""
utils/config.py
───────────────
Loads and provides access to config.json.
Access settings anywhere via: from utils.config import CFG
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


class _Config:
    """Singleton-style config loader. Dot-access to nested keys."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict = {}
        self.reload()

    # ── public API ────────────────────────────────────────
    def reload(self) -> None:
        """Re-read config.json from disk."""
        with open(self._path, "r", encoding="utf-8") as f:
            self._data = json.load(f)
        # Resolve relative paths to project root
        root = self._path.parent
        for key in ("data_dir", "logs_dir", "plugins_dir"):
            val = self._data.get(key, "")
            if val:
                self._data[key] = str(root / val)
        # Also resolve nested path values
        for section_key, nested_key in [
            ("memory", "long_term_file"),
            ("memory", "history_file"),
            ("logging", "file"),
        ]:
            raw = self._data.get(section_key, {}).get(nested_key, "")
            if raw and not os.path.isabs(raw):
                self._data[section_key][nested_key] = str(root / raw)

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Safe nested get.
        Example: CFG.get("ai", "model", default="qwen3:4b")
        """
        node = self._data
        for k in keys:
            if not isinstance(node, dict):
                return default
            node = node.get(k, default)  # type: ignore[assignment]
        return node

    # Convenient section shortcuts
    @property
    def ai(self) -> dict:
        return self._data.get("ai", {})

    @property
    def voice(self) -> dict:
        return self._data.get("voice", {})

    @property
    def safety(self) -> dict:
        return self._data.get("safety", {})

    @property
    def memory(self) -> dict:
        return self._data.get("memory", {})

    @property
    def logging(self) -> dict:
        return self._data.get("logging", {})

    @property
    def data_dir(self) -> Path:
        return Path(self._data.get("data_dir", "data"))

    @property
    def logs_dir(self) -> Path:
        return Path(self._data.get("logs_dir", "logs"))

    @property
    def plugins_dir(self) -> Path:
        return Path(self._data.get("plugins_dir", "plugins"))


# Create the dirs if they don't exist, then expose singleton
CFG = _Config(_CONFIG_PATH)

for _d in (CFG.data_dir, CFG.logs_dir, CFG.plugins_dir):
    _d.mkdir(parents=True, exist_ok=True)
