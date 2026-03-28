"""
core/safety.py
──────────────
Safety layer for JARVIS.

Features:
  • Categorises actions by risk level (SAFE, CONFIRM, DANGEROUS)
  • Prompts for confirmation before CONFIRM/DANGEROUS actions
  • Rate-limits DANGEROUS actions (once per N seconds)
  • Maintains a protected-process list
  • Provides a decorator @require_safety for module functions
"""

from __future__ import annotations

import time
from enum import Enum, auto
from typing import Callable

from utils.config import CFG
from utils.logger import get_logger

log = get_logger(__name__)


# ── Risk levels ───────────────────────────────────────────
class RiskLevel(Enum):
    SAFE      = auto()   # runs immediately
    CONFIRM   = auto()   # one yes/no prompt
    DANGEROUS = auto()   # prompt + rate-limited


# ── Colour helpers (graceful fallback) ───────────────────
try:
    from colorama import Fore, Style
    _Y  = Fore.YELLOW
    _R  = Fore.RED
    _G  = Fore.GREEN
    _RS = Style.RESET_ALL
except ImportError:
    _Y = _R = _G = _RS = ""


class SafetyManager:
    """
    Central safety manager.
    All dangerous operations should be routed through this.
    """

    def __init__(self) -> None:
        cfg = CFG.safety
        self._require_confirm: bool     = cfg.get("require_confirmation", True)
        self._rate_limit:      int      = cfg.get("dangerous_rate_limit_seconds", 60)
        self._protected_procs: set[str] = set(cfg.get("protected_processes", []))
        self._last_dangerous:  dict[str, float] = {}

    # ── Public helpers ────────────────────────────────────
    def is_protected_process(self, name: str) -> bool:
        return name.lower().replace(".exe", "") in self._protected_procs

    def confirm(self, action_description: str, risk: RiskLevel = RiskLevel.CONFIRM) -> bool:
        """
        Prompt the user for confirmation.
        Returns True if the user approves, False otherwise.
        """
        if not self._require_confirm:
            return True

        color = _R if risk == RiskLevel.DANGEROUS else _Y
        print(
            f"\n{color}⚠  Safety Check — {risk.name}"
            f"\n   Action : {action_description}"
            f"\n   Proceed? (yes / no){_RS} ",
            end="",
        )
        try:
            answer = input().strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "no"

        approved = answer in {"y", "yes", "confirm", "ok", "sure"}
        log.info(
            f"Safety prompt for '{action_description}' → {'APPROVED' if approved else 'DENIED'}"
        )
        if not approved:
            print(f"{_G}  Cancelled.{_RS}\n")
        return approved

    def rate_check(self, action_key: str) -> tuple[bool, int]:
        """
        Check if a dangerous action is within its rate-limit window.
        Returns (allowed: bool, seconds_remaining: int).
        """
        now  = time.time()
        last = self._last_dangerous.get(action_key, 0.0)
        diff = now - last
        if diff < self._rate_limit:
            remaining = int(self._rate_limit - diff)
            return False, remaining
        return True, 0

    def record_dangerous(self, action_key: str) -> None:
        """Record that a dangerous action was just executed."""
        self._last_dangerous[action_key] = time.time()

    def guard(
        self,
        action_description: str,
        action_key: str,
        risk: RiskLevel = RiskLevel.CONFIRM,
    ) -> bool:
        """
        Full safety pipeline:
          1. Rate-limit check (DANGEROUS only)
          2. Confirmation prompt
          3. Record execution time (DANGEROUS only)

        Returns True if the action should proceed, False to abort.
        """
        if risk == RiskLevel.DANGEROUS:
            allowed, secs = self.rate_check(action_key)
            if not allowed:
                msg = (
                    f"Action '{action_key}' is rate-limited. "
                    f"Try again in {secs}s."
                )
                log.warning(msg)
                print(f"{_Y}  ⏳  {msg}{_RS}\n")
                return False

        approved = self.confirm(action_description, risk)
        if not approved:
            return False

        if risk == RiskLevel.DANGEROUS:
            self.record_dangerous(action_key)

        return True


# ── Module-level singleton ────────────────────────────────
SAFETY = SafetyManager()


# ── Decorator ─────────────────────────────────────────────
def require_confirmation(
    description: str,
    action_key: str,
    risk: RiskLevel = RiskLevel.CONFIRM,
) -> Callable:
    """
    Decorator that gates a function behind the safety manager.

    Usage:
        @require_confirmation("Delete file", "delete_file", RiskLevel.DANGEROUS)
        def delete_file(path: str) -> str:
            ...
    """
    def decorator(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # Build a readable description, include first arg if useful
            full_desc = description
            if args:
                full_desc = f"{description}: {str(args[0])[:80]}"
            if not SAFETY.guard(full_desc, action_key, risk):
                return f"Action cancelled: {description}"
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        wrapper.__doc__  = fn.__doc__
        return wrapper
    return decorator
