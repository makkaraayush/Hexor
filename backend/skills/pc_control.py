import subprocess
import os
import sys
import psutil
from typing import Dict, Any
from .base import BaseSkill

class PCControlSkill(BaseSkill):
    name = "pc_control"
    description = "Controls local PC operations: launch/close apps, run commands, volume, and media keys."
    category = "pc_control"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "launch_app", "close_app", "execute_command",
                    "set_volume", "volume_up", "volume_down", "mute",
                    "media_play_pause", "media_next", "media_prev",
                    "lock_pc", "minimize_all", "screenshot"
                ]
            },
            "target": {"type": "string"},
            "value": {"type": "string"}
        },
        "required": ["action"]
    }

    async def execute(self, action: str, target: str = "", value: str = "", **kwargs) -> Dict[str, Any]:
        try:
            if action == "launch_app":
                target_lower = target.lower().strip()
                known_apps = {
                    "spotify": "spotify",
                    "chrome": "chrome",
                    "notepad": "notepad",
                    "calc": "calc",
                    "calculator": "calc",
                    "bambu studio": "bambu-studio",
                    "bambu": "bambu-studio",
                    "vscode": "code",
                    "code": "code",
                    "terminal": "wt",
                    "explorer": "explorer",
                    "edge": "msedge"
                }
                app_cmd = known_apps.get(target_lower, target)
                subprocess.Popen(f'start "" "{app_cmd}"', shell=True)
                return {
                    "success": True,
                    "message": f"Successfully launched {target}.",
                    "data": {"app": target}
                }

            elif action == "close_app":
                target_lower = target.lower()
                killed = []
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        pname = proc.info['name'].lower()
                        if target_lower in pname:
                            proc.terminate()
                            killed.append(pname)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                if killed:
                    return {
                        "success": True,
                        "message": f"Closed process {target}.",
                        "data": {"terminated": list(set(killed))}
                    }
                return {
                    "success": False,
                    "message": f"No active processes found matching '{target}'.",
                    "data": None
                }

            elif action == "execute_command":
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", target],
                    capture_output=True,
                    text=True,
                    timeout=15
                )
                output = (result.stdout or result.stderr).strip()
                return {
                    "success": result.returncode == 0,
                    "message": f"Command executed (exit code {result.returncode}).",
                    "data": {"output": output[:2000]}
                }

            elif action in ["set_volume", "volume_up", "volume_down", "mute"]:
                if action == "volume_up":
                    cmd = "$obj = New-Object -ComObject Wscript.Shell; 1..5 | ForEach-Object { $obj.SendKeys([char]175) }"
                elif action == "volume_down":
                    cmd = "$obj = New-Object -ComObject Wscript.Shell; 1..5 | ForEach-Object { $obj.SendKeys([char]174) }"
                elif action == "mute":
                    cmd = "$obj = New-Object -ComObject Wscript.Shell; $obj.SendKeys([char]173)"
                else:
                    level = int(value) if value.isdigit() else 50
                    cmd = f"""
                    Function Set-Speaker($volume) {{
                        $wsh = New-Object -ComObject WScript.Shell
                        1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }}
                        1..[math]::Round($volume/2) | ForEach-Object {{ $wsh.SendKeys([char]175) }}
                    }}
                    Set-Speaker {level}
                    """
                subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
                return {
                    "success": True,
                    "message": f"Volume command executed: {action}",
                    "data": {"action": action}
                }

            elif action in ["media_play_pause", "media_next", "media_prev"]:
                key_map = {
                    "media_play_pause": 179,
                    "media_next": 176,
                    "media_prev": 177
                }
                char_code = key_map.get(action, 179)
                cmd = f"$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]{char_code})"
                subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
                return {
                    "success": True,
                    "message": f"Media key dispatched: {action}",
                    "data": {"media_action": action}
                }

            elif action == "lock_pc":
                subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"])
                return {"success": True, "message": "Workstation locked.", "data": None}

            elif action == "minimize_all":
                cmd = "$wsh = New-Object -ComObject Shell.Application; $wsh.MinimizeAll()"
                subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
                return {"success": True, "message": "All windows minimized.", "data": None}

            elif action == "screenshot":
                from ..config import AUDIO_CACHE_DIR
                import time
                shot_file = AUDIO_CACHE_DIR / f"screenshot_{int(time.time())}.png"
                cmd = f"""
                Add-Type -AssemblyName System.Windows.Forms
                Add-Type -AssemblyName System.Drawing
                $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
                $bitmap = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
                $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
                $bitmap.Save('{shot_file}')
                $graphics.Dispose()
                $bitmap.Dispose()
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True)
                return {
                    "success": True,
                    "message": "Desktop screenshot captured.",
                    "data": {"file_path": str(shot_file), "filename": shot_file.name},
                    "ui_action": "show_screenshot"
                }

            return {"success": False, "message": f"Unknown action: {action}", "data": None}

        except Exception as e:
            return {"success": False, "message": f"PC control error: {str(e)}", "data": None}
