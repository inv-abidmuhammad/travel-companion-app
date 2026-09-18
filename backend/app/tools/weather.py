"""
get_weather — backed by OpenWeatherMap's free Geocoding + 5-day/3-hour
forecast APIs for near-term dates. Free tier only forecasts ~5 days
out; further out, this falls back to a web-search-based seasonal
estimate (clearly labeled as such via source="seasonal-estimate" —
never presented as a forecast). Unparseable or past dates come back
as an explicit error rather than a guess.
"""
from datetime import datetime, timezone
from typing import Optional

import requests
from langchain_core.tools import tool

from app.config import get_settings
from .places import _run_search

GEOCODE_URL = "https://api.openweathermap.org/geo/1.0/direct"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
REQUEST_TIMEOUT_SECONDS = 8
FORECAST_HORIZON_DAYS = 5

# location name -> (lat, lon), so repeated lookups within a process
# (e.g. multiple days of the same trip) don't re-geocode every time.
_geocode_cache: dict[str, tuple[float, float]] = {}


def _error(location: str, date: str, message: str, source: str = "openweathermap") -> dict:
    return {
        "location": location,
        "date": date,
        "condition": None,
        "temp_c": None,
        "rain_probability": None,
        "source": source,
        "error": message,
    }


def _seasonal_estimate(location: str, date: str, api_key: Optional[str]) -> dict:
    """Best-effort typical-conditions estimate for a date beyond the
    forecast horizon, via web search rather than a real forecast.
    condition/temp_c/rain_probability are deliberately left as a single
    free-text summary rather than structured numbers — a search result
    doesn't give reliable exact figures, and reporting fake precision
    here would be worse than not having them."""
    if not api_key:
        return _error(location, date, "Search API key is not configured for a seasonal estimate.", "seasonal-estimate")
    try:
        month_name = datetime.strptime(date, "%Y-%m-%d").strftime("%B")
        results = _run_search(f"typical weather in {location} in {month_name}", api_key)
    except requests.RequestException as exc:
        return _error(location, date, f"Seasonal estimate search failed: {exc}", "seasonal-estimate")

    if not results:
        return _error(location, date, "No seasonal weather information found.", "seasonal-estimate")

    summary = " ".join(r.get("content", "") for r in results[:2])[:500]
    return {
        "location": location,
        "date": date,
        "condition": summary or None,
        "temp_c": None,
        "rain_probability": None,
        "source": "seasonal-estimate",
        "error": None,
    }


def _parse_date(date: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _geocode(location: str, api_key: str) -> Optional[tuple[float, float]]:
    if location in _geocode_cache:
        return _geocode_cache[location]
    resp = requests.get(
        GEOCODE_URL,
        params={"q": location, "limit": 1, "appid": api_key},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    coords = (results[0]["lat"], results[0]["lon"])
    _geocode_cache[location] = coords
    return coords


@tool
def get_weather(location: str, date: str) -> dict:
    """Return weather info for a location on a given date. Use this
    when weather could affect route or activity choices — e.g.
    mountain driving, outdoor activities, or when the user asks
    directly. Args: location (city or place name), date in YYYY-MM-DD
    format. Dates within ~5 days return a real forecast
    (source="openweathermap"); further out returns a general seasonal
    estimate instead (source="seasonal-estimate") — say so plainly to
    the user rather than presenting it as a precise forecast. An
    unparseable or past date returns an error.
    """
    settings = get_settings()
    api_key = getattr(settings, "weather_api_key", None)

    target = _parse_date(date)
    if target is None:
        return _error(location, date, f"Could not parse date '{date}'. Use YYYY-MM-DD.")

    now = datetime.now(timezone.utc)
    days_out = (target.date() - now.date()).days
    if days_out < 0:
        return _error(location, date, "Date is in the past; no forecast available.")
    if days_out > FORECAST_HORIZON_DAYS:
        return _seasonal_estimate(location, date, getattr(settings, "search_api_key", None))

    if not api_key:
        return _error(location, date, "Weather API key is not configured.")

    try:
        coords = _geocode(location, api_key)
    except requests.RequestException as exc:
        return _error(location, date, f"Geocoding request failed: {exc}")
    if coords is None:
        return _error(location, date, f"Could not find location '{location}'.")
    lat, lon = coords

    try:
        resp = requests.get(
            FORECAST_URL,
            params={"lat": lat, "lon": lon, "appid": api_key, "units": "metric"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        return _error(location, date, f"Forecast request failed: {exc}")

    # Forecast entries are 3-hour steps as "YYYY-MM-DD HH:MM:SS". Pick the
    # entries for the target date and use the one closest to midday as
    # representative, since that's the most informative single snapshot
    # for planning purposes.
    same_day = [
        entry for entry in payload.get("list", [])
        if entry.get("dt_txt", "").startswith(target.strftime("%Y-%m-%d"))
    ]
    if not same_day:
        return _error(location, date, "No forecast data returned for that date.")

    def _hour_of(entry: dict) -> int:
        return int(entry["dt_txt"][11:13])

    best = min(same_day, key=lambda e: abs(_hour_of(e) - 12))

    return {
        "location": location,
        "date": date,
        "condition": best["weather"][0]["description"] if best.get("weather") else None,
        "temp_c": best.get("main", {}).get("temp"),
        "rain_probability": best.get("pop"),
        "source": "openweathermap",
        "error": None,
    }