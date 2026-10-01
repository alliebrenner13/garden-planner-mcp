from __future__ import annotations

from typing import Any

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DAILY = "temperature_2m_min,temperature_2m_max"


class WeatherError(Exception):
    pass


def _parse_daily(payload: dict[str, Any]) -> list[dict[str, Any]]:
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    mins = daily.get("temperature_2m_min") or []
    maxs = daily.get("temperature_2m_max") or []
    out: list[dict[str, Any]] = []
    for i, day in enumerate(times):
        tmin = mins[i] if i < len(mins) else None
        tmax = maxs[i] if i < len(maxs) else None
        out.append({"date": day, "tmin_c": tmin, "tmax_c": tmax})
    return out


def fetch_forecast(
    *,
    latitude: float,
    longitude: float,
    timezone: str,
    forecast_days: int = 7,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": DAILY,
        "timezone": timezone,
        "forecast_days": forecast_days,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(FORECAST_URL, params=params)
            resp.raise_for_status()
            return _parse_daily(resp.json())
    except httpx.HTTPError as exc:
        raise WeatherError(str(exc)) from exc


def fetch_archive(
    *,
    latitude: float,
    longitude: float,
    timezone: str,
    start_date: str,
    end_date: str,
    timeout: float = 20.0,
) -> list[dict[str, Any]]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": DAILY,
        "timezone": timezone,
        "start_date": start_date,
        "end_date": end_date,
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(ARCHIVE_URL, params=params)
            resp.raise_for_status()
            return _parse_daily(resp.json())
    except httpx.HTTPError as exc:
        raise WeatherError(str(exc)) from exc
