from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from garden_planner.config import project_root
from garden_planner.db import get_plant, insert_planting, list_plantings


def layout_path() -> Path:
    return project_root() / "data" / "layout.json"


def load_layout_file(path: Path | None = None) -> dict[str, Any]:
    file = path or layout_path()
    if not file.is_file():
        return {"planted_on": None, "plantings": []}
    raw = json.loads(file.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return {"planted_on": None, "plantings": raw}
    return {
        "planted_on": raw.get("planted_on"),
        "plantings": list(raw.get("plantings") or []),
    }


def import_layout(conn, items: list[dict[str, Any]] | None = None, planted_on: str | None = None) -> dict[str, int]:
    """Insert layout rows that are not already in the log."""
    bundled = load_layout_file()
    rows = items if items is not None else bundled["plantings"]
    default_date = planted_on or bundled.get("planted_on")
    existing = {
        (
            row["plant"],
            row["variety"] or "",
            row["bed"] or "",
            row["planted_on"],
        )
        for row in list_plantings(conn)
    }
    added = 0
    skipped = 0
    for item in rows:
        plant = get_plant(conn, item["plant_name"])
        if plant is None:
            raise ValueError(f"unknown plant in layout: {item['plant_name']}")
        date_on = item.get("planted_on") or default_date
        if not date_on:
            raise ValueError("each planting needs planted_on")
        key = (
            plant["name"],
            item.get("variety") or "",
            item.get("bed") or "",
            date_on,
        )
        if key in existing:
            skipped += 1
            continue
        insert_planting(
            conn,
            plant_id=plant["id"],
            planted_on=date_on,
            variety=item.get("variety"),
            quantity=item.get("quantity"),
            bed=item.get("bed"),
            status=item.get("status") or "planted",
            notes=item.get("notes"),
        )
        existing.add(key)
        added += 1
    return {"added": added, "skipped": skipped, "n": len(rows)}
