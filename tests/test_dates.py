from garden_planner.dates import parse_date


def test_iso_and_us_numeric_dates():
    assert parse_date("2026-09-11").isoformat() == "2026-09-11"
    assert parse_date("09-11-2026").isoformat() == "2026-09-11"
    assert parse_date("9/11/26").isoformat() == "2026-09-11"
    assert parse_date("9/11/2026").isoformat() == "2026-09-11"


def test_month_name_dates():
    assert parse_date("September 11, 2026").isoformat() == "2026-09-11"
    assert parse_date("11 Sep 2026").isoformat() == "2026-09-11"


def test_rejects_empty_and_garbage():
    assert parse_date("") is None
    assert parse_date("   ") is None
    assert parse_date("not-a-date") is None
