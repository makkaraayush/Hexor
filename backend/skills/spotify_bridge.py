import json
import asyncio
from typing import Optional, Dict, Any, Callable
from fastapi import WebSocket


class SpotifyBridgeManager:
    """
    Manages the direct WebSocket connection with Spotify desktop client via Spicetify internal extension.
    Allows zero-token, zero-keystroke, zero-mouse native playback control without Spotify Premium.
    """

    def __init__(self):
        self.active_socket: Optional[WebSocket] = None
        self.current_status: Dict[str, Any] = {
            "title": "Awaiting Command",
            "artist": "Spotify Ready",
            "is_playing": False,
            "uri": ""
        }
        self.on_status_change: Optional[Callable] = None

    @property
    def is_connected(self) -> bool:
        return self.active_socket is not None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_socket = websocket
        print("[SpotifyBridge] Internal Spotify client connected via WebSocket!")

    def disconnect(self):
        self.active_socket = None
        print("[SpotifyBridge] Internal Spotify client disconnected.")

    async def send_command(self, action: str, **kwargs) -> bool:
        if not self.active_socket:
            return False
        payload = {"action": action, **kwargs}
        try:
            await self.active_socket.send_text(json.dumps(payload))
            return True
        except Exception as e:
            print(f"[SpotifyBridge] Failed to send command to Spotify: {e}")
            self.active_socket = None
            return False

    async def handle_message(self, text_data: str):
        try:
            data = json.loads(text_data)
            if data.get("type") in ["status", "track_change"]:
                self.current_status = {
                    "title": data.get("title", ""),
                    "artist": data.get("artist", ""),
                    "is_playing": data.get("is_playing", False),
                    "uri": data.get("uri", "")
                }
                if self.on_status_change:
                    try:
                        res = self.on_status_change(self.current_status)
                        if asyncio.iscoroutine(res):
                            await res
                    except Exception:
                        pass
        except Exception:
            pass


spotify_bridge = SpotifyBridgeManager()

