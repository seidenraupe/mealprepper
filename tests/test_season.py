from season import format_season, in_season, parse_months


def test_empty_months_are_year_round():
    assert parse_months("") == []
    assert parse_months(None) == []
    assert in_season([], 1) is True
    assert format_season([]) == "ganzjährig"


def test_all_twelve_months_collapse_to_year_round():
    assert parse_months(list(range(1, 13))) == []


def test_season_ranges_wrap_the_year():
    assert format_season([4, 5, 6]) == "Apr–Jun"
    assert format_season([11, 12, 1, 2, 3]) == "Nov–Mär"
    assert format_season([6, 8]) == "Jun, Aug"
    assert in_season([4, 5, 6], 5) is True
    assert in_season([4, 5, 6], 1) is False


def test_invalid_month_is_rejected():
    try:
        parse_months([0, 4])
    except ValueError as exc:
        assert "1" in str(exc)
    else:
        raise AssertionError("Monat 0 muss scheitern")
