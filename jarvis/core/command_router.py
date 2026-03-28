"""
core/command_router.py
──────────────────────
The heart of JARVIS's command system.

Design:
  • CommandRegistry  — maps trigger phrases → handler functions
  • Each module registers its own commands via `registry.register(...)`
  • Route decides: built-in command OR pass to AI engine
  • Plugin system: auto-loads Python files from the plugins/ directory

Registration example (in any module):
    from core.command_router import registry

    @registry.register(
        triggers=["open notepad", "launch notepad"],
        description="Open Notepad",
        category="Apps",
    )
    def open_notepad() -> str:
        ...
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from utils.config import CFG
from utils.logger import get_logger

log = get_logger(__name__)


# ════════════════════════════════════════════════════════════
#  COMMAND ENTRY
# ════════════════════════════════════════════════════════════
@dataclass
class Command:
    handler:     Callable
    triggers:    list[str]       # exact lower-case phrases
    patterns:    list[str]       # regex patterns (compiled on first use)
    description: str
    category:    str
    _compiled:   list[re.Pattern] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def matches(self, text: str) -> re.Match | None:
        """Return first regex match, or None."""
        for pat in self._compiled:
            m = pat.search(text)
            if m:
                return m
        return None


# ════════════════════════════════════════════════════════════
#  REGISTRY
# ════════════════════════════════════════════════════════════
class CommandRegistry:
    def __init__(self) -> None:
        self._commands: list[Command] = []

    # ── Registration ─────────────────────────────────────
    def register(
        self,
        triggers:    list[str] | None = None,
        patterns:    list[str] | None = None,
        description: str              = "",
        category:    str              = "General",
    ) -> Callable:
        """
        Decorator to register a function as a JARVIS command.

        @registry.register(
            triggers=["what time is it"],
            description="Current time",
            category="Info",
        )
        def get_time() -> str: ...
        """
        def decorator(fn: Callable) -> Callable:
            cmd = Command(
                handler=fn,
                triggers=[t.lower().strip() for t in (triggers or [])],
                patterns=patterns or [],
                description=description,
                category=category,
            )
            self._commands.append(cmd)
            log.debug(f"Registered command: '{description}' ({category})")
            return fn
        return decorator

    # ── Routing ───────────────────────────────────────────
    def route(self, raw_input: str) -> tuple[Callable | None, re.Match | None]:
        """
        Find the best matching command for raw_input.
        Returns (handler, match_object) or (None, None).
        """
        lower = raw_input.lower().strip()

        # 1. Exact trigger match (fastest)
        for cmd in self._commands:
            for trigger in cmd.triggers:
                if trigger in lower:
                    return cmd.handler, None

        # 2. Regex pattern match
        for cmd in self._commands:
            m = cmd.matches(lower)
            if m:
                return cmd.handler, m

        return None, None

    # ── Help text ─────────────────────────────────────────
    def help_text(self) -> str:
        categories: dict[str, list[Command]] = {}
        for cmd in self._commands:
            categories.setdefault(cmd.category, []).append(cmd)

        lines = ["⚡  JARVIS  —  Available Commands", "─" * 50]
        for cat, cmds in sorted(categories.items()):
            lines.append(f"\n🔹  {cat}")
            for c in cmds:
                sample = c.triggers[0] if c.triggers else (c.patterns[0] if c.patterns else "…")
                lines.append(f"    • {c.description:<40} e.g. \"{sample}\"")
        lines.append("\nAnything else → AI response")
        return "\n".join(lines)

    # ── Plugin loader ─────────────────────────────────────
    def load_plugins(self) -> list[str]:
        """
        Scan CFG.plugins_dir for .py files and import them.
        Each plugin simply needs to call registry.register() at module level.
        Returns list of loaded plugin names.
        """
        plugins_dir = CFG.plugins_dir
        loaded: list[str] = []

        if not plugins_dir.is_dir():
            return loaded

        for plugin_path in sorted(plugins_dir.glob("*.py")):
            if plugin_path.stem.startswith("_"):
                continue
            try:
                spec   = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
                module = importlib.util.module_from_spec(spec)          # type: ignore
                sys.modules[plugin_path.stem] = module
                spec.loader.exec_module(module)                          # type: ignore
                loaded.append(plugin_path.stem)
                log.info(f"Plugin loaded: {plugin_path.stem}")
            except Exception as e:
                log.error(f"Failed to load plugin '{plugin_path.stem}': {e}")

        return loaded

    # ── Introspection ────────────────────────────────────
    def list_commands(self) -> list[dict]:
        return [
            {
                "category":    c.category,
                "description": c.description,
                "triggers":    c.triggers[:3],
            }
            for c in self._commands
        ]

    def __len__(self) -> int:
        return len(self._commands)


# ── Module-level singleton ────────────────────────────────
registry = CommandRegistry()


# ════════════════════════════════════════════════════════════
#  ROUTER  (high-level entry called by main loop)
# ════════════════════════════════════════════════════════════
class Router:
    """
    High-level router used by main.py.

    Checks for:
      1. Exit sentinel
      2. Built-in registry commands
      3. Falls through to AI engine
    """

    EXIT_PHRASES = {
        "exit", "quit", "bye", "goodbye",
        "shutdown jarvis", "close jarvis", "stop jarvis",
    }

    def __init__(self) -> None:
        self._registry = registry

    def is_exit(self, raw: str) -> bool:
        return raw.lower().strip() in self.EXIT_PHRASES

    def dispatch(self, raw: str) -> tuple[str | None, bool]:
        """
        Dispatch raw input.
        Returns (response_string, handled_by_command).
        response_string is None if not handled (caller should use AI).
        """
        handler, match = self._registry.route(raw)
        if handler is None:
            return None, False

        try:
            # Pass regex match groups if the function accepts arguments
            import inspect
            sig  = inspect.signature(handler)
            npar = len([
                p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty
            ])
            if npar == 0 or match is None:
                result = handler()
            else:
                # Pass all named groups from the match as kwargs
                groups = match.groupdict()
                if groups:
                    result = handler(**groups)
                elif match.lastindex:
                    result = handler(*match.groups())
                else:
                    result = handler()
        except Exception as e:
            log.error(f"Command handler error: {e}", exc_info=True)
            result = f"Command failed: {e}"

        return str(result) if result is not None else None, True


ROUTER = Router()
