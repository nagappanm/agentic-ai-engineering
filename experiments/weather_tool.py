"""A real weather tool for the Module 2 agent experiment (Experiment 3).

Uses Open-Meteo — keyless and free — in two steps: geocode the city, then fetch
a daily forecast. Standard library only (``urllib``), so it adds no dependency.

If it proves better than DuckDuckGo snippets for weather questions, it's a
candidate to graduate into ``documind/tools.py``.
"""

from __future__ import annotations

import json
import ssl
import urllib.parse
import urllib.request

import certifi
from langchain_core.tools import tool

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Use certifi's CA bundle explicitly: a stock python.org build on macOS doesn't
# trust the system roots, so urllib otherwise fails with CERTIFICATE_VERIFY_FAILED.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())


def _get(url: str, params: dict) -> dict:
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(  # noqa: S310
        f"{url}?{query}", timeout=10, context=_SSL_CONTEXT
    ) as response:
        return json.load(response)


def fetch_forecast(city: str, days: int = 14) -> str:
    """Return a plain-text daily forecast for ``city`` (pure, testable)."""
    geo = _get(_GEOCODE_URL, {"name": city, "count": 1})
    matches = geo.get("results")
    if not matches:
        return f"Error: could not find a location named {city!r}."
    place = matches[0]
    name = ", ".join(p for p in (place.get("name"), place.get("country")) if p)

    data = _get(
        _FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": min(max(days, 1), 16),
            "timezone": "auto",
        },
    )
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    rain = daily.get("precipitation_probability_max", [])

    lines = [f"Daily forecast for {name} (temperatures in °C):"]
    for i, date in enumerate(dates):
        rain_pct = rain[i] if i < len(rain) and rain[i] is not None else "?"
        lines.append(f"{date}: high {highs[i]}, low {lows[i]}, rain chance {rain_pct}%")
    return "\n".join(lines)


@tool
def weather_forecast(city: str) -> str:
    """Get the multi-day daily weather forecast (high/low temp, rain chance) for a city.

    Use this for any weather question instead of web search — it returns real
    forecast data (up to 16 days ahead) from Open-Meteo.
    """
    try:
        return fetch_forecast(city)
    except Exception as exc:  # network / JSON errors degrade gracefully
        return f"Error fetching weather for {city!r}: {exc}"
