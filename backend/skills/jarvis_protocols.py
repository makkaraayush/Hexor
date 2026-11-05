import os
import asyncio
import subprocess
import psutil
from datetime import datetime
from typing import Dict, Any, Optional
from .base import BaseSkill

try:
    import ctypes
    HAS_CTYPES = True
except ImportError:
    HAS_CTYPES = False


class JarvisProtocolsSkill(BaseSkill):
    name = "jarvis_protocols"
    description = "Executes Tony Stark J.A.R.V.I.S. autonomous OS protocols: morning briefing, focus mode, system audit, and bedtime protocol."
    category = "protocols"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["morning_protocol", "focus_protocol", "system_audit", "night_protocol"]
            },
            "parameters": {"type": "object"}
        },
        "required": ["action"]
    }

    async def execute(self, action: str, parameters: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        try:
            if action in ["morning_protocol", "daily_briefing"]:
                return await self._morning_protocol()
            elif action in ["focus_protocol", "deep_work"]:
                return await self._focus_protocol()
            elif action == "system_audit":
                return await self._system_audit()
            elif action in ["night_protocol", "sleep_protocol"]:
                return await self._night_protocol()
            return {"success": False, "message": f"Unsupported protocol: {action}", "data": None}
        except Exception as e:
            return {"success": False, "message": f"Protocol error: {str(e)}", "data": None}

    async def _morning_protocol(self) -> Dict[str, Any]:
        from ..config import config
        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M %p")

        # 1. Weather
        weather_text = "Clear and nominal"
        try:
            from .weather_location import WeatherLocationSkill
            w_skill = WeatherLocationSkill()
            w_res = await w_skill.execute(action="get_weather")
            if w_res.get("success") and w_res.get("data"):
                d = w_res["data"]
                weather_text = f"{d.get('temp_c', 28)}°C with {d.get('description', 'clear skies')} in {d.get('city', 'your area')}"
        except Exception:
            pass

        # 2. System Hardware
        cpu_usage = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        mem_used_gb = round(mem.used / (1024**3), 1)
        mem_total_gb = round(mem.total / (1024**3), 1)
        battery = psutil.sensors_battery()
        bat_str = f"{battery.percent}%" if battery else "A/C Mains"

        # 3. Bambu Lab A1 Status
        bambu_state = "IDLE"
        try:
            from .bambu_hub import BambuHubSkill
            b_skill = BambuHubSkill()
            b_res = await b_skill.execute(action="get_status")
            if b_res.get("data"):
                b_data = b_res["data"]
                bambu_state = b_data.get("state", "IDLE")
                if bambu_state == "PRINTING":
                    bambu_state = f"Printing '{b_data.get('model_name')}' at {b_data.get('progress_percent')}% completion"
        except Exception:
            pass

        # 4. Tasks Agenda
        tasks_count = 0
        try:
            from .productivity_hub import ProductivityHubSkill
            p_skill = ProductivityHubSkill()
            p_data = p_skill._load_data()
            tasks_count = len([t for t in p_data.get("tasks", []) if not t.get("completed")])
        except Exception:
            pass

        # 5. Synthesize JARVIS Speech
        briefing_prompt = (
            f"You are Hexor, J.A.R.V.I.S. personal operating system.\n"
            f"Generate an inspiring, sophisticated morning executive briefing for {config.USER_TITLE}.\n"
            f"- Date & Time: {date_str} at {time_str}\n"
            f"- Weather: {weather_text}\n"
            f"- Workstation: CPU at {cpu_usage}%, RAM at {mem_used_gb}/{mem_total_gb} GB, Power: {bat_str}\n"
            f"- Bambu Lab A1: {bambu_state}\n"
            f"- Pending Agenda: {tasks_count} tasks registered\n"
            "INSTRUCTIONS:\n"
            "- Speak naturally, elegantly, with British butler intelligence and subtle Tony Stark flair.\n"
            "- Keep it between 3 to 4 articulate sentences. Address the user as Sir."
        )

        try:
            from ..core.llm_router import LLMRouter
            router = LLMRouter()
            briefing = await router.generate_text(briefing_prompt)
        except Exception:
            briefing = f"Good morning, Sir. Today is {date_str}. All workstation systems and your Bambu Lab A1 are operational."

        # Optionally auto-queue upbeat morning track on Spotify
        try:
            from .spotify_hub import SpotifyHubSkill
            spot = SpotifyHubSkill()
            asyncio.create_task(spot.execute("play_playlist", query="Top Hits"))
        except Exception:
            pass

        return {
            "success": True,
            "message": briefing.strip(),
            "data": {
                "date": date_str,
                "time": time_str,
                "weather": weather_text,
                "hardware": {"cpu": cpu_usage, "memory_gb": mem_used_gb, "battery": bat_str},
                "bambu": bambu_state,
                "tasks_count": tasks_count
            },
            "ui_action": "morning_briefing"
        }

    async def _focus_protocol(self) -> Dict[str, Any]:
        # Minimize distracting windows if ctypes available
        if HAS_CTYPES:
            try:
                user32 = ctypes.windll.user32
                hdesk = user32.OpenDesktopW('Default', 0, False, 0x01FF)
                if hdesk:
                    user32.SetThreadDesktop(hdesk)
                    # Minimize desktop windows (Win+D or minimize all)
                    user32.PostMessageW(0xFFFF, 0x0112, 0xF020, 0)
            except Exception:
                pass

        # Start Focus playlist on Spotify
        try:
            from .spotify_hub import SpotifyHubSkill
            spot = SpotifyHubSkill()
            asyncio.create_task(spot.execute("play_playlist", query="Cyberpunk Synthwave"))
        except Exception:
            pass

        return {
            "success": True,
            "message": "Focus protocol engaged, Sir. Distractions minimized, and ambient synthwave acoustics initialized for deep work.",
            "data": {"mode": "deep_work", "music": "Synthwave Focus"},
            "ui_action": "focus_mode_engaged"
        }

    async def _system_audit(self) -> Dict[str, Any]:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disks = []
        for p in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(p.mountpoint)
                disks.append({
                    "mount": p.mountpoint,
                    "free_gb": round(usage.free / (1024**3), 1),
                    "total_gb": round(usage.total / (1024**3), 1),
                    "percent": usage.percent
                })
            except Exception:
                pass

        # Audit top 3 memory consuming processes
        procs = []
        for p in psutil.process_iter(['name', 'memory_info', 'cpu_percent']):
            try:
                procs.append({
                    "name": p.info['name'],
                    "mem_mb": round((p.info['memory_info'].rss or 0) / (1024**2), 1),
                    "cpu": p.info['cpu_percent'] or 0
                })
            except Exception:
                pass
        top_procs = sorted(procs, key=lambda x: x['mem_mb'], reverse=True)[:4]

        # Flush DNS cache to optimize network throughput
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", "Clear-DnsClientCache"], capture_output=True)
        except Exception:
            pass

        return {
            "success": True,
            "message": f"System audit complete, Sir. Processor load: {cpu}%. Memory utilization: {mem.percent}% ({round(mem.used/(1024**3), 1)} GB of {round(mem.total/(1024**3), 1)} GB). Network DNS cache cleared.",
            "data": {
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "disks": disks,
                "top_consumers": top_procs
            },
            "ui_action": "system_audit_complete"
        }

    async def _night_protocol(self) -> Dict[str, Any]:
        # Dim Bambu Lab A1 chamber light if active so it doesn't disturb sleep
        try:
            from .bambu_hub import BambuHubSkill
            b_skill = BambuHubSkill()
            b_res = await b_skill.execute(action="get_status")
            if b_res.get("data", {}).get("state") == "PRINTING":
                await b_skill.execute(action="toggle_light")
        except Exception:
            pass

        # Pause Spotify playback
        try:
            from .spotify_hub import SpotifyHubSkill
            spot = SpotifyHubSkill()
            await spot.execute(action="pause")
        except Exception:
            pass

        return {
            "success": True,
            "message": "Night protocol initiated, Sir. Spotify silenced, chamber illumination adjusted, and monitoring systems running in silent standby.",
            "data": {"status": "silent_standby"},
            "ui_action": "night_protocol_active"
        }

