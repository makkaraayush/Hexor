# Hexor Engineering Log: Challenges and Solutions

Building an autonomous voice assistant that interfaces with real hardware, operating system controls, and desktop media players is messy. Unlike simple LLM wrappers or terminal chatbots, Hexor had to run continuously in the background on a primary workstation without eating API credits, stealing window focus, leaking keystrokes across multiple monitors, or crashing when external devices were offline.

Getting all of these pieces to cooperate reliably took about 3 to 4 months of iterative prototyping, real-world daily testing, and throwing away architectures that seemed fine on paper but failed during day-to-day multitasking.

Here is a breakdown of the major technical hurdles we ran into during development and how we solved them.

---

## 1. The 24/7 Standby Whisper Token Drain

### The Problem
In early iterations, Hexor used cloud-based Whisper (via Groq) to listen for the wake phrase. Because the assistant needed to be awake and listening at all times, it was continuously streaming 3 to 5 second audio buffers up to the cloud API. 

Within hours, thousands of API calls were burned just listening to silence, keyboard clatter, or room background noise. Even on generous free tier allocations, running a continuous audio listener against a cloud LLM/STT endpoint is unsustainable and introduces unnecessary latency.

### The Solution
We separated wake-word listening from active conversational transcription:
- **Local Audio Analysis and Dynamic Calibration**: In standby mode, `backend/core/wake_listener.py` captures raw PCM audio locally through `sounddevice` without sending any data over the network. On startup, it samples ambient room sound for 1.5 seconds to compute a dynamic baseline RMS noise floor (`max(22.0, ambient_rms * 2.2)`).
- **Zero-Token Standby Processing**: Audio buffers are only evaluated if sound volume exceeds the ambient floor. The raw audio chunk is then passed to a zero-cost local speech recognition pipeline.
- **Phonetic Regex Matching**: Wake detection matches variations of the name ("Hexor", "Hey Hexor", "Hector", "Hex sir", and "Jarvis").
- **Cloud STT Gate**: Groq Whisper is only invoked once Hexor is actively in a conversation session, reducing API consumption to zero during idle periods.

---

## 2. The SAPI Floating Window Nightmare

### The Problem
To avoid cloud STT costs, we experimented with the built-in Windows Speech Recognition engine via `win32com` / SAPI. While it ran locally, Windows automatically spawned `sapisvr.exe`, which forced an immovable, high-contrast floating speech recognition bar on top of all active applications. 

Worse, SAPI frequently crashed when audio sample rates mismatched or when switching audio input devices, leaving orphaned floating windows across virtual desktops.

### The Solution
We ripped out all Windows COM / SAPI speech bindings completely:
- Migrated all standby wake detection to a pure Python pipeline using `sounddevice` and `SpeechRecognition` feeding standard audio streams directly in memory.
- Added explicit process termination (`_kill_sapisvr()`) to ensure any orphaned Windows speech recognition processes are wiped on startup.
- The assistant now runs completely headless in the background without spawning any rogue OS dialogs or floating overlays.

---

## 3. Dual Monitors, GUI Automation, and Keystroke Leaking

### The Problem
Playing specific songs on desktop Spotify without a paid Spotify Premium API key typically relies on desktop GUI automation (e.g., launching Spotify, bringing the window into focus, clicking the search bar, typing the song title, and pressing Enter).

On a multi-monitor workstation, this approach broke constantly:
- If the user was typing in an IDE, terminal, or browser on monitor 2, bringing Spotify to the foreground would violently steal focus mid-sentence.
- If focus failed to switch in time, keystrokes intended for Spotify were typed into whatever code editor or browser tab the user was working in.
- UI elements in Spotify shift dynamically depending on window dimensions, banner ads, and sidebar widths, causing fixed coordinate clicks to land in the wrong place.

### The Solution: The Internal Spicetify WebSocket Bridge
Instead of manipulating the desktop UI from the outside, we injected a lightweight JavaScript extension (`integrations/spicetify/hexor_bridge.js`) directly into Spotify's client runtime using Spicetify:
- **Direct Internal API Access**: Inside Spotify's Electron/Chromium runtime, `Spicetify.Player.playUri(uri)` has native access to playback methods. It works on both free and premium accounts and starts playback instantly without bringing the window to the front or moving the mouse.
- **WebSocket Protocol**: The extension establishes a persistent local WebSocket connection (`ws://127.0.0.1:8000/api/spotify/bridge`) with the Hexor FastAPI backend.
- **Bi-Directional State**: Hexor can send `play_uri`, `play`, `pause`, `next`, and `previous` commands over the socket. In return, the bridge broadcasts live track metadata and playback state back to the Hexor HUD.
- **Track Resolution Fallback**: If Spotify Web API keys are provided in `.env`, Hexor searches Spotify's catalog directly. If no keys are provided, it resolves track URIs via DuckDuckGo HTML scraping (`query site:open.spotify.com/track`), making the entire music setup work with zero credentials required.

---

## 4. Conversation Timeouts vs. Natural Speech Gaps

### The Problem
Early conversational flow used a rigid 25-second countdown timer. This caused two major frustrations:
1. If the user was giving a long, multi-part prompt or pausing to think, the static timer would expire mid-sentence and dump the assistant back into standby.
2. Conversely, if the user finished speaking in 3 seconds, they had to sit in awkward silence waiting for the remainder of the 25-second window before Hexor would start generating a response.
3. Common conversational phrases like "I'm heading to sleep" or "Thanks for the help" contained trigger words ("sleep", "thank you") that accidentally matched standby dismissal patterns, cutting off the conversation prematurely.

### The Solution
We implemented a voice-activity-driven session state:
- **Dynamic Speech Extension**: While the user is speaking (RMS energy stays above the noise threshold), the expiration timestamp is continuously refreshed forward (`conversation_until = time.time() + 25.0`). Hexor will never cut you off while you are actively talking.
- **Instant Silence Cutoff**: When speech drops below the threshold for more than 0.55 seconds, Hexor treats the turn as complete and immediately hands the audio to the transcription and reasoning engine.
- **Strict Dismissal Grammar**: Standby commands were tightened to explicit, intentional phrases ("stand down", "stop listening", "go to sleep", "dismissed"). Saying "I am going to sleep" or "Thank you" now keeps the assistant engaged and generates an appropriate, friendly response.

---

## 5. Non-Blocking Background Alarms

### The Problem
Integrating an alarm clock into a conversational agent often leads to concurrency bottlenecks. If the alarm checking loop runs inside the main request-response cycle or shares state with the LLM router, an alarm could fail to fire if Hexor is waiting on a slow LLM stream or executing a heavy shell task.

### The Solution
We built `backend/skills/alarm_clock.py` as an independent background worker:
- **Dedicated Polling Loop**: A dedicated async task checks active alarms against system time once every second.
- **Persistent Storage**: Alarms are saved to `backend/storage/alarms.json` so scheduled wake-ups survive server restarts.
- **Music Alarm Integration**: When an alarm triggers, it automatically dispatches a command to the Spotify bridge to play a wake-up track, while concurrently triggering an audible chime and broadcasting a visual alarm banner to the React HUD via WebSockets.
- **Zero Frontend Interference**: The alarm triggers completely independently of whether the user is talking to Hexor, working in other apps, or idling.

---

## 6. Bambu Lab A1 3D Printer Local MQTT Control

### The Problem
Most 3D printer integrations rely on vendor cloud APIs, which introduce latency, require active internet connections, and often restrict automation due to rate limiting or authentication token expirations.

### The Solution
We connected Hexor directly to the Bambu Lab A1 using its local LAN mode MQTT broker:
- **Zero Cloud Dependency**: Communicates directly over the local network via port 8883 using the printer's local serial number and LAN access code.
- **Real-Time Telemetry**: Subscribes to report topics to read live nozzle temperature, bed temperature, active layer, and print progress percentage.
- **Human-in-the-Loop Safety Gate**: Sending a print job to physical hardware without inspection is a fire and mechanical risk. When asked to print a model, Hexor downloads the 3D file, generates a slicing parameter dossier (infill, material, estimated time, bed temp), displays a visual 3D preview card in the HUD, and pauses for explicit voice or click confirmation before sending any start commands.
