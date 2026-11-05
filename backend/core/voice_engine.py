import os
import hashlib
import asyncio
import base64
from pathlib import Path
from typing import Optional, Dict, Any
from ..config import config, AUDIO_CACHE_DIR

try:
    import edge_tts
except ImportError:
    edge_tts = None

class VoiceEngine:
    AVAILABLE_VOICES = {
        "jarvis_british": "en-GB-RyanNeural",
        "jarvis_deep": "en-US-ChristopherNeural",
        "jarvis_standard": "en-US-GuyNeural",
        "cyber_female": "en-US-AriaNeural"
    }

    def __init__(self):
        self.cache_dir = AUDIO_CACHE_DIR
        self.current_voice = config.VOICE_NAME
        self.rate = config.VOICE_RATE
        self.pitch = config.VOICE_PITCH

    def set_voice_profile(self, voice_key: str = None, rate: str = None, pitch: str = None):
        if voice_key:
            self.current_voice = self.AVAILABLE_VOICES.get(voice_key, voice_key)
        if rate:
            self.rate = rate
        if pitch:
            self.pitch = pitch

    async def synthesize(self, text: str) -> Optional[Dict[str, Any]]:
        if not text or not text.strip():
            return None

        clean_text = text.replace("*", "").replace("`", "").strip()
        hash_input = f"{self.current_voice}_{self.rate}_{self.pitch}_{clean_text}"
        file_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
        output_file = self.cache_dir / f"{file_hash}.mp3"

        if output_file.exists():
            with open(output_file, "rb") as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            return {
                "file_path": str(output_file),
                "audio_base64": b64,
                "mime_type": "audio/mp3",
                "cached": True
            }

        if edge_tts:
            try:
                communicate = edge_tts.Communicate(
                    text=clean_text,
                    voice=self.current_voice,
                    rate=self.rate,
                    pitch=self.pitch
                )
                await communicate.save(str(output_file))

                with open(output_file, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')

                return {
                    "file_path": str(output_file),
                    "audio_base64": b64,
                    "mime_type": "audio/mp3",
                    "cached": False
                }
            except Exception:
                pass

        return None
