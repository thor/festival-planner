import datetime

import pytest

from festival_planner.domain.programme import Event, Screening


def at(hhmm: str) -> datetime.datetime:
    return datetime.datetime.combine(
        datetime.date(2025, 11, 8), datetime.time.fromisoformat(hhmm)
    )


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
        Event("Panel", start_time=at("16:00"))
    assert not Event("Q&A").is_separately_timed
    assert Event("Panel", at("16:00"), at("17:00")).is_separately_timed


def test_screening_ends_at_its_end_time_by_default():
    panel = Event("Panel", at("16:15"), at("17:00"))
    assert screening(panel).ends_at(include_events=False) == at("16:00")


def test_separately_timed_events_extend_the_screening_when_included():
    panel = Event("Panel", at("16:15"), at("17:00"))
    assert screening(panel).ends_at(include_events=True) == at("17:00")
    assert screening(Event("Q&A")).ends_at(include_events=True) == at("16:00")
