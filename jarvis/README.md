# ⚡ JARVIS v3.0 — Local AI Assistant

> Just A Rather Very Intelligent System  
> Runs 100% locally. No cloud. No API keys.

---

## Project Structure

```
jarvis/
├── main.py                  ← Entry point
├── config.json              ← All settings (edit this)
├── requirements.txt
│
├── core/
│   ├── ai_engine.py         ← Ollama wrapper (streaming + async)
│   ├── command_router.py    ← Command registry + dispatcher
│   ├── memory.py            ← Short-term + long-term memory
│   └── safety.py            ← Confirmation prompts + rate limits
│
├── modules/
│   ├── system_control.py    ← Apps, websites, volume, power, processes
│   ├── file_ops.py          ← List, find, open, create, delete files
│   ├── web_ops.py           ← Google, YouTube, GitHub, Wikipedia search
│   └── automation.py        ← Screenshot, clipboard, typing, reminders
│
├── voice/
│   ├── text_to_speech.py    ← pyttsx3 TTS (background thread)
│   └── speech_to_text.py    ← SpeechRecognition STT (optional wake word)
│
├── utils/
│   ├── config.py            ← Config loader singleton (CFG)
│   └── logger.py            ← Rotating file + console logging
│
├── plugins/                 ← Drop .py files here to auto-load
│   ├── weather.py           ← Example: weather via wttr.in
│   └── notes.py             ← Example: quick notepad
│
├── data/                    ← Auto-created: memory, screenshots, notes
└── logs/                    ← Auto-created: jarvis.log
```

---

## Installation

### 1. Install Ollama
Download from https://ollama.com and install it.  
Then pull the model:
```bash
ollama pull qwen3:4b
```
Keep Ollama running in the background (`ollama serve`).

### 2. Clone / copy the project
```bash
cd C:\Users\YourName\
# copy the jarvis/ folder here
cd jarvis
```

### 3. Create a virtual environment (recommended)
```bash
python -m venv venv
venv\Scripts\activate
```

### 4. Install dependencies
```bash
pip install -r requirements.txt
```

> **PyAudio troubleshooting on Windows:**  
> If `pip install pyaudio` fails:
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

### 5. Run JARVIS
```bash
python main.py
```

---

## Configuration

Edit `config.json` to change any setting at runtime.  
Type `reload config` in JARVIS to apply changes without restarting.

Key settings:

| Key | Default | Description |
|-----|---------|-------------|
| `ai.model` | `qwen3:4b` | Ollama model name |
| `ai.context_turns` | `20` | Conversation turns kept in memory |
| `voice.tts_enabled` | `false` | Start with voice output on |
| `voice.stt_enabled` | `false` | Start with voice input on |
| `voice.wake_word` | `"jarvis"` | Say this before commands (STT mode) |
| `voice.continuous_listening` | `false` | Always-on mic mode |
| `safety.require_confirmation` | `true` | Prompt before dangerous actions |
| `safety.dangerous_rate_limit_seconds` | `60` | Min seconds between dangerous actions |

---

## Usage Examples

```
# Information
what time is it
today's date
system info
battery
uptime

# Apps & Websites
open notepad
open chrome
open youtube
open downloads

# File Operations
list files
list files C:/Users/Vishnu/Documents
find files named report
open file notes.txt
create file test.txt
delete file old_file.txt        ← asks for confirmation

# Web Search
search for python tutorials
search youtube for lofi music
github search fastapi

# System Control
volume up
mute
next track
minimize all
snap left
kill process notepad            ← asks for confirmation
shutdown pc                     ← asks for confirmation + rate limited

# Memory
remember that my GPU is RTX 9060 XT
recall gpu
forget gpu
clear history
show preferences
past sessions

# Reminders
remind me in 10 minutes to drink water
list reminders
cancel reminder 1

# Plugins
weather in Chennai
add note finish the JARVIS project
show notes

# Meta
help
status
enable voice
disable voice
reload config
exit
```

---

## How to Add a New Plugin

1. Create a `.py` file in the `plugins/` directory.
2. Import `registry` and use `@registry.register(...)`.
3. Restart JARVIS (or it loads automatically next startup).

**Template:**
```python
# plugins/my_feature.py
from core.command_router import registry

@registry.register(
    triggers=["my command", "run my thing"],
    patterns=[r"do something with\s+(?P<target>.+)"],
    description="My custom feature",
    category="Custom",
)
def my_command(target: str = "") -> str:
    # do something
    return f"Done with: {target}"
```

That's all. No other files need to change.

---

## How to Add a New Built-in Module

1. Create `modules/my_module.py`
2. Import and use `@registry.register(...)`
3. Add `import modules.my_module` in `main.py` (one line)

---

## Safety System

Every destructive action (shutdown, delete, kill) is gated:

| Risk Level | Behaviour |
|------------|-----------|
| `SAFE` | Runs immediately |
| `CONFIRM` | Single yes/no prompt |
| `DANGEROUS` | Prompt + rate-limited (once per 60s by default) |

Protected system processes (`explorer`, `lsass`, `svchost`, etc.) can **never** be killed regardless of user input.

---

## Voice Setup

### Text-to-Speech (TTS)
```
enable voice      → turns on spoken replies
disable voice     → turns off
```
Or set `"tts_enabled": true` in `config.json`.

### Speech-to-Text (STT)
Requires a microphone.
```
enable listening  → press Enter (blank) to trigger mic
disable listening → back to keyboard only
```
For always-on mode, set `"continuous_listening": true` in `config.json`.  
Then say **"jarvis open youtube"** — the wake word filters random background speech.

---

## Logs

All activity is logged to `logs/jarvis.log` (rotates at 5 MB, keeps 3 backups).  
Log level can be changed in `config.json` → `logging.level` → `DEBUG / INFO / WARNING`.
