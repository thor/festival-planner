import datetime

import pytest
from pydantic import ValidationError

from festival_planner.domain.festival import Festival


def festival(**overrides) -> Festival:
    fields = {
        "id": "f",
        "slug": "films-from-the-south-2025",
        "name": "Films from the South 2025",
        "start_date": datetime.date(2025, 11, 6),
        "end_date": datetime.date(2025, 11, 16),
        "time_zone": "Europe/Oslo",
    }
    return Festival(**(fields | overrides))


def test_festival_cannot_end_before_it_starts():
    with pytest.raises(ValidationError, match="cannot end before it starts"):
        festival(end_date=datetime.date(2025, 11, 5))


def test_slug_must_be_lowercase_words_joined_by_hyphens():
    with pytest.raises(ValidationError):
        festival(slug="Films From The South")


def test_festival_time_zone_must_be_known():
    with pytest.raises(ValidationError, match="Unknown time zone"):
        festival(time_zone="Mars/Olympus")


def test_local_date():
    instant = datetime.datetime(2025, 11, 8, 23, 30, tzinfo=datetime.UTC)
    assert festival().local_date(instant) == datetime.date(2025, 11, 9)
