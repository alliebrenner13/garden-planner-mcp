from garden_planner.frost import evaluate_frost, planting_window
from datetime import date


def test_no_frost_empty_plantings():
    days = [{"date": "2026-05-01", "tmin_c": 8.0}]
    out = evaluate_frost(days, [], 0.0, source="test")
    assert out["ok"] is True
    assert out["frost_nights"] == []
    assert out["at_risk"] == []
    assert out["n_plantings"] == 0


def test_light_frost_flags_garden_and_tender_not_hardy():
    days = [{"date": "2026-04-16", "tmin_c": 0.0}]
    plantings = [
        {"id": 1, "slug": "tomato", "min_temp_c": 0.0},
        {"id": 2, "slug": "kale", "min_temp_c": -9.0},
    ]
    out = evaluate_frost(days, plantings, 0.0, source="test")
    assert out["frost_nights"] == [{"date": "2026-04-16", "tmin_c": 0.0}]
    slugs = [r["slug"] for r in out["at_risk"]]
    assert slugs == ["tomato"]
    assert out["at_risk"][0]["threshold_c"] == 0.0


def test_hard_freeze_flags_hardy_and_tender():
    days = [{"date": "2026-01-20", "tmin_c": -10.0}]
    plantings = [
        {"id": 1, "slug": "tomato", "min_temp_c": 0.0},
        {"id": 2, "slug": "kale", "min_temp_c": -9.0},
    ]
    out = evaluate_frost(days, plantings, 0.0, source="test")
    assert len(out["frost_nights"]) == 1
    assert {r["slug"] for r in out["at_risk"]} == {"tomato", "kale"}


def test_half_hardy_survives_light_frost():
    days = [{"date": "2026-04-16", "tmin_c": -1.0}]
    plantings = [{"id": 3, "slug": "lettuce", "min_temp_c": -2.0}]
    out = evaluate_frost(days, plantings, 0.0, source="test")
    assert out["frost_nights"]
    assert out["at_risk"] == []


def test_skips_null_tmin():
    days = [{"date": "2026-04-16", "tmin_c": None}]
    plantings = [{"id": 1, "slug": "tomato", "min_temp_c": 0.0}]
    out = evaluate_frost(days, plantings, 0.0, source="test")
    assert out["frost_nights"] == []
    assert out["at_risk"] == []


def test_planting_window_offsets():
    out = planting_window(
        slug="tomato",
        name="Tomato",
        hardiness="tender",
        days_to_maturity=75,
        spring_offset_days=14,
        fall_offset_days=90,
        last_spring=date(2026, 4, 15),
        first_fall=date(2026, 10, 20),
        year=2026,
    )
    assert out["spring_plant"] == "2026-04-29"
    assert out["fall_last_plant"] == "2026-07-22"
    assert out["days_to_maturity"] == 75
