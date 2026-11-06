import time
import re
import threading
import asyncio
from typing import Optional, Callable, Dict, Any
import numpy as np

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

from ..config import config, AUDIO_CACHE_DIR


def _kill_sapisvr():
    """Ensure Windows Speech Recognition GUI bar never hangs around."""
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            if 'sapisvr' in p.info['name'].lower():
                p.kill()
    except Exception:
        pass


class WakeListener:
    """
    OS-level zero-token wake word & hands-free conversation listener.
    Uses local sounddevice microphone capture + SpeechRecognition (Google free STT).
    Consumes ZERO Groq Whisper tokens in standby!
    Bypasses browser sandboxes, background tab throttling, and Web Speech drops.
    """

    def __init__(self, brain=None, broadcast_callback: Optional[Callable] = None):
        self.brain = brain
        self.broadcast_callback = broadcast_callback
        self.is_running = False
        self.is_enabled = True
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.cooldown_until = 0.0

        self.sample_rate = 16000
        self.chunk_size = 1024
        self.speech_threshold = 35.0  # Dynamically calibrated on mic start
        self.silence_limit = 1.2      # Natural conversational pause limit (1.2s)
        self.max_record_seconds = 7.0

        # Continuous hands-free conversation state
        self.conversation_until = 0.0
        self.cached_wake_audio: Optional[Dict[str, Any]] = None
        self.recognizer = sr.Recognizer() if HAS_SR else None
        self._active_stream: Optional[Any] = None

        _kill_sapisvr()

    def enter_standby(self):
        """Immediately drop conversation mode and require wake word."""
        self.conversation_until = 0.0
        print("[WakeListener] Standby mode engaged. Wake word required.")
        if self.broadcast_callback and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_callback({"type": "standby_entered"}),
                self.loop
            )

    def start(self, loop: asyncio.AbstractEventLoop):
        if not HAS_SOUNDDEVICE:
            print("[WakeListener] sounddevice not available; OS wake listener disabled.")
            return

        _kill_sapisvr()
        self.loop = loop
        self.is_running = True
        self.thread = threading.Thread(target=self._mic_listen_loop, daemon=True)
        self.thread.start()
        print("[WakeListener] Zero-token OS-level microphone listener active.")

        if self.brain and self.brain.voice_engine:
            asyncio.run_coroutine_threadsafe(self._pre_cache_wake_audio(), self.loop)

    async def _pre_cache_wake_audio(self):
        try:
            reply = f"Online, {config.USER_TITLE}."
            res = await self.brain.voice_engine.synthesize(reply)
            if res and res.get("audio_base64"):
                self.cached_wake_audio = res
        except Exception:
            pass

    def stop(self):
        self.is_running = False
        if self._active_stream:
            try:
                self._active_stream.abort()
                self._active_stream.close()
            except Exception:
                pass
            self._active_stream = None

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        if not enabled:
            self.conversation_until = 0.0
            if self._active_stream:
                try:
                    self._active_stream.abort()
                    self._active_stream.close()
                except Exception:
                    pass
                self._active_stream = None
            print("[WakeListener] Microphone hardware released and muted (Wake listener disabled).")
        else:
            print("[WakeListener] Wake listener enabled.")

    def notify_hexor_speaking(self, duration_seconds: float, extend_conversation: bool = True):
        self.cooldown_until = time.time() + duration_seconds + 0.2
        if extend_conversation:
            # Ensure the 25-second conversation timeout only starts AFTER Hexor finishes speaking!
            self.conversation_until = self.cooldown_until + 25.0
        else:
            self.conversation_until = 0.0

    def _get_best_input_device(self) -> Optional[int]:
        try:
            devices = sd.query_devices()
            # 1. Prefer default system input device
            def_in = sd.default.device[0]
            if def_in is not None and def_in >= 0 and def_in < len(devices):
                if devices[def_in].get('max_input_channels', 0) > 0:
                    return def_in

            # 2. Check for Redgear or HyperX
            for idx, d in enumerate(devices):
                if d.get('max_input_channels', 0) > 0:
                    name = d.get('name', '').lower()
                    if any(m in name for m in ['redgear', 'hyperx', 'shadow vox', 'headset', 'mic']):
                        return idx

            # 3. First available input device
            for idx, d in enumerate(devices):
                if d.get('max_input_channels', 0) > 0:
                    return idx
        except Exception:
            pass
        return None

    def _calibrate_noise_floor(self, device_id: Optional[int]):
        """Sample ambient room noise for 0.4s to dynamically adapt the voice trigger threshold."""
        try:
            rec = sd.rec(int(0.4 * self.sample_rate), samplerate=self.sample_rate, channels=1, dtype='int16', device=device_id)
            sd.wait()
            ambient = float(np.sqrt(np.mean(rec.astype(np.float32)**2)))
            # Set speech threshold above ambient floor
            self.speech_threshold = max(22.0, ambient * 2.2)
            print(f"[WakeListener] Ambient RMS: {ambient:.1f} | Calibrated voice trigger threshold: {self.speech_threshold:.1f}")
        except Exception as e:
            self.speech_threshold = 35.0

    def _mic_listen_loop(self):
        device_id = self._get_best_input_device()
        self._calibrate_noise_floor(device_id)

        while self.is_running:
            if not self.is_enabled or time.time() < self.cooldown_until:
                time.sleep(0.08)
                continue

            try:
                stream = sd.InputStream(
                    device=device_id,
                    channels=1,
                    samplerate=self.sample_rate,
                    dtype='int16',
                    blocksize=self.chunk_size
                )
                self._active_stream = stream
                with stream:
                    audio_buffer = []
                    is_speaking = False
                    silence_start = None
                    record_start = None
                    was_convo_at_start = False

                    while self.is_running and self.is_enabled:
                        if time.time() < self.cooldown_until:
                            time.sleep(0.05)
                            continue

                        try:
                            data, _ = stream.read(self.chunk_size)
                        except Exception:
                            break
                        samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
                        rms = float(np.sqrt(np.mean(samples**2)))

                        if rms > self.speech_threshold:
                            if not is_speaking:
                                is_speaking = True
                                record_start = time.time()
                                was_convo_at_start = (time.time() < self.conversation_until)
                                audio_buffer = []
                                # Only broadcast user_speaking to HUD if actively in conversation mode
                                if was_convo_at_start and self.broadcast_callback and self.loop:
                                    asyncio.run_coroutine_threadsafe(
                                        self.broadcast_callback({"type": "user_speaking", "speaking": True}),
                                        self.loop
                                    )
                            silence_start = None
                            audio_buffer.append(data)
                        elif is_speaking:
                            audio_buffer.append(data)
                            if silence_start is None:
                                silence_start = time.time()
                            elif (time.time() - silence_start) >= self.silence_limit:
                                if was_convo_at_start and self.broadcast_callback and self.loop:
                                    asyncio.run_coroutine_threadsafe(
                                        self.broadcast_callback({"type": "user_speaking", "speaking": False}),
                                        self.loop
                                    )
                                break

                        if is_speaking and record_start and (time.time() - record_start) >= self.max_record_seconds:
                            if was_convo_at_start and self.broadcast_callback and self.loop:
                                asyncio.run_coroutine_threadsafe(
                                    self.broadcast_callback({"type": "user_speaking", "speaking": False}),
                                    self.loop
                                )
                            break

                    if audio_buffer and is_speaking:
                        raw_bytes = b"".join(audio_buffer)
                        # Process if at least 0.3s of audio recorded
                        if len(raw_bytes) >= int(self.sample_rate * 2 * 0.3):
                            self._process_speech(raw_bytes, was_convo_at_start)
                        else:
                            if self.broadcast_callback and self.loop:
                                asyncio.run_coroutine_threadsafe(
                                    self.broadcast_callback({"type": "user_speaking", "speaking": False}),
                                    self.loop
                                )

            except Exception as e:
                time.sleep(0.5)
            finally:
                self._active_stream = None

    def _process_speech(self, raw_audio_bytes: bytes, was_convo_at_start: bool = False):
        if not self.recognizer or not HAS_SR:
            return

        try:
            audio_data = sr.AudioData(raw_audio_bytes, sample_rate=self.sample_rate, sample_width=2)
            # Free Google STT (0 Groq tokens, 0 cloud cost)
            text = self.recognizer.recognize_google(audio_data)
            if not text:
                return

            transcript_clean = text.strip().lower()
            words_only = re.sub(r'[^\w\s]', '', transcript_clean)
            is_convo_active = was_convo_at_start or (time.time() < self.conversation_until)

            print(f"[WakeListener Mic] Heard: '{text}' (Active Convo: {is_convo_active})")

            # 1. Explicit dismissal in active conversation (NEVER dismiss on "sleep", "good night", or "thank you")
            dismiss_regex = r'\b(?:stand\s*down|stop\s*listening|dismissed|hexor\s*stand\s*down|jarvis\s*stand\s*down|shut\s*up|stop\s*talking|exit\s*conversation)\b'
            if is_convo_active and re.search(dismiss_regex, words_only):
                self.conversation_until = 0.0
                dismissal = f"Standing by, {config.USER_TITLE}."
                self.notify_hexor_speaking(1.0, extend_conversation=False)
                if self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self._dispatch_dismissal(dismissal),
                        self.loop
                    )
                return

            # 2. Wake words (Supports 'Hexor' alone, 'Hex', 'Hey Hexor', 'Jarvis', etc.)
            wake_regex = r'\b(?:hey\s+|ok\s+|okay\s+|hello\s+|hi\s+|yo\s+)?(?:hex[\s_-]?(?:or|er|ar|ur|o|sir|are)?|heck[\s_-]?(?:sir|er|or|le)?|hack[\s_-]?(?:sir|er|saw)?|exor|exer|jarvis|javis|travis|charvis|hector|vector|axel)\b'
            match = re.search(wake_regex, words_only)

            if match:
                self.conversation_until = time.time() + 25.0
                command = text[match.end():].strip().lstrip(',.- ')
                print(f"[WakeListener] Wake Word Matched! Phrase: '{text}', Command: '{command}'")
                if self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self._dispatch_wake_event(text, command),
                        self.loop
                    )
                return

            # 3. Active conversation input
            if is_convo_active and len(words_only) > 1:
                self.conversation_until = time.time() + 25.0
                print(f"[WakeListener] Active Conversation Input: '{text}'")
                if self.loop:
                    asyncio.run_coroutine_threadsafe(
                        self._dispatch_command(text),
                        self.loop
                    )

        except sr.UnknownValueError:
            pass
        except Exception as e:
            pass

    async def _dispatch_dismissal(self, message: str):
        audio_payload = None
        if self.brain and self.brain.voice_engine:
            audio_payload = await self.brain.voice_engine.synthesize(message)
        res = {
            "user_prompt": "Stand down",
            "response_text": message,
            "tool_name": None,
            "tool_arguments": None,
            "tool_result": None,
            "ui_action": "standby",
            "audio": audio_payload,
            "latency_seconds": 0.1,
            "timestamp": time.time()
        }
        if self.broadcast_callback:
            await self.broadcast_callback({"type": "chat_response", "payload": res})

    async def _dispatch_wake_event(self, full_transcript: str, command: str):
        if not self.brain:
            return

        if self.broadcast_callback:
            await self.broadcast_callback({"type": "user_speaking", "speaking": False})
            await self.broadcast_callback({
                "type": "wake_detected",
                "transcript": full_transcript,
                "command": command
            })

        if len(command) > 2:
            res = await self.brain.process_user_input(command, voice_enabled=True)
            dur = self._estimate_duration(res.get("response_text", ""))
            self.notify_hexor_speaking(dur)
            self.conversation_until = time.time() + dur + 25.0
            if self.broadcast_callback:
                await self.broadcast_callback({"type": "chat_response", "payload": res})
        else:
            reply = f"Online, {config.USER_TITLE}."
            audio_payload = self.cached_wake_audio
            if not audio_payload and self.brain.voice_engine:
                audio_payload = await self.brain.voice_engine.synthesize(reply)

            dur = 0.6
            self.notify_hexor_speaking(dur)
            self.conversation_until = time.time() + dur + 25.0

            res = {
                "user_prompt": full_transcript,
                "response_text": reply,
                "tool_name": None,
                "tool_arguments": None,
                "tool_result": None,
                "ui_action": "wake_acknowledgement",
                "audio": audio_payload,
                "latency_seconds": 0.05,
                "timestamp": time.time()
            }
            if self.broadcast_callback:
                await self.broadcast_callback({"type": "chat_response", "payload": res})

    async def _dispatch_command(self, query: str):
        if not self.brain:
            return
        if self.broadcast_callback:
            await self.broadcast_callback({"type": "user_speaking", "speaking": False})
        res = await self.brain.process_user_input(query, voice_enabled=True)
        dur = self._estimate_duration(res.get("response_text", ""))
        self.notify_hexor_speaking(dur)
        self.conversation_until = time.time() + dur + 25.0
        if self.broadcast_callback:
            await self.broadcast_callback({"type": "chat_response", "payload": res})

    def _estimate_duration(self, text: str) -> float:
        words = len(text.split())
        return max(0.6, words * 0.22)
