"""
core/memory.py
──────────────
Two-tier memory system:

  ShortTermMemory  — in-RAM conversation turns for AI context
  LongTermMemory   — persistent JSON store for preferences,
                     facts the user wants remembered, and
                     session summaries

Both are accessible through the single MemoryManager class.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from utils.config import CFG
from utils.logger import get_logger

log = get_logger(__name__)


# ════════════════════════════════════════════════════════════
#  SHORT-TERM  (conversation context)
# ════════════════════════════════════════════════════════════
class ShortTermMemory:
    """
    Keeps the last N turn-pairs for the AI chat context.
    Each turn: {"role": "user"|"assistant", "content": "..."}
    """

    def __init__(self, max_turns: int = 20) -> None:
        self._turns: list[dict] = []
        self.max_turns = max_turns

    def add(self, role: str, content: str) -> None:
        self._turns.append({"role": role, "content": content})
        # Keep only the most recent max_turns * 2 messages
        limit = self.max_turns * 2
        if len(self._turns) > limit:
            self._turns = self._turns[-limit:]

    def get_context(self) -> list[dict]:
        return list(self._turns)

    def clear(self) -> None:
        self._turns.clear()
        log.info("Short-term memory cleared.")

    def __len__(self) -> int:
        return len(self._turns)


# ════════════════════════════════════════════════════════════
#  LONG-TERM  (persistent JSON)
# ════════════════════════════════════════════════════════════
class LongTermMemory:
    """
    Persists structured data to a JSON file.

    Schema:
    {
      "preferences": { "key": "value", ... },
      "facts":       [ {"fact": "...", "ts": 1234567890}, ... ],
      "sessions":    [ {"date": "...", "summary": "..."}, ... ]
    }
    """

    def __init__(self, filepath: str | Path) -> None:
        self._path = Path(filepath)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict = self._load()

    # ── Persistence ───────────────────────────────────────
    def _load(self) -> dict:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log.error(f"Failed to load long-term memory: {e}")
        return {"preferences": {}, "facts": [], "sessions": []}

    def save(self) -> str:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            log.info("Long-term memory saved.")
            return f"Memory saved to {self._path}"
        except OSError as e:
            log.error(f"Memory save failed: {e}")
            return f"Memory save failed: {e}"

    # ── Preferences ───────────────────────────────────────
    def set_preference(self, key: str, value: Any) -> str:
        self._data["preferences"][key.lower()] = value
        self.save()
        return f"Preference saved — {key}: {value}"

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self._data["preferences"].get(key.lower(), default)

    def list_preferences(self) -> str:
        prefs = self._data["preferences"]
        if not prefs:
            return "No preferences stored."
        lines = [f"  {k}: {v}" for k, v in prefs.items()]
        return "Stored preferences:\n" + "\n".join(lines)

    # ── Facts ─────────────────────────────────────────────
    def remember_fact(self, fact: str) -> str:
        entry = {"fact": fact, "ts": int(time.time())}
        self._data["facts"].append(entry)
        self.save()
        return f"Noted: {fact}"

    def recall_facts(self, keyword: str = "") -> str:
        facts = self._data["facts"]
        if keyword:
            facts = [f for f in facts if keyword.lower() in f["fact"].lower()]
        if not facts:
            return "Nothing found in long-term memory."
        lines = [f"  • {f['fact']}" for f in facts[-20:]]
        return f"I remember ({len(facts)} entries):\n" + "\n".join(lines)

    def forget_fact(self, keyword: str) -> str:
        before = len(self._data["facts"])
        self._data["facts"] = [
            f for f in self._data["facts"]
            if keyword.lower() not in f["fact"].lower()
        ]
        removed = before - len(self._data["facts"])
        self.save()
        return f"Forgot {removed} entr{'y' if removed == 1 else 'ies'} matching '{keyword}'."

    # ── Session log ───────────────────────────────────────
    def log_session(self, summary: str) -> None:
        import datetime
        entry = {
            "date":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "summary": summary,
        }
        self._data["sessions"].append(entry)
        # Keep last 100 sessions
        self._data["sessions"] = self._data["sessions"][-100:]
        self.save()

    def recall_sessions(self, n: int = 5) -> str:
        sessions = self._data["sessions"][-n:]
        if not sessions:
            return "No past sessions recorded."
        lines = [f"  [{s['date']}] {s['summary']}" for s in reversed(sessions)]
        return "Recent sessions:\n" + "\n".join(lines)


# ════════════════════════════════════════════════════════════
#  MEMORY MANAGER  (unified facade)
# ════════════════════════════════════════════════════════════
class MemoryManager:
    """
    Single access point for both memory tiers.
    Import and use:
        from core.memory import MEMORY
    """

    def __init__(self) -> None:
        mem_cfg   = CFG.memory
        max_turns = mem_cfg.get("max_history_turns", 50)
        lt_file   = mem_cfg.get("long_term_file", "data/long_term_memory.json")

        self.short = ShortTermMemory(max_turns=max_turns)
        self.long  = LongTermMemory(filepath=lt_file)
        log.info("MemoryManager initialised.")

    # ── Short-term pass-throughs ──────────────────────────
    def add_turn(self, role: str, content: str) -> None:
        self.short.add(role, content)

    def get_context(self) -> list[dict]:
        return self.short.get_context()

    def clear_context(self) -> str:
        self.short.clear()
        return "Conversation memory cleared."

    # ── Long-term pass-throughs ───────────────────────────
    def remember(self, fact: str) -> str:
        return self.long.remember_fact(fact)

    def recall(self, keyword: str = "") -> str:
        return self.long.recall_facts(keyword)

    def forget(self, keyword: str) -> str:
        return self.long.forget_fact(keyword)

    def set_pref(self, key: str, value: Any) -> str:
        return self.long.set_preference(key, value)

    def get_pref(self, key: str, default: Any = None) -> Any:
        return self.long.get_preference(key, default)

    def list_prefs(self) -> str:
        return self.long.list_preferences()

    def save_history(self) -> str:
        return self.long.save()

    def recall_sessions(self, n: int = 5) -> str:
        return self.long.recall_sessions(n)


# Singleton
MEMORY = MemoryManager()
