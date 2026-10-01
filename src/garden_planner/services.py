from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any

from garden_planner.config import (
    AppConfig,
    FrostClimate,
    Location,
    PlotNotes,
    config_exists,
    load_config,
    save_config,
)
from garden_planner.dates import DATE_HINT, parse_date
from garden_planner.db import (
    PLANTS_SEED,
    connect,
    get_plant,
    init_db,
    insert_planting,
    list_plantings as db_list_plantings,
    list_plants,
    plantings_for_frost,
    row_to_dict,
    update_planting as db_update_planting,
)
from garden_planner.frost import evaluate_frost, planting_window as compute_window
from garden_planner.geocode import search_places as geocode_search
from garden_planner.onboarding import estimate_frost_mmdd
from garden_planner.present import forecast_for_user, frost_for_user, plant_for_user, planting_for_user
from garden_planner.units import c_to_f, f_to_c
from garden_planner.weather import WeatherError, fetch_archive, fetch_forecast

STATUSES = {"planned", "planted", "harvested", "failed"}
PLANT_EXAMPLES = ", ".join(name for _slug, name, *_rest in PLANTS_SEED)


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
        hint=f"Try a catalog plant such as {PLANT_EXAMPLES}.",
    )


def _blank(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def garden_snapshot() -> dict[str, Any]:
    if not config_exists():
        return {"ok": True, "needs_setup": True}
    cfg = load_config()
    today = date.today()
    last_spring = cfg.last_spring_date(today.year)
    first_fall = cfg.first_fall_date(today.year)
    if today < last_spring:
        season = "late winter"
    elif today < date(today.year, 6, 21):
        season = "spring"
    elif today < date(today.year, 9, 22):
        season = "summer"
    elif today < first_fall:
        season = "early fall"
    else:
        season = "frost season"
    return {
        "ok": True,
        "place": cfg.plot.name or "Garden",
        "aspect": cfg.plot.aspect,
        "sun": cfg.plot.sun,
        "mulch": cfg.plot.mulch,
        "rules": [line for line in cfg.plot.rules.splitlines() if line.strip()],
        "latitude": cfg.location.latitude,
        "longitude": cfg.location.longitude,
        "timezone": cfg.location.timezone,
        "today": today.isoformat(),
        "year": today.year,
        "season": season,
        "last_spring_frost": last_spring.isoformat(),
        "first_fall_frost": first_fall.isoformat(),
        "days_until_fall_frost": (first_fall - today).days,
        "frost_threshold_f": c_to_f(cfg.frost.threshold_c),
    }


def _frost_mmdd(raw: str, field: str) -> str | dict[str, Any]:
    text = raw.strip()
    parsed = parse_date(text)
    if parsed is not None:
        return f"{parsed.month:02d}-{parsed.day:02d}"
    parts = text.replace("/", "-").replace(".", "-").split("-")
    if len(parts) == 2:
        try:
            month, day = int(parts[0]), int(parts[1])
            date(2000, month, day)
            return f"{month:02d}-{day:02d}"
        except ValueError:
            pass
    return _err("bad_date", field=field, input=raw, hint=DATE_HINT)


def update_plot(payload: dict[str, Any]) -> dict[str, Any]:
    if not config_exists():
        return _err("needs_setup", hint="Finish garden setup first.")
    cfg = load_config()
    plot = cfg.plot
    frost = cfg.frost
    name = str(payload.get("place") or payload.get("name") or "").strip()
    if "place" in payload or "name" in payload:
        plot = replace(plot, name=name or plot.name)
    if "aspect" in payload:
        plot = replace(plot, aspect=str(payload.get("aspect") or "").strip())
    if "sun" in payload:
        plot = replace(plot, sun=str(payload.get("sun") or "").strip())
    last_spring = frost.last_spring
    first_fall = frost.first_fall
    threshold_c = frost.threshold_c
    if "last_spring_frost" in payload:
        raw = str(payload.get("last_spring_frost") or "").strip()
        if raw:
            mmdd = _frost_mmdd(raw, "last_spring_frost")
            if isinstance(mmdd, dict):
                return mmdd
            last_spring = mmdd
    if "first_fall_frost" in payload:
        raw = str(payload.get("first_fall_frost") or "").strip()
        if raw:
            mmdd = _frost_mmdd(raw, "first_fall_frost")
            if isinstance(mmdd, dict):
                return mmdd
            first_fall = mmdd
    if "frost_threshold_f" in payload:
        raw = payload.get("frost_threshold_f")
        if raw != "" and raw is not None:
            try:
                threshold_c = f_to_c(float(raw))
            except (TypeError, ValueError):
                return _err("bad_temperature", hint="Garden frost should be a number in Fahrenheit.")
    cfg = replace(
        cfg,
        plot=plot,
        frost=replace(frost, last_spring=last_spring, first_fall=first_fall, threshold_c=threshold_c),
    )
    save_config(cfg)
    return garden_snapshot()


def setup_status() -> dict[str, Any]:
    plants = [name for _slug, name, *_rest in PLANTS_SEED]
    plants.sort()
    return {"ok": True, "needs_setup": not config_exists(), "plants": plants}


def search_places(query: str) -> dict[str, Any]:
    try:
        places = geocode_search(query)
    except WeatherError as exc:
        return _err("geocode", detail=str(exc), hint="Try a city and state, or a ZIP code.")
    if not places:
        return _err("no_places", hint="Try a more specific place name, or enter latitude and longitude.")
    for place in places:
        spring, fall = estimate_frost_mmdd(place["latitude"])
        place["last_spring"] = spring
        place["first_fall"] = fall
    return {"ok": True, "places": places}


def complete_setup(payload: dict[str, Any]) -> dict[str, Any]:
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    timezone = str(payload.get("timezone") or "").strip()
    query = str(payload.get("query") or payload.get("place_query") or "").strip()
    if latitude in (None, "") or longitude in (None, ""):
        if not query:
            return _err("missing_location", hint="Search for a city or ZIP, or enter latitude and longitude.")
        found = search_places(query)
        if not found.get("ok"):
            return found
        pick = found["places"][0]
        latitude = pick["latitude"]
        longitude = pick["longitude"]
        timezone = timezone or pick["timezone"]
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return _err("bad_coordinates", hint="Latitude and longitude should be numbers.")
    if not timezone:
        timezone = "UTC"
    spring, fall = estimate_frost_mmdd(latitude)
    if payload.get("last_spring_frost"):
        parsed = _frost_mmdd(str(payload["last_spring_frost"]), "last_spring_frost")
        if isinstance(parsed, dict):
            return parsed
        spring = parsed
    if payload.get("first_fall_frost"):
        parsed = _frost_mmdd(str(payload["first_fall_frost"]), "first_fall_frost")
        if isinstance(parsed, dict):
            return parsed
        fall = parsed
    threshold_c = 0.0
    if payload.get("frost_threshold_f") not in (None, ""):
        try:
            converted = f_to_c(float(payload["frost_threshold_f"]))
        except (TypeError, ValueError):
            return _err("bad_temperature", hint="Garden frost should be a number in Fahrenheit.")
        if converted is not None:
            threshold_c = converted
    cfg = AppConfig(
        location=Location(latitude=latitude, longitude=longitude, timezone=timezone),
        frost=FrostClimate(last_spring=spring, first_fall=fall, threshold_c=threshold_c),
        plot=PlotNotes(
            name=str(payload.get("place") or payload.get("name") or "Garden").strip() or "Garden",
            aspect=str(payload.get("aspect") or "").strip(),
            sun=str(payload.get("sun") or "").strip(),
            mulch="",
            rules="",
        ),
    )
    save_config(cfg)
    added = 0
    errors: list[str] = []
    for item in payload.get("plantings") or []:
        if not isinstance(item, dict):
            continue
        if not str(item.get("plant_name") or "").strip():
            continue
        result = add_planting(item)
        if result.get("ok"):
            added += 1
        else:
            errors.append(str(result.get("hint") or result.get("error") or "Could not add a planting."))
    snapshot = garden_snapshot()
    snapshot["plantings_added"] = added
    if errors:
        snapshot["planting_warnings"] = errors
    return snapshot


def catalog() -> dict[str, Any]:
    conn = _db()
    try:
        plants = [plant_for_user(row_to_dict(r)) for r in list_plants(conn)]
        plants.sort(key=lambda p: p["name"])
        return {"ok": True, "plants": plants}
    finally:
        conn.close()


def list_log(*, status: str | None = None, plant_name: str | None = None) -> dict[str, Any]:
    status = _blank(status)
    plant_name = _blank(plant_name)
    if status is not None and status not in STATUSES:
        return _err("bad_status", status=status, hint="planned, planted, harvested, or failed")
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


def add_planting(payload: dict[str, Any]) -> dict[str, Any]:
    plant_name = (payload.get("plant_name") or "").strip()
    planted_on = (payload.get("planted_on") or "").strip()
    status = payload.get("status") or "planted"
    if not plant_name:
        return _err("missing_plant", hint="Choose a plant from the catalog.")
    if not planted_on:
        return _err("missing_date", field="planted_on", hint=DATE_HINT)
    if status not in STATUSES:
        return _err("bad_status", status=status)
    planted = _parse_date_arg(planted_on, "planted_on")
    if isinstance(planted, dict):
        return planted
    quantity = payload.get("quantity")
    if quantity == "" or quantity is None:
        quantity = None
    else:
        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return _err("bad_quantity", hint="Quantity should be a whole number.")
    conn = _db()
    try:
        plant = get_plant(conn, plant_name)
        if plant is None:
            return _unknown_plant(plant_name)
        row = insert_planting(
            conn,
            plant_id=plant["id"],
            planted_on=planted.isoformat(),
            variety=_blank(payload.get("variety")),
            quantity=quantity,
            bed=_blank(payload.get("bed")),
            status=status,
            notes=_blank(payload.get("notes")),
        )
        return {"ok": True, "planting": planting_for_user(row_to_dict(row))}
    finally:
        conn.close()


def patch_planting(planting_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if "status" in payload:
        status = _blank(payload.get("status"))
        if status is None or status not in STATUSES:
            return _err("bad_status", status=status, hint="planned, planted, harvested, or failed")
        fields["status"] = status
    if "planted_on" in payload:
        planted_on = _blank(payload.get("planted_on"))
        if planted_on is None:
            return _err("missing_date", field="planted_on", hint=DATE_HINT)
        planted = _parse_date_arg(str(planted_on), "planted_on")
        if isinstance(planted, dict):
            return planted
        fields["planted_on"] = planted.isoformat()
    if "harvested_on" in payload:
        harvested_on = _blank(payload.get("harvested_on"))
        if harvested_on is None:
            fields["harvested_on"] = None
        else:
            harvested = _parse_date_arg(str(harvested_on), "harvested_on")
            if isinstance(harvested, dict):
                return harvested
            fields["harvested_on"] = harvested.isoformat()
    if "quantity" in payload:
        quantity = payload.get("quantity")
        if quantity == "" or quantity is None:
            fields["quantity"] = None
        else:
            try:
                fields["quantity"] = int(quantity)
            except (TypeError, ValueError):
                return _err("bad_quantity", hint="Quantity should be a whole number.")
    if "variety" in payload:
        fields["variety"] = _blank(payload.get("variety"))
    if "bed" in payload:
        fields["bed"] = _blank(payload.get("bed"))
    if "notes" in payload:
        fields["notes"] = _blank(payload.get("notes"))
    conn = _db()
    try:
        if "plant_name" in payload:
            plant_name = str(payload.get("plant_name") or "").strip()
            if not plant_name:
                return _err("missing_plant", hint="Choose a plant from the catalog.")
            plant = get_plant(conn, plant_name)
            if plant is None:
                return _unknown_plant(plant_name)
            fields["plant_id"] = plant["id"]
        row = db_update_planting(conn, planting_id, fields, allow_null=True)
        if row is None:
            return _err("not_found", id=planting_id)
        return {"ok": True, "planting": planting_for_user(row_to_dict(row))}
    finally:
        conn.close()


def forecast(forecast_days: int = 7) -> dict[str, Any]:
    if not config_exists():
        return _err("needs_setup", hint="Finish garden setup first.")
    days_n = max(1, min(16, int(forecast_days)))
    cfg = load_config()
    try:
        days = fetch_forecast(
            latitude=cfg.location.latitude,
            longitude=cfg.location.longitude,
            timezone=cfg.location.timezone,
            forecast_days=days_n,
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


def frost_report(
    *,
    forecast_days: int = 7,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    if not config_exists():
        return _err("needs_setup", hint="Finish garden setup first.")
    cfg = load_config()
    start_date = _blank(start_date)
    end_date = _blank(end_date)
    if (start_date is None) != (end_date is None):
        return _err(
            "need_both_dates",
            hint="To look up past weather, fill in both start date and end date.",
        )
    if start_date:
        start = _parse_date_arg(str(start_date), "start_date")
        if isinstance(start, dict):
            return start
        end = _parse_date_arg(str(end_date), "end_date")
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
        days_n = max(1, min(16, int(forecast_days)))
        try:
            days = fetch_forecast(
                latitude=cfg.location.latitude,
                longitude=cfg.location.longitude,
                timezone=cfg.location.timezone,
                forecast_days=days_n,
            )
        except WeatherError as exc:
            return _err("weather", detail=str(exc))
    conn = _db()
    try:
        plantings = [row_to_dict(r) for r in plantings_for_frost(conn)]
    finally:
        conn.close()
    result = evaluate_frost(days, plantings, cfg.frost.threshold_c, source=source)
    out = frost_for_user(result, plantings)
    out["latitude"] = cfg.location.latitude
    out["longitude"] = cfg.location.longitude
    return out


def window(plant_name: str, year: int | None = None) -> dict[str, Any]:
    if not config_exists():
        return _err("needs_setup", hint="Finish garden setup first.")
    year = year or date.today().year
    cfg = load_config()
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
        "min_temp_f": c_to_f(plant["min_temp_c"]),
    }
