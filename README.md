# Hexor

An autonomous, locally-orchestrated desktop assistant inspired by J.A.R.V.I.S. from Iron Man. Built to manage real workstation tasks, automate desktop Spotify playback without focus-stealing, control a Bambu Lab 3D printer over local LAN MQTT, handle non-blocking background alarms, execute deep Windows system tasks, and dynamically synthesize new skills on the fly.

---

## Why Hexor?

Most AI assistants available today are glorified chat windows. They run inside a browser tab, have zero awareness of your operating system, cannot interact with your local apps, and require you to manually copy and paste everything.

Hexor was built out of a desire for a real desktop companion: an assistant that listens quietly in the background, acts immediately when called, talks back in natural speech, controls your physical hardware, manages your music without taking your mouse away while you are coding, and continuously learns new capabilities.

Getting Hexor to this point took about 3 to 4 months of late nights, trial-and-error, and rebuilding systems from scratch. What sounds simple on paper—like playing a specific song without stealing window focus or having a continuous voice listener that doesn't burn hundreds of API calls an hour—turned out to be surprisingly tricky in practice. Every piece here was battle-tested and refined through real everyday use on my own machine until it became genuinely fast, reliable, and invisible when idling.

---

## What Can Hexor Do?

### 1. Hands-Free Voice Engine
- **Zero-Token Standby Listening**: Monitors the microphone locally using dynamic ambient noise floor calibration (`max(22.0, ambient_rms * 2.2)`). It does not burn cloud API credits while idling.
- **Phonetic Wake Detection**: Wakes up to "Hexor", "Hey Hexor", or "Jarvis".
- **Dynamic Speech Turn-Taking**: If you are actively speaking, the conversation timeout automatically extends so you are never cut off mid-thought. As soon as you pause for 0.55 seconds, it immediately starts processing your request.
- **Natural Neural TTS**: Speaks back using high-fidelity neural voices (defaulting to the British `en-GB-RyanNeural` voice).

### 2. Spicetify Spotify Integration
- **Direct Internal Player Bridge**: Connects directly into Spotify's client runtime via an internal Spicetify WebSocket extension (`integrations/spicetify/hexor_bridge.js`).
- **No Premium Required**: Triggers exact track playback directly through `Spicetify.Player.playUri()`, bypassing the restrictions of the Spotify Web Playback SDK.
- **Multi-Monitor Safe**: Zero mouse movement, zero window focus stealing, and zero simulated keyboard inputs. You can be actively typing in your editor on monitor 2 while Hexor queues and plays music in the background.
- **Zero-Config Track Search**: If Spotify Web API keys are provided, it queries the catalog directly. If not, it resolves track URIs via web search fallbacks.

### 3. Background Alarms with Wake Music
- **Independent Background Worker**: An asynchronous 1-second scheduler runs completely decoupled from conversational LLM turns. It will never lag or skip a beat.
- **Music Alarms**: Wake up to specific tracks or mood playlists on Spotify.
- **Persistent Storage**: Alarms are saved locally to disk and persist across restarts.
- **HUD Synchronization**: Active alarms broadcast status to the frontend HUD with visual dismissal controls.

### 4. Bambu Lab A1 3D Printer Hub
- **Local LAN MQTT**: Connects directly to the printer over local Wi-Fi (port 8883) with no cloud dependency.
- **Live Hardware Telemetry**: Real-time nozzle temperature, heatbed temperature, print progress percentage, and current layer count.
- **Repository Search**: Searches 3D model catalogs (MakerWorld, Printables, Thingiverse) by voice.
- **Safety Approval Gate**: When asked to print a model, Hexor downloads the geometry, calculates slicing parameters (material, layer height, infill, temperatures), generates a visual approval card in the HUD, and waits for your confirmation before starting.

### 5. PC Deep Control & Telemetry
- **System Operations**: Adjust master audio volume, toggle mute, lock workstation, take screenshots, and open or terminate desktop applications.
- **Live System Telemetry**: Monitors CPU usage, RAM allocation, disk capacity, network traffic, and battery status.

### 6. Autonomous Self-Learning
- **Dynamic Skill Synthesis**: When you ask Hexor to do something it does not have a tool for, the self-learning engine writes a new Python skill file, runs a syntax and safety check, loads it into the runtime dynamically, and saves it permanently to `backend/skills/custom/`.

### 7. Web Intel & Productivity
- **Fast Web Research**: Wikipedia article summaries, DuckDuckGo instant answers, Hacker News developer digests, and location-aware weather forecasts.
- **Local Notes**: Create, search, and review persistent notes on your local drive.

---

## Architecture Overview

```
Hexor/
├── backend/
│   ├── core/
│   │   ├── hexor_brain.py         # Primary cognitive orchestrator and skill dispatcher
│   │   ├── llm_router.py          # Groq, Gemini, and Ollama provider manager
│   │   ├── wake_listener.py       # Local zero-token VAD & phonetic wake listener
│   │   ├── voice_engine.py        # Edge-TTS neural speech synthesis pipeline
│   │   └── self_learner.py        # Dynamic Python skill synthesis and hot-loader
│   ├── skills/
│   │   ├── alarm_clock.py         # Non-blocking background alarm scheduler
│   │   ├── spotify_hub.py         # Spotify track resolver and command dispatcher
│   │   ├── spotify_bridge.py      # WebSocket endpoint for Spicetify client bridge
│   │   ├── bambu_hub.py           # Bambu Lab MQTT telemetry and print dispatcher
│   │   ├── pc_control.py          # Windows volume, apps, and window operations
│   │   ├── windows_deep_ops.py    # Shell commands, screenshot capture, lock screen
│   │   ├── system_telemetry.py    # Hardware performance metrics (CPU, RAM, GPU)
│   │   ├── web_intel.py           # Web scraping, Wikipedia, Hacker News
│   │   ├── weather_location.py    # Geolocation and weather data
│   │   ├── productivity_hub.py    # Local persistent notes and tasks
│   │   └── custom/                # Dynamically generated user skills
│   ├── config.py                  # Environment settings and paths
│   └── main.py                    # FastAPI server, REST API, and WebSocket endpoints
├── ui/                            # Cybernetic React + Vite HUD
│   ├── src/                       # Frontend components, audio visualizers, panels
│   └── dist/                      # Compiled production assets served by FastAPI
├── integrations/
│   └── spicetify/
│       └── hexor_bridge.js        # Internal Spotify client extension
├── docs/
│   └── CHALLENGES_AND_SOLUTIONS.md # Detailed engineering post-mortem
├── run_hexor.py                   # Python entry point
├── start_hexor.bat                # Windows quick launcher
├── Close_hexor.bat                # Quick shutdown script (kills core, terminal & ports)
└── .env.example                   # Environment configuration template
```

---

## Getting Started

### Prerequisites
- **Operating System**: Windows 10 / 11 (recommended for deep PC controls and SAPI cleanup).
- **Python**: Version 3.10, 3.11, or 3.12.
- **Node.js**: Version 18 or higher (needed for compiling the UI).
- **Spotify**: Desktop client installed.
- **Spicetify CLI**: For injecting the Spotify bridge (optional but recommended for background music control).

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/makkaraayush/Hexor.git
cd Hexor
```

---

### Step 2: Set Up Python Backend

Create and activate a virtual environment:

```bash
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Linux/macOS:
source venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

---

### Step 3: Compile the Frontend HUD

```bash
cd ui
npm install
npm run build
cd ..
```

---

### Step 4: Set Up the Spicetify Bridge (Recommended)

The Spicetify bridge lets Hexor control Spotify in the background without needing a paid Spotify Premium subscription or hijacking your mouse.

1. Install Spicetify if you do not already have it:
   ```powershell
   iwr -useb https://raw.githubusercontent.com/spicetify/cli/main/install.ps1 | iex
   ```
2. Copy `integrations/spicetify/hexor_bridge.js` to your Spicetify Extensions directory:
   - On Windows: `%APPDATA%\spicetify\Extensions\hexor_bridge.js`
   - On Linux/macOS: `~/.config/spicetify/Extensions/hexor_bridge.js`
3. Register the extension and apply it:
   ```bash
   spicetify config extensions hexor_bridge.js
   spicetify apply
   ```
4. Restart your Spotify desktop app. When Hexor starts, Spotify will automatically link with Hexor's local WebSocket bridge.

---

### Step 5: Configure Environment Variables

Copy `.env.example` to `backend/.env`:

```bash
cp .env.example backend/.env
```

Open `backend/.env` and add your keys:

- **LLM Provider (Groq is recommended)**:
  - Get a free key at [console.groq.com/keys](https://console.groq.com/keys).
  - Set `LLM_PROVIDER=groq` and paste your key into `GROQ_API_KEY`.
- **Google Gemini (Optional alternative)**:
  - Get a free key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
  - Set `GEMINI_API_KEY`.
- **Bambu Lab 3D Printer (Optional)**:
  - On your printer screen, go to: `Settings -> Network -> LAN Mode`.
  - Enter the displayed IP, Serial Number, and Access Code in `BAMBU_IP`, `BAMBU_SERIAL`, and `BAMBU_ACCESS_CODE`.
- **Spotify Web API (Optional)**:
  - The Spicetify bridge already handles music playback directly. If you also want Spotify catalog search, create an app at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard) and fill in `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`.

---

### Step 6: Launch Hexor

You can launch Hexor using the batch script:

```bash
start_hexor.bat
```

Or run it directly from your terminal:

```bash
python run_hexor.py
```

The system will start the FastAPI backend on `http://127.0.0.1:8000`, open the HUD in your default browser, and begin listening for the wake word in the background.

---

## Interacting with Hexor

Hexor can be controlled by voice or by typing directly into the terminal/HUD interface.

### Voice Commands
- **Wake Words**: "Hexor", "Hey Hexor", or "Jarvis".
- **Music Playback**:
  - *"Play Starboy on Spotify."*
  - *"Play some synthwave music."*
  - *"Pause music."* / *"Resume playback."* / *"Next song."*
- **Background Alarms**:
  - *"Set an alarm for 7:30 AM."*
  - *"Set an alarm for 15 minutes from now with wake up music."*
  - *"Show my active alarms."*
  - *"Delete alarm 1."*
- **3D Printing**:
  - *"Find me a phone stand to 3D print."*
  - *"What is my printer doing right now?"*
  - *"Turn on the chamber light on my Bambu printer."*
- **PC & Workspace Controls**:
  - *"Set master volume to 50 percent."*
  - *"Take a screenshot."*
  - *"Lock my workstation."*
  - *"Open Chrome."* / *"Close Spotify."*
- **Self-Learning**:
  - *"Learn how to convert temperature from Celsius to Fahrenheit."*
- **Standby & Dismissal**:
  - *"Stand down."*
  - *"Stop listening."*
  - *"Dismissed."*
- **System Shutdown & Process Exit**:
  - *"Shut down Hexor."*
  - *"Power down system."*
  - *"Close Hexor."*

---

### Shutting Down Hexor Completely

Hexor is designed to release all hardware resources (microphone handles, audio drivers) and terminate cleanly with zero background overhead:
1. **Via Voice**: Say *"Hexor, shut down"* or *"Power down system"*.
2. **Via HUD**: Click the red Power icon in the top header and confirm.
3. **Via Batch Script**: Double-click `Close_hexor.bat`. It will gracefully signal Hexor to shut down, close the dedicated terminal window, terminate all child processes, and release port 8000.

---

## Technical Deep-Dive

For a complete breakdown of the technical hurdles encountered during development—including the 24/7 Groq token drain in standby, SAPI floating UI conflicts, dual-monitor keystroke leakage, and conversational silence gap calibration—read our detailed engineering log in:

[docs/CHALLENGES_AND_SOLUTIONS.md](docs/CHALLENGES_AND_SOLUTIONS.md)

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
