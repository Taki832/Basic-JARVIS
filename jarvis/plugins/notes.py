"""
plugins/notes.py
────────────────
Example JARVIS plugin: quick notepad stored in data/notes.json.
Demonstrates how to add a self-contained feature as a plugin.
"""

from __future__ import annotations

import json
import datetime
from pathlib import Path

from core.command_router import registry
from utils.config import CFG

_NOTES_FILE = Path(CFG.data_dir) / "notes.json"


def _load() -> list[dict]:
    if _NOTES_FILE.exists():
        try:
            return json.loads(_NOTES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(notes: list[dict]) -> None:
    _NOTES_FILE.write_text(json.dumps(notes, indent=2, ensure_ascii=False), encoding="utf-8")


@registry.register(
    patterns=[r"(?:add note|take note|note down|jot down)\s+(?P<text>.+)"],
    description="Add a quick note",
    category="Notes",
)
def add_note(text: str = "") -> str:
    text = (text or "").strip()
    if not text:
        return "Nothing to note."
    notes = _load()
    notes.append({"text": text, "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})
    _save(notes)
    return f"Note saved: '{text}'"


@registry.register(
    triggers=["show notes", "list notes", "my notes", "read notes"],
    description="Show all saved notes",
    category="Notes",
)
def show_notes() -> str:
    notes = _load()
    if not notes:
        return "No notes yet."
    lines = [f"  {i+1}. [{n['date']}] {n['text']}" for i, n in enumerate(notes[-20:])]
    return f"Notes ({len(notes)} total):\n" + "\n".join(lines)


@registry.register(
    patterns=[r"delete\s+note\s+(?P<number>\d+)"],
    description="Delete a note by number",
    category="Notes",
)
def delete_note(number: str = "1") -> str:
    notes = _load()
    try:
        idx = int(number) - 1
        if 0 <= idx < len(notes):
            removed = notes.pop(idx)
            _save(notes)
            return f"Deleted note: '{removed['text']}'"
        return f"No note #{number}."
    except ValueError:
        return "Invalid note number."


@registry.register(
    triggers=["clear notes", "delete all notes", "wipe notes"],
    description="Delete all notes",
    category="Notes",
)
def clear_notes() -> str:
    _save([])
    return "All notes cleared."
