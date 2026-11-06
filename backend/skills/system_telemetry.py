import psutil
import time
from typing import Dict, Any
from .base import BaseSkill

class SystemTelemetrySkill(BaseSkill):
    name = "system_telemetry"
    description = "Provides real-time PC diagnostic metrics: CPU, RAM, Disk, Network, and battery."
    category = "system"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_metrics", "list_top_processes"]
            }
        },
        "required": ["action"]
    }

    def __init__(self):
        self._prev_net = psutil.net_io_counters()
        self._prev_time = time.time()
        self._last_cpu_time = 0.0
        self._cached_cpu = 0.0
        try:
            self._cached_cpu = psutil.cpu_percent(interval=None)
            self._last_cpu_time = time.time()
        except Exception:
            pass

    async def execute(self, action: str = "get_metrics", **kwargs) -> Dict[str, Any]:
        try:
            if action == "get_metrics":
                now = time.time()
                # Rate-limit psutil.cpu_percent queries to minimum 0.8s interval.
                # Microsecond calls between WS broadcaster and REST poll cause psutil to calculate false 100.0% spikes.
                if now - self._last_cpu_time >= 0.8:
                    try:
                        self._cached_cpu = psutil.cpu_percent(interval=None)
                        self._last_cpu_time = now
                    except Exception:
                        pass
                cpu_percent = self._cached_cpu
                mem = psutil.virtual_memory()
                import os
                try:
                    drive = os.path.splitdrive(os.getcwd())[0] or "C:"
                    disk = psutil.disk_usage(f"{drive}\\")
                except Exception:
                    try:
                        disk = psutil.disk_usage("C:\\")
                    except Exception:
                        disk = psutil.disk_usage('/')
                
                now = time.time()
                curr_net = psutil.net_io_counters()
                dt = max(0.1, now - self._prev_time)
                up_speed = (curr_net.bytes_sent - self._prev_net.bytes_sent) / dt / 1024
                down_speed = (curr_net.bytes_recv - self._prev_net.bytes_recv) / dt / 1024
                self._prev_net = curr_net
                self._prev_time = now

                battery = psutil.sensors_battery()
                battery_info = {
                    "percent": battery.percent if battery else 100,
                    "power_plugged": battery.power_plugged if battery else True
                }

                telemetry = {
                    "cpu_usage": round(cpu_percent, 1),
                    "cpu_cores": psutil.cpu_count(logical=True),
                    "memory_percent": round(mem.percent, 1),
                    "memory_used_gb": round(mem.used / (1024**3), 2),
                    "memory_total_gb": round(mem.total / (1024**3), 2),
                    "disk_percent": round(disk.percent, 1),
                    "disk_free_gb": round(disk.free / (1024**3), 2),
                    "net_upload_kbps": round(up_speed, 1),
                    "net_download_kbps": round(down_speed, 1),
                    "battery": battery_info,
                    "timestamp": time.time()
                }

                return {
                    "success": True,
                    "message": f"Diagnostics: CPU {telemetry['cpu_usage']}%, RAM {telemetry['memory_percent']}%.",
                    "data": telemetry,
                    "ui_action": "telemetry_update"
                }

            elif action == "list_top_processes":
                procs = []
                for p in sorted(psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']), 
                                key=lambda x: x.info.get('cpu_percent', 0) or 0, 
                                reverse=True)[:5]:
                    procs.append({
                        "pid": p.info['pid'],
                        "name": p.info['name'],
                        "cpu": round(p.info.get('cpu_percent', 0) or 0, 1),
                        "memory": round(p.info.get('memory_percent', 0) or 0, 1)
                    })
                return {
                    "success": True,
                    "message": f"Retrieved top {len(procs)} processes.",
                    "data": {"processes": procs}
                }

            return {"success": False, "message": f"Unsupported action: {action}", "data": None}

        except Exception as e:
            return {"success": False, "message": f"Telemetry error: {str(e)}", "data": None}
