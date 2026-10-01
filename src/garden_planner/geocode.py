from __future__ import annotations

from typing import Any

import httpx

from garden_planner.weather import WeatherError

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"


def search_places(query: str, *, count: int = 6, timeout: float = 20.0) -> list[dict[str, Any]]:
    text = query.strip()
    if not text:
        return []
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(
                GEOCODE_URL,
                params={"name": text, "count": max(1, min(10, count)), "language": "en", "format": "json"},
            )
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:
        raise WeatherError(str(exc)) from exc
    out: list[dict[str, Any]] = []
    for hit in payload.get("results") or []:
        parts = [hit.get("name"), hit.get("admin1"), hit.get("country")]
        label = ", ".join(str(part) for part in parts if part)
        out.append(
            {
                "label": label,
                "name": hit.get("name") or label,
                "latitude": hit.get("latitude"),
                "longitude": hit.get("longitude"),
                "timezone": hit.get("timezone") or "UTC",
                "country": hit.get("country") or "",
                "admin1": hit.get("admin1") or "",
            }
        )
    return out
