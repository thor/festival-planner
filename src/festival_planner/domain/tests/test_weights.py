from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event
from festival_planner.domain.solving import DEFAULT_WEIGHT, screening_weight
from festival_planner.domain.tests.builders import at, entry, screening


def test_default_weight():
    assert (
        screening_weight(screening("s", "14:00", "16:00"), entry("s"), Preferences())
        == DEFAULT_WEIGHT
    )


def test_programme_entry_weight_replaces_default():
    preferences = Preferences(programme_entry_weights={"s": 0.5})
    assert (
        screening_weight(screening("s", "14:00", "16:00"), entry("s"), preferences)
        == 0.5
    )


def test_screening_weight_beats_programme_entry_weight():
    preferences = Preferences(
        programme_entry_weights={"s": 0.5}, screening_weights={"s": 2.0}
    )
    assert (
        screening_weight(screening("s", "14:00", "16:00"), entry("s"), preferences)
        == 2.0
    )


def test_year_weight_is_added():
    preferences = Preferences(year_weights={1960: 0.3})
    assert (
        screening_weight(
            screening("s", "14:00", "16:00"), entry("s", year=1960), preferences
        )
        == DEFAULT_WEIGHT + 0.3
    )


def test_no_year_means_no_year_weight():
    preferences = Preferences(year_weights={1960: 0.3})
    assert (
        screening_weight(screening("s", "14:00", "16:00"), entry("s"), preferences)
        == DEFAULT_WEIGHT
    )


def test_event_weight_applies_to_screenings_with_events():
    preferences = Preferences(event_weight=0.5)
    talk = Event("Director Q&A")
    assert (
        screening_weight(
            screening("s", "14:00", "16:00", events=(talk,)), entry("s"), preferences
        )
        == DEFAULT_WEIGHT + 0.5
    )
    assert (
        screening_weight(screening("t", "14:00", "16:00"), entry("t"), preferences)
        == DEFAULT_WEIGHT
    )


def test_separately_timed_event_also_counts():
    preferences = Preferences(event_weight=0.5)
    panel = Event("Panel", at("16:15"), at("17:00"))
    assert (
        screening_weight(
            screening("s", "14:00", "16:00", events=(panel,)), entry("s"), preferences
        )
        == DEFAULT_WEIGHT + 0.5
    )


def test_weights_combine_and_may_be_negative():
    preferences = Preferences(
        programme_entry_weights={"s": -1.0}, year_weights={2025: -0.2}, event_weight=0.5
    )
    weight = screening_weight(
        screening("s", "14:00", "16:00", events=(Event("Q&A"),)),
        entry("s", year=2025),
        preferences,
    )
    assert weight == -1.0 - 0.2 + 0.5
