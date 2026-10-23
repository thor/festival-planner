import datetime

import pytest
from pydantic import ValidationError

from festival_planner.domain.planning import (
    Comparison,
    PlanningInputs,
    Preferences,
    Ticket,
    days_between,
)
from festival_planner.domain.programme import ProgrammeEntryId, ScreeningId, VenueId

DAY = datetime.date(2025, 11, 8)
ONE_DAY = datetime.timedelta(days=1)


def test_venue_buffer_overrides_general_buffer():
    preferences = Preferences(
        buffer_minutes=15, venue_buffer_minutes={VenueId("A"): 25}
    )
    assert preferences.buffer_for(VenueId("A")) == 25
    assert preferences.buffer_for(VenueId("B")) == 15


def test_days_may_have_gaps():
    preferences = Preferences(days=(DAY + 2 * ONE_DAY, DAY))
    assert preferences.days == (DAY, DAY + 2 * ONE_DAY)
    assert preferences.covers(DAY) and preferences.covers(DAY + 2 * ONE_DAY)
    assert not preferences.covers(DAY + ONE_DAY)


def test_no_days_means_every_day():
    assert Preferences().covers(DAY + 365 * ONE_DAY)
    with pytest.raises(ValidationError):
        Preferences(days=())


def test_days_between_includes_both_ends():
    assert days_between(DAY, DAY + 2 * ONE_DAY) == (
        DAY,
        DAY + ONE_DAY,
        DAY + 2 * ONE_DAY,
    )


def test_preferences_do_not_alias_the_mappings_they_are_given():
    weights = {ProgrammeEntryId("a"): 1.0}
    preferences = Preferences(programme_entry_weights=weights)
    weights[ProgrammeEntryId("a")] = 2.0
    assert preferences.programme_entry_weights[ProgrammeEntryId("a")] == 1.0


def test_a_comparison_needs_two_entries():
    with pytest.raises(ValidationError):
        Comparison(preferred=ProgrammeEntryId("a"), other=ProgrammeEntryId("a"))


def test_one_comparison_per_pair():
    with pytest.raises(ValidationError):
        Preferences(
            comparisons=(
                Comparison(
                    preferred=ProgrammeEntryId("a"), other=ProgrammeEntryId("b")
                ),
                Comparison(
                    preferred=ProgrammeEntryId("b"), other=ProgrammeEntryId("a")
                ),
            )
        )


def test_comparisons_are_kept_in_a_stable_order():
    one = Preferences(
        comparisons=(
            Comparison(preferred=ProgrammeEntryId("c"), other=ProgrammeEntryId("d")),
            Comparison(preferred=ProgrammeEntryId("a"), other=ProgrammeEntryId("b")),
        )
    )
    other = Preferences(
        comparisons=(
            Comparison(preferred=ProgrammeEntryId("a"), other=ProgrammeEntryId("b")),
            Comparison(preferred=ProgrammeEntryId("c"), other=ProgrammeEntryId("d")),
        )
    )
    assert one == other


def test_preferences_round_trip_through_json():
    preferences = Preferences(
        year_weights={2025: 0.2},
        venue_buffer_minutes={VenueId("v"): 5},
        comparisons=(
            Comparison(preferred=ProgrammeEntryId("a"), other=ProgrammeEntryId("b")),
        ),
    )
    assert Preferences.model_validate_json(preferences.model_dump_json()) == preferences


def test_empty_planning_inputs_have_default_preferences():
    assert PlanningInputs().preferences == Preferences()
    assert PlanningInputs().screening_commitments == frozenset()


def test_tickets_are_neither_exchangeable_nor_refundable_by_default():
    ticket = Ticket(screening_id=ScreeningId("s"))
    assert (ticket.exchangeable, ticket.refundable) == (False, False)


def test_a_negative_comparison_weight_is_rejected():
    with pytest.raises(ValidationError):
        Preferences(comparison_weight=-0.1)
