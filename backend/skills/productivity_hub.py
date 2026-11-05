import json
import time
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from .base import BaseSkill
from ..config import STORAGE_DIR

class ProductivityHubSkill(BaseSkill):
    name = "productivity_hub"
    description = "Manages daily tasks, to-do lists, quick notes, and asynchronous voice timers for maximum efficiency."
    category = "productivity"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "add_task", "list_tasks", "complete_task", "delete_task",
                    "take_note", "list_notes", "set_timer", "status"
                ]
            },
            "text": {"type": "string", "description": "Task description or note content"},
            "title": {"type": "string", "description": "Note title or timer label"},
            "duration_seconds": {"type": "integer", "description": "Timer duration in seconds"}
        },
        "required": ["action"]
    }

    def __init__(self):
        self.storage_file = STORAGE_DIR / "productivity.json"
        self.active_timers = {}
        self._ensure_storage()

    def _ensure_storage(self):
        if not self.storage_file.exists():
            default_data = {
                "tasks": [
                    {"id": 1, "text": "Inspect Bambu Lab A1 first layer adhesion", "completed": False, "created_at": datetime.now().isoformat()}
                ],
                "notes": [
                    {"id": 1, "title": "System Parameters", "content": "Hexor autonomous desktop active with 120B neural routing.", "created_at": datetime.now().isoformat()}
                ]
            }
            with open(self.storage_file, "w") as f:
                json.dump(default_data, f, indent=2)

    def _load_data(self) -> Dict[str, Any]:
        try:
            with open(self.storage_file, "r") as f:
                return json.load(f)
        except Exception:
            return {"tasks": [], "notes": []}

    def _save_data(self, data: Dict[str, Any]):
        try:
            with open(self.storage_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    async def execute(self, action: str, text: str = "", title: str = "", duration_seconds: int = 0, **kwargs) -> Dict[str, Any]:
        data = self._load_data()

        if action == "add_task":
            task_text = text or title or kwargs.get("query", "")
            if not task_text:
                return {"success": False, "message": "Task description required.", "data": None}
            new_id = max([t["id"] for t in data["tasks"]] + [0]) + 1
            new_task = {
                "id": new_id,
                "text": task_text,
                "completed": False,
                "created_at": datetime.now().isoformat()
            }
            data["tasks"].append(new_task)
            self._save_data(data)
            return {
                "success": True,
                "message": f"Task added to your docket, Sir: '{task_text}'.",
                "data": {"task": new_task, "total_active": len([t for t in data["tasks"] if not t["completed"]])},
                "ui_action": "tasks_updated"
            }

        elif action == "list_tasks":
            tasks = data.get("tasks", [])
            pending = [t for t in tasks if not t.get("completed")]
            if not pending:
                return {
                    "success": True,
                    "message": "Your task agenda is currently clear, Sir.",
                    "data": {"tasks": tasks}
                }
            items_str = "; ".join([f"#{t['id']} {t['text']}" for t in pending])
            return {
                "success": True,
                "message": f"You have {len(pending)} pending tasks, Sir: {items_str}.",
                "data": {"tasks": tasks, "pending_count": len(pending)},
                "ui_action": "tasks_updated"
            }

        elif action == "complete_task":
            query = (text or title or str(kwargs.get("task_id", ""))).lower().strip()
            tasks = data.get("tasks", [])
            found = None
            for t in tasks:
                if str(t["id"]) == query or (query and query in t["text"].lower()):
                    t["completed"] = True
                    found = t
                    break
            if found:
                self._save_data(data)
                return {
                    "success": True,
                    "message": f"Task #{found['id']} marked as complete, Sir.",
                    "data": {"completed_task": found},
                    "ui_action": "tasks_updated"
                }
            return {"success": False, "message": f"Could not find matching task for '{query}'.", "data": None}

        elif action == "delete_task":
            query = (text or title or str(kwargs.get("task_id", ""))).lower().strip()
            before_len = len(data["tasks"])
            data["tasks"] = [t for t in data["tasks"] if str(t["id"]) != query and query not in t["text"].lower()]
            if len(data["tasks"]) < before_len:
                self._save_data(data)
                return {"success": True, "message": "Task excised from records, Sir.", "data": None}
            return {"success": False, "message": "No matching task found.", "data": None}

        elif action == "take_note":
            note_content = text or kwargs.get("content", "")
            note_title = title or (note_content[:30] + "...")
            new_id = max([n["id"] for n in data["notes"]] + [0]) + 1
            new_note = {
                "id": new_id,
                "title": note_title,
                "content": note_content,
                "created_at": datetime.now().isoformat()
            }
            data["notes"].append(new_note)
            self._save_data(data)
            return {
                "success": True,
                "message": f"Note recorded in internal memory, Sir: '{note_title}'.",
                "data": {"note": new_note},
                "ui_action": "notes_updated"
            }

        elif action == "list_notes":
            notes = data.get("notes", [])
            return {
                "success": True,
                "message": f"Retrieved {len(notes)} archived notes, Sir.",
                "data": {"notes": notes},
                "ui_action": "notes_updated"
            }

        elif action == "set_timer":
            secs = duration_seconds
            if not secs and text:
                # Extract numbers from text e.g. "10 minutes", "30 seconds"
                import re
                m_min = re.search(r'(\d+)\s*(?:m|min|minute)', text.lower())
                m_sec = re.search(r'(\d+)\s*(?:s|sec|second)', text.lower())
                if m_min:
                    secs += int(m_min.group(1)) * 60
                if m_sec:
                    secs += int(m_sec.group(1))
            secs = secs or 60
            label = title or text or "Timer"

            timer_id = f"timer_{int(time.time())}"
            asyncio.create_task(self._run_async_timer(secs, label, timer_id))

            mins_display = f"{secs // 60}m {secs % 60}s" if secs >= 60 else f"{secs}s"
            return {
                "success": True,
                "message": f"Timer set for {mins_display} for '{label}', Sir. I shall alert you upon expiration.",
                "data": {"duration_seconds": secs, "label": label},
                "ui_action": "timer_started"
            }

        elif action == "status":
            tasks = data.get("tasks", [])
            pending = [t for t in tasks if not t.get("completed")]
            notes = data.get("notes", [])
            return {
                "success": True,
                "message": f"Productivity status: {len(pending)} pending tasks, {len(notes)} notes.",
                "data": {"pending_tasks": len(pending), "notes_count": len(notes)}
            }

        return {"success": False, "message": f"Unsupported productivity action: {action}", "data": None}

    async def _run_async_timer(self, seconds: int, label: str, timer_id: str):
        await asyncio.sleep(seconds)
        try:
            # Play audible alert sound via powershell beep or TTS
            cmd = '[console]::beep(800, 300); [console]::beep(1000, 400); [console]::beep(1200, 500)'
            import subprocess
            subprocess.Popen(["powershell", "-NoProfile", "-Command", cmd])
        except Exception:
            pass

