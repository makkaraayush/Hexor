# Hexor Cybernetic HUD (Frontend)

The frontend interface for Hexor, built with React, Vite, Tailwind CSS, and Lucide icons. Designed with a dark cybernetic aesthetic inspired by holographic tactical interfaces.

---

## What's in Here

- **HexCoreReactor**: Central holographic audio visualizer responding to microphone inputs and system state.
- **TerminalCommandDeck**: Live conversational feed, command input bar, and audio playback status.
- **Bambu3DPanel**: Real-time telemetry for Bambu Lab 3D printers, search interface for 3D repositories, and slicing approval cards.
- **SpotifyPlayerPanel**: Live playback controls, track metadata, and mood presets communicating through the Spicetify bridge.
- **SystemDiagnostics**: Hardware gauges for CPU, RAM, Disk, and Network telemetry.
- **SkillEvolutionVault**: Inspects dynamically learned skills synthesized by Hexor.
- **SettingsModal**: Configuration dialog for switching LLM providers (Groq, Gemini, Ollama), testing keys, and setting assistant preferences.

---

## Development Setup

If you want to modify or work on the UI directly:

```bash
cd ui
npm install
npm run dev
```

This starts the Vite development server on `http://localhost:5173` with Hot Module Replacement.

---

## Production Build

To build the static production bundle served by the FastAPI backend:

```bash
npm run build
```

This compiles optimized assets directly into `ui/dist`, which FastAPI serves automatically at `http://127.0.0.1:8000`.
