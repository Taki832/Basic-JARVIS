"""
modules/system_control.py
─────────────────────────
All OS-level control: apps, volume, media, windows, processes, power.
Every dangerous action is gated through core.safety.
"""

from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path

from core.command_router import registry
from core.safety import SAFETY, RiskLevel
from utils.logger import get_logger

log = get_logger(__name__)

# ── Optional deps ────────────────────────────────────────
try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    _PYAUTO = True
except ImportError:
    _PYAUTO = False


# ════════════════════════════════════════════════════════════
#  CONSTANTS
# ════════════════════════════════════════════════════════════
WEBSITES: dict[str, str] = {
    "youtube":        "https://youtube.com",
    "google":         "https://google.com",
    "github":         "https://github.com",
    "stackoverflow":  "https://stackoverflow.com",
    "reddit":         "https://reddit.com",
    "twitter":        "https://twitter.com",
    "x":              "https://x.com",
    "linkedin":       "https://linkedin.com",
    "gmail":          "https://mail.google.com",
    "chatgpt":        "https://chat.openai.com",
    "claude":         "https://claude.ai",
    "netflix":        "https://netflix.com",
    "spotify web":    "https://open.spotify.com",
    "wikipedia":      "https://wikipedia.org",
}

APPS: dict[str, str] = {
    "notepad":        "notepad",
    "calculator":     "calc",
    "paint":          "mspaint",
    "task manager":   "taskmgr",
    "file explorer":  "explorer",
    "explorer":       "explorer",
    "cmd":            "start cmd",
    "command prompt": "start cmd",
    "powershell":     "start powershell",
    "vs code":        "code",
    "vscode":         "code",
    "chrome":         "start chrome",
    "firefox":        "start firefox",
    "edge":           "start msedge",
    "discord":        "start discord",
    "spotify":        "start spotify",
    "vlc":            "start vlc",
    "steam":          "start steam",
    "obs":            "start obs64",
    "zoom":           "start zoom",
    "word":           "winword",
    "excel":          "excel",
    "powerpoint":     "powerpnt",
}

FOLDERS: dict[str, str] = {
    "downloads":  "~/Downloads",
    "documents":  "~/Documents",
    "desktop":    "~/Desktop",
    "pictures":   "~/Pictures",
    "music":      "~/Music",
    "videos":     "~/Videos",
}


# ════════════════════════════════════════════════════════════
#  WEBSITES
# ════════════════════════════════════════════════════════════
def _make_site_opener(site: str, url: str):
    @registry.register(
        triggers=[f"open {site}", f"go to {site}", f"launch {site}"],
        description=f"Open {site.title()} in browser",
        category="Websites",
    )
    def _opener() -> str:
        webbrowser.open(url)
        log.info(f"Opened website: {url}")
        return f"Opening {site.title()}…"
    _opener.__name__ = f"open_{site.replace(' ', '_')}"
    return _opener

for _site, _url in WEBSITES.items():
    _make_site_opener(_site, _url)


# ════════════════════════════════════════════════════════════
#  APPLICATIONS
# ════════════════════════════════════════════════════════════
def _make_app_opener(app: str, cmd: str):
    @registry.register(
        triggers=[f"open {app}", f"launch {app}", f"start {app}"],
        description=f"Launch {app.title()}",
        category="Apps",
    )
    def _launcher() -> str:
        try:
            if cmd.startswith("start "):
                os.system(cmd)
            else:
                subprocess.Popen(cmd, shell=True)
            log.info(f"Launched: {app}")
            return f"Opening {app.title()}…"
        except Exception as e:
            log.error(f"Failed to open {app}: {e}")
            return f"Failed to open {app}: {e}"
    _launcher.__name__ = f"open_{app.replace(' ', '_')}"
    return _launcher

for _app, _cmd in APPS.items():
    _make_app_opener(_app, _cmd)


# ════════════════════════════════════════════════════════════
#  FOLDERS
# ════════════════════════════════════════════════════════════
def _make_folder_opener(fname: str, fpath: str):
    @registry.register(
        triggers=[f"open {fname}", f"open my {fname}"],
        description=f"Open {fname.title()} folder",
        category="Folders",
    )
    def _folder_open() -> str:
        expanded = os.path.expanduser(fpath)
        if os.path.isdir(expanded):
            os.startfile(expanded)
            return f"Opening {fname.title()} folder…"
        return f"Folder not found: {expanded}"
    _folder_open.__name__ = f"open_folder_{fname}"
    return _folder_open

for _fname, _fpath in FOLDERS.items():
    _make_folder_opener(_fname, _fpath)


# ════════════════════════════════════════════════════════════
#  SYSTEM STATS
# ════════════════════════════════════════════════════════════
@registry.register(
    triggers=["system info", "pc stats", "system stats", "hardware info"],
    description="CPU, RAM, and disk usage",
    category="System",
)
def system_info() -> str:
    if not _PSUTIL:
        return "psutil not installed — run: pip install psutil"
    cpu  = psutil.cpu_percent(interval=1)
    ram  = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return (
        f"CPU:   {cpu}%\n"
        f"RAM:   {ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB  ({ram.percent}%)\n"
        f"Disk:  {disk.used // (1024**3)} GB / {disk.total // (1024**3)} GB  ({disk.percent}%)"
    )


@registry.register(
    triggers=["battery", "battery status", "battery level"],
    description="Battery status",
    category="System",
)
def battery_status() -> str:
    if not _PSUTIL:
        return "psutil not installed."
    bat = psutil.sensors_battery()
    if bat is None:
        return "No battery detected."
    plug = "Charging ⚡" if bat.power_plugged else "Discharging 🔋"
    time_info = ""
    if not bat.power_plugged and bat.secsleft > 0:
        h, m = divmod(bat.secsleft // 60, 60)
        time_info = f"  ~{h}h {m}m remaining"
    return f"Battery: {bat.percent:.1f}%  —  {plug}{time_info}"


@registry.register(
    triggers=["top processes", "running processes", "what's running", "process list"],
    description="Top running processes by CPU",
    category="System",
)
def top_processes() -> str:
    if not _PSUTIL:
        return "psutil not installed."
    procs = sorted(
        psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]),
        key=lambda p: p.info.get("cpu_percent") or 0,
        reverse=True,
    )[:10]
    lines = ["PID    CPU%   RAM(MB)  Name"]
    lines.append("─" * 40)
    for p in procs:
        ram_mb = (p.info["memory_info"].rss // (1024**2)) if p.info.get("memory_info") else 0
        lines.append(
            f"{p.info['pid']:5d}  "
            f"{p.info.get('cpu_percent', 0):5.1f}  "
            f"{ram_mb:7d}  "
            f"{p.info['name'][:25]}"
        )
    return "\n".join(lines)


@registry.register(
    triggers=["uptime", "system uptime", "how long has pc been on"],
    description="System uptime",
    category="System",
)
def system_uptime() -> str:
    if not _PSUTIL:
        return "psutil not installed."
    import time
    secs    = int(time.time() - psutil.boot_time())
    h, rem  = divmod(secs, 3600)
    m, s    = divmod(rem, 60)
    return f"System uptime: {h}h {m}m {s}s"


# ════════════════════════════════════════════════════════════
#  VOLUME
# ════════════════════════════════════════════════════════════
@registry.register(
    triggers=["volume up", "increase volume", "louder", "turn up"],
    description="Increase system volume",
    category="Media",
)
def volume_up() -> str:
    if not _PYAUTO:
        return "pyautogui not installed."
    for _ in range(5):
        pyautogui.press("volumeup")
    return "Volume increased."


@registry.register(
    triggers=["volume down", "decrease volume", "quieter", "lower volume", "turn down"],
    description="Decrease system volume",
    category="Media",
)
def volume_down() -> str:
    if not _PYAUTO:
        return "pyautogui not installed."
    for _ in range(5):
        pyautogui.press("volumedown")
    return "Volume decreased."


@registry.register(
    triggers=["mute", "unmute", "toggle mute"],
    description="Toggle mute",
    category="Media",
)
def volume_mute() -> str:
    if not _PYAUTO:
        return "pyautogui not installed."
    pyautogui.press("volumemute")
    return "Volume mute toggled."


# ════════════════════════════════════════════════════════════
#  MEDIA KEYS
# ════════════════════════════════════════════════════════════
@registry.register(
    triggers=["play", "pause", "play pause", "toggle music"],
    description="Play/pause media",
    category="Media",
)
def media_play_pause() -> str:
    if not _PYAUTO:
        return "pyautogui not installed."
    pyautogui.press("playpause")
    return "Play/Pause."


@registry.register(
    triggers=["next track", "next song", "skip song"],
    description="Next media track",
    category="Media",
)
def media_next() -> str:
    if not _PYAUTO:
        return "pyautogui not installed."
    pyautogui.press("nexttrack")
    return "Next track."


@registry.register(
    triggers=["previous track", "previous song", "prev track", "back track"],
    description="Previous media track",
    category="Media",
)
def media_prev() -> str:
    if not _PYAUTO:
        return "pyautogui not installed."
    pyautogui.press("prevtrack")
    return "Previous track."


# ════════════════════════════════════════════════════════════
#  WINDOW MANAGEMENT
# ════════════════════════════════════════════════════════════
def _hotkey(*keys: str) -> str | None:
    if not _PYAUTO:
        return "pyautogui not installed."
    try:
        pyautogui.hotkey(*keys)
        return None
    except Exception as e:
        return f"Hotkey error: {e}"


@registry.register(triggers=["minimize all", "show desktop"], description="Minimize all windows", category="Windows")
def minimize_all() -> str:   return _hotkey("win", "d") or "All windows minimized."

@registry.register(triggers=["maximize window", "maximize"], description="Maximize current window", category="Windows")
def maximize_window() -> str: return _hotkey("win", "up") or "Window maximized."

@registry.register(triggers=["snap left", "window left"], description="Snap window to left", category="Windows")
def snap_left() -> str:       return _hotkey("win", "left") or "Snapped left."

@registry.register(triggers=["snap right", "window right"], description="Snap window to right", category="Windows")
def snap_right() -> str:      return _hotkey("win", "right") or "Snapped right."

@registry.register(triggers=["open settings", "windows settings"], description="Open Windows Settings", category="Windows")
def open_settings() -> str:   return _hotkey("win", "i") or "Settings opened."

@registry.register(triggers=["task view", "open task view"], description="Task View / alt-tab", category="Windows")
def task_view() -> str:       return _hotkey("win", "tab") or "Task view opened."

@registry.register(triggers=["new virtual desktop", "create virtual desktop"], description="New virtual desktop", category="Windows")
def new_vdesktop() -> str:    return _hotkey("win", "ctrl", "d") or "New virtual desktop."

@registry.register(triggers=["next desktop", "switch desktop right"], description="Next virtual desktop", category="Windows")
def next_vdesktop() -> str:   return _hotkey("win", "ctrl", "right") or "Switched right."

@registry.register(triggers=["prev desktop", "previous desktop"], description="Previous virtual desktop", category="Windows")
def prev_vdesktop() -> str:   return _hotkey("win", "ctrl", "left") or "Switched left."


# ════════════════════════════════════════════════════════════
#  KILL PROCESS  (with safety)
# ════════════════════════════════════════════════════════════
@registry.register(
    patterns=[r"(?:kill|close|terminate|end|stop)\s+(?:process\s+)?(?P<proc>[a-z0-9_.\- ]+)"],
    description="Kill a running process",
    category="System",
)
def kill_process(proc: str = "") -> str:
    if not proc:
        return "Specify a process name."
    proc = proc.strip()
    base = proc.lower().replace(".exe", "")

    if SAFETY.is_protected_process(base):
        return f"⚠ '{proc}' is a protected system process. Refusing."

    if not SAFETY.guard(
        f"Kill process: {proc}",
        action_key=f"kill_{base}",
        risk=RiskLevel.CONFIRM,
    ):
        return "Kill cancelled."

    proc_name = proc if proc.endswith(".exe") else proc + ".exe"
    try:
        result = subprocess.run(
            ["taskkill", "/f", "/im", proc_name],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            log.info(f"Killed process: {proc_name}")
            return f"Process '{proc_name}' terminated."
        return f"Could not kill '{proc_name}': {result.stderr.strip()}"
    except Exception as e:
        return f"Kill error: {e}"


# ════════════════════════════════════════════════════════════
#  POWER MANAGEMENT  (DANGEROUS — rate limited)
# ════════════════════════════════════════════════════════════
@registry.register(
    triggers=["shutdown pc", "shut down pc", "turn off pc", "power off"],
    description="Shutdown the PC",
    category="Power",
)
def shutdown_pc() -> str:
    if not SAFETY.guard("Shutdown PC", "shutdown", RiskLevel.DANGEROUS):
        return "Shutdown cancelled."
    os.system("shutdown /s /t 30")
    return "Shutting down in 30 seconds. Say 'cancel shutdown' to abort."


@registry.register(
    triggers=["restart pc", "reboot pc", "restart computer"],
    description="Restart the PC",
    category="Power",
)
def restart_pc() -> str:
    if not SAFETY.guard("Restart PC", "restart", RiskLevel.DANGEROUS):
        return "Restart cancelled."
    os.system("shutdown /r /t 30")
    return "Restarting in 30 seconds. Say 'cancel shutdown' to abort."


@registry.register(
    triggers=["cancel shutdown", "abort shutdown", "cancel restart"],
    description="Cancel a pending shutdown/restart",
    category="Power",
)
def cancel_shutdown() -> str:
    code = os.system("shutdown /a")
    return "Shutdown cancelled." if code == 0 else "No pending shutdown found."


@registry.register(
    triggers=["lock pc", "lock screen", "lock computer"],
    description="Lock the workstation",
    category="Power",
)
def lock_pc() -> str:
    os.system("rundll32.exe user32.dll,LockWorkStation")
    return "Locked."


@registry.register(
    triggers=["sleep", "sleep pc", "sleep mode"],
    description="Put PC to sleep",
    category="Power",
)
def sleep_pc() -> str:
    if not SAFETY.guard("Sleep PC", "sleep", RiskLevel.CONFIRM):
        return "Sleep cancelled."
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
    return "Going to sleep…"


@registry.register(
    triggers=["hibernate", "hibernate pc"],
    description="Hibernate the PC",
    category="Power",
)
def hibernate_pc() -> str:
    if not SAFETY.guard("Hibernate PC", "hibernate", RiskLevel.DANGEROUS):
        return "Hibernate cancelled."
    os.system("shutdown /h")
    return "Hibernating…"
