from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from garden_planner.config import db_path

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS plants (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  min_temp_c REAL NOT NULL,
  hardiness TEXT NOT NULL CHECK (hardiness IN ('tender', 'half-hardy', 'hardy')),
  days_to_maturity INTEGER,
  spring_offset_days INTEGER NOT NULL DEFAULT 0,
  fall_offset_days INTEGER NOT NULL DEFAULT 0,
  notes TEXT
);

CREATE TABLE IF NOT EXISTS plantings (
  id INTEGER PRIMARY KEY,
  plant_id INTEGER NOT NULL REFERENCES plants(id),
  variety TEXT,
  planted_on TEXT NOT NULL,
  quantity INTEGER,
  bed TEXT,
  status TEXT NOT NULL DEFAULT 'planted'
    CHECK (status IN ('planned', 'planted', 'harvested', 'failed')),
  notes TEXT,
  harvested_on TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_plantings_status ON plantings(status);
CREATE INDEX IF NOT EXISTS idx_plantings_plant_id ON plantings(plant_id);
CREATE INDEX IF NOT EXISTS idx_plantings_planted_on ON plantings(planted_on);
"""

# USDA-typical damage thresholds and frost offsets for common vegetables.
PLANTS_SEED: list[tuple[Any, ...]] = [
    ("tomato", "Tomato", 0.0, "tender", 75, 14, 90, "Set out after nights stay above 10C."),
    ("pepper", "Pepper", 2.0, "tender", 80, 21, 95, "Needs warm soil; very frost-tender."),
    ("basil", "Basil", 5.0, "tender", 60, 14, 70, "Chills below ~10C; frost kills."),
    ("bean", "Bean", 0.0, "tender", 55, 7, 65, "Direct sow after last frost."),
    ("corn", "Corn", 0.0, "tender", 80, 10, 90, "Warm-season; frost ends ears."),
    ("zucchini", "Zucchini", 0.0, "tender", 50, 10, 60, "Summer squash; frost-tender."),
    ("cucumber", "Cucumber", 0.0, "tender", 55, 14, 65, "Warm soil; vine killed by frost."),
    ("lettuce", "Lettuce", -2.0, "half-hardy", 45, -14, 30, "Light frost ok; bolt in heat."),
    ("spinach", "Spinach", -7.0, "hardy", 40, -28, 35, "Sow well before last frost."),
    ("kale", "Kale", -9.0, "hardy", 55, -21, 40, "Sweeter after frost."),
    ("broccoli", "Broccoli", -4.0, "hardy", 70, -7, 80, "Prefers cool weather."),
    ("cabbage", "Cabbage", -4.0, "hardy", 80, -14, 90, "Tolerates several degrees of frost."),
    ("carrot", "Carrot", -4.0, "hardy", 70, -14, 80, "Can overwinter with mulch."),
    ("pea", "Pea", -4.0, "hardy", 60, -35, 70, "Sow as soon as soil can be worked."),
    ("potato", "Potato", -1.0, "half-hardy", 90, 0, 100, "Foliage dies at light frost."),
    ("radish", "Radish", -2.0, "hardy", 28, -21, 25, "Fast cool-season crop."),
            ("onion", "Onion", -7.0, "hardy", 100, -14, 90, "Keep away from beans; prefers cool weather."),
    ("marigold", "Marigold", 0.0, "tender", 50, 7, 50, "Deters aphids, flea beetles, and bean beetles."),
    ("chamomile", "Chamomile", -4.0, "hardy", 60, -7, 40, "Plant physician; self-seeds. Improves peppers and onions."),
    ("nasturtium", "Nasturtium", 0.0, "tender", 50, 7, 45, "Sacrificial trap crop; edible flowers."),
    ("thyme", "Thyme", -10.0, "hardy", 90, 0, 0, "Perennial kitchen herb."),
    ("dill", "Dill", -2.0, "half-hardy", 40, 0, 40, "Keep away from tomatoes; it can stunt them."),
    ("rosemary", "Rosemary", -4.0, "half-hardy", 90, 14, 0, "Perennial; repels bean beetles. Protect in hard freezes."),
    ("oregano", "Oregano", -7.0, "hardy", 80, 0, 0, "Perennial kitchen herb."),
    ("borage", "Borage", -2.0, "hardy", 50, 0, 40, "Deters hornworm; attracts pollinators."),
    ("lavender", "Lavender", -12.0, "hardy", 90, 0, 0, "Perennial; boosts bee pollination. Deer resistant."),
    ("mint", "Mint", -10.0, "hardy", 60, 0, 0, "Invasive. Isolated pot only."),
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.executemany(
        """
        INSERT OR IGNORE INTO plants (
          slug, name, min_temp_c, hardiness, days_to_maturity,
          spring_offset_days, fall_offset_days, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        PLANTS_SEED,
    )
    conn.commit()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_plant(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    key = slug.strip().lower()
    if not key:
        return None
    return conn.execute(
        "SELECT * FROM plants WHERE slug = ? OR lower(name) = ?",
        (key, key),
    ).fetchone()


def list_plants(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM plants ORDER BY slug"))


def insert_planting(
    conn: sqlite3.Connection,
    *,
    plant_id: int,
    planted_on: str,
    variety: str | None = None,
    quantity: int | None = None,
    bed: str | None = None,
    status: str = "planted",
    notes: str | None = None,
) -> sqlite3.Row:
    now = utcnow_iso()
    cur = conn.execute(
        """
        INSERT INTO plantings (
          plant_id, variety, planted_on, quantity, bed, status, notes,
          harvested_on, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (plant_id, variety, planted_on, quantity, bed, status, notes, now, now),
    )
    conn.commit()
    return conn.execute(
        _PLANTING_SELECT + " WHERE p.id = ?", (cur.lastrowid,)
    ).fetchone()


_PLANTING_SELECT = """
SELECT
  p.id, p.plant_id, pl.slug, pl.name AS plant, pl.min_temp_c, pl.hardiness,
  p.variety, p.planted_on, p.quantity, p.bed, p.status, p.notes, p.harvested_on,
  p.created_at, p.updated_at
FROM plantings p
JOIN plants pl ON pl.id = p.plant_id
"""


def list_plantings(
    conn: sqlite3.Connection,
    *,
    status: str | None = None,
    slug: str | None = None,
) -> list[sqlite3.Row]:
    clauses: list[str] = []
    args: list[Any] = []
    if status:
        clauses.append("p.status = ?")
        args.append(status)
    if slug:
        key = slug.strip().lower()
        clauses.append("(pl.slug = ? OR lower(pl.name) = ?)")
        args.extend([key, key])
    sql = _PLANTING_SELECT
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY p.planted_on DESC, p.id DESC"
    return list(conn.execute(sql, args))


def get_planting(conn: sqlite3.Connection, planting_id: int) -> sqlite3.Row | None:
    return conn.execute(_PLANTING_SELECT + " WHERE p.id = ?", (planting_id,)).fetchone()


ALLOWED_UPDATE = {
    "plant_id",
    "variety",
    "planted_on",
    "quantity",
    "bed",
    "status",
    "notes",
    "harvested_on",
}


def update_planting(
    conn: sqlite3.Connection,
    planting_id: int,
    fields: dict[str, Any],
    *,
    allow_null: bool = False,
) -> sqlite3.Row | None:
    if allow_null:
        patch = {k: v for k, v in fields.items() if k in ALLOWED_UPDATE}
    else:
        patch = {k: v for k, v in fields.items() if k in ALLOWED_UPDATE and v is not None}
    if not patch:
        return get_planting(conn, planting_id)
    cols = ", ".join(f"{k} = ?" for k in patch)
    vals = list(patch.values()) + [utcnow_iso(), planting_id]
    conn.execute(
        f"UPDATE plantings SET {cols}, updated_at = ? WHERE id = ?",
        vals,
    )
    conn.commit()
    return get_planting(conn, planting_id)


def plantings_for_frost(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            _PLANTING_SELECT + " WHERE p.status IN ('planned', 'planted') ORDER BY p.id"
        )
    )


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}
