# 🤖 JARVIS v3 — Local AI Assistant Framework

**JARVIS v3** is a fully local, modular AI assistant designed for real-time automation, intelligent command execution, and extensible feature development — all without relying on cloud APIs.

> ⚡ Runs 100% locally using LLMs (via Ollama)
> 🧠 Built with a scalable, plugin-based architecture
> 🛡️ Includes safety controls for secure execution

---

## 🚀 Why This Project Exists

Most AI assistants today:

* Depend heavily on cloud APIs
* Lack modularity and extensibility
* Have no safety control over system-level actions

**JARVIS v3 solves this by:**

* Running entirely offline using local AI models
* Providing a structured command routing system
* Supporting plugin-based feature expansion
* Enforcing safety checks for sensitive operations

---

## 🧠 How It Works

```text
User Input (Voice/Text)
        ↓
Speech-to-Text (optional)
        ↓
Command Router
        ↓
 ┌───────────────┬───────────────┬───────────────┐
 │ Modules       │ Plugins       │ AI Engine     │
 │ (system ops)  │ (custom)      │ (LLM)         │
 └───────────────┴───────────────┴───────────────┘
        ↓
Response Generation
        ↓
Text-to-Speech (optional)
```

---

## ✨ Key Features

* 🎙️ Voice Input (Speech-to-Text)
* 🗣️ Voice Output (Text-to-Speech)
* 🧠 Local AI Integration (Ollama)
* ⚙️ System Automation (apps, files, processes)
* 🌐 Web Operations (search, open sites)
* 🧩 Plugin-Based Architecture
* 🛡️ Safety Layer (confirmation + rate limiting)
* 🧠 Memory System (context + preferences)
* 🖥️ CLI + GUI Support

---

## 📂 Project Structure

```text
jarvis/
├── core/        # AI engine, command routing, memory, safety
├── modules/     # System-level operations
├── plugins/     # Extendable features
├── voice/       # Speech input/output
├── ui/          # GUI system
├── utils/       # Config & logging
├── main.py      # CLI entry point
├── run_ui.py    # GUI launcher
├── config.json  # Runtime configuration
```

---

## ⚙️ Installation

### 1. Install Ollama

Download and install from:
https://ollama.com

Then pull a model:

```bash
ollama pull qwen3:4b
```

Start Ollama:

```bash
ollama serve
```

---

### 2. Clone the Repository

```bash
git clone https://github.com/yourusername/jarvis-v3.git
cd jarvis-v3
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## ▶️ Run the Assistant

### CLI Mode

```bash
python jarvis/main.py
```

### GUI Mode

```bash
python jarvis/run_ui.py
```

---

## 🧪 Example Usage

```text
User: open youtube
JARVIS: Opening YouTube...

User: search for python tutorials
JARVIS: Searching Google...

User: delete file test.txt
JARVIS: Are you sure? (yes/no)
→ Safety system activated
```

---

## 🔌 Plugin System

Easily extend functionality by adding new plugins.

Create a file inside `plugins/`:

```python
from core.command_router import registry

@registry.register(
    triggers=["my command"],
    description="Custom feature"
)
def my_feature():
    return "Executed!"
```

No core files need to be modified.

---

## 🛡️ Safety System

Sensitive operations are protected:

| Level     | Behavior                     |
| --------- | ---------------------------- |
| SAFE      | Executes instantly           |
| CONFIRM   | Requires user confirmation   |
| DANGEROUS | Confirmation + rate limiting |

Examples:

* File deletion
* Process termination
* System shutdown

---

## 🧠 Memory System

JARVIS can:

* Store user preferences
* Recall previous inputs
* Maintain conversational context

---

## ⚠️ Notes

* VOSK model is not included (large size)
* Download separately if using offline STT
* Microphone required for voice features

---

## 🔮 Future Improvements

* 🌐 Web dashboard interface
* 📱 Mobile integration
* 🧠 Long-term AI memory
* 🏠 Smart home automation
* 🔗 Task chaining (multi-step commands)

---

## 👤 Author

Vishnu

---

## ⭐ Support

If you find this project useful, consider giving it a star ⭐
