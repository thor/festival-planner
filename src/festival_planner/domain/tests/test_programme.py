import datetime

import pytest
from pydantic import ValidationError

from festival_planner.domain.programme import (
    Event,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
    title_key,
    venue_name_key,
)

from .builders import at


def screening(*events: Event) -> Screening:
    return Screening(
        id=ScreeningId("s"),
        programme_entry_id=ProgrammeEntryId("e"),
        venue_id=VenueId("v"),
        start_time=at("14:00"),
        end_time=at("16:00"),
        events=events,
    )


def test_event_needs_both_times_or_neither():
    with pytest.raises(ValueError):
        Event(description="Panel", start_time=at("16:00"))
    assert not Event(description="Q&A").is_separately_timed
    assert Event(
        description="Panel", start_time=at("16:00"), end_time=at("17:00")
    ).is_separately_timed


def test_screening_ends_at_its_end_time_by_default():
    panel = Event(description="Panel", start_time=at("16:15"), end_time=at("17:00"))
    assert screening(panel).ends_at(include_events=False) == at("16:00")


def test_separately_timed_events_extend_the_screening_when_included():
    panel = Event(description="Panel", start_time=at("16:15"), end_time=at("17:00"))
    assert screening(panel).ends_at(include_events=True) == at("17:00")
    assert screening(Event(description="Q&A")).ends_at(include_events=True) == at(
        "16:00"
    )


def test_screening_starts_at_its_start_time_by_default():
    ceremony = Event(
        description="Ceremony", start_time=at("13:30"), end_time=at("13:55")
    )
    assert screening(ceremony).starts_at(include_events=False) == at("14:00")


def test_earlier_separately_timed_events_start_the_screening_when_included():
    ceremony = Event(
        description="Ceremony", start_time=at("13:30"), end_time=at("13:55")
    )
    assert screening(ceremony).starts_at(include_events=True) == at("13:30")
    assert screening(Event(description="Q&A")).starts_at(include_events=True) == at(
        "14:00"
    )


def test_event_cannot_end_before_it_starts():
    with pytest.raises(ValueError):
        Event(description="Panel", start_time=at("17:00"), end_time=at("16:00"))


def test_screening_cannot_end_before_it_starts():
    with pytest.raises(ValueError):
        Screening(
            id=ScreeningId("s"),
            programme_entry_id=ProgrammeEntryId("e"),
            venue_id=VenueId("v"),
            start_time=at("16:00"),
            end_time=at("14:00"),
        )


def test_screening_rejects_naive_times():
    with pytest.raises(ValidationError):
        Screening(
            id=ScreeningId("s"),
            programme_entry_id=ProgrammeEntryId("e"),
            venue_id=VenueId("A"),
            start_time=datetime.datetime(2025, 11, 8, 18, 0),
            end_time=datetime.datetime(2025, 11, 8, 20, 0),
        )


def test_event_rejects_naive_times():
    with pytest.raises(ValidationError):
        Event(
            description="Q&A",
            start_time=datetime.datetime(2025, 11, 8, 20, 0),
            end_time=datetime.datetime(2025, 11, 8, 21, 0),
        )


def test_times_in_different_zones_compare_as_instants():
    utc = at("17:00").astimezone(datetime.UTC)
    assert utc == at("18:00") - datetime.timedelta(hours=1)


def test_title_key_ignores_case_width_and_spacing():
    assert title_key("  Fallen  Leaves ") == title_key("fallen leaves")
    assert title_key("Ｆａｌｌｅｎ") == title_key("fallen")


def test_venue_is_called_by_its_name_or_any_alias_ignoring_case():
    vika = Venue(id=VenueId("v"), name="Vika", aliases=frozenset({"Vika Kino"}))
    assert vika.is_called("VIKA") and vika.is_called("vika  kino")
    assert not vika.is_called("Vega")
    assert venue_name_key(" Vika  Kino ") == "vika kino"
