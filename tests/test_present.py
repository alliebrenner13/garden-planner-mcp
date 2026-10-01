import sqlite3

from garden_planner.db import get_plant, init_db
from garden_planner.present import forecast_for_user, frost_for_user, planting_for_user
from garden_planner.units import c_to_f


def test_c_to_f():
    assert c_to_f(0) == 32.0
    assert c_to_f(-9) == 15.8
    assert c_to_f(None) is None


def test_f_to_c():
    from garden_planner.units import f_to_c

    assert f_to_c(32) == 0.0
    assert f_to_c(15.8) == -9.0
    assert f_to_c(None) is None


def test_forecast_and_planting_use_fahrenheit_and_plant_name():
    days = forecast_for_user([{"date": "2026-09-26", "tmin_c": 13.6, "tmax_c": 19.1}])
    assert days == [{"date": "2026-09-26", "low_f": 56.5, "high_f": 66.4}]

    planting = planting_for_user(
        {
            "id": 1,
            "plant": "Kale",
            "variety": None,
            "planted_on": "2026-09-11",
            "quantity": None,
            "bed": None,
            "status": "planted",
            "notes": None,
            "harvested_on": None,
            "hardiness": "hardy",
            "min_temp_c": -9.0,
            "created_at": "2026-09-26T18:17:26+00:00",
            "updated_at": "2026-09-26T18:17:26+00:00",
        }
    )
    assert planting["plant_name"] == "Kale"
    assert planting["min_temp_f"] == 15.8
    assert "min_temp_c" not in planting
    assert "slug" not in planting


def test_frost_for_user_converts_temps():
    result = {
        "ok": True,
        "source": "test",
        "threshold_c": 0.0,
        "frost_nights": [{"date": "2026-04-16", "tmin_c": 0.0}],
        "at_risk": [
            {
                "id": 1,
                "slug": "tomato",
                "date": "2026-04-16",
                "tmin_c": 0.0,
                "threshold_c": 0.0,
            }
        ],
        "n_days": 1,
        "n_plantings": 1,
    }
    plantings = [{"id": 1, "plant": "Tomato", "slug": "tomato"}]
    out = frost_for_user(result, plantings)
    assert out["threshold_f"] == 32.0
    assert out["frost_nights"] == [{"date": "2026-04-16", "low_f": 32.0}]
    assert out["at_risk"][0]["plant_name"] == "Tomato"
    assert out["at_risk"][0]["low_f"] == 32.0


def test_catalog_lists_fahrenheit_plants():
    from garden_planner.services import catalog

    out = catalog()
    names = {p["name"] for p in out["plants"]}
    kale = next(p for p in out["plants"] if p["name"] == "Kale")
    assert "Kale" in names
    assert kale["min_temp_f"] == 15.8


def test_get_plant_accepts_display_name():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    assert get_plant(conn, "Kale")["slug"] == "kale"
    assert get_plant(conn, "kale")["name"] == "Kale"
    assert get_plant(conn, "not-a-plant") is None
    conn.close()
