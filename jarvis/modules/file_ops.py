"""
modules/file_ops.py
───────────────────
File system operations: list, search, open, create, delete (with safety).
"""

from __future__ import annotations

import os
from pathlib import Path

from core.command_router import registry
from core.safety import SAFETY, RiskLevel
from utils.logger import get_logger

log = get_logger(__name__)

# Paths where delete is always refused
_PROTECTED_ROOTS = [
    Path("C:/Windows"),
    Path("C:/Windows/System32"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
]


# ── List directory ────────────────────────────────────────
@registry.register(
    patterns=[r"list\s+(?:files?|directory|folder|contents?)\s*(?:of\s+|in\s+)?(?P<path>.+)?"],
    triggers=["list files", "list directory", "list folder"],
    description="List directory contents",
    category="Files",
)
def list_directory(path: str = ".") -> str:
    path    = (path or ".").strip().strip('"\'') or "."
    expanded = os.path.expanduser(path)
    try:
        entries = sorted(os.listdir(expanded))
        dirs    = [e for e in entries if os.path.isdir(os.path.join(expanded, e))]
        files   = [e for e in entries if os.path.isfile(os.path.join(expanded, e))]
        result  = f"📁 {expanded}\n"
        result += f"Folders ({len(dirs)}): {', '.join(dirs[:15]) or 'none'}\n"
        result += f"Files   ({len(files)}): {', '.join(files[:15]) or 'none'}"
        if len(files) > 15:
            result += f" … (+{len(files) - 15} more)"
        return result
    except PermissionError:
        return f"Access denied: {expanded}"
    except FileNotFoundError:
        return f"Directory not found: {expanded}"


# ── Find files ────────────────────────────────────────────
@registry.register(
    patterns=[
        r"(?:find|search for)\s+(?:files?\s+)?(?:named\s+|called\s+)?(?P<keyword>[^\s].+)",
    ],
    description="Search for files by name",
    category="Files",
)
def find_files(keyword: str = "") -> str:
    keyword = (keyword or "").strip()
    if not keyword:
        return "Specify a search keyword."

    search_dir = os.path.expanduser("~")   # search from home dir
    results: list[str] = []
    try:
        for root, _dirs, files in os.walk(search_dir):
            for f in files:
                if keyword.lower() in f.lower():
                    results.append(os.path.join(root, f))
                    if len(results) >= 25:
                        break
            if len(results) >= 25:
                break
    except Exception as e:
        return f"Search error: {e}"

    if results:
        items = "\n".join(f"  • {r}" for r in results)
        return f"Found {len(results)} match(es) for '{keyword}':\n{items}"
    return f"No files matching '{keyword}' found."


# ── Open file ─────────────────────────────────────────────
@registry.register(
    patterns=[r"open\s+(?:file\s+)?['\"]?(?P<filepath>[^\s'\"]+\.[a-zA-Z0-9]{1,8})['\"]?"],
    description="Open a file with its default application",
    category="Files",
)
def open_file(filepath: str = "") -> str:
    filepath = (filepath or "").strip()
    if not filepath:
        return "Specify a file path."
    expanded = os.path.expanduser(filepath)
    if os.path.exists(expanded):
        try:
            os.startfile(expanded)
            return f"Opening: {expanded}"
        except Exception as e:
            return f"Could not open file: {e}"
    return f"File not found: {expanded}"


# ── Create file ───────────────────────────────────────────
@registry.register(
    patterns=[r"create\s+(?:a\s+)?(?:new\s+)?file\s+(?:named\s+|called\s+)?['\"]?(?P<filename>[^\s'\"]+)['\"]?"],
    description="Create a new empty file",
    category="Files",
)
def create_file(filename: str = "") -> str:
    filename = (filename or "").strip()
    if not filename:
        return "Specify a filename."
    try:
        p = Path(filename)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.touch()
        log.info(f"Created file: {p.resolve()}")
        return f"File created: {p.resolve()}"
    except Exception as e:
        return f"Failed to create file: {e}"


# ── Delete file (DANGEROUS) ───────────────────────────────
@registry.register(
    patterns=[r"delete\s+(?:file\s+)?['\"]?(?P<filepath>[^\s'\"]+)['\"]?"],
    description="Delete a file (with confirmation)",
    category="Files",
)
def delete_file(filepath: str = "") -> str:
    filepath = (filepath or "").strip()
    if not filepath:
        return "Specify a file path."

    p = Path(os.path.expanduser(filepath)).resolve()

    # Check against protected roots
    for root in _PROTECTED_ROOTS:
        try:
            p.relative_to(root)
            return f"⚠ Refusing to delete '{p}' — inside protected directory."
        except ValueError:
            pass

    if not p.exists():
        return f"File not found: {p}"

    if p.is_dir():
        return f"'{p}' is a directory. I won't delete directories automatically."

    if not SAFETY.guard(f"Delete file: {p}", "delete_file", RiskLevel.DANGEROUS):
        return "Delete cancelled."

    try:
        p.unlink()
        log.info(f"Deleted: {p}")
        return f"Deleted: {p}"
    except Exception as e:
        return f"Delete failed: {e}"


# ── Read file contents ────────────────────────────────────
@registry.register(
    patterns=[r"read\s+(?:file\s+)?['\"]?(?P<filepath>[^\s'\"]+\.[a-zA-Z0-9]{1,8})['\"]?"],
    description="Read and display a text file",
    category="Files",
)
def read_file(filepath: str = "") -> str:
    filepath = (filepath or "").strip()
    if not filepath:
        return "Specify a file path."
    p = Path(os.path.expanduser(filepath))
    if not p.exists():
        return f"File not found: {p}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        if len(content) > 2000:
            return content[:2000] + f"\n… (truncated, {len(content)} total chars)"
        return content
    except Exception as e:
        return f"Read error: {e}"
