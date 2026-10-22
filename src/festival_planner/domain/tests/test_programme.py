import datetime

import pytest

from pydantic import ValidationError

from festival_planner.domain.programme import Event, Screening

from .builders import at


def screening(*events: Event) -> Screening:
    return Screening(
        id="s",
        programme_entry_id="e",
        venue_id="v",
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
            id="s",
            programme_entry_id="e",
            venue_id="v",
            start_time=at("16:00"),
            end_time=at("14:00"),
        )


def test_screening_rejects_naive_times():
    with pytest.raises(ValidationError):
        Screening(
            id="s",
            programme_entry_id="e",
            venue_id="A",
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
