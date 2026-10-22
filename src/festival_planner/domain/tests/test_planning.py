import datetime

from festival_planner.domain.planning import Preferences

DAY = datetime.date(2025, 11, 8)
ONE_DAY = datetime.timedelta(days=1)


def test_venue_buffer_overrides_general_buffer():
    preferences = Preferences(buffer_minutes=15, venue_buffer_minutes={"A": 25})
    assert preferences.buffer_for("A") == 25
    assert preferences.buffer_for("B") == 15


def test_date_range_is_inclusive():
    preferences = Preferences(start_date=DAY, end_date=DAY)
    assert preferences.covers(DAY)
    assert not preferences.covers(DAY - ONE_DAY)
    assert not preferences.covers(DAY + ONE_DAY)


def test_date_range_may_be_open_ended():
    assert Preferences(start_date=DAY).covers(DAY + 365 * ONE_DAY)
    assert Preferences(end_date=DAY).covers(DAY - 365 * ONE_DAY)
    assert Preferences().covers(DAY)
