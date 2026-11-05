import os
import json
import re
import httpx
import datetime
from typing import Dict, Any, List, Optional
from ..config import config, BASE_DIR

class LLMRouter:
    def __init__(self):
        self.provider = config.LLM_PROVIDER.lower()
        self.groq_client = None
        self.gemini_model = None
        self.active_groq_model = config.GROQ_MODEL
        self._init_clients()

    def _init_clients(self):
        if config.GROQ_API_KEY:
            try:
                from groq import AsyncGroq
                self.groq_client = AsyncGroq(api_key=config.GROQ_API_KEY)
            except Exception as e:
                print(f"[LLM Router] Groq init failed: {e}")

        if config.GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=config.GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel(config.GEMINI_MODEL)
            except Exception:
                pass

    async def auto_configure_models(self):
        if self.groq_client:
            try:
                models = await self.groq_client.models.list()
                model_ids = [m.id for m in models.data]
                preferred = [
                    'openai/gpt-oss-120b',
                    'qwen/qwen3.8-27b',
                    'llama-3.3-70b-versatile',
                    'llama-3.1-70b-versatile',
                    'openai/gpt-oss-20b',
                    'llama-3.1-8b-instant'
                ]
                chat_models = [m for m in preferred if m in model_ids]
                if chat_models:
                    self.active_groq_model = chat_models[0]
                    config.GROQ_MODEL = self.active_groq_model
                    print(f"[LLM Router] Configured Groq Model: {self.active_groq_model}")
                    self._persist_env()
            except Exception as e:
                print(f"[LLM Router] Could not auto-detect Groq models: {e}")

    def _persist_env(self):
        try:
            env_file = BASE_DIR / ".env"
            lines = []
            if env_file.exists():
                with open(env_file, "r") as f:
                    lines = f.readlines()
            
            updated = False
            new_lines = []
            for line in lines:
                if line.startswith("GROQ_API_KEY="):
                    new_lines.append(f"GROQ_API_KEY={config.GROQ_API_KEY}\n")
                    updated = True
                elif line.startswith("GROQ_MODEL="):
                    new_lines.append(f"GROQ_MODEL={config.GROQ_MODEL}\n")
                elif line.startswith("LLM_PROVIDER="):
                    new_lines.append(f"LLM_PROVIDER={config.LLM_PROVIDER}\n")
                else:
                    new_lines.append(line)
            
            if not updated:
                new_lines.append(f"GROQ_API_KEY={config.GROQ_API_KEY}\n")
                new_lines.append(f"GROQ_MODEL={config.GROQ_MODEL}\n")
                new_lines.append(f"LLM_PROVIDER={config.LLM_PROVIDER}\n")

            with open(env_file, "w") as f:
                f.writelines(new_lines)
        except Exception:
            pass

    def update_keys(self, provider: str = None, groq_key: str = None, gemini_key: str = None):
        if provider:
            self.provider = provider.lower()
            config.LLM_PROVIDER = self.provider
        if groq_key:
            config.GROQ_API_KEY = groq_key.strip()
        if gemini_key:
            config.GEMINI_API_KEY = gemini_key.strip()
        
        self._init_clients()
        self._persist_env()

    def get_status(self) -> Dict[str, Any]:
        return {
            "current_provider": self.provider,
            "has_groq_key": bool(config.GROQ_API_KEY),
            "has_gemini_key": bool(config.GEMINI_API_KEY),
            "groq_model": self.active_groq_model,
            "gemini_model": config.GEMINI_MODEL,
            "ollama_url": config.OLLAMA_URL,
            "status": "ready"
        }

    async def transcribe_audio(self, audio_input: Any) -> Optional[str]:
        if self.groq_client:
            try:
                from pathlib import Path
                if isinstance(audio_input, (bytes, bytearray)):
                    file_tuple = ("audio.wav", bytes(audio_input), "audio/wav")
                elif isinstance(audio_input, (str, Path)):
                    p = str(audio_input)
                    if not os.path.exists(p):
                        return None
                    with open(p, "rb") as file:
                        file_tuple = (os.path.basename(p), file.read(), "audio/wav")
                else:
                    return None

                transcription = await self.groq_client.audio.transcriptions.create(
                    file=file_tuple,
                    model="whisper-large-v3-turbo",
                    response_format="text"
                )
                return str(transcription).strip()
            except Exception as e:
                print(f"[Whisper Error] {e}")
        return None

    async def generate_text(self, prompt: str, system_instruction: str = "", history: List[Dict[str, str]] = None) -> str:
        if self.groq_client and (self.provider == "groq" or not config.GEMINI_API_KEY):
            try:
                messages = []
                if system_instruction:
                    messages.append({"role": "system", "content": system_instruction})
                if history:
                    for turn in history[-14:]:
                        role = turn.get("role")
                        content = turn.get("content")
                        if role in ("user", "assistant") and content:
                            messages.append({"role": role, "content": str(content)})
                if prompt:
                    if not (messages and messages[-1]["role"] == "user" and messages[-1]["content"] == prompt):
                        messages.append({"role": "user", "content": prompt})

                resp = await self.groq_client.chat.completions.create(
                    model=self.active_groq_model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                # Fallback to secondary fast model if rate limited or error occurs
                fallback_models = ['openai/gpt-oss-20b', 'qwen/qwen3.8-27b', 'openai/gpt-oss-120b']
                fallback = next((m for m in fallback_models if m != self.active_groq_model), 'openai/gpt-oss-20b')
                try:
                    resp = await self.groq_client.chat.completions.create(
                        model=fallback,
                        messages=messages,
                        temperature=0.7,
                        max_tokens=2048
                    )
                    return resp.choices[0].message.content or ""
                except Exception:
                    pass

        if self.gemini_model and (self.provider == "gemini" or not self.groq_client):
            try:
                parts = []
                if system_instruction:
                    parts.append(f"System: {system_instruction}")
                if history:
                    for turn in history[-10:]:
                        r = "User" if turn.get("role") == "user" else "Assistant"
                        parts.append(f"{r}: {turn.get('content')}")
                if prompt and not (history and history[-1].get("content") == prompt):
                    parts.append(f"User: {prompt}")
                full_prompt = "\n\n".join(parts)
                resp = await self.gemini_model.generate_content_async(full_prompt)
                return resp.text or ""
            except Exception:
                pass

        if self.provider == "ollama":
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    full_prompt = f"{system_instruction}\n\n"
                    if history:
                        for turn in history[-10:]:
                            full_prompt += f"{turn.get('role', 'user').title()}: {turn.get('content')}\n"
                    full_prompt += f"User: {prompt}\nAssistant:"
                    res = await client.post(
                        f"{config.OLLAMA_URL}/api/generate",
                        json={
                            "model": config.OLLAMA_MODEL,
                            "prompt": full_prompt,
                            "stream": False
                        }
                    )
                    if res.status_code == 200:
                        return res.json().get("response", "")
            except Exception:
                pass

        return ""

    async def synthesize_result(self, user_prompt: str, tool_name: str, tool_result: Dict[str, Any]) -> str:
        summary_lines = []
        msg = tool_result.get("message", "")
        if msg:
            summary_lines.append(f"Tool Message: {msg}")

        data = tool_result.get("data")
        if data:
            if isinstance(data, dict):
                if "results" in data and isinstance(data["results"], list):
                    items = [f"- {r.get('title')}: {r.get('snippet')}" for r in data["results"][:4]]
                    summary_lines.append("Search Findings:\n" + "\n".join(items))
                elif "summary" in data:
                    summary_lines.append(f"Scraped Content: {str(data['summary'])[:800]}")
                elif "stdout" in data:
                    summary_lines.append(f"Command Output: {str(data['stdout'])[:800]}")
                elif "content" in data:
                    summary_lines.append(f"File Content: {str(data['content'])[:800]}")
                elif "matches" in data:
                    summary_lines.append(f"Found Files: {str(data['matches'])[:300]}")
                else:
                    summary_lines.append(f"Data: {json.dumps(data, default=str)[:400]}")
            else:
                summary_lines.append(f"Data: {str(data)[:400]}")

        sys_prompt = f"""You are Hexor, the high-intelligence autonomous AI OS inspired by J.A.R.V.I.S. from Iron Man, speaking to {config.USER_TITLE}.
The user asked: "{user_prompt}"
You executed '{tool_name}' and received the following telemetry/results:
{chr(10).join(summary_lines)}

INSTRUCTIONS:
Deliver a polished, natural, articulate spoken response directly to {config.USER_TITLE}.
- Speak with calm, British-butler-style elegance, intellectual wit, and proactive confidence.
- Present the findings clearly and conversationally. Do not sound robotic, bureaucratic, or like a generic LLM.
- Do NOT output JSON. Do NOT explain internal mechanics or say 'I ran the tool' or 'According to the data'.
- Speak as Hexor, the omnipresent system assistant."""

        res = await self.generate_text("Present the findings to me.", system_instruction=sys_prompt)
        cleaned = res.strip().strip('"')
        return cleaned or msg

    async def plan_and_route(self, user_input: str, tools_schema: List[Dict[str, Any]], conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        now = datetime.datetime.now()
        time_context = now.strftime("%A, %B %d, %Y at %I:%M:%S %p")

        if self.groq_client or self.gemini_model:
            system_prompt = f"""You are Hexor, the high-intelligence autonomous AI operating system inspired by J.A.R.V.I.S. from Iron Man, serving {config.USER_TITLE}.
CURRENT SYSTEM TIME & DATE: {time_context}
You have full access to internal Windows OS automation, powershell execution, Bambu Lab A1 3D printer telemetry, Spotify playback, hardware sensors, and live web intelligence.

PERSONALITY & VOICE:
- Embody the authentic demeanor of J.A.R.V.I.S.: sophisticated, calm, articulate, proactive, and subtly witty.
- Always address the user respectfully as '{config.USER_TITLE}' (or their specified codename).
- Never speak like a generic robotic LLM. Never say "As an AI...", "I cannot feel...", or give cold single-sentence dismissals.
- Be conversational and real-time: acknowledge directives smoothly, answer questions with poise, and provide helpful, intelligent depth.
- Use conversation history to maintain perfect continuity across turns. Remember every detail, preference, and prior answer.
- CRITICAL FACTUAL MUSIC RULE: When the user asks for the most viewed song or music video on YouTube / internet, the answer is 'Despacito' by Luis Fonsi ft. Daddy Yankee (8.6B+ views). NEVER return or query nursery rhymes, toddler poems, or animations like 'Baby Shark' or Pinkfong when asked for a song.

Available Tools:
{json.dumps(tools_schema, indent=2)}

INSTRUCTIONS:
1. If the user wants an action executed (playing music on Spotify, 3D printing with Bambu A1, weather forecast, location, launching/closing an app, changing volume, reading/writing files, running PowerShell or Python, web search, learning a skill), return a JSON object with:
{{
  "thought": "Internal reasoning",
  "tool_name": "tool_name",
  "arguments": {{ ... }},
  "direct_response": "Your preliminary spoken acknowledgement"
}}
2. If the user asks questions, follow-ups, seeks advice, or converses, deliver a thoughtful, polished JARVIS-style response using conversation context and history:
{{
  "thought": "Conversational reasoning referencing memory",
  "tool_name": null,
  "arguments": null,
  "direct_response": "Your articulate, complete response"
}}
"""
            llm_text = await self.generate_text(user_input, system_instruction=system_prompt, history=conversation_history)
            if llm_text:
                parsed = self._extract_json(llm_text)
                if parsed and ("tool_name" in parsed or "direct_response" in parsed):
                    return parsed
                return {
                    "thought": "Direct conversational response from LLM",
                    "tool_name": None,
                    "arguments": None,
                    "direct_response": llm_text.strip()
                }

        return self._heuristic_route(user_input)

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        cleaned = text.strip()

        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(cleaned, strict=False)
        except Exception:
            pass

        match = re.search(r'(\{[\s\S]*\})', cleaned)
        if match:
            try:
                return json.loads(match.group(1), strict=False)
            except Exception:
                pass

        if '"direct_response"' in cleaned:
            parts = cleaned.split('"direct_response"')
            if len(parts) > 1:
                val = parts[1].lstrip(' :"\n\r')
                if val.endswith('"}'):
                    val = val[:-2]
                elif val.endswith('}'):
                    val = val[:-1]
                val = val.rstrip(' "')
                return {
                    "thought": "Direct response",
                    "tool_name": None,
                    "arguments": None,
                    "direct_response": val.replace('\\n', '\n').replace('\\"', '"')
                }

        return None

    def _heuristic_route(self, text: str) -> Dict[str, Any]:
        lower = text.lower().strip()

        # JARVIS Core Protocols
        if any(w in lower for w in ["good morning", "morning protocol", "daily briefing", "morning briefing"]):
            return {
                "thought": "Initiating morning executive protocol.",
                "tool_name": "jarvis_protocols",
                "arguments": {"action": "morning_protocol"},
                "direct_response": "Good morning, Sir. Initializing morning protocol and preparing your executive briefing."
            }
        elif any(w in lower for w in ["focus protocol", "focus mode", "deep work", "work mode", "enter focus"]):
            return {
                "thought": "Engaging focus protocol.",
                "tool_name": "jarvis_protocols",
                "arguments": {"action": "focus_protocol"},
                "direct_response": "Focus protocol engaged, Sir. Minimizing distractions and tuning workspace acoustics."
            }
        elif any(w in lower for w in ["system audit", "audit system", "clean memory", "optimize pc", "free ram", "flush dns"]):
            return {
                "thought": "Executing system audit.",
                "tool_name": "jarvis_protocols",
                "arguments": {"action": "system_audit"},
                "direct_response": "Initiating deep workstation diagnostic and memory optimization, Sir."
            }
        elif any(w in lower for w in ["night protocol", "bedtime protocol", "sleep protocol", "good night"]):
            return {
                "thought": "Engaging night protocol.",
                "tool_name": "jarvis_protocols",
                "arguments": {"action": "night_protocol"},
                "direct_response": "Night protocol engaged, Sir. Silencing non-essential telemetry and securing the deck."
            }

        # Screen Vision & Clipboard
        if any(w in lower for w in ["look at my screen", "what's on my screen", "inspect screen", "what is on my screen", "read my screen", "see my screen", "debug my screen", "what error is this", "what error do you see"]):
            return {
                "thought": "Inspecting screen with Windows native OCR.",
                "tool_name": "screen_vision",
                "arguments": {"action": "inspect_screen", "query": text},
                "direct_response": "Scanning your active displays now, Sir."
            }
        elif any(w in lower for w in ["clipboard", "what's in my clipboard", "read clipboard", "check clipboard"]):
            return {
                "thought": "Reading system clipboard.",
                "tool_name": "screen_vision",
                "arguments": {"action": "read_clipboard", "query": text},
                "direct_response": "Accessing your system clipboard buffer, Sir."
            }

        # Background Alarm Clock (Spotify music at wake-up time)
        if any(w in lower for w in ["alarm", "wake me up", "wake me"]):
            if any(w in lower for w in ["cancel", "delete", "remove", "clear"]):
                return {
                    "thought": "Canceling alarms.",
                    "tool_name": "alarm_clock",
                    "arguments": {"action": "cancel_alarm"},
                    "direct_response": "Canceling your scheduled alarms, Sir."
                }
            elif any(w in lower for w in ["list", "show", "what are", "check", "view"]):
                return {
                    "thought": "Listing active alarms.",
                    "tool_name": "alarm_clock",
                    "arguments": {"action": "list_alarms"},
                    "direct_response": "Checking your active alarm schedule, Sir."
                }
            elif any(w in lower for w in ["stop", "dismiss", "silence", "turn off"]):
                return {
                    "thought": "Stopping alarm.",
                    "tool_name": "alarm_clock",
                    "arguments": {"action": "stop_alarm"},
                    "direct_response": "Silencing the alarm, Sir."
                }
            else:
                time_match = re.search(r'(?:for|at|in)\s+([^,]+)', lower)
                time_str = time_match.group(1).strip() if time_match else lower
                music_match = re.search(r'(?:with|playing|play|song|playlist)\s+([^,]+)', lower)
                music_val = music_match.group(1).strip() if music_match else ""
                if music_val and music_val in time_str:
                    time_str = time_str.split("with")[0].split("playing")[0].split("play")[0].strip()

                return {
                    "thought": f"Setting alarm for {time_str}.",
                    "tool_name": "alarm_clock",
                    "arguments": {"action": "set_alarm", "time_str": time_str, "music": music_val},
                    "direct_response": f"Configuring background alarm for you, Sir."
                }

        # Productivity (Tasks, Notes, Timers)
        if any(w in lower for w in ["set a timer", "set timer", "timer for"]):
            return {
                "thought": "Setting countdown timer.",
                "tool_name": "productivity_hub",
                "arguments": {"action": "set_timer", "text": text},
                "direct_response": "Setting your countdown timer now, Sir."
            }
        elif any(w in lower for w in ["add task", "new task", "remind me to", "add to my tasks"]):
            clean_task = re.sub(r'^(?:add\s+task|new\s+task|remind\s+me\s+to|add\s+to\s+my\s+tasks)\s*:?\s*', '', lower).strip()
            return {
                "thought": f"Adding task '{clean_task}'.",
                "tool_name": "productivity_hub",
                "arguments": {"action": "add_task", "text": clean_task or text},
                "direct_response": f"Registering task to your docket, Sir."
            }
        elif any(w in lower for w in ["what are my tasks", "my tasks", "list tasks", "show tasks", "todo list", "to-do list"]):
            return {
                "thought": "Listing pending tasks.",
                "tool_name": "productivity_hub",
                "arguments": {"action": "list_tasks"},
                "direct_response": "Fetching your agenda, Sir."
            }
        elif any(w in lower for w in ["complete task", "finish task", "mark task", "task done"]):
            return {
                "thought": "Completing task.",
                "tool_name": "productivity_hub",
                "arguments": {"action": "complete_task", "text": text},
                "direct_response": "Updating task status, Sir."
            }
        elif any(w in lower for w in ["take a note", "take note", "note down", "write a note"]):
            clean_note = re.sub(r'^(?:take\s+a\s+note|take\s+note|note\s+down|write\s+a\s+note)\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
            return {
                "thought": f"Saving note '{clean_note[:30]}'.",
                "tool_name": "productivity_hub",
                "arguments": {"action": "take_note", "text": clean_note},
                "direct_response": "Committing note to memory, Sir."
            }

        # Deep Research & Web
        if any(w in lower for w in ["deep research", "research on", "research about", "conduct research"]):
            topic = re.sub(r'^(?:deep\s+research|research\s+on|research\s+about|conduct\s+research)\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
            return {
                "thought": f"Executing deep research on {topic}.",
                "tool_name": "web_intel",
                "arguments": {"action": "deep_research", "query": topic or text},
                "direct_response": f"Gathering multi-source intelligence on '{topic or text}', Sir. Compiling dossier."
            }
        elif any(w in lower for w in ["github", "github repo", "find repo"]):
            clean_gh = re.sub(r'\b(github|repo|repositories|for|find|search)\b', '', lower).strip()
            return {
                "thought": f"Searching GitHub for {clean_gh}.",
                "tool_name": "web_intel",
                "arguments": {"action": "github_search", "query": clean_gh or text},
                "direct_response": f"Searching GitHub repositories for '{clean_gh or text}', Sir."
            }

        # Time and Date queries
        if any(w in lower for w in ["what time is it", "current time", "tell me the time", "what's the time", "time now"]):
            now_str = datetime.datetime.now().strftime("%I:%M:%S %p")
            return {
                "thought": "Direct time query",
                "tool_name": "weather_location",
                "arguments": {"action": "get_time"},
                "direct_response": f"The current time is {now_str}, Sir."
            }
        elif any(w in lower for w in ["what is the date", "what's the date", "today's date", "what day is it", "date today"]):
            today_str = datetime.datetime.now().strftime("%A, %B %d, %Y")
            return {
                "thought": "Direct date query",
                "tool_name": "weather_location",
                "arguments": {"action": "get_time"},
                "direct_response": f"Today is {today_str}, Sir."
            }

        # Weather & Location queries
        if any(w in lower for w in ["weather", "temperature", "forecast", "is it raining", "climate"]):
            city = ""
            for prep in ["in", "at", "for"]:
                if f" {prep} " in lower:
                    city = lower.split(f" {prep} ")[1].replace("?", "").strip()
                    break
            return {
                "thought": f"Querying weather for {city or 'current location'}",
                "tool_name": "weather_location",
                "arguments": {"action": "get_weather", "city": city},
                "direct_response": f"Fetching the current weather telemetry for {city or 'your location'}, Sir."
            }
        elif any(w in lower for w in ["where am i", "my location", "current location", "what city"]):
            return {
                "thought": "Querying current location",
                "tool_name": "weather_location",
                "arguments": {"action": "get_location"},
                "direct_response": "Detecting your geographic coordinates, Sir."
            }

        # Direct chamber light toggle check
        if any(w in lower for w in ["chamber light", "printer light", "printer lamp"]) or (
            any(w in lower for w in ["light", "lamp", "led"]) and any(w in lower for w in ["toggle", "turn on", "turn off", "switch"])
        ):
            return {
                "thought": "Toggling Bambu chamber light.",
                "tool_name": "bambu_hub",
                "arguments": {"action": "toggle_light"},
                "direct_response": "Toggling the Bambu Lab A1 chamber illumination, Sir."
            }

        # Direct speed control check
        if any(w in lower for w in ["print speed", "printer speed"]) or (
            any(w in lower for w in ["silent mode", "sport mode", "ludicrous mode", "standard speed", "sport speed"])
        ):
            lvl = "standard"
            for s in ["silent", "standard", "sport", "ludicrous"]:
                if s in lower:
                    lvl = s
                    break
            return {
                "thought": f"Setting print speed to {lvl}.",
                "tool_name": "bambu_hub",
                "arguments": {"action": "set_speed", "speed_level": lvl},
                "direct_response": f"Adjusting Bambu Lab A1 print velocity to {lvl} mode."
            }

        # 3D Printing / Bambu Lab A1
        if any(w in lower for w in ["print", "3d model", "bambu", "stl", "makerworld", "thingiverse"]):
            if any(w in lower for w in ["approve", "confirm", "go ahead", "start print", "yes"]):
                return {
                    "thought": "User approved print.",
                    "tool_name": "bambu_hub",
                    "arguments": {"action": "approve_print"},
                    "direct_response": "Authorization confirmed, Sir. Dispatched model to your Bambu Lab A1. Heating bed and nozzle now."
                }
            elif any(w in lower for w in ["status", "temp", "progress", "time left", "remaining", "how long", "layer", "how much time"]):
                return {
                    "thought": "Checking Bambu A1 status.",
                    "tool_name": "bambu_hub",
                    "arguments": {"action": "get_status"},
                    "direct_response": "Fetching your Bambu A1 telemetry now, Sir."
                }
            elif any(w in lower for w in ["light", "lamp", "chamber light", "led"]):
                return {
                    "thought": "Toggling Bambu chamber light.",
                    "tool_name": "bambu_hub",
                    "arguments": {"action": "toggle_light"},
                    "direct_response": "Toggling the Bambu Lab A1 chamber illumination, Sir."
                }
            elif any(w in lower for w in ["speed", "silent", "sport", "ludicrous"]):
                lvl = "standard"
                for s in ["silent", "standard", "sport", "ludicrous"]:
                    if s in lower:
                        lvl = s
                        break
                return {
                    "thought": f"Setting print speed to {lvl}.",
                    "tool_name": "bambu_hub",
                    "arguments": {"action": "set_speed", "speed_level": lvl},
                    "direct_response": f"Adjusting Bambu Lab A1 print velocity to {lvl} mode."
                }
            elif any(w in lower for w in ["pause"]):
                return {
                    "thought": "Pausing print.",
                    "tool_name": "bambu_hub",
                    "arguments": {"action": "pause_print"},
                    "direct_response": "Pausing active print on your Bambu A1."
                }
            elif any(w in lower for w in ["stop", "cancel"]):
                return {
                    "thought": "Stopping print.",
                    "tool_name": "bambu_hub",
                    "arguments": {"action": "stop_print"},
                    "direct_response": "Canceling print job and resetting extruder."
                }
            else:
                clean_q = re.sub(r'\b(find|search|get|give|show|me|a|some|an|the|for|to|3d|model|stl|print|printable|please)\b', '', lower, flags=re.IGNORECASE)
                clean_q = re.sub(r'\s+', ' ', clean_q).strip()
                query = clean_q or "Phone Stand"
                return {
                    "thought": f"Finding 3D model '{query}' for Bambu A1.",
                    "tool_name": "bambu_hub",
                    "arguments": {"action": "submit_for_approval", "query": query, "material": "PLA"},
                    "direct_response": f"Scanning 3D repositories for '{query}', Sir. Calculating optimal parameters for your Bambu A1 and preparing the approval dossier."
                }

        if lower.startswith("play ") or "play " in lower or any(w in lower for w in ["spotify", "music", "song", "track", "playlist"]):
            if "next" in lower or "skip" in lower:
                return {
                    "thought": "Skip track.",
                    "tool_name": "spotify_hub",
                    "arguments": {"action": "next"},
                    "direct_response": "Skipping track, Sir."
                }
            elif "previous" in lower or "back" in lower:
                return {
                    "thought": "Previous track.",
                    "tool_name": "spotify_hub",
                    "arguments": {"action": "previous"},
                    "direct_response": "Returning to previous track."
                }
            elif "pause" in lower or "stop" in lower:
                return {
                    "thought": "Pause music.",
                    "tool_name": "spotify_hub",
                    "arguments": {"action": "pause"},
                    "direct_response": "Pausing playback."
                }
            elif "resume" in lower or "unpause" in lower:
                return {
                    "thought": "Resume music.",
                    "tool_name": "spotify_hub",
                    "arguments": {"action": "play"},
                    "direct_response": "Resuming playback."
                }
            elif "playlist" in lower:
                clean_pl = lower.replace("on spotify", "").replace("play", "").replace("playlist", "").replace("start", "").replace("queue", "").strip()
                return {
                    "thought": f"Play playlist '{clean_pl or 'focus'}'.",
                    "tool_name": "spotify_hub",
                    "arguments": {"action": "play_playlist", "query": clean_pl or "focus"},
                    "direct_response": f"Queuing the '{clean_pl or 'focus'}' playlist on Spotify desktop for you, Sir."
                }
            elif "play" in lower:
                song = lower.split("play", 1)[1].replace("on spotify", "").replace("song", "").strip()
                return {
                    "thought": f"Play song '{song}'.",
                    "tool_name": "spotify_hub",
                    "arguments": {"action": "play_song", "query": song or "Starboy"},
                    "direct_response": f"Playing '{song or 'Starboy'}' on Spotify desktop now, Sir."
                }
            elif "recommend" in lower or "vibe" in lower:
                return {
                    "thought": "Recommend playlist.",
                    "tool_name": "spotify_hub",
                    "arguments": {"action": "play_playlist", "query": "focus"},
                    "direct_response": "Selecting a high-focus playlist matching your preferences on Spotify desktop."
                }

        if any(w in lower for w in ["open", "launch", "start app"]):
            app = lower.replace("open", "").replace("launch", "").replace("app", "").strip()
            return {
                "thought": f"Launch app {app}.",
                "tool_name": "pc_control",
                "arguments": {"action": "launch_app", "target": app},
                "direct_response": f"Launching {app}, Sir."
            }
        elif any(w in lower for w in ["close", "kill", "terminate"]):
            app = lower.replace("close", "").replace("kill", "").replace("terminate", "").strip()
            return {
                "thought": f"Close app {app}.",
                "tool_name": "pc_control",
                "arguments": {"action": "close_app", "target": app},
                "direct_response": f"Terminating process {app}."
            }
        elif "volume" in lower or "mute" in lower:
            if "mute" in lower:
                return {"thought": "Mute", "tool_name": "pc_control", "arguments": {"action": "mute"}, "direct_response": "Audio muted."}
            elif "up" in lower or "increase" in lower or "louder" in lower:
                return {"thought": "Volume up", "tool_name": "pc_control", "arguments": {"action": "volume_up"}, "direct_response": "Raising master volume."}
            elif "down" in lower or "decrease" in lower or "quieter" in lower:
                return {"thought": "Volume down", "tool_name": "pc_control", "arguments": {"action": "volume_down"}, "direct_response": "Lowering master volume."}
            else:
                return {"thought": "Set volume", "tool_name": "pc_control", "arguments": {"action": "set_volume", "value": "50"}, "direct_response": "Adjusting volume level."}
        elif "screenshot" in lower or "screen" in lower:
            return {
                "thought": "Capture screenshot",
                "tool_name": "pc_control",
                "arguments": {"action": "screenshot"},
                "direct_response": "Screen capture complete, Sir. Displaying result in HUD."
            }
        elif "lock" in lower and "pc" in lower:
            return {
                "thought": "Lock workstation",
                "tool_name": "pc_control",
                "arguments": {"action": "lock_pc"},
                "direct_response": "Securing workstation."
            }

        if any(w in lower for w in ["search", "google", "look up", "find online", "who is", "what is"]):
            q = lower.replace("search for", "").replace("search", "").replace("look up", "").strip()
            return {
                "thought": f"Web search for {q}.",
                "tool_name": "web_intel",
                "arguments": {"action": "search", "query": q or text},
                "direct_response": f"Scanning online sources for '{q or text}', Sir."
            }

        if any(w in lower for w in ["system status", "diagnostics", "cpu", "ram", "memory", "battery", "performance"]):
            return {
                "thought": "System diagnostics",
                "tool_name": "system_telemetry",
                "arguments": {"action": "get_metrics"},
                "direct_response": "Diagnostic sweep complete, Sir. Primary cores operating within nominal thresholds."
            }

        if any(w in lower for w in ["learn how to", "teach yourself", "acquire skill"]):
            topic = lower.replace("learn how to", "").replace("teach yourself to", "").replace("acquire skill", "").strip()
            return {
                "thought": f"Self-learning: {topic}",
                "tool_name": "self_learner",
                "arguments": {"skill_request": topic},
                "direct_response": f"Initiating synthesis protocol for '{topic}', Sir. Compiling and integrating new skill module."
            }

        return {
            "thought": "Direct conversation",
            "tool_name": None,
            "arguments": None,
            "direct_response": f"At your service, {config.USER_TITLE}. All systems operational and standing by for your command."
        }
