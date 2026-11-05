import os
import json
import time
import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .base import BaseSkill
from ..config import STORAGE_DIR, config


class AlarmClockSkill(BaseSkill):
    name = "alarm_clock"
    description = (
        "Controls Hexor's background alarm system. Sets, lists, and cancels alarms, "
        "and automatically triggers Spotify music and vocal wake-up calls at the specified time."
    )
    category = "automation"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set_alarm", "list_alarms", "cancel_alarm", "stop_alarm"],
                "description": "Alarm action to perform."
            },
            "time_str": {
                "type": "string",
                "description": "Alarm time (e.g., '7:00 AM', '19:30', 'in 15 minutes', '8 am')."
            },
            "music": {
                "type": "string",
                "description": "Optional song, artist, or playlist to play on Spotify when alarm fires."
            },
            "label": {
                "type": "string",
                "description": "Optional label for the alarm (e.g., 'Morning Wake Up', 'Meeting')."
            }
        },
        "required": ["action"]
    }

    def __init__(self):
        self.alarms_file = STORAGE_DIR / "alarms.json"
        self._ensure_storage()
        self.broadcast_callback = None
        self.spotify_skill = None
        self.voice_engine = None
        self.monitor_task: Optional[asyncio.Task] = None
        self.ringing_alarm: Optional[Dict[str, Any]] = None

    def _ensure_storage(self):
        if not self.alarms_file.exists():
            try:
                with open(self.alarms_file, "w") as f:
                    json.dump([], f)
            except Exception:
                pass

    def _load_alarms(self) -> List[Dict[str, Any]]:
        self._ensure_storage()
        try:
            with open(self.alarms_file, "r") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_alarms(self, alarms: List[Dict[str, Any]]):
        try:
            with open(self.alarms_file, "w") as f:
                json.dump(alarms, f, indent=2)
        except Exception:
            pass

    def start_monitor(self, broadcast_callback=None, spotify_skill=None, voice_engine=None):
        self.broadcast_callback = broadcast_callback
        self.spotify_skill = spotify_skill
        self.voice_engine = voice_engine
        if not self.monitor_task or self.monitor_task.done():
            self.monitor_task = asyncio.create_task(self._alarm_loop())
            print("[AlarmClock] Background alarm monitor started.")

    async def _alarm_loop(self):
        """Autonomous background monitor: zero frontend or chat thread blocking."""
        while True:
            try:
                now = time.time()
                alarms = self._load_alarms()
                remaining = []
                fired_alarms = []

                for a in alarms:
                    if a.get("status") == "active" and a.get("timestamp", 0) <= now:
                        fired_alarms.append(a)
                    else:
                        remaining.append(a)

                if fired_alarms:
                    self._save_alarms(remaining)
                    for alarm in fired_alarms:
                        asyncio.create_task(self._trigger_alarm(alarm))

            except Exception as e:
                pass

            await asyncio.sleep(1.0)

    async def _trigger_alarm(self, alarm: Dict[str, Any]):
        """Fires the alarm: triggers Spotify music, vocal announcement, and HUD alert."""
        self.ringing_alarm = alarm
        time_str = alarm.get("time_str", "now")
        label = alarm.get("label", "Alarm")
        music = alarm.get("music") or "Morning Chill"

        print(f"[AlarmClock] ALARM FIRING: '{label}' at {time_str} with music '{music}'")

        # 1. Trigger Spotify playback in background
        if self.spotify_skill:
            try:
                await self.spotify_skill.execute(action="play_song", query=music)
            except Exception as e:
                print(f"[AlarmClock] Error launching alarm Spotify music: {e}")

        # 2. Vocal Wake Greeting
        greeting = f"Sir, your alarm for {time_str} is ringing. Good morning."
        audio_payload = None
        if self.voice_engine:
            try:
                audio_payload = await self.voice_engine.synthesize(greeting)
            except Exception:
                pass

        # 3. Broadcast to HUD
        if self.broadcast_callback:
            packet = {
                "type": "alarm_triggered",
                "alarm": alarm,
                "greeting": greeting,
                "audio": audio_payload
            }
            await self.broadcast_callback(packet)

    def _parse_time(self, time_str: str) -> Optional[float]:
        """Parses flexible time expressions like '7:00 AM', '7:30', 'in 15 minutes', '8pm'."""
        now = datetime.now()
        clean = time_str.lower().strip()

        # Relative minutes/hours/seconds: "in 10 minutes", "in 1 hour"
        rel_match = re.search(r'in\s+(\d+)\s*(minute|min|m|hour|hr|h|second|sec|s)', clean)
        if rel_match:
            qty = int(rel_match.group(1))
            unit = rel_match.group(2)
            if unit.startswith('h'):
                delta = timedelta(hours=qty)
            elif unit.startswith('s'):
                delta = timedelta(seconds=qty)
            else:
                delta = timedelta(minutes=qty)
            return (now + delta).timestamp()

        # Just number + minutes: "10 minutes", "5 mins"
        quick_rel = re.match(r'^(\d+)\s*(minute|min|m|second|sec|s)$', clean)
        if quick_rel:
            qty = int(quick_rel.group(1))
            unit = quick_rel.group(2)
            delta = timedelta(seconds=qty) if unit.startswith('s') else timedelta(minutes=qty)
            return (now + delta).timestamp()

        # Standard 12h or 24h clock: "7:30 AM", "7:30", "19:00", "7 pm", "8am"
        # Extract hours, minutes, and am/pm
        m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', clean)
        if m:
            hour = int(m.group(1))
            minute = int(m.group(2)) if m.group(2) else 0
            meridiem = m.group(3)

            if meridiem == 'pm' and hour < 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0

            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            # If the target time has already passed today, schedule for tomorrow
            if target <= now:
                target += timedelta(days=1)
            return target.timestamp()

        return None

    async def execute(self, action: str, time_str: str = "", music: str = "", label: str = "", **kwargs) -> Dict[str, Any]:
        try:
            alarms = self._load_alarms()

            if action == "set_alarm":
                if not time_str:
                    return {"success": False, "message": "Please specify a time for the alarm, Sir."}

                target_ts = self._parse_time(time_str)
                if not target_ts:
                    return {"success": False, "message": f"Could not understand the time '{time_str}'. Try '7:00 AM' or 'in 15 minutes'."}

                chosen_music = music or "Morning Chill"
                alarm_id = f"alm_{int(time.time()*1000)}"
                dt_target = datetime.fromtimestamp(target_ts)
                formatted_time = dt_target.strftime("%I:%M %p").lstrip('0')

                alarm_entry = {
                    "id": alarm_id,
                    "time_str": formatted_time,
                    "timestamp": target_ts,
                    "music": chosen_music,
                    "label": label or "Wake Up",
                    "status": "active",
                    "created_at": time.time()
                }

                alarms.append(alarm_entry)
                self._save_alarms(alarms)

                # Broadcast updated alarms list to UI
                if self.broadcast_callback:
                    await self.broadcast_callback({"type": "alarms_updated", "alarms": alarms})

                diff_seconds = int(target_ts - time.time())
                diff_hours = diff_seconds // 3600
                diff_mins = (diff_seconds % 3600) // 60
                in_time = f"{diff_hours}h {diff_mins}m" if diff_hours > 0 else f"{diff_mins} minutes"

                return {
                    "success": True,
                    "message": f"Alarm set for {formatted_time} (in {in_time}). Spotify will play '{chosen_music}', Sir.",
                    "data": alarm_entry,
                    "ui_action": "alarm_set"
                }

            elif action == "list_alarms":
                now = time.time()
                active = [a for a in alarms if a.get("status") == "active" and a.get("timestamp", 0) > now]
                if not active:
                    return {
                        "success": True,
                        "message": "You have no active alarms scheduled, Sir.",
                        "data": {"alarms": []}
                    }

                items = []
                for a in active:
                    rem = max(0, int(a["timestamp"] - now))
                    h, m = rem // 3600, (rem % 3600) // 60
                    t_desc = f"{h}h {m}m" if h > 0 else f"{m}m"
                    items.append(f"{a['time_str']} ({a.get('label', 'Alarm')}, music: {a.get('music', 'Default')}, in {t_desc})")

                summary = "; ".join(items)
                return {
                    "success": True,
                    "message": f"Active alarms: {summary}.",
                    "data": {"alarms": active}
                }

            elif action in ["cancel_alarm", "stop_alarm"]:
                if action == "stop_alarm" and self.ringing_alarm:
                    self.ringing_alarm = None
                    if self.spotify_skill:
                        try:
                            await self.spotify_skill.execute(action="pause")
                        except Exception:
                            pass
                    return {
                        "success": True,
                        "message": "Alarm silenced and music paused, Sir.",
                        "data": None,
                        "ui_action": "alarm_stopped"
                    }

                # Cancel active alarms
                self._save_alarms([])
                if self.broadcast_callback:
                    await self.broadcast_callback({"type": "alarms_updated", "alarms": []})

                return {
                    "success": True,
                    "message": "All active alarms have been canceled, Sir.",
                    "data": {"alarms": []},
                    "ui_action": "alarm_cancelled"
                }

            return {"success": False, "message": f"Unsupported action: {action}"}

        except Exception as e:
            return {"success": False, "message": f"Alarm error: {str(e)}"}

