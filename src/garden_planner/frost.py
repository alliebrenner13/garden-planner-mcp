from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Sequence


def evaluate_frost(
    days: Sequence[Mapping[str, Any]],
    plantings: Sequence[Mapping[str, Any]],
    threshold_c: float,
    *,
    source: str,
) -> dict[str, Any]:
    frost_nights: list[dict[str, Any]] = []
    at_risk: list[dict[str, Any]] = []
    for day in days:
        tmin = day["tmin_c"]
        if tmin is None:
            continue
        tmin_c = float(tmin)
        date_s = str(day["date"])
        if tmin_c <= threshold_c:
            frost_nights.append({"date": date_s, "tmin_c": tmin_c})
        for planting in plantings:
            plant_min = float(planting["min_temp_c"])
            if tmin_c <= plant_min:
                at_risk.append(
                    {
                        "id": planting["id"],
                        "slug": planting["slug"],
                        "date": date_s,
                        "tmin_c": tmin_c,
                        "threshold_c": plant_min,
                    }
                )
    return {
        "ok": True,
        "source": source,
        "threshold_c": threshold_c,
        "frost_nights": frost_nights,
        "at_risk": at_risk,
        "n_days": len(days),
        "n_plantings": len(plantings),
    }


def planting_window(
    *,
    slug: str,
    name: str,
    hardiness: str,
    days_to_maturity: int | None,
    spring_offset_days: int,
    fall_offset_days: int,
    last_spring: date,
    first_fall: date,
    year: int,
) -> dict[str, Any]:
    spring_plant = last_spring + timedelta(days=spring_offset_days)
    fall_last = first_fall - timedelta(days=fall_offset_days)
    return {
        "ok": True,
        "slug": slug,
        "name": name,
        "hardiness": hardiness,
        "year": year,
        "days_to_maturity": days_to_maturity,
        "last_spring": last_spring.isoformat(),
        "first_fall": first_fall.isoformat(),
        "spring_plant": spring_plant.isoformat(),
        "fall_last_plant": fall_last.isoformat(),
        "spring_offset_days": spring_offset_days,
        "fall_offset_days": fall_offset_days,
    }
