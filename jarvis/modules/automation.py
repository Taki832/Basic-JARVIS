"""
modules/automation.py
─────────────────────
GUI automation, clipboard, date/time, memory commands, and task scheduler.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
import time
from pathlib import Path

from core.command_router import registry
from core.memory import MEMORY
from utils.config import CFG
from utils.logger import get_logger

log = get_logger(__name__)

# ── Optional deps ────────────────────────────────────────
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    _PYAUTO = True
except ImportError:
    _PYAUTO = False

try:
    import pyperclip
    _CLIP = True
except ImportError:
    _CLIP = False


# ════════════════════════════════════════════════════════════
#  DATE / TIME
# ════════════════════════════════════════════════════════════
@registry.register(
    triggers=["what time is it", "current time", "time is it", "tell me the time"],
    description="Current time",
    category="Info",
)
def get_time() -> str:
    return datetime.datetime.now().strftime("⏰  %I:%M %p")


@registry.register(
    triggers=["today's date", "what date is it", "current date", "what is today"],
    description="Today's date",
    category="Info",
)
def get_date() -> str:
    return datetime.datetime.now().strftime("📅  %A, %B %d, %Y")


@registry.register(
    triggers=["date and time", "time and date", "datetime"],
    description="Current date and time",
    category="Info",
)
def get_datetime() -> str:
    return datetime.datetime.now().strftime("📅  %A, %B %d, %Y  —  ⏰  %I:%M %p")


# ════════════════════════════════════════════════════════════
#  SCREENSHOT
# ════════════════════════════════════════════════════════════
@registry.register(
    triggers=["screenshot", "take screenshot", "capture screen", "capture display"],
    description="Take a screenshot",
    category="Automation",
)
def take_screenshot() -> str:
    if not _PYAUTO:
        return "pyautogui not installed — run: pip install pyautogui pillow"
    try:
        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = Path(CFG.data_dir) / f"screenshot_{ts}.png"
        img      = pyautogui.screenshot()
        img.save(str(filename))
        log.info(f"Screenshot saved: {filename}")
        return f"Screenshot saved → {filename}"
    except Exception as e:
        return f"Screenshot failed: {e}"


# ════════════════════════════════════════════════════════════
#  CLIPBOARD
# ════════════════════════════════════════════════════════════
@registry.register(
    triggers=["clipboard", "read clipboard", "what's in clipboard", "show clipboard"],
    description="Read clipboard contents",
    category="Automation",
)
def read_clipboard() -> str:
    if not _CLIP:
        return "pyperclip not installed — run: pip install pyperclip"
    try:
        text = pyperclip.paste()
        if not text:
            return "Clipboard is empty."
        preview = text[:400] + ("…" if len(text) > 400 else "")
        return f"Clipboard ({len(text)} chars):\n{preview}"
    except Exception as e:
        return f"Clipboard read error: {e}"


@registry.register(
    patterns=[r"copy\s+['\"]?(?P<text>.+?)['\"]?\s+to\s+clipboard"],
    description="Copy text to clipboard",
    category="Automation",
)
def write_clipboard(text: str = "") -> str:
    if not _CLIP:
        return "pyperclip not installed."
    text = (text or "").strip()
    if not text:
        return "Nothing to copy."
    try:
        pyperclip.copy(text)
        return f"Copied to clipboard: {text[:60]}{'…' if len(text) > 60 else ''}"
    except Exception as e:
        return f"Clipboard write error: {e}"


# ════════════════════════════════════════════════════════════
#  TYPING AUTOMATION
# ════════════════════════════════════════════════════════════
@registry.register(
    patterns=[r"type\s+(?:out\s+)?['\"]?(?P<text>.+?)['\"]?$"],
    description="Type text into the focused window",
    category="Automation",
)
def type_text(text: str = "") -> str:
    if not _PYAUTO:
        return "pyautogui not installed."
    text = (text or "").strip()
    if not text:
        return "Nothing to type."
    try:
        time.sleep(1.5)   # user has time to click the target field
        pyautogui.write(text, interval=0.025)
        return f"Typed: {text[:60]}{'…' if len(text) > 60 else ''}"
    except Exception as e:
        return f"Typing error: {e}"


@registry.register(
    patterns=[r"press\s+(?:key\s+)?(?P<key>[a-z0-9_]+)$"],
    description="Press a keyboard key",
    category="Automation",
)
def press_key(key: str = "") -> str:
    if not _PYAUTO:
        return "pyautogui not installed."
    key = (key or "").strip()
    if not key:
        return "Specify a key name."
    try:
        pyautogui.press(key)
        return f"Pressed: {key}"
    except Exception as e:
        return f"Key press error: {e}"


# ════════════════════════════════════════════════════════════
#  MEMORY COMMANDS
# ════════════════════════════════════════════════════════════
@registry.register(
    patterns=[r"(?:remember|note|save fact)\s+(?:that\s+)?(?P<fact>.+)"],
    description="Store a fact in long-term memory",
    category="Memory",
)
def remember(fact: str = "") -> str:
    fact = (fact or "").strip()
    if not fact:
        return "What should I remember?"
    return MEMORY.remember(fact)


@registry.register(
    patterns=[r"(?:recall|what do you know about|what do you remember about)\s+(?P<keyword>.+)"],
    triggers=["recall", "what do you remember", "show memories"],
    description="Recall stored facts",
    category="Memory",
)
def recall(keyword: str = "") -> str:
    return MEMORY.recall((keyword or "").strip())


@registry.register(
    patterns=[r"forget\s+(?:everything about\s+)?(?P<keyword>.+)"],
    description="Remove facts from long-term memory",
    category="Memory",
)
def forget(keyword: str = "") -> str:
    keyword = (keyword or "").strip()
    if not keyword:
        return "Specify what to forget."
    return MEMORY.forget(keyword)


@registry.register(
    triggers=["clear history", "clear memory", "forget everything", "reset memory"],
    description="Clear conversation history",
    category="Memory",
)
def clear_history() -> str:
    return MEMORY.clear_context()


@registry.register(
    triggers=["show preferences", "list preferences", "my preferences"],
    description="Show stored preferences",
    category="Memory",
)
def show_preferences() -> str:
    return MEMORY.list_prefs()


@registry.register(
    triggers=["past sessions", "session history", "previous sessions"],
    description="Show past sessions",
    category="Memory",
)
def past_sessions() -> str:
    return MEMORY.recall_sessions(5)


# ════════════════════════════════════════════════════════════
#  TASK SCHEDULER
# ════════════════════════════════════════════════════════════
_SCHEDULE_FILE = Path(CFG.data_dir) / "scheduled_tasks.json"
_scheduled_tasks: list[dict] = []
_scheduler_started = False


def _load_tasks() -> None:
    global _scheduled_tasks
    if _SCHEDULE_FILE.exists():
        try:
            with open(_SCHEDULE_FILE, "r", encoding="utf-8") as f:
                _scheduled_tasks = json.load(f)
        except Exception:
            _scheduled_tasks = []


def _save_tasks() -> None:
    with open(_SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(_scheduled_tasks, f, indent=2)


def _scheduler_loop() -> None:
    """Background thread: check scheduled tasks every 30 seconds."""
    while True:
        now  = datetime.datetime.now()
        done: list[int] = []
        for i, task in enumerate(_scheduled_tasks):
            try:
                target = datetime.datetime.fromisoformat(task["run_at"])
                if now >= target:
                    print(f"\n⏰  Scheduled task: {task['message']}\n")
                    log.info(f"Scheduled task fired: {task['message']}")
                    if not task.get("recurring"):
                        done.append(i)
            except Exception:
                done.append(i)
        # Remove completed one-shot tasks (reverse order to preserve indices)
        for i in reversed(done):
            _scheduled_tasks.pop(i)
        if done:
            _save_tasks()
        time.sleep(30)


def _ensure_scheduler() -> None:
    global _scheduler_started
    if not _scheduler_started:
        _load_tasks()
        t = threading.Thread(target=_scheduler_loop, daemon=True, name="scheduler")
        t.start()
        _scheduler_started = True
        log.info("Task scheduler started.")


@registry.register(
    patterns=[
        r"remind\s+me\s+(?:in\s+)?(?P<minutes>\d+)\s+min(?:ute)?s?\s+(?:to\s+)?(?P<message>.+)",
        r"set\s+(?:a\s+)?reminder\s+(?:in\s+)?(?P<minutes>\d+)\s+min(?:ute)?s?\s+(?:to\s+)?(?P<message>.+)",
    ],
    description="Set a reminder in N minutes",
    category="Scheduler",
)
def remind_in(minutes: str = "5", message: str = "") -> str:
    _ensure_scheduler()
    try:
        mins    = int(minutes)
        run_at  = datetime.datetime.now() + datetime.timedelta(minutes=mins)
        task    = {"run_at": run_at.isoformat(), "message": message, "recurring": False}
        _scheduled_tasks.append(task)
        _save_tasks()
        return f"Reminder set — I'll alert you in {mins} minute(s): '{message}'"
    except ValueError:
        return "Could not parse minutes."


@registry.register(
    triggers=["list reminders", "show reminders", "my reminders", "pending reminders"],
    description="List all scheduled reminders",
    category="Scheduler",
)
def list_reminders() -> str:
    _ensure_scheduler()
    if not _scheduled_tasks:
        return "No reminders scheduled."
    lines = []
    for i, t in enumerate(_scheduled_tasks, 1):
        dt  = datetime.datetime.fromisoformat(t["run_at"])
        lines.append(f"  {i}. [{dt.strftime('%H:%M %d/%m')}] {t['message']}")
    return "Scheduled reminders:\n" + "\n".join(lines)


@registry.register(
    patterns=[r"cancel\s+reminder\s+(?P<number>\d+)"],
    description="Cancel reminder by number",
    category="Scheduler",
)
def cancel_reminder(number: str = "1") -> str:
    _ensure_scheduler()
    try:
        idx = int(number) - 1
        if 0 <= idx < len(_scheduled_tasks):
            removed = _scheduled_tasks.pop(idx)
            _save_tasks()
            return f"Cancelled reminder: '{removed['message']}'"
        return f"No reminder #{number}."
    except ValueError:
        return "Invalid number."


# Kick-start the scheduler when this module loads
_ensure_scheduler()
