import datetime

import pytest
from pydantic import ValidationError

from festival_planner.domain.planning import (
    Comparison,
    PlanningInputs,
    Preferences,
    Ticket,
)

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


def test_preferences_do_not_alias_the_mappings_they_are_given():
    weights = {"a": 1.0}
    preferences = Preferences(programme_entry_weights=weights)
    weights["a"] = 2.0
    assert preferences.programme_entry_weights["a"] == 1.0


def test_a_comparison_needs_two_entries():
    with pytest.raises(ValidationError):
        Comparison(preferred="a", other="a")


def test_one_comparison_per_pair():
    with pytest.raises(ValidationError):
        Preferences(
            comparisons=(
                Comparison(preferred="a", other="b"),
                Comparison(preferred="b", other="a"),
            )
        )


def test_comparisons_are_kept_in_a_stable_order():
    one = Preferences(
        comparisons=(
            Comparison(preferred="c", other="d"),
            Comparison(preferred="a", other="b"),
        )
    )
    other = Preferences(
        comparisons=(
            Comparison(preferred="a", other="b"),
            Comparison(preferred="c", other="d"),
        )
    )
    assert one == other


def test_preferences_round_trip_through_json():
    preferences = Preferences(
        year_weights={2025: 0.2},
        venue_buffer_minutes={"v": 5},
        comparisons=(Comparison(preferred="a", other="b"),),
    )
    assert Preferences.model_validate_json(preferences.model_dump_json()) == preferences


def test_empty_planning_inputs_have_default_preferences():
    assert PlanningInputs().preferences == Preferences()
    assert PlanningInputs().screening_commitments == frozenset()


def test_tickets_are_neither_exchangeable_nor_refundable_by_default():
    ticket = Ticket(screening_id="s")
    assert (ticket.exchangeable, ticket.refundable) == (False, False)
