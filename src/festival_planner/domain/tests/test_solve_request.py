import datetime

import pytest
from pydantic import ValidationError

from festival_planner.domain.solving import SolveRequest
from festival_planner.domain.tests.builders import entry, request, screening


def with_venues(req: SolveRequest, venues) -> SolveRequest:
    return SolveRequest(**{**dict(req), "venues": venues})


def test_duplicate_screening_ids_are_rejected():
    with pytest.raises(ValueError, match="'a'"):
        request(
            screening("a", "14:00", "16:00"),
            screening("a", "18:00", "20:00"),
            entries=(entry("a"),),
        )


def test_duplicate_programme_entry_ids_are_rejected():
    with pytest.raises(ValueError, match="'a'"):
        request(screening("a", "14:00", "16:00"), entries=(entry("a"), entry("a")))


def test_duplicate_venue_ids_are_rejected():
    req = request(screening("a", "14:00", "16:00"))
    with pytest.raises(ValueError, match="'A'"):
        with_venues(req, req.venues * 2)


def test_unknown_programme_entry_is_rejected_naming_both_ids():
    with pytest.raises(ValueError, match="'a'.*'e'"):
        request(
            screening("a", "14:00", "16:00", entry_id="e"), entries=(entry("other"),)
        )


def test_unknown_venue_is_rejected_naming_both_ids():
    req = request(screening("a", "14:00", "16:00"))
    with pytest.raises(ValueError, match="'a'.*'A'"):
        with_venues(req, ())


def test_unknown_fields_are_rejected():
    with pytest.raises(ValueError, match="surprise"):
        SolveRequest.model_validate(
            {
                "venues": (),
                "programme_entries": (),
                "screenings": (),
                "time_zone": "Europe/Oslo",
                "surprise": 1,
            }
        )


def test_unknown_time_zone_is_rejected():
    with pytest.raises(ValidationError, match="Unknown time zone"):
        request(screening("s", "18:00", "20:00"), time_zone="Mars/Olympus")


def test_local_date_uses_the_festival_time_zone():
    # 23:30 UTC on 8 Nov is 00:30 on 9 Nov in Oslo.
    instant = datetime.datetime(2025, 11, 8, 23, 30, tzinfo=datetime.UTC)
    assert request(time_zone="Europe/Oslo").local_date(instant) == datetime.date(
        2025, 11, 9
    )
