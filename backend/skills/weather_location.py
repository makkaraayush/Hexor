import httpx
import datetime
from typing import Dict, Any, Optional
from .base import BaseSkill
from ..config import config, STORAGE_DIR

class WeatherLocationSkill(BaseSkill):
    name = "weather_location"
    description = (
        "Provides real-time local and global weather forecasts, current time/date, "
        "and geographical location tracking."
    )
    category = "system"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get_weather", "get_location", "get_time"],
                "description": "Weather or location action."
            },
            "city": {
                "type": "string",
                "description": "Optional city name for weather (e.g. 'Tokyo', 'London', 'New York'). Defaults to current location."
            }
        },
        "required": ["action"]
    }

    WMO_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snowfall",
        73: "Moderate snowfall",
        75: "Heavy snowfall",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }

    def __init__(self):
        default_city = config.DEFAULT_LOCATION or "Unknown"
        default_lat = config.DEFAULT_LATITUDE if config.DEFAULT_LATITUDE != 0.0 else 28.6139
        default_lon = config.DEFAULT_LONGITUDE if config.DEFAULT_LONGITUDE != 0.0 else 77.2090

        self.cached_location = {
            "city": default_city,
            "region": "Haryana" if "haryana" in default_city.lower() else "",
            "country": "India",
            "lat": default_lat,
            "lon": default_lon
        }
        self.last_weather = {}

    def set_browser_location(self, lat: float, lon: float, city: str = ""):
        self.cached_location["lat"] = lat
        self.cached_location["lon"] = lon
        if city:
            self.cached_location["city"] = city

    async def _resolve_ip_location(self) -> Dict[str, Any]:
        if config.DEFAULT_LOCATION and config.DEFAULT_LATITUDE != 0.0:
            return self.cached_location
        try:
            async with httpx.AsyncClient(verify=False, timeout=4.0) as client:
                res = await client.get('http://ip-api.com/json/')
                if res.status_code == 200:
                    data = res.json()
                    self.cached_location = {
                        "city": data.get("city", "Current City"),
                        "region": data.get("regionName", ""),
                        "country": data.get("country", ""),
                        "lat": data.get("lat", 28.6139),
                        "lon": data.get("lon", 77.2090),
                        "timezone": data.get("timezone", "UTC")
                    }
        except Exception:
            pass
        return self.cached_location

    async def _geocode_city(self, city: str) -> Optional[Dict[str, Any]]:
        try:
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1"
            async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    results = res.json().get("results", [])
                    if results:
                        return {
                            "name": results[0]["name"],
                            "country": results[0].get("country", ""),
                            "lat": results[0]["latitude"],
                            "lon": results[0]["longitude"]
                        }
        except Exception:
            pass
        return None

    async def execute(self, action: str = "get_weather", city: str = "", **kwargs) -> Dict[str, Any]:
        try:
            if action == "get_time":
                now = datetime.datetime.now()
                time_str = now.strftime("%I:%M:%S %p")
                date_str = now.strftime("%A, %B %d, %Y")
                return {
                    "success": True,
                    "message": f"The current time is {time_str} on {date_str}.",
                    "data": {
                        "time": time_str,
                        "date": date_str,
                        "iso": now.isoformat()
                    }
                }

            elif action == "get_location":
                if self.cached_location["city"] == "Unknown":
                    await self._resolve_ip_location()
                loc = self.cached_location
                loc_str = f"{loc['city']}, {loc['country']}" if loc.get("country") else loc["city"]
                return {
                    "success": True,
                    "message": f"Your current location is {loc_str}.",
                    "data": loc,
                    "ui_action": "location_update"
                }

            elif action == "get_weather":
                lat = self.cached_location["lat"]
                lon = self.cached_location["lon"]
                target_city = city.strip() or self.cached_location["city"]

                if city.strip():
                    geo = await self._geocode_city(city.strip())
                    if geo:
                        lat = geo["lat"]
                        lon = geo["lon"]
                        target_city = f"{geo['name']}, {geo['country']}"
                elif self.cached_location["city"] == "Unknown":
                    await self._resolve_ip_location()
                    lat = self.cached_location["lat"]
                    lon = self.cached_location["lon"]
                    target_city = f"{self.cached_location['city']}, {self.cached_location['country']}"

                url = (
                    f"https://api.open-meteo.com/v1/forecast?"
                    f"latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,"
                    f"apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m&timezone=auto"
                )
                async with httpx.AsyncClient(verify=False, timeout=6.0) as client:
                    res = await client.get(url)
                    if res.status_code == 200:
                        cur = res.json().get("current", {})
                        temp_c = cur.get("temperature_2m", 0)
                        temp_f = round((temp_c * 9/5) + 32, 1)
                        feels_c = cur.get("apparent_temperature", temp_c)
                        humidity = cur.get("relative_humidity_2m", 0)
                        wind = cur.get("wind_speed_10m", 0)
                        wcode = cur.get("weather_code", 0)
                        condition = self.WMO_CODES.get(wcode, "Clear")

                        weather_data = {
                            "location": target_city,
                            "temperature_c": temp_c,
                            "temperature_f": temp_f,
                            "feels_like_c": feels_c,
                            "humidity": humidity,
                            "wind_speed_kmh": wind,
                            "condition": condition,
                            "lat": lat,
                            "lon": lon
                        }
                        self.last_weather = weather_data

                        msg = (
                            f"The current weather in {target_city} is {condition} at {temp_c}°C ({temp_f}°F), "
                            f"feels like {feels_c}°C with {humidity}% humidity."
                        )
                        return {
                            "success": True,
                            "message": msg,
                            "data": weather_data,
                            "ui_action": "show_weather"
                        }

                return {"success": False, "message": "Could not retrieve weather data at this moment.", "data": None}

            return {"success": False, "message": f"Unsupported weather action: {action}", "data": None}

        except Exception as e:
            return {"success": False, "message": f"Weather error: {str(e)}", "data": None}

