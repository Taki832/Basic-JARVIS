"""
plugins/weather.py
──────────────────
Example JARVIS plugin: weather lookup via wttr.in (no API key needed).

This file demonstrates the plugin system.
Drop any .py file into the plugins/ directory to auto-load it.
"""

from __future__ import annotations

import urllib.request
import urllib.parse

# All plugins import from core to register commands
from core.command_router import registry


@registry.register(
    patterns=[r"(?:weather|weather in|what's the weather in|how's the weather in)\s+(?P<city>.+)"],
    triggers=["weather", "weather today"],
    description="Get weather for a city (uses wttr.in)",
    category="Web",
)
def get_weather(city: str = "London") -> str:
    city = (city or "London").strip()
    try:
        encoded = urllib.parse.quote(city)
        url     = f"https://wttr.in/{encoded}?format=3"
        req     = urllib.request.Request(url, headers={"User-Agent": "JARVIS/3.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = resp.read().decode("utf-8").strip()
        return f"🌤  {result}"
    except Exception as e:
        return f"Could not fetch weather for '{city}': {e}"
