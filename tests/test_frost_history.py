import pytest

from garden_planner.frost import evaluate_frost
from garden_planner.weather import WeatherError, fetch_archive

CHICAGO_LAT = 41.88
CHICAGO_LON = -87.63
START = "2021-04-20"
END = "2021-04-21"


@pytest.mark.network
def test_chicago_april_2021_freeze_caught():
    try:
        days = fetch_archive(
            latitude=CHICAGO_LAT,
            longitude=CHICAGO_LON,
            timezone="America/Chicago",
            start_date=START,
            end_date=END,
        )
    except WeatherError as exc:
        pytest.skip(f"open-meteo archive unavailable: {exc}")

    mins = [d["tmin_c"] for d in days if d["tmin_c"] is not None]
    assert mins, "archive returned no daily mins"
    assert min(mins) <= 0.0

    plantings = [
        {"id": 1, "slug": "tomato", "min_temp_c": 0.0},
        {"id": 2, "slug": "kale", "min_temp_c": -9.0},
    ]
    out = evaluate_frost(days, plantings, 0.0, source="archive")
    assert out["frost_nights"], "logic missed a documented freeze night"
    tomato_hits = [r for r in out["at_risk"] if r["slug"] == "tomato"]
    kale_hits = [r for r in out["at_risk"] if r["slug"] == "kale"]
    assert tomato_hits
    # Light/moderate freeze should flag tomato; kale only if tmin <= -9
    if min(mins) > -9.0:
        assert kale_hits == []
