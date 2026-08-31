"""
get_weather — Phase 2's first new tool.

Mocked, per the blueprint's "Architecture principle: don't integrate
every service on day one." Same shape a real weather API tool will
return later (see the blueprint's tool contract pattern), so swapping
in a real API in Phase 2+ later means changing the tool body, not the
graph, the agent's prompt, or anything that calls it.
"""
import hashlib

from langchain_core.tools import tool

_CONDITIONS = ["clear", "partly cloudy", "overcast", "light rain", "thunderstorms"]


@tool
def get_weather(location: str, date: str) -> dict:
    """Return a forecast for a location on a given date. Use this when
    weather could affect route or activity choices — e.g. mountain
    driving, outdoor activities, or when the user asks directly.
    Args: location (city or place name), date (any reasonable format,
    e.g. '2026-09-15' or 'day 2 of the trip').
    """
    # Deterministic mock: same (location, date) always returns the same
    # forecast, so you can reason about and test agent behavior without
    # results changing between runs. A real implementation replaces the
    # body below with an actual API call — the return shape stays the same.
    seed = int(hashlib.sha256(f"{location}|{date}".encode()).hexdigest(), 16)
    condition = _CONDITIONS[seed % len(_CONDITIONS)]
    temp_c = 18 + (seed % 15)
    rain_probability = round((seed % 100) / 100, 2)

    return {
        "location": location,
        "date": date,
        "condition": condition,
        "temp_c": temp_c,
        "rain_probability": rain_probability,
        "source": "mock",
    }
