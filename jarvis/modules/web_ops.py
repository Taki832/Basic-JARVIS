"""
modules/web_ops.py
──────────────────
Web-related operations: search, URL open, and convenience lookups.
"""

from __future__ import annotations

import webbrowser

from core.command_router import registry
from utils.logger import get_logger

log = get_logger(__name__)


# ── Generic URL ───────────────────────────────────────────
@registry.register(
    patterns=[r"(?:open|go to|visit|navigate to)\s+(?P<url>https?://\S+)"],
    description="Open any URL in the browser",
    category="Web",
)
def open_url(url: str = "") -> str:
    url = (url or "").strip()
    if not url.startswith("http"):
        return "Invalid URL — must start with http:// or https://"
    webbrowser.open(url)
    log.info(f"Opened URL: {url}")
    return f"Opening: {url}"


# ── Google search ─────────────────────────────────────────
@registry.register(
    patterns=[r"(?:search|google|search for|look up)\s+(?P<query>.+)"],
    description="Search Google",
    category="Web",
)
def google_search(query: str = "") -> str:
    query = (query or "").strip()
    if not query:
        return "Specify a search query."
    url = "https://www.google.com/search?q=" + query.replace(" ", "+")
    webbrowser.open(url)
    return f"Searching Google for: '{query}'"


# ── YouTube search ────────────────────────────────────────
@registry.register(
    patterns=[
        r"(?:search youtube|youtube search|play on youtube)\s+(?:for\s+)?(?P<query>.+)",
    ],
    triggers=["youtube search", "search youtube"],
    description="Search YouTube",
    category="Web",
)
def youtube_search(query: str = "") -> str:
    query = (query or "").strip()
    if not query:
        return "Specify a search term."
    url = "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")
    webbrowser.open(url)
    return f"Searching YouTube for: '{query}'"


# ── GitHub search ─────────────────────────────────────────
@registry.register(
    patterns=[r"(?:search github|github search)\s+(?:for\s+)?(?P<query>.+)"],
    description="Search GitHub",
    category="Web",
)
def github_search(query: str = "") -> str:
    query = (query or "").strip()
    if not query:
        return "Specify a search term."
    url = "https://github.com/search?q=" + query.replace(" ", "+")
    webbrowser.open(url)
    return f"Searching GitHub for: '{query}'"


# ── Wikipedia ─────────────────────────────────────────────
@registry.register(
    patterns=[r"(?:wikipedia|wiki)\s+(?:search\s+)?(?P<query>.+)"],
    description="Search Wikipedia",
    category="Web",
)
def wikipedia_search(query: str = "") -> str:
    query = (query or "").strip()
    if not query:
        return "Specify a search term."
    url = "https://en.wikipedia.org/wiki/Special:Search?search=" + query.replace(" ", "_")
    webbrowser.open(url)
    return f"Searching Wikipedia for: '{query}'"
