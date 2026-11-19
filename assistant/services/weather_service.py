"""Current weather from Open-Meteo (free, no API key). Needs internet.
Only two fixed HTTPS hosts are ever contacted."""
import json
import urllib.error
import urllib.parse
import urllib.request

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

CODES = {0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "foggy", 48: "foggy",
         51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
         61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
         71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
         80: "rain showers", 81: "rain showers", 82: "heavy rain showers", 85: "snow showers", 86: "snow showers",
         95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}


def _get(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=6) as resp:
        return json.load(resp)


def get_weather(city):
    """Returns (True, data_dict) or (False, error_code) with code in
    'no_city', 'not_found', 'network'."""
    city = (city or "").strip()[:80]
    if not city:
        return False, "no_city"
    try:
        found = (_get(GEOCODE_URL, {"name": city, "count": 1}).get("results") or [])
        if not found:
            return False, "not_found"
        place = found[0]
        cur = _get(FORECAST_URL, {
            "latitude": place["latitude"], "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
        })["current"]
        return True, {
            "city": place["name"], "temp": round(cur["temperature_2m"]),
            "feels": round(cur["apparent_temperature"]), "humidity": round(cur["relative_humidity_2m"]),
            "wind": round(cur["wind_speed_10m"]), "condition": CODES.get(cur["weather_code"], "unsettled weather"),
        }
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, TypeError):
        return False, "network"
