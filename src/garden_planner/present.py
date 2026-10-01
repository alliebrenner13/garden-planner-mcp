from __future__ import annotations

from typing import Any, Mapping, Sequence

from garden_planner.units import c_to_f


def plant_for_user(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "name": row["name"],
        "slug": row["slug"],
        "hardiness": row["hardiness"],
        "days_to_maturity": row["days_to_maturity"],
        "min_temp_f": c_to_f(row["min_temp_c"]),
        "notes": row["notes"],
    }


def planting_for_user(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "plant_name": row["plant"],
        "variety": row["variety"],
        "planted_on": row["planted_on"],
        "quantity": row["quantity"],
        "bed": row["bed"],
        "status": row["status"],
        "notes": row["notes"],
        "harvested_on": row["harvested_on"],
        "hardiness": row["hardiness"],
        "min_temp_f": c_to_f(row["min_temp_c"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def forecast_for_user(days: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "date": day["date"],
            "low_f": c_to_f(day["tmin_c"]),
            "high_f": c_to_f(day["tmax_c"]),
        }
        for day in days
    ]


def frost_for_user(
    result: Mapping[str, Any],
    plantings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_id = {row["id"]: row for row in plantings}
    nights = [
        {"date": night["date"], "low_f": c_to_f(night["tmin_c"])}
        for night in result["frost_nights"]
    ]
    at_risk = []
    for hit in result["at_risk"]:
        src = by_id.get(hit["id"], {})
        at_risk.append(
            {
                "id": hit["id"],
                "plant_name": src.get("plant") or hit.get("slug"),
                "date": hit["date"],
                "low_f": c_to_f(hit["tmin_c"]),
                "damage_at_or_below_f": c_to_f(hit["threshold_c"]),
            }
        )
    return {
        "ok": result["ok"],
        "source": result["source"],
        "threshold_f": c_to_f(result["threshold_c"]),
        "frost_nights": nights,
        "at_risk": at_risk,
        "n_days": result["n_days"],
        "n_plantings": result["n_plantings"],
    }
