import os
import io
import asyncio
import subprocess
from typing import Dict, Any, Optional
from .base import BaseSkill

try:
    import ctypes
    from ctypes import wintypes
    import psutil
    from PIL import ImageGrab
    from winsdk.windows.media.ocr import OcrEngine
    from winsdk.windows.globalization import Language
    from winsdk.windows.graphics.imaging import BitmapDecoder
    from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter
    HAS_VISION_DEPS = True
except ImportError:
    HAS_VISION_DEPS = False


class ScreenVisionSkill(BaseSkill):
    name = "screen_vision"
    description = "Inspects the user's screen using native Windows OCR, reads/writes clipboard, and diagnoses displayed code or errors."
    category = "vision"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["inspect_screen", "read_clipboard", "copy_to_clipboard"]
            },
            "query": {"type": "string", "description": "Specific question about what is on screen (e.g. 'what error is showing', 'explain this code')"},
            "text": {"type": "string", "description": "Text to copy to clipboard"}
        },
        "required": ["action"]
    }

    async def execute(self, action: str, query: str = "", text: str = "", **kwargs) -> Dict[str, Any]:
        try:
            if action == "inspect_screen":
                return await self._inspect_screen(query)
            elif action == "read_clipboard":
                return await self._read_clipboard(query)
            elif action == "copy_to_clipboard":
                return await self._copy_to_clipboard(text or query)
            return {"success": False, "message": f"Unsupported vision action: {action}", "data": None}
        except Exception as e:
            return {"success": False, "message": f"Screen Vision error: {str(e)}", "data": None}

    async def _inspect_screen(self, query: str = "") -> Dict[str, Any]:
        if not HAS_VISION_DEPS:
            return {"success": False, "message": "Vision dependencies unavailable.", "data": None}

        # 1. Attach to Default interactive desktop
        user32 = ctypes.windll.user32
        hdesk = user32.OpenDesktopW('Default', 0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)

        # 2. Get active foreground window title and process
        fg_hwnd = user32.GetForegroundWindow()
        fg_title = "Unknown Window"
        fg_proc_name = "unknown"
        if fg_hwnd:
            length = user32.GetWindowTextLengthW(fg_hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(fg_hwnd, buff, length + 1)
                fg_title = buff.value
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(pid))
            try:
                fg_proc_name = psutil.Process(pid.value).name()
            except Exception:
                pass

        # 3. Capture screen and run Windows Native OCR
        try:
            img = ImageGrab.grab(all_screens=True)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            bytes_data = buf.getvalue()

            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream.get_output_stream_at(0))
            writer.write_bytes(bytes_data)
            await writer.store_async()
            await writer.flush_async()

            decoder = await BitmapDecoder.create_async(stream)
            bitmap = await decoder.get_software_bitmap_async()

            lang = Language('en-US')
            engine = OcrEngine.try_create_from_language(lang)
            ocr_result = await engine.recognize_async(bitmap)
            extracted_text = (ocr_result.text or "").strip()
        except Exception as e:
            extracted_text = f"OCR capture notice: {str(e)}"

        # 4. Synthesize intelligent J.A.R.V.I.S. analysis via LLM
        analysis_prompt = (
            f"You are Hexor, the high-intelligence J.A.R.V.I.S. desktop operating system.\n"
            f"The user asked: '{query or 'What is currently displayed on my screen?'}'\n\n"
            f"Active Foreground Window: {fg_title} (Process: {fg_proc_name})\n"
            f"Screen Content Extracted via Hardware-Accelerated OCR:\n"
            f"\"\"\"\n{extracted_text[:4000]}\n\"\"\"\n\n"
            "INSTRUCTIONS:\n"
            "- Deliver a sharp, articulate, British-butler style J.A.R.V.I.S. spoken response directly addressing what the user asked.\n"
            "- If there is an error message, explain the root cause and provide the direct code or operational fix.\n"
            "- If there is code, explain its purpose or spot any bugs.\n"
            "- If asked generally about the screen, summarize the active workspace, document, or project status clearly.\n"
            "- Address the user respectfully as Sir."
        )

        try:
            from ..core.llm_router import LLMRouter
            router = LLMRouter()
            analysis_text = await router.generate_text(analysis_prompt)
        except Exception:
            analysis_text = f"I observe you have {fg_title} open in the foreground, Sir."

        return {
            "success": True,
            "message": analysis_text.strip(),
            "data": {
                "active_window": fg_title,
                "process": fg_proc_name,
                "extracted_text_snippet": extracted_text[:500],
                "analysis": analysis_text.strip()
            },
            "ui_action": "screen_analyzed"
        }

    async def _read_clipboard(self, query: str = "") -> Dict[str, Any]:
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=5
            )
            clip_text = (res.stdout or "").strip()
            if not clip_text:
                return {
                    "success": True,
                    "message": "Your system clipboard is currently empty, Sir.",
                    "data": {"clipboard": ""}
                }

            if query:
                from ..core.llm_router import LLMRouter
                router = LLMRouter()
                prompt = (
                    f"User asked regarding their clipboard: '{query}'.\n"
                    f"Clipboard content:\n```\n{clip_text[:3000]}\n```\n"
                    "Respond with JARVIS-style intellectual wit and clarity, Sir."
                )
                answer = await router.generate_text(prompt)
                return {
                    "success": True,
                    "message": answer.strip(),
                    "data": {"clipboard": clip_text, "analysis": answer.strip()}
                }

            return {
                "success": True,
                "message": f"Clipboard contents retrieved, Sir: '{clip_text[:120]}...'",
                "data": {"clipboard": clip_text}
            }
        except Exception as e:
            return {"success": False, "message": f"Could not read clipboard: {str(e)}", "data": None}

    async def _copy_to_clipboard(self, text: str) -> Dict[str, Any]:
        if not text:
            return {"success": False, "message": "No text provided to copy.", "data": None}
        try:
            safe = text.replace('"', '`"')
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", f'Set-Clipboard -Value "{safe}"'],
                capture_output=True,
                timeout=5
            )
            return {
                "success": True,
                "message": "Content successfully copied to your system clipboard, Sir.",
                "data": {"copied_length": len(text)}
            }
        except Exception as e:
            return {"success": False, "message": f"Could not copy to clipboard: {str(e)}", "data": None}

