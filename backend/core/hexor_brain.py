import asyncio
import json
import time
import re
from typing import Dict, Any, List, Optional
from ..config import config, STORAGE_DIR
from .llm_router import LLMRouter
from .voice_engine import VoiceEngine
from .self_learner import SelfLearner
from ..skills.base import BaseSkill
from ..skills.pc_control import PCControlSkill
from ..skills.spotify_hub import SpotifyHubSkill
from ..skills.bambu_hub import BambuHubSkill
from ..skills.web_intel import WebIntelSkill
from ..skills.system_telemetry import SystemTelemetrySkill
from ..skills.windows_deep_ops import WindowsDeepOpsSkill
from ..skills.weather_location import WeatherLocationSkill
from ..skills.screen_vision import ScreenVisionSkill
from ..skills.productivity_hub import ProductivityHubSkill
from ..skills.jarvis_protocols import JarvisProtocolsSkill
from ..skills.alarm_clock import AlarmClockSkill

class HexorBrain:
    def __init__(self):
        self.llm_router = LLMRouter()
        self.voice_engine = VoiceEngine()
        self.self_learner = SelfLearner(brain=self)
        self.history_file = STORAGE_DIR / "conversation_history.json"
        
        self.skills: Dict[str, BaseSkill] = {}
        self._register_default_skills()
        self._load_learned_skills()
        self.conversation_history = self._load_history()
        
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.llm_router.auto_configure_models())
        except RuntimeError:
            pass

    def _register_default_skills(self):
        default_skills = [
            PCControlSkill(),
            SpotifyHubSkill(),
            BambuHubSkill(),
            WebIntelSkill(),
            SystemTelemetrySkill(),
            WindowsDeepOpsSkill(),
            WeatherLocationSkill(),
            ScreenVisionSkill(),
            ProductivityHubSkill(),
            JarvisProtocolsSkill(),
            AlarmClockSkill()
        ]
        for skill in default_skills:
            self.register_skill(skill)

    def register_skill(self, skill: BaseSkill):
        self.skills[skill.name] = skill

    def _load_learned_skills(self):
        learned = self.self_learner.load_persisted_skills()
        for name, skill in learned.items():
            self.skills[name] = skill

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        for name, skill in self.skills.items():
            schemas.append({
                "name": name,
                "description": skill.description,
                "category": getattr(skill, "category", "general"),
                "parameters": skill.parameters
            })
        return schemas

    def _load_history(self) -> List[Dict[str, str]]:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)[-20:]
            except Exception:
                pass
        return []

    def _save_history(self):
        try:
            with open(self.history_file, "w") as f:
                json.dump(self.conversation_history[-30:], f, indent=2)
        except Exception:
            pass

    def _prepare_spoken_summary(self, text: str) -> str:
        if not text:
            return ""
        clean = text.replace("*", "").replace("`", "").replace("#", "").strip()
        # Remove raw URLs for speech
        clean = re.sub(r'https?://\S+', '', clean)
        # Remove raw code blocks
        clean = re.sub(r'```[\s\S]*?```', '', clean)
        # Remove markdown table rows
        clean = re.sub(r'\|.*?\|', '', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()

        # Natural speech: Never truncate mid-sentence.
        # Allow full natural explanations up to 1400 characters
        if len(clean) <= 1400:
            return clean

        # For exceptionally long text, preserve clean sentence boundaries up to 1000 characters
        sentences = re.split(r'(?<=[.!?])\s+', clean)
        spoken_parts = []
        cur_len = 0
        for s in sentences:
            if cur_len + len(s) > 1000:
                break
            spoken_parts.append(s)
            cur_len += len(s)

        if spoken_parts:
            summary = " ".join(spoken_parts).strip()
            summary += f" I have presented the complete intelligence report on your command deck, {config.USER_TITLE}."
            return summary

        return clean[:800]

    async def process_user_input(self, text: str, voice_enabled: bool = True) -> Dict[str, Any]:
        start_time = time.time()
        user_message = text.strip()
        if not user_message:
            return {"error": "Empty message"}

        if user_message.lower() in ("clear chat", "clear history", "reset conversation", "reset history", "/clear"):
            self.conversation_history.clear()
            self._save_history()
            spoken_response = f"Conversation memory cleared, {config.USER_TITLE}. Ready for new directives."
            audio_payload = None
            if voice_enabled:
                audio_payload = await self.voice_engine.synthesize(spoken_response)
            return {
                "user_prompt": user_message,
                "response_text": spoken_response,
                "tool_name": None,
                "tool_arguments": None,
                "tool_result": None,
                "ui_action": "clear_chat",
                "requires_approval": False,
                "audio": audio_payload,
                "latency_seconds": round(time.time() - start_time, 2),
                "timestamp": time.time()
            }

        self.conversation_history.append({"role": "user", "content": user_message})

        tools_schema = self.get_tool_schemas()
        plan = await self.llm_router.plan_and_route(user_message, tools_schema, self.conversation_history)

        tool_name = plan.get("tool_name")
        args = plan.get("arguments") or {}
        spoken_response = plan.get("direct_response") or ""
        
        # If response was returned as raw json string, unpack direct_response
        if isinstance(spoken_response, str) and spoken_response.startswith("{") and '"direct_response"' in spoken_response:
            extracted = self.llm_router._extract_json(spoken_response)
            if extracted and extracted.get("direct_response"):
                spoken_response = extracted["direct_response"]
            elif '"direct_response":' in spoken_response:
                try:
                    val = spoken_response.split('"direct_response":', 1)[1].strip()
                    if val.startswith('"'):
                        val = val[1:]
                        if val.endswith('"}'):
                            val = val[:-2]
                        elif val.endswith('"'):
                            val = val[:-1]
                        spoken_response = val.replace('\\n', '\n').replace('\\"', '"')
                except Exception:
                    pass

        tool_result = None
        ui_action = None
        requires_approval = False

        if tool_name == "self_learner":
            skill_request = args.get("skill_request") or user_message
            learn_res = await self.self_learner.learn_and_integrate_skill(skill_request)
            tool_result = learn_res
            if learn_res.get("success"):
                new_skill_instance = learn_res.get("instance")
                spoken_response = f"Sir, I have synthesized and registered the skill '{learn_res['skill_name']}'."
                if new_skill_instance:
                    try:
                        exec_res = await new_skill_instance.execute()
                        tool_result["initial_execution"] = exec_res
                    except Exception as e:
                        tool_result["initial_execution"] = str(e)
            else:
                spoken_response = f"Could not synthesize skill: {learn_res.get('message')}"

        elif tool_name and tool_name in self.skills:
            skill = self.skills[tool_name]
            try:
                tool_result = await skill.execute(**args)
                ui_action = tool_result.get("ui_action")
                requires_approval = tool_result.get("requires_approval", False)
                
                if tool_result.get("success"):
                    if tool_name in ("web_intel", "windows_deep_ops") or (tool_result.get("data") and not tool_result.get("message")):
                        try:
                            synth = await self.llm_router.synthesize_result(user_message, tool_name, tool_result)
                            spoken_response = synth if synth else tool_result.get("message", f"Done, {config.USER_TITLE}.")
                        except Exception:
                            spoken_response = tool_result.get("message") or f"Task executed, {config.USER_TITLE}."
                    else:
                        spoken_response = tool_result.get("message") or f"Action completed, {config.USER_TITLE}."
                else:
                    spoken_response = tool_result.get("message") or f"Unable to complete {tool_name}, {config.USER_TITLE}."
            except Exception as e:
                tool_result = {"success": False, "message": f"Execution error: {str(e)}"}
                spoken_response = f"Apologies {config.USER_TITLE}, an issue occurred with {tool_name}: {str(e)}"

        elif tool_name and tool_name not in self.skills:
            learn_res = await self.self_learner.learn_and_integrate_skill(user_message, f"Missing tool: {tool_name}")
            tool_result = learn_res
            if learn_res.get("success"):
                spoken_response = f"Sir, I synthesized and integrated '{learn_res['skill_name']}' for you."
            else:
                spoken_response = f"Could not find or synthesize skill: '{tool_name}'."

        if not spoken_response:
            spoken_response = f"Task completed, {config.USER_TITLE}."

        self.conversation_history.append({"role": "assistant", "content": spoken_response})
        self._save_history()

        audio_payload = None
        if voice_enabled:
            spoken_summary = self._prepare_spoken_summary(spoken_response)
            audio_payload = await self.voice_engine.synthesize(spoken_summary)

        execution_latency = round(time.time() - start_time, 2)

        return {
            "user_prompt": user_message,
            "response_text": spoken_response,
            "tool_name": tool_name,
            "tool_arguments": args,
            "tool_result": tool_result,
            "ui_action": ui_action,
            "requires_approval": requires_approval,
            "audio": audio_payload,
            "latency_seconds": execution_latency,
            "timestamp": time.time()
        }

    async def handle_approval(self, approved: bool) -> Dict[str, Any]:
        bambu = self.skills.get("bambu_hub")
        if not bambu:
            return {"success": False, "message": "Bambu hub not available"}

        if approved:
            res = await bambu.execute(action="approve_print")
            spoken = res.get("message", "Print job dispatched.")
            audio = await self.voice_engine.synthesize(spoken)
            return {
                "success": True,
                "response_text": spoken,
                "tool_result": res,
                "audio": audio
            }
        else:
            bambu.current_pending_approval = None
            bambu._save_state()
            spoken = f"Print job canceled, {config.USER_TITLE}."
            audio = await self.voice_engine.synthesize(spoken)
            return {
                "success": True,
                "response_text": spoken,
                "audio": audio
            }
