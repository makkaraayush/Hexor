import os
import sys
import subprocess
import glob
from pathlib import Path
from typing import Dict, Any, List, Optional
from .base import BaseSkill

class WindowsDeepOpsSkill(BaseSkill):
    name = "windows_deep_ops"
    description = (
        "Internal Windows OS automation and code execution engine. "
        "Allows reading/writing files, directory scanning, running PowerShell commands, "
        "executing Python code, and inspecting Windows processes."
    )
    category = "pc_control"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "read_file", "write_file", "list_dir", "search_files",
                    "execute_powershell", "execute_python", "get_system_info"
                ]
            },
            "path": {"type": "string"},
            "content": {"type": "string"},
            "code": {"type": "string"},
            "pattern": {"type": "string"}
        },
        "required": ["action"]
    }

    async def execute(self, action: str, path: str = "", content: str = "", code: str = "", pattern: str = "", **kwargs) -> Dict[str, Any]:
        try:
            if action == "read_file":
                target_path = Path(path)
                if not target_path.exists():
                    return {"success": False, "message": f"File not found: {path}", "data": None}
                with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
                    data = f.read(10000)
                return {
                    "success": True,
                    "message": f"Read {len(data)} characters from {path}.",
                    "data": {"path": str(target_path), "content": data}
                }

            elif action == "write_file":
                target_path = Path(path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {
                    "success": True,
                    "message": f"File successfully written to {path}.",
                    "data": {"path": str(target_path), "bytes": len(content)}
                }

            elif action == "list_dir":
                target_dir = Path(path or ".")
                if not target_dir.exists():
                    return {"success": False, "message": f"Directory not found: {path}", "data": None}
                items = []
                for p in target_dir.iterdir():
                    items.append({
                        "name": p.name,
                        "is_dir": p.is_dir(),
                        "size": p.stat().st_size if p.is_file() else None
                    })
                return {
                    "success": True,
                    "message": f"Found {len(items)} items in {path}.",
                    "data": {"directory": str(target_dir), "items": items[:50]}
                }

            elif action == "search_files":
                search_root = path or "."
                search_pattern = pattern or "*"
                full_pattern = os.path.join(search_root, "**", search_pattern)
                matches = glob.glob(full_pattern, recursive=True)[:30]
                return {
                    "success": True,
                    "message": f"Found {len(matches)} files matching pattern '{search_pattern}'.",
                    "data": {"matches": matches}
                }

            elif action == "execute_powershell":
                cmd = code or content or path
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", cmd],
                    capture_output=True,
                    text=True,
                    timeout=20
                )
                output = (res.stdout or res.stderr).strip()
                return {
                    "success": res.returncode == 0,
                    "message": f"PowerShell completed with exit code {res.returncode}.",
                    "data": {"output": output[:3000], "exit_code": res.returncode}
                }

            elif action == "execute_python":
                py_code = code or content
                res = subprocess.run(
                    [sys.executable, "-c", py_code],
                    capture_output=True,
                    text=True,
                    timeout=20
                )
                output = (res.stdout or res.stderr).strip()
                return {
                    "success": res.returncode == 0,
                    "message": f"Python script completed with exit code {res.returncode}.",
                    "data": {"output": output[:3000], "exit_code": res.returncode}
                }

            elif action == "get_system_info":
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, TotalPhysicalMemory | ConvertTo-Json"],
                    capture_output=True,
                    text=True
                )
                return {
                    "success": True,
                    "message": "Windows system diagnostics retrieved.",
                    "data": {"info": res.stdout.strip()}
                }

            return {"success": False, "message": f"Unsupported Windows deep action: {action}", "data": None}

        except Exception as e:
            return {"success": False, "message": f"Windows deep ops error: {str(e)}", "data": None}

