import os
import subprocess
import urllib.parse
import json
import re
import time
import asyncio
from typing import Dict, Any, Optional, Tuple
import httpx
from .base import BaseSkill
from ..config import config, STORAGE_DIR
from .spotify_bridge import spotify_bridge

# WinSDK is intentionally disabled to prevent COM apartment deadlocks on Windows 11
HAS_WINSDK = False


class SpotifyHubSkill(BaseSkill):
    name = "spotify_hub"
    description = "Controls Spotify and Windows media playback, searches tracks, and plays music in the background via Spotify Web API and Media Sessions."
    category = "spotify"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["play", "pause", "next", "previous", "play_song", "play_playlist", "search_playlist", "recommend_music", "status"]
            },
            "query": {"type": "string"},
            "mood": {"type": "string"}
        },
        "required": ["action"]
    }

    def __init__(self):
        self.profile_file = STORAGE_DIR / "music_profile.json"
        self.spotify_cache_file = STORAGE_DIR / ".spotify_cache"
        self.api_premium_blocked = False
        if not self.profile_file.exists():
            default_profile = {
                "favorites": ["Synthwave", "Cyberpunk 2077 OST", "Hans Zimmer", "The Weeknd"],
                "current_track": {
                    "title": "Awaiting Command",
                    "artist": "Spotify Ready",
                    "status": "idle"
                }
            }
            with open(self.profile_file, "w") as f:
                json.dump(default_profile, f, indent=2)

    def _get_spotipy(self) -> Optional[Any]:
        if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
            return None
        if getattr(self, "_cached_sp", None) is not None:
            return self._cached_sp
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
            sp_oauth = SpotifyOAuth(
                client_id=config.SPOTIFY_CLIENT_ID,
                client_secret=config.SPOTIFY_CLIENT_SECRET,
                redirect_uri=config.SPOTIFY_REDIRECT_URI,
                scope="user-modify-playback-state user-read-playback-state user-read-currently-playing playlist-read-private",
                cache_path=str(self.spotify_cache_file),
                open_browser=False
            )
            token_info = sp_oauth.get_cached_token()
            if token_info:
                self._cached_sp = spotipy.Spotify(auth_manager=sp_oauth)
                return self._cached_sp
            return None
        except Exception:
            return None

    def get_auth_url(self) -> Optional[str]:
        if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
            return None
        try:
            from spotipy.oauth2 import SpotifyOAuth
            sp_oauth = SpotifyOAuth(
                client_id=config.SPOTIFY_CLIENT_ID,
                client_secret=config.SPOTIFY_CLIENT_SECRET,
                redirect_uri=config.SPOTIFY_REDIRECT_URI,
                scope="user-modify-playback-state user-read-playback-state user-read-currently-playing playlist-read-private",
                cache_path=str(self.spotify_cache_file),
                open_browser=False
            )
            return sp_oauth.get_authorize_url()
        except Exception:
            return None

    def handle_auth_code(self, code: str) -> bool:
        try:
            from spotipy.oauth2 import SpotifyOAuth
            sp_oauth = SpotifyOAuth(
                client_id=config.SPOTIFY_CLIENT_ID,
                client_secret=config.SPOTIFY_CLIENT_SECRET,
                redirect_uri=config.SPOTIFY_REDIRECT_URI,
                scope="user-modify-playback-state user-read-playback-state user-read-currently-playing playlist-read-private",
                cache_path=str(self.spotify_cache_file),
                open_browser=False
            )
            token = sp_oauth.get_access_token(code, as_dict=False)
            return bool(token)
        except Exception:
            return False

    async def _get_windows_media_session(self, spotify_only: bool = False):
        return None

    def _get_cached_track(self) -> Optional[dict]:
        if self.profile_file.exists():
            try:
                with open(self.profile_file, "r") as f:
                    return json.load(f).get("current_track")
            except Exception:
                pass
        return None

    def _get_spotify_hwnd(self) -> Optional[int]:
        try:
            import ctypes
            from ctypes import wintypes
            import psutil

            user32 = ctypes.windll.user32
            hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)

            hwnds = []
            pids = [p.pid for p in psutil.process_iter(['name']) if 'spotify' in p.info['name'].lower()]
            WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def enum_proc(hwnd, lparam):
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in pids:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, cls, 256)
                    if 'Chrome_WidgetWin_1' in cls.value:
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        w = rect.right - rect.left
                        if w > 200 or rect.left == -32000:
                            hwnds.append(hwnd)
                return True

            user32.EnumDesktopWindows(hdesk, WNDENUMPROC(enum_proc), 0)
            return hwnds[0] if hwnds else None
        except Exception:
            return None

    def _send_media_key(self, key_code: int):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.keybd_event(key_code, 0, 1, 0)
            user32.keybd_event(key_code, 0, 1 | 2, 0)
        except Exception:
            pass

    def _launch_spotify_uri(self, uri: str):
        try:
            os.startfile(uri)
            return
        except Exception:
            pass
        try:
            subprocess.Popen(f'cmd /c start "" "{uri}"', shell=True)
        except Exception:
            pass

    async def _find_spotify_track_id(self, query: str) -> Optional[str]:
        """Fast, robust track ID resolution via DuckDuckGo without burning any API tokens or requiring Premium."""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            async with httpx.AsyncClient(headers=headers, timeout=5.0, follow_redirects=True) as client:
                res = await client.post('https://html.duckduckgo.com/html/', data={'q': f'{query} site:open.spotify.com/track'})
                matches = re.findall(r'open\.spotify\.com(?:%2F|/)track(?:%2F|/)([a-zA-Z0-9]+)', res.text)
                if matches:
                    return matches[0]
        except Exception:
            pass
        return None

    async def _resolve_descriptive_query(self, query: str) -> Tuple[str, str]:
        q_lower = query.lower().strip()

        # Check for ordinal rankings
        has_ordinal = bool(re.search(r'\b(?:\d+(?:st|nd|rd|th)?|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b', q_lower))

        # Explicit negative filtering (user says not poem, not rhyme, not baby shark)
        if any(neg in q_lower for neg in [
            "not poem", "not the poem", "not a poem", "not rhymes", "not rhyme",
            "not baby shark", "i meant song", "meant song", "real song", "actual song"
        ]) and not has_ordinal:
            return "Despacito", "Luis Fonsi ft. Daddy Yankee"

        # Explicit query for THE #1 most viewed song on YouTube
        if not has_ordinal and any(mv in q_lower for mv in ["most viewed song", "most viewed music", "top viewed song", "most watched music video"]) and any(y in q_lower for y in ["youtube", "yt"]):
            return "Despacito", "Luis Fonsi ft. Daddy Yankee"

        descriptive_cues = [
            "most", "popular", "best", "youtube", "tiktok", "trend",
            "soundtrack", "theme", "ost", "movie", "film", "anime",
            "latest", "newest", "which goes", "lyrics", "song from",
            "song about", "top viewed", "4th", "second", "third", "ranking"
        ]
        is_descriptive = any(k in q_lower for k in descriptive_cues) or has_ordinal or len(query.split()) >= 4

        if is_descriptive:
            try:
                from ..core.llm_router import LLMRouter
                router = LLMRouter()
                prompt = (
                    f"User asked to play this on Spotify: '{query}'.\n"
                    "Identify the exact real-world commercial song title and primary musical recording artist.\n"
                    "CRITICAL RULES:\n"
                    "- Use exact factual music industry data for rankings (e.g. 1st most viewed music video is Despacito, 4th most viewed is Shape of You by Ed Sheeran, etc.).\n"
                    "- STRICTLY NEVER return children's nursery rhymes, toddler poems, or animations like 'Baby Shark', 'Pinkfong', 'Cocomelon', or 'Wheels on the Bus' when asked for a song.\n"
                    'Respond strictly in valid JSON format: {"title": "<song title>", "artist": "<primary artist>"}'
                )
                raw = await router.generate_text(prompt)
                if raw:
                    match = re.search(r'(\{[\s\S]*\})', raw)
                    if match:
                        data = json.loads(match.group(1))
                        t = data.get("title", "").strip()
                        a = data.get("artist", "").strip()
                        if t:
                            if "baby shark" in t.lower() or "pinkfong" in a.lower():
                                return "Despacito", "Luis Fonsi ft. Daddy Yankee"
                            return t, a
            except Exception:
                pass

        cleaned = re.sub(r'^(?:play|start|listen to|hear)\s+', '', query, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r'\s+on spotify$', '', cleaned, flags=re.IGNORECASE).strip()
        return cleaned or query, ""

    async def _play_track_desktop(self, track_id: Optional[str], search_text: str):
        """
        Play track cleanly on Windows desktop:
        - NEVER uses blind pyautogui.write (zero keystrokes leak to secondary displays/browsers)
        - ZERO mouse cursor movements
        - Opens direct Spotify URI and triggers media playback
        """
        if track_id:
            self._launch_spotify_uri(f"spotify:track:{track_id}")
        else:
            encoded = urllib.parse.quote(search_text)
            self._launch_spotify_uri(f"spotify:search:{encoded}")

        # Wait briefly for Spotify to load the track view, then trigger media play
        await asyncio.sleep(0.8)
        
        # 1. Try Windows SMTC
        session = await self._get_windows_media_session(spotify_only=True)
        if session:
            try:
                await session.try_play_async()
                return
            except Exception:
                pass

        # 2. Native media play key (Play/Pause: 179)
        self._send_media_key(179)

    async def execute(self, action: str, query: str = "", mood: str = "", **kwargs) -> Dict[str, Any]:
        try:
            sp = self._get_spotipy()

            if action in ["play", "pause"]:
                track = self._get_cached_track() or {"title": "Spotify", "artist": "Media Player"}
                track["status"] = "playing" if action == "play" else "idle"
                self._update_profile_current_track(track)

                if spotify_bridge.is_connected:
                    if action == "play":
                        await spotify_bridge.send_command("play")
                    else:
                        await spotify_bridge.send_command("pause")
                    return {
                        "success": True,
                        "message": f"Spotify playback {action}ed via internal bridge.",
                        "data": {"action": action, "current_track": track},
                        "ui_action": "spotify_update"
                    }

                if sp and not self.api_premium_blocked:
                    try:
                        def do_sp_play():
                            if action == "play":
                                sp.start_playback()
                            else:
                                sp.pause_playback()
                        await asyncio.wait_for(asyncio.to_thread(do_sp_play), timeout=0.8)
                        return {
                            "success": True,
                            "message": f"Spotify {action}ed via Web API.",
                            "data": {"action": action, "current_track": track},
                            "ui_action": "spotify_update"
                        }
                    except Exception as e:
                        if "403" in str(e) or "premium" in str(e).lower():
                            self.api_premium_blocked = True

                self._send_media_key(179)
                return {
                    "success": True,
                    "message": "Spotify playback toggled.",
                    "data": {"action": action, "current_track": track},
                    "ui_action": "spotify_update"
                }

            elif action == "next":
                if spotify_bridge.is_connected:
                    await spotify_bridge.send_command("next")
                else:
                    self._send_media_key(176)
                return {"success": True, "message": "Skipped to next track on Spotify.", "data": {"action": "next"}, "ui_action": "spotify_update"}

            elif action == "previous":
                if spotify_bridge.is_connected:
                    await spotify_bridge.send_command("previous")
                else:
                    self._send_media_key(177)
                return {"success": True, "message": "Returned to previous track on Spotify.", "data": {"action": "previous"}, "ui_action": "spotify_update"}

                self._send_media_key(176)
                return {
                    "success": True,
                    "message": "Skipped to next track.",
                    "data": {"action": "next"},
                    "ui_action": "spotify_update"
                }

            elif action == "previous":
                if spotify_bridge.is_connected:
                    await spotify_bridge.send_command("previous")
                    return {"success": True, "message": "Returned to previous track via internal bridge.", "data": {"action": "previous"}}

                if sp and not self.api_premium_blocked:
                    try:
                        sp.previous_track()
                        return {"success": True, "message": "Returned to previous track via Web API.", "data": {"action": "previous"}}
                    except Exception:
                        pass

                if session:
                    try:
                        await session.try_skip_previous_async()
                        return {"success": True, "message": "Returned to previous track.", "data": {"action": "previous"}, "ui_action": "spotify_update"}
                    except Exception:
                        pass

                self._send_media_key(177)
                return {
                    "success": True,
                    "message": "Returned to previous track.",
                    "data": {"action": "previous"},
                    "ui_action": "spotify_update"
                }

            elif action == "play_song":
                if not query:
                    return {"success": False, "message": "Song query required.", "data": None}

                q_raw = query.lower()
                if "baby shark" in q_raw or "pinkfong" in q_raw:
                    if any(w in q_raw for w in ["not", "never", "meant", "song", "real", "youtube", "yt"]):
                        query = "Despacito"

                if "playlist" in query.lower():
                    clean_query = query.lower().replace("playlist", "").strip()
                    return await self.execute("play_playlist", query=clean_query or query)

                resolved_title, resolved_artist = await self._resolve_descriptive_query(query)
                search_text = f"{resolved_title} {resolved_artist}".strip()

                # Find exact track ID (0.3s DuckDuckGo lookup)
                track_id = await self._find_spotify_track_id(search_text)

                # 1. PRIMARY PATH: Spicetify Internal WebSocket Bridge (100% Free, instant, zero focus)
                if spotify_bridge.is_connected and track_id:
                    await spotify_bridge.send_command("play_uri", uri=f"spotify:track:{track_id}")
                    track_info = {
                        "title": resolved_title.title(),
                        "artist": resolved_artist or "Spotify",
                        "status": "playing",
                        "query": query,
                        "track_id": track_id
                    }
                    self._update_profile_current_track(track_info)
                    artist_str = f" by {resolved_artist}" if resolved_artist else ""
                    return {
                        "success": True,
                        "message": f"Playing '{resolved_title.title()}'{artist_str} on Spotify, Sir.",
                        "data": track_info,
                        "ui_action": "spotify_track_change"
                    }

                # 2. SECONDARY PATH: Spotify Web API (Active Premium accounts)
                if sp and not self.api_premium_blocked:
                    try:
                        track_uri = f"spotify:track:{track_id}" if track_id else None
                        if not track_uri:
                            res = sp.search(q=search_text, type="track", limit=1)
                            tracks = res.get("tracks", {}).get("items", [])
                            if tracks:
                                track_uri = tracks[0].get("uri")

                        if track_uri:
                            devices = sp.devices().get("devices", [])
                            active_id = next((d["id"] for d in devices if d.get("is_active")), None)
                            if not active_id and devices:
                                active_id = devices[0]["id"]

                            sp.start_playback(device_id=active_id, uris=[track_uri])
                            track_info = {
                                "title": resolved_title.title(),
                                "artist": resolved_artist or "Spotify",
                                "status": "playing",
                                "query": query,
                                "uri": track_uri
                            }
                            self._update_profile_current_track(track_info)
                            return {
                                "success": True,
                                "message": f"Playing '{resolved_title.title()}' by {resolved_artist or 'Spotify'} on Spotify via Web API.",
                                "data": track_info,
                                "ui_action": "spotify_track_change"
                            }
                    except Exception as e:
                        if "403" in str(e) or "Active premium subscription" in str(e):
                            self.api_premium_blocked = True

                # 2. SECONDARY PATH: Desktop Protocol Handler (Works 100% on Free & Premium accounts)
                # Opens exact track URI without moving mouse and without typing into other screens
                await self._play_track_desktop(track_id, search_text)

                track_info = {
                    "title": resolved_title.title(),
                    "artist": resolved_artist or "Spotify",
                    "status": "playing",
                    "query": query,
                    "track_id": track_id
                }
                self._update_profile_current_track(track_info)

                artist_str = f" by {resolved_artist}" if resolved_artist else ""
                return {
                    "success": True,
                    "message": f"Playing '{resolved_title.title()}'{artist_str} on Spotify desktop, Sir.",
                    "data": track_info,
                    "ui_action": "spotify_track_change"
                }

            elif action in ["play_playlist", "search_playlist", "recommend_music"]:
                pl_query = query or mood or "focus"
                clean_name = pl_query.replace("playlist", "").replace("on spotify", "").strip()
                search_text = f"{clean_name or pl_query} playlist"

                if sp and not self.api_premium_blocked:
                    try:
                        res = sp.search(q=search_text, type="playlist", limit=1)
                        pls = res.get("playlists", {}).get("items", [])
                        if pls:
                            pl = pls[0]
                            pl_uri = pl.get("uri")
                            pl_name = pl.get("name", clean_name.title())
                            devices = sp.devices().get("devices", [])
                            active_id = next((d["id"] for d in devices if d.get("is_active")), None)
                            if not active_id and devices:
                                active_id = devices[0]["id"]
                            sp.start_playback(device_id=active_id, context_uri=pl_uri)
                            track_info = {
                                "title": pl_name,
                                "artist": "Spotify Playlist",
                                "status": "playing",
                                "playlist": pl_query
                            }
                            self._update_profile_current_track(track_info)
                            return {
                                "success": True,
                                "message": f"Playing playlist '{pl_name}' on Spotify.",
                                "data": track_info,
                                "ui_action": "spotify_update"
                            }
                    except Exception:
                        pass

                encoded = urllib.parse.quote(search_text)
                self._launch_spotify_uri(f"spotify:search:{encoded}")
                
                track_info = {
                    "title": f"{clean_name.title() or pl_query.title()} Playlist",
                    "artist": "Spotify",
                    "status": "playing",
                    "playlist": pl_query
                }
                self._update_profile_current_track(track_info)

                return {
                    "success": True,
                    "message": f"Queued '{clean_name.title() or pl_query.title()}' playlist on Spotify.",
                    "data": track_info,
                    "ui_action": "spotify_update"
                }

            elif action == "status":
                if spotify_bridge.is_connected and spotify_bridge.current_status.get("title") not in ["", "Awaiting Command"]:
                    bs = spotify_bridge.current_status
                    return {
                        "success": True,
                        "message": f"Media status: {bs.get('title')} by {bs.get('artist')}",
                        "data": {
                            "is_running": True,
                            "api_connected": True,
                            "bridge_connected": True,
                            "current_track": {
                                "title": bs.get("title", "Standby"),
                                "artist": bs.get("artist", "Ready"),
                                "status": "playing" if bs.get("is_playing") else "idle"
                            }
                        },
                        "ui_action": "spotify_update"
                    }

                current_title = "Standby"
                current_artist = "Ready"
                is_playing = False

                cached = self._get_cached_track()
                if cached:
                    current_title = cached.get("title", current_title)
                    current_artist = cached.get("artist", current_artist)
                    is_playing = (cached.get("status") == "playing")

                if sp and not self.api_premium_blocked:
                    try:
                        def get_curr():
                            return sp.current_playback()
                        curr = await asyncio.wait_for(asyncio.to_thread(get_curr), timeout=0.8)
                        if curr and curr.get("item"):
                            item = curr["item"]
                            current_title = item.get("name", current_title)
                            current_artist = item["artists"][0]["name"] if item.get("artists") else current_artist
                            is_playing = curr.get("is_playing", is_playing)
                    except Exception as e:
                        if "403" in str(e) or "premium" in str(e).lower():
                            self.api_premium_blocked = True

                return {
                    "success": True,
                    "message": f"Media status: {current_title} by {current_artist}",
                    "data": {
                        "is_running": True,
                        "api_connected": bool(sp),
                        "current_track": {
                            "title": current_title,
                            "artist": current_artist,
                            "status": "playing" if is_playing else "idle"
                        }
                    },
                    "ui_action": "spotify_update"
                }

            return {"success": False, "message": f"Unsupported action: {action}", "data": None}

        except Exception as e:
            return {"success": False, "message": f"Spotify error: {str(e)}", "data": None}

    def _update_profile_current_track(self, track: dict):
        try:
            with open(self.profile_file, "w") as f:
                json.dump({"current_track": track}, f, indent=2)
        except Exception:
            pass
