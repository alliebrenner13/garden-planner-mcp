from __future__ import annotations

import logging
import sys
from datetime import date
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from garden_planner.config import ConfigMissingError, load_config
from garden_planner import services
from garden_planner.dates import DATE_HINT, parse_date
from garden_planner.db import (
    PLANTS_SEED,
    connect,
    get_plant,
    init_db,
    insert_planting,
    list_plantings as db_list_plantings,
    plantings_for_frost,
    row_to_dict,
    update_planting as db_update_planting,
)
from garden_planner.frost import evaluate_frost, planting_window as compute_window
from garden_planner.onboarding import setup_prompt
from garden_planner.present import forecast_for_user, frost_for_user, planting_for_user
from garden_planner.weather import WeatherError, fetch_archive, fetch_forecast

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("garden_planner")

mcp = FastMCP("garden-planner")

_STATUSES = {"planned", "planted", "harvested", "failed"}
_STATUS_HINT = "planned, planted, harvested, or failed"
_PLANT_EXAMPLES = ", ".join(name for _slug, name, *_rest in PLANTS_SEED)
_PLANT_HINT = f"Common name from the catalog, such as {_PLANT_EXAMPLES}."

PlantName = Annotated[str, Field(title="Plant name", description=_PLANT_HINT, examples=["Kale", "Tomato"])]
OptionalPlantName = Annotated[
    str | None,
    Field(title="Plant name", description=f"Optional filter. {_PLANT_HINT}"),
]
PlantedOn = Annotated[
    str,
    Field(
        title="Planted on",
        description=f"Date you planted. {DATE_HINT}",
        examples=["2026-09-11", "09-11-2026", "9/11/26"],
    ),
]
OptionalPlantedOn = Annotated[
    str | None,
    Field(
        title="Planted on",
        description=f"New planting date, if you are changing it. {DATE_HINT}",
    ),
]
HarvestedOn = Annotated[
    str | None,
    Field(
        title="Harvested on",
        description=f"Harvest date, if this planting is done. {DATE_HINT}",
    ),
]
Variety = Annotated[
    str | None,
    Field(title="Variety", description="Optional cultivar, such as Brandywine or Lacinato."),
]
Quantity = Annotated[
    int | None,
    Field(title="Quantity", description="How many plants or row-feet. Whole number, optional."),
]
Bed = Annotated[
    str | None,
    Field(title="Bed", description="Optional bed or garden area name, such as Front bed."),
]
Status = Annotated[
    str,
    Field(title="Status", description=f"One of: {_STATUS_HINT}. Default is planted."),
]
OptionalStatus = Annotated[
    str | None,
    Field(title="Status", description=f"Optional filter or new status. One of: {_STATUS_HINT}."),
]
Notes = Annotated[
    str | None,
    Field(title="Notes", description="Optional free-text notes about this planting."),
]
ForecastDays = Annotated[
    int,
    Field(
        title="Days to forecast",
        description="How many days ahead to fetch (1–16). Default is 7.",
        ge=1,
        le=16,
    ),
]
StartDate = Annotated[
    str | None,
    Field(
        title="Start date",
        description=(
            "Optional start of a past date range. If you fill this in, also fill end date. "
            f"{DATE_HINT}"
        ),
    ),
]
EndDate = Annotated[
    str | None,
    Field(
        title="End date",
        description=(
            "Optional end of a past date range. If you fill this in, also fill start date. "
            f"{DATE_HINT}"
        ),
    ),
]
Year = Annotated[
    int | None,
    Field(title="Year", description="Garden year. Leave blank for the current year."),
]
PlantingId = Annotated[
    int,
    Field(title="Planting ID", description="The id number shown by list_plantings."),
]


def _err(msg: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "error": msg, **extra}


def _db():
    conn = connect()
    init_db(conn)
    return conn


def _parse_date_arg(raw: str, field: str) -> date | dict[str, Any]:
    parsed = parse_date(raw)
    if parsed is None:
        return _err("bad_date", field=field, input=raw, hint=DATE_HINT)
    return parsed


def _unknown_plant(plant_name: str) -> dict[str, Any]:
    return _err(
        "unknown_plant",
        plant_name=plant_name,
        hint=f"Try a catalog plant such as {_PLANT_EXAMPLES}.",
    )


def _need_setup() -> dict[str, Any]:
    return _err(
        "needs_setup",
        hint="Use the set_up_my_garden prompt, or open the web app at http://127.0.0.1:8765/ to answer the setup questions.",
    )


@mcp.prompt
def set_up_my_garden() -> str:
    """Ask the gardener for location, beds, and plantings, then save them locally."""
    return setup_prompt()


@mcp.tool
def search_places(query: str) -> dict[str, Any]:
    """Look up a city, town, or ZIP so weather can use the right coordinates."""
    return services.search_places(query)


@mcp.tool
def save_garden_setup(
    latitude: float,
    longitude: float,
    timezone: str,
    place: str,
    aspect: str = "",
    sun: str = "",
    last_spring_frost: str = "",
    first_fall_frost: str = "",
    frost_threshold_f: float = 32,
    plantings_json: str = "[]",
) -> dict[str, Any]:
    """Save this garden's location, plot notes, and optional plantings to the local config and log."""
    import json

    try:
        plantings = json.loads(plantings_json or "[]")
    except json.JSONDecodeError:
        return _err("bad_json", hint="plantings_json should be a JSON list of planting objects.")
    if not isinstance(plantings, list):
        return _err("bad_json", hint="plantings_json should be a JSON list.")
    return services.complete_setup(
        {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone,
            "place": place,
            "aspect": aspect,
            "sun": sun,
            "last_spring_frost": last_spring_frost,
            "first_fall_frost": first_fall_frost,
            "frost_threshold_f": frost_threshold_f,
            "plantings": plantings,
        }
    )


@mcp.tool
def log_planting(
    plant_name: PlantName,
    planted_on: PlantedOn,
    variety: Variety = None,
    quantity: Quantity = None,
    bed: Bed = None,
    status: Status = "planted",
    notes: Notes = None,
) -> dict[str, Any]:
    """Add a planting to your garden log."""
    if status not in _STATUSES:
        return _err("bad_status", status=status, hint=_STATUS_HINT)
    planted = _parse_date_arg(planted_on, "planted_on")
    if isinstance(planted, dict):
        return planted
    conn = _db()
    try:
        plant = get_plant(conn, plant_name)
        if plant is None:
            return _unknown_plant(plant_name)
        row = insert_planting(
            conn,
            plant_id=plant["id"],
            planted_on=planted.isoformat(),
            variety=variety,
            quantity=quantity,
            bed=bed,
            status=status,
            notes=notes,
        )
        return {"ok": True, "planting": planting_for_user(row_to_dict(row))}
    finally:
        conn.close()


@mcp.tool
def list_plantings(
    status: OptionalStatus = None,
    plant_name: OptionalPlantName = None,
) -> dict[str, Any]:
    """Show plantings. You can filter by status or plant name."""
    if status is not None and status not in _STATUSES:
        return _err("bad_status", status=status, hint=_STATUS_HINT)
    conn = _db()
    try:
        rows = db_list_plantings(conn, status=status, slug=plant_name)
        return {
            "ok": True,
            "n": len(rows),
            "plantings": [planting_for_user(row_to_dict(r)) for r in rows],
        }
    finally:
        conn.close()


@mcp.tool
def update_planting(
    id: PlantingId,
    variety: Variety = None,
    planted_on: OptionalPlantedOn = None,
    quantity: Quantity = None,
    bed: Bed = None,
    status: OptionalStatus = None,
    notes: Notes = None,
    harvested_on: HarvestedOn = None,
) -> dict[str, Any]:
    """Update an existing planting. Only fill in the fields you want to change."""
    if status is not None and status not in _STATUSES:
        return _err("bad_status", status=status, hint=_STATUS_HINT)
    planted_iso = None
    if planted_on is not None:
        planted = _parse_date_arg(planted_on, "planted_on")
        if isinstance(planted, dict):
            return planted
        planted_iso = planted.isoformat()
    harvested_iso = None
    if harvested_on is not None:
        harvested = _parse_date_arg(harvested_on, "harvested_on")
        if isinstance(harvested, dict):
            return harvested
        harvested_iso = harvested.isoformat()
    conn = _db()
    try:
        row = db_update_planting(
            conn,
            id,
            {
                "variety": variety,
                "planted_on": planted_iso,
                "quantity": quantity,
                "bed": bed,
                "status": status,
                "notes": notes,
                "harvested_on": harvested_iso,
            },
        )
        if row is None:
            return _err("not_found", id=id, hint="Use list_plantings to see valid ids.")
        return {"ok": True, "planting": planting_for_user(row_to_dict(row))}
    finally:
        conn.close()


@mcp.tool
def get_forecast(forecast_days: ForecastDays = 7) -> dict[str, Any]:
    """Daily low and high forecast for the garden, in Fahrenheit."""
    try:
        cfg = load_config()
    except ConfigMissingError:
        return _need_setup()
    try:
        days = fetch_forecast(
            latitude=cfg.location.latitude,
            longitude=cfg.location.longitude,
            timezone=cfg.location.timezone,
            forecast_days=forecast_days,
        )
    except WeatherError as exc:
        return _err("weather", detail=str(exc))
    return {
        "ok": True,
        "source": "forecast",
        "latitude": cfg.location.latitude,
        "longitude": cfg.location.longitude,
        "days": forecast_for_user(days),
    }


@mcp.tool
def frost_check(
    forecast_days: ForecastDays = 7,
    start_date: StartDate = None,
    end_date: EndDate = None,
) -> dict[str, Any]:
    """Flag frost nights and plantings that could be hurt. Uses the forecast unless you give a past date range."""
    try:
        cfg = load_config()
    except ConfigMissingError:
        return _need_setup()
    if (start_date is None) != (end_date is None):
        return _err(
            "need_both_dates",
            hint="To look up past weather, fill in both start date and end date. Leave both blank to use the forecast.",
        )
    if start_date:
        start = _parse_date_arg(start_date, "start_date")
        if isinstance(start, dict):
            return start
        end = _parse_date_arg(end_date or "", "end_date")
        if isinstance(end, dict):
            return end
        source = "archive"
        try:
            days = fetch_archive(
                latitude=cfg.location.latitude,
                longitude=cfg.location.longitude,
                timezone=cfg.location.timezone,
                start_date=start.isoformat(),
                end_date=end.isoformat(),
            )
        except WeatherError as exc:
            return _err("weather", detail=str(exc))
    else:
        source = "forecast"
        try:
            days = fetch_forecast(
                latitude=cfg.location.latitude,
                longitude=cfg.location.longitude,
                timezone=cfg.location.timezone,
                forecast_days=forecast_days,
            )
        except WeatherError as exc:
            return _err("weather", detail=str(exc))
    conn = _db()
    try:
        plantings = [row_to_dict(r) for r in plantings_for_frost(conn)]
    finally:
        conn.close()
    result = evaluate_frost(
        days, plantings, cfg.frost.threshold_c, source=source
    )
    out = frost_for_user(result, plantings)
    out["latitude"] = cfg.location.latitude
    out["longitude"] = cfg.location.longitude
    return out


@mcp.tool
def planting_window(plant_name: PlantName, year: Year = None) -> dict[str, Any]:
    """Suggested spring and fall planting dates from average frost dates."""
    try:
        cfg = load_config()
    except ConfigMissingError:
        return _need_setup()
    year = year or date.today().year
    conn = _db()
    try:
        plant = get_plant(conn, plant_name)
    finally:
        conn.close()
    if plant is None:
        return _unknown_plant(plant_name)
    raw = compute_window(
        slug=plant["slug"],
        name=plant["name"],
        hardiness=plant["hardiness"],
        days_to_maturity=plant["days_to_maturity"],
        spring_offset_days=plant["spring_offset_days"],
        fall_offset_days=plant["fall_offset_days"],
        last_spring=cfg.last_spring_date(year),
        first_fall=cfg.first_fall_date(year),
        year=year,
    )
    return {
        "ok": True,
        "plant_name": raw["name"],
        "hardiness": raw["hardiness"],
        "year": raw["year"],
        "days_to_maturity": raw["days_to_maturity"],
        "last_spring_frost": raw["last_spring"],
        "first_fall_frost": raw["first_fall"],
        "plant_in_spring": raw["spring_plant"],
        "last_fall_planting": raw["fall_last_plant"],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
