from garden_planner.onboarding import estimate_frost_mmdd
from garden_planner.services import complete_setup, garden_snapshot, setup_status


def test_estimate_frost_mid_latitudes():
    assert estimate_frost_mmdd(38.8) == ("04-15", "10-20")
    assert estimate_frost_mmdd(25) == ("02-15", "12-01")


def test_setup_status_and_snapshot_without_config(tmp_path, monkeypatch):
    monkeypatch.setenv("GARDEN_PLANNER_CONFIG", str(tmp_path / "missing.toml"))
    monkeypatch.setenv("GARDEN_PLANNER_DB", str(tmp_path / "garden.db"))
    status = setup_status()
    assert status["ok"] is True
    assert status["needs_setup"] is True
    assert "Tomato" in status["plants"]
    snap = garden_snapshot()
    assert snap["needs_setup"] is True


def test_complete_setup_writes_private_config(tmp_path, monkeypatch):
    config = tmp_path / "config.toml"
    monkeypatch.setenv("GARDEN_PLANNER_CONFIG", str(config))
    monkeypatch.setenv("GARDEN_PLANNER_DB", str(tmp_path / "garden.db"))
    result = complete_setup(
        {
            "latitude": 40.7,
            "longitude": -74.0,
            "timezone": "America/New_York",
            "place": "Test plot",
            "aspect": "South-facing",
            "sun": "Full sun",
            "last_spring_frost": "4/15/2026",
            "first_fall_frost": "October 20, 2026",
            "frost_threshold_f": 32,
            "plantings": [
                {
                    "plant_name": "Kale",
                    "variety": "Lacinato",
                    "bed": "Front bed",
                    "planted_on": "5/1/26",
                    "quantity": 4,
                    "status": "planted",
                    "notes": "test",
                }
            ],
        }
    )
    assert result["ok"] is True
    assert result.get("needs_setup") is not True
    assert result["place"] == "Test plot"
    assert result["plantings_added"] == 1
    assert config.is_file()
    text = config.read_text(encoding="utf-8")
    assert "40.7" in text
    assert "Test plot" in text
