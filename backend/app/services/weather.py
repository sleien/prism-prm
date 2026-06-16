"""Weather enrichment for events via Open-Meteo (free, no API key).

Geocodes an event's location, then fetches the daily forecast for the event
date. Open-Meteo only forecasts ~16 days out, so events further away simply get
no weather (the field stays null). All network calls are best-effort.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

log = logging.getLogger("prism.weather")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
FORECAST_HORIZON_DAYS = 16
_DAILY_VARS = "temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max"

# WMO weather interpretation codes -> (description, emoji).
_WMO: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "☀️"),
    1: ("Mainly clear", "🌤️"),
    2: ("Partly cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Fog", "🌫️"),
    48: ("Rime fog", "🌫️"),
    51: ("Light drizzle", "🌦️"),
    53: ("Drizzle", "🌦️"),
    55: ("Heavy drizzle", "🌧️"),
    61: ("Light rain", "🌦️"),
    63: ("Rain", "🌧️"),
    65: ("Heavy rain", "🌧️"),
    71: ("Light snow", "🌨️"),
    73: ("Snow", "🌨️"),
    75: ("Heavy snow", "❄️"),
    77: ("Snow grains", "🌨️"),
    80: ("Rain showers", "🌦️"),
    81: ("Rain showers", "🌧️"),
    82: ("Violent rain showers", "⛈️"),
    85: ("Snow showers", "🌨️"),
    86: ("Heavy snow showers", "❄️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with hail", "⛈️"),
    99: ("Thunderstorm with hail", "⛈️"),
}


def describe(code: int) -> tuple[str, str]:
    return _WMO.get(code, ("Unknown", "❓"))


async def geocode(client: httpx.AsyncClient, location: str) -> tuple[float, float] | None:
    resp = await client.get(GEOCODE_URL, params={"name": location, "count": 1})
    resp.raise_for_status()
    results = resp.json().get("results") or []
    if not results:
        return None
    return results[0]["latitude"], results[0]["longitude"]


async def daily_forecast(
    client: httpx.AsyncClient, lat: float, lon: float, day: date
) -> dict[str, Any] | None:
    resp = await client.get(
        FORECAST_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "daily": _DAILY_VARS,
            "start_date": day.isoformat(),
            "end_date": day.isoformat(),
            "timezone": "auto",
        },
    )
    resp.raise_for_status()
    daily = resp.json().get("daily") or {}
    if not daily.get("time"):
        return None
    code = int((daily.get("weather_code") or [0])[0])
    description, emoji = describe(code)
    return {
        "date": day.isoformat(),
        "temp_max": (daily.get("temperature_2m_max") or [None])[0],
        "temp_min": (daily.get("temperature_2m_min") or [None])[0],
        "weather_code": code,
        "description": description,
        "emoji": emoji,
        "precipitation_probability": (daily.get("precipitation_probability_max") or [None])[0],
    }


async def enrich_event_weather(event: Any) -> None:
    """Geocode + fetch forecast for an event, mutating latitude/longitude/weather.

    No-op when there's no location, the date is out of the forecast window, or a
    network error occurs.
    """
    if not event.location:
        return
    start = event.starts_at
    event_day = start.astimezone(UTC).date() if start.tzinfo else start.date()
    horizon = datetime.now(UTC).date() + timedelta(days=FORECAST_HORIZON_DAYS)
    if event_day < datetime.now(UTC).date() or event_day > horizon:
        return
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            coords = await geocode(client, event.location)
            if coords is None:
                return
            event.latitude, event.longitude = coords
            forecast = await daily_forecast(client, coords[0], coords[1], event_day)
            if forecast is not None:
                event.weather = forecast
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("Weather enrichment failed for '%s': %s", event.location, exc)
