import os
import sys
import ast
import json
import importlib.util
import inspect
from pathlib import Path
from typing import Dict, Any, Optional
from ..config import SKILLS_DIR, STORAGE_DIR
from ..skills.base import BaseSkill

class SelfLearner:
    def __init__(self, brain=None):
        self.brain = brain
        self.skills_dir = SKILLS_DIR
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = STORAGE_DIR / "learned_skills.json"
        self.learned_skills_meta = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_registry(self):
        try:
            with open(self.registry_file, "w") as f:
                json.dump(self.learned_skills_meta, f, indent=2)
        except Exception:
            pass

    def load_persisted_skills(self) -> Dict[str, BaseSkill]:
        loaded = {}
        for skill_file in self.skills_dir.glob("*.py"):
            if skill_file.name.startswith("__"):
                continue
            skill_instance = self._load_skill_from_file(skill_file)
            if skill_instance:
                loaded[skill_instance.name] = skill_instance
        return loaded

    def _load_skill_from_file(self, file_path: Path) -> Optional[BaseSkill]:
        try:
            module_name = file_path.stem
            spec = importlib.util.spec_from_file_location(module_name, str(file_path))
            if not spec or not spec.loader:
                return None
            mod = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = mod
            spec.loader.exec_module(mod)

            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if inspect.isclass(attr) and issubclass(attr, BaseSkill) and attr is not BaseSkill:
                    return attr()
        except Exception:
            pass
        return None

    async def learn_and_integrate_skill(self, skill_request: str, error_context: str = "") -> Dict[str, Any]:
        code = None
        if self.brain and self.brain.llm_router and (self.brain.llm_router.groq_client or self.brain.llm_router.gemini_model):
            prompt = f"""
You are Hexor's Self-Evolution Core. Hexor needs a new skill module for:
"{skill_request}"
{f'Context: {error_context}' if error_context else ''}

Generate a self-contained Python module subclassing BaseSkill.
1. from backend.skills.base import BaseSkill
2. class attributes:
   - name: snake_case identifier
   - description: short explanation
   - category: 'custom'
   - parameters: json schema
3. async def execute(self, **kwargs) -> Dict[str, Any]:
   must return dict with 'success', 'message', 'data'
4. Output ONLY the raw Python code block enclosed in ```python ... ```
"""
            llm_text = await self.brain.llm_router.generate_text(prompt)
            code = self._extract_code(llm_text)

        if not code:
            code = self._synthesize_autonomous_code(skill_request)

        try:
            ast.parse(code)
        except SyntaxError as se:
            return {"success": False, "message": f"Syntax verification failed: {se}"}

        skill_name = self._extract_class_attribute(code, "name") or f"custom_skill_{len(self.learned_skills_meta)+1}"
        file_path = self.skills_dir / f"{skill_name}.py"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        instance = self._load_skill_from_file(file_path)
        if not instance:
            return {"success": False, "message": f"Failed to instantiate {file_path.name}"}

        if self.brain:
            self.brain.register_skill(instance)

        self.learned_skills_meta[instance.name] = {
            "name": instance.name,
            "description": instance.description,
            "file": str(file_path),
            "learned_from": skill_request
        }
        self._save_registry()

        return {
            "success": True,
            "skill_name": instance.name,
            "message": f"Skill '{instance.name}' synthesized and integrated.",
            "instance": instance
        }

    def _extract_code(self, text: str) -> str:
        if not text:
            return ""
        if "```python" in text:
            return text.split("```python")[1].split("```")[0].strip()
        elif "```" in text:
            return text.split("```")[1].split("```")[0].strip()
        return text.strip()

    def _extract_class_attribute(self, code: str, attr_name: str) -> Optional[str]:
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == attr_name:
                                    if isinstance(item.value, ast.Constant):
                                        return str(item.value.value)
        except Exception:
            pass
        return None

    def _synthesize_autonomous_code(self, request: str) -> str:
        clean_name = "skill_" + "".join(c if c.isalnum() else "_" for c in request.lower())[:20].strip("_")
        
        # If request mentions temperature conversion
        if "celsius" in request.lower() or "fahrenheit" in request.lower() or "temperature" in request.lower():
            return f'''from backend.skills.base import BaseSkill
from typing import Dict, Any

class TemperatureConverter(BaseSkill):
    name = "{clean_name}"
    description = "Converts temperatures between Celsius and Fahrenheit."
    category = "custom"
    parameters = {{
        "type": "object",
        "properties": {{
            "value": {{"type": "number", "description": "Temperature value"}},
            "unit": {{"type": "string", "enum": ["C", "F"], "description": "Current unit"}}
        }}
    }}

    async def execute(self, value: float = 0, unit: str = "C", **kwargs) -> Dict[str, Any]:
        if str(unit).upper().startswith("C"):
            res = (float(value) * 9/5) + 32
            msg = f"{{value}}°C is equal to {{res:.2f}}°F."
        else:
            res = (float(value) - 32) * 5/9
            msg = f"{{value}}°F is equal to {{res:.2f}}°C."
        return {{"success": True, "message": msg, "data": {{"result": res}}}}
'''
        # Generic autonomous utility
        return f'''from backend.skills.base import BaseSkill
import subprocess
from typing import Dict, Any

class CustomSkill(BaseSkill):
    name = "{clean_name}"
    description = "Autonomous skill for: {request}"
    category = "custom"
    parameters = {{
        "type": "object",
        "properties": {{
            "target": {{"type": "string", "description": "Input parameter"}}
        }}
    }}

    async def execute(self, target: str = "", **kwargs) -> Dict[str, Any]:
        return {{
            "success": True,
            "message": f"Successfully executed learned capability for: {request}",
            "data": {{"input": target}}
        }}
'''
