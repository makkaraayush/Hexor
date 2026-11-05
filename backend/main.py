import asyncio
import json
import os
import sys
import signal
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

from .config import config, BASE_DIR, AUDIO_CACHE_DIR, MODELS_DIR
from .core.hexor_brain import HexorBrain
from .core.wake_listener import WakeListener

app = FastAPI(title="Hexor OS", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

brain = HexorBrain()
wake_listener: Optional[WakeListener] = None

async def broadcast_ws_message(msg: dict):
    dead = set()
    for ws in active_connections:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            dead.add(ws)
    for d in dead:
        active_connections.remove(d)

class ChatRequest(BaseModel):
    message: str
    voice_enabled: bool = True

class ApprovalRequest(BaseModel):
    approved: bool

class SettingsRequest(BaseModel):
    llm_provider: Optional[str] = None
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    voice_name: Optional[str] = None
    bambu_ip: Optional[str] = None
    bambu_serial: Optional[str] = None
    bambu_access_code: Optional[str] = None
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None

class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    city: Optional[str] = ""

class SpeakRequest(BaseModel):
    text: str
    voice_name: Optional[str] = None

active_connections: set[WebSocket] = set()

@app.on_event("startup")
async def startup_event():
    global wake_listener
    await brain.llm_router.auto_configure_models()
    weather_skill = brain.skills.get("weather_location")
    if weather_skill:
        asyncio.create_task(weather_skill.execute(action="get_weather"))
    asyncio.create_task(telemetry_broadcaster())

    # Start background alarm system
    alarm_skill = brain.skills.get("alarm_clock")
    if alarm_skill:
        spotify_skill = brain.skills.get("spotify_hub")
        alarm_skill.start_monitor(
            broadcast_callback=broadcast_ws_message,
            spotify_skill=spotify_skill,
            voice_engine=brain.voice_engine
        )

    # Start OS-level zero-token wake listener
    try:
        loop = asyncio.get_running_loop()
        wake_listener = WakeListener(brain=brain, broadcast_callback=broadcast_ws_message)
        wake_listener.start(loop)
    except Exception as e:
        print(f"[Main] Wake listener initialization notice: {e}")

    async def on_spotify_bridge_status(status_dict):
        packet = {
            "type": "spotify_update",
            "data": {
                "is_running": True,
                "api_connected": True,
                "current_track": {
                    "title": status_dict.get("title", "Standby"),
                    "artist": status_dict.get("artist", "Ready"),
                    "status": "playing" if status_dict.get("is_playing") else "paused"
                }
            }
        }
        await broadcast_ws_message(packet)

    spotify_bridge.on_status_change = on_spotify_bridge_status

async def telemetry_broadcaster():
    weather_tick = 0
    while True:
        try:
            if active_connections:
                telemetry_skill = brain.skills.get("system_telemetry")
                bambu_skill = brain.skills.get("bambu_hub")
                weather_skill = brain.skills.get("weather_location")
                spotify_skill = brain.skills.get("spotify_hub")
                
                system_data = await telemetry_skill.execute(action="get_metrics") if telemetry_skill else {}
                bambu_data = await bambu_skill.execute(action="get_status") if bambu_skill else {}
                spotify_data = await spotify_skill.execute(action="status") if spotify_skill else {}
                
                # Refresh weather every 60 iterations (~90 seconds)
                if weather_skill and (weather_tick % 60 == 0 or not weather_skill.last_weather):
                    asyncio.create_task(weather_skill.execute(action="get_weather"))
                weather_tick += 1

                packet = {
                    "type": "hud_telemetry",
                    "system": system_data.get("data", {}),
                    "bambu": bambu_data.get("data", {}),
                    "weather": getattr(weather_skill, "last_weather", {}),
                    "spotify": spotify_data.get("data", {}),
                    "pending_approval": getattr(bambu_skill, "current_pending_approval", None)
                }

                dead_connections = set()
                for ws in active_connections:
                    try:
                        await ws.send_text(json.dumps(packet))
                    except Exception:
                        dead_connections.add(ws)
                for dead in dead_connections:
                    active_connections.remove(dead)
        except Exception:
            pass

        await asyncio.sleep(1.5)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        await websocket.send_text(json.dumps({
            "type": "welcome",
            "message": f"Hexor Core Online. Standing by, {config.USER_TITLE}.",
            "skills": [s["name"] for s in brain.get_tool_schemas()]
        }))
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            action = payload.get("action")

            if action == "chat":
                msg = payload.get("message", "")
                voice_on = payload.get("voice_enabled", True)
                result = await brain.process_user_input(msg, voice_enabled=voice_on)
                await websocket.send_text(json.dumps({
                    "type": "chat_response",
                    "payload": result
                }))

            elif action == "approval":
                approved = payload.get("approved", False)
                res = await brain.handle_approval(approved)
                await websocket.send_text(json.dumps({
                    "type": "approval_response",
                    "payload": res
                }))

    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    return await brain.process_user_input(req.message, voice_enabled=req.voice_enabled)

@app.get("/api/chat/history")
async def get_chat_history_endpoint():
    return {"history": brain.conversation_history[-30:]}

@app.post("/api/chat/clear")
async def clear_chat_history_endpoint():
    brain.conversation_history.clear()
    brain._save_history()
    return {"success": True, "message": "History cleared"}

@app.post("/api/approval")
async def approval_endpoint(req: ApprovalRequest):
    return await brain.handle_approval(req.approved)

@app.post("/api/location")
async def update_location_endpoint(req: LocationRequest):
    skill = brain.skills.get("weather_location")
    if skill:
        skill.set_browser_location(req.latitude, req.longitude, req.city or "")
        weather_res = await skill.execute(action="get_weather")
        return {"success": True, "location": skill.cached_location, "weather": weather_res.get("data")}
    return {"success": False}

from .skills.spotify_bridge import spotify_bridge

@app.websocket("/api/spotify/bridge")
async def spotify_bridge_websocket(websocket: WebSocket):
    await spotify_bridge.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            await spotify_bridge.handle_message(msg)
    except WebSocketDisconnect:
        spotify_bridge.disconnect()
    except Exception:
        spotify_bridge.disconnect()

@app.post("/api/voice/speak")
async def voice_speak_endpoint(req: SpeakRequest):
    if brain.voice_engine:
        res = await brain.voice_engine.synthesize(req.text)
        if res:
            return res
    return {"success": False, "audio_base64": None}

@app.post("/api/voice/transcribe")
async def transcribe_audio_endpoint(file: UploadFile = File(...)):
    temp_path = AUDIO_CACHE_DIR / f"upload_{file.filename}"
    with open(temp_path, "wb") as f:
        f.write(await file.read())
    
    text = await brain.llm_router.transcribe_audio(str(temp_path))
    try:
        temp_path.unlink(missing_ok=True)
    except Exception:
        pass

    if text:
        return {"success": True, "transcript": text}
    return {"success": False, "transcript": ""}

@app.post("/api/alarms/stop")
async def stop_ringing_alarm():
    skill = brain.skills.get("alarm_clock")
    if skill:
        return await skill.execute(action="stop_alarm")
    return {"success": False, "message": "Alarm skill not active."}

@app.get("/api/alarms")
async def get_alarms():
    skill = brain.skills.get("alarm_clock")
    if skill:
        return await skill.execute(action="list_alarms")
    return {"success": False, "alarms": []}

@app.delete("/api/alarms/{alarm_id}")
async def cancel_alarm_by_id(alarm_id: str):
    skill = brain.skills.get("alarm_clock")
    if skill:
        return await skill.execute(action="cancel_alarm", alarm_id=alarm_id)
    return {"success": False, "message": "Alarm skill not active."}

@app.post("/api/voice/wake_listener")
async def toggle_wake_listener(req: Dict[str, Any]):
    global wake_listener
    enabled = req.get("enabled", True)
    if wake_listener:
        wake_listener.set_enabled(enabled)
        return {"success": True, "enabled": enabled}
    return {"success": False, "message": "Wake listener not initialized."}

@app.post("/api/voice/standby")
async def enter_standby_endpoint():
    global wake_listener
    if wake_listener:
        wake_listener.enter_standby()
        return {"success": True, "state": "standby"}
    return {"success": False, "message": "Wake listener not initialized."}

@app.post("/api/system/shutdown")
async def shutdown_system():
    async def do_exit():
        # 1. Inform frontend via WebSocket that system is shutting down
        try:
            await broadcast_hud_event({"type": "system_shutdown"})
        except Exception:
            pass

        await asyncio.sleep(0.3)
        try:
            import ctypes
            import psutil
            import subprocess

            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32

            # Close and hide attached console window directly
            try:
                hwnd = kernel32.GetConsoleWindow()
                if hwnd:
                    user32.ShowWindow(hwnd, 0)  # SW_HIDE
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            except Exception:
                pass

            curr_pid = os.getpid()
            curr = psutil.Process(curr_pid)
            parent = curr.parent()

            pids_to_kill = [curr_pid]
            # If parent is python (e.g. uvicorn reloader supervisor), include it for termination
            if parent and "python" in parent.name().lower():
                try:
                    cmdline = " ".join(parent.cmdline() if hasattr(parent, 'cmdline') else []).lower()
                    if not any(safe in cmdline for safe in ["antigravity", "code", "vscode", "cursor", "pycharm", "idea"]):
                        pids_to_kill.append(parent.pid)
                except Exception:
                    pass

            # Terminate Hexor child processes (excluding external user apps)
            for child in curr.children(recursive=True):
                try:
                    cname = child.name().lower()
                    if cname not in ["spotify.exe", "chrome.exe", "msedge.exe", "bambu-studio.exe"]:
                        child.kill()
                except Exception:
                    pass

            for pid in pids_to_kill:
                try:
                    subprocess.Popen(f"taskkill /F /PID {pid} /T", shell=True)
                except Exception:
                    pass

            os._exit(0)
        except Exception:
            os._exit(0)

    asyncio.create_task(do_exit())
    return {"success": True, "message": "Hexor core and terminal shutting down safely, Sir."}

@app.get("/api/telemetry")
async def get_telemetry():
    skill = brain.skills.get("system_telemetry")
    if skill:
        return await skill.execute(action="get_metrics")
    return {"success": False}

class BambuActionRequest(BaseModel):
    action: str
    query: Optional[str] = ""
    speed_level: Optional[str] = "standard"
    material: Optional[str] = "PLA"

@app.get("/api/bambu/status")
async def get_bambu_status():
    skill = brain.skills.get("bambu_hub")
    if skill:
        res = await skill.execute(action="get_status")
        res["pending_approval"] = getattr(skill, "current_pending_approval", None)
        return res
    return {"success": False}

@app.post("/api/bambu/action")
async def execute_bambu_action(req: BambuActionRequest):
    skill = brain.skills.get("bambu_hub")
    if not skill:
        raise HTTPException(status_code=500, detail="Bambu hub skill unavailable")
    res = await skill.execute(
        action=req.action,
        query=req.query,
        speed_level=req.speed_level,
        material=req.material
    )
    return res

@app.get("/api/models/file/{category}/{filename}")
async def get_model_stl_file(category: str, filename: str):
    file_path = MODELS_DIR / category / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Model file '{filename}' not found.")
    return FileResponse(file_path, media_type="application/octet-stream", filename=filename)

@app.get("/api/models/list")
async def get_models_list():
    if not MODELS_DIR.exists():
        return {"models": []}
    
    results = []
    from .skills.mesh_analyzer import MeshAnalyzer
    for folder in MODELS_DIR.iterdir():
        if folder.is_dir():
            for stl_path in folder.glob("*.stl"):
                try:
                    metrics = MeshAnalyzer.analyze_stl(stl_path)
                    results.append({
                        "category": folder.name,
                        "filename": stl_path.name,
                        "stl_url": f"/api/models/file/{folder.name}/{stl_path.name}",
                        "metrics": metrics,
                        "size_bytes": stl_path.stat().st_size,
                        "modified": stl_path.stat().st_mtime
                    })
                except Exception:
                    pass
    return {"models": sorted(results, key=lambda x: x.get("modified", 0), reverse=True)}

class TaskAddRequest(BaseModel):
    text: str

class TaskToggleRequest(BaseModel):
    task_id: int

class NoteAddRequest(BaseModel):
    title: Optional[str] = ""
    content: str

@app.get("/api/productivity/data")
async def get_productivity_data():
    skill = brain.skills.get("productivity_hub")
    if skill:
        return skill._load_data()
    return {"tasks": [], "notes": []}

@app.post("/api/productivity/task/add")
async def add_productivity_task(req: TaskAddRequest):
    skill = brain.skills.get("productivity_hub")
    if skill:
        return await skill.execute(action="add_task", text=req.text)
    return {"success": False}

@app.post("/api/productivity/task/toggle")
async def toggle_productivity_task(req: TaskToggleRequest):
    skill = brain.skills.get("productivity_hub")
    if skill:
        data = skill._load_data()
        for t in data.get("tasks", []):
            if t["id"] == req.task_id:
                t["completed"] = not t.get("completed", False)
                skill._save_data(data)
                return {"success": True, "task": t}
    return {"success": False}

@app.post("/api/productivity/task/delete")
async def delete_productivity_task(req: TaskToggleRequest):
    skill = brain.skills.get("productivity_hub")
    if skill:
        return await skill.execute(action="delete_task", task_id=req.task_id)
    return {"success": False}

@app.post("/api/productivity/note/add")
async def add_productivity_note(req: NoteAddRequest):
    skill = brain.skills.get("productivity_hub")
    if skill:
        return await skill.execute(action="take_note", title=req.title, text=req.content)
    return {"success": False}

@app.get("/api/spotify/status")
async def get_spotify_status():
    skill = brain.skills.get("spotify_hub")
    if skill:
        return await skill.execute(action="status")
    return {"success": False}

@app.get("/api/skills")
async def get_skills():
    return {
        "skills": brain.get_tool_schemas(),
        "learned_count": len(brain.self_learner.learned_skills_meta)
    }

@app.get("/api/settings")
async def get_settings():
    spotify_skill = brain.skills.get("spotify_hub")
    is_spot_auth = bool(spotify_skill and spotify_skill._get_spotipy() is not None)
    return {
        "llm": brain.llm_router.get_status(),
        "voice": {
            "name": brain.voice_engine.current_voice,
            "rate": brain.voice_engine.rate,
            "pitch": brain.voice_engine.pitch,
            "available": brain.voice_engine.AVAILABLE_VOICES
        },
        "bambu": {
            "ip": config.BAMBU_IP,
            "serial": config.BAMBU_SERIAL,
            "has_access_code": bool(config.BAMBU_ACCESS_CODE)
        },
        "spotify": {
            "client_id": config.SPOTIFY_CLIENT_ID,
            "has_secret": bool(config.SPOTIFY_CLIENT_SECRET),
            "is_authenticated": is_spot_auth,
            "auth_url": spotify_skill.get_auth_url() if (spotify_skill and not is_spot_auth) else None
        },
        "user_title": config.USER_TITLE
    }

@app.post("/api/settings")
async def update_settings(req: SettingsRequest):
    if req.llm_provider:
        config.LLM_PROVIDER = req.llm_provider
    if req.groq_api_key is not None:
        config.GROQ_API_KEY = req.groq_api_key.strip()
    if req.gemini_api_key is not None:
        config.GEMINI_API_KEY = req.gemini_api_key.strip()
    if req.voice_name:
        config.VOICE_NAME = req.voice_name
        brain.voice_engine.set_voice_profile(req.voice_name)
    if req.bambu_ip is not None:
        config.BAMBU_IP = req.bambu_ip
    if req.bambu_serial is not None:
        config.BAMBU_SERIAL = req.bambu_serial
    if req.bambu_access_code is not None:
        config.BAMBU_ACCESS_CODE = req.bambu_access_code
    if req.spotify_client_id is not None:
        config.SPOTIFY_CLIENT_ID = req.spotify_client_id.strip()
    if req.spotify_client_secret is not None:
        config.SPOTIFY_CLIENT_SECRET = req.spotify_client_secret.strip()

    # Save to .env
    env_file = BASE_DIR / ".env"
    env_lines = []
    if env_file.exists():
        with open(env_file, "r") as f:
            env_lines = f.readlines()
    
    def set_env_val(key, val):
        nonlocal env_lines
        found = False
        for idx, line in enumerate(env_lines):
            if line.startswith(f"{key}="):
                env_lines[idx] = f"{key}={val}\n"
                found = True
                break
        if not found:
            env_lines.append(f"{key}={val}\n")

    set_env_val("SPOTIFY_CLIENT_ID", config.SPOTIFY_CLIENT_ID)
    set_env_val("SPOTIFY_CLIENT_SECRET", config.SPOTIFY_CLIENT_SECRET)
    with open(env_file, "w") as f:
        f.writelines(env_lines)

    brain.llm_router.update_keys(
        provider=req.llm_provider,
        groq_key=req.groq_api_key,
        gemini_key=req.gemini_api_key
    )
    await brain.llm_router.auto_configure_models()

    return {"success": True, "message": "Settings updated and saved to .env."}

@app.get("/api/spotify/login")
async def spotify_login():
    from fastapi.responses import RedirectResponse
    spotify_skill = brain.skills.get("spotify_hub")
    url = spotify_skill.get_auth_url() if spotify_skill else None
    if url:
        return RedirectResponse(url)
    raise HTTPException(status_code=400, detail="Spotify credentials not configured in Settings.")

@app.get("/api/spotify/callback")
async def spotify_callback(code: str = ""):
    from fastapi.responses import RedirectResponse
    spotify_skill = brain.skills.get("spotify_hub")
    if spotify_skill and code:
        ok = spotify_skill.handle_auth_code(code)
        if ok:
            return RedirectResponse("/?spotify=connected")
    return RedirectResponse("/?spotify=error")

ui_dist = BASE_DIR.parent / "ui" / "dist"
if ui_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(ui_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        target_file = ui_dist / full_path
        if target_file.exists() and target_file.is_file():
            return FileResponse(str(target_file))
        return FileResponse(str(ui_dist / "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=config.HOST, port=config.PORT, reload=True)
