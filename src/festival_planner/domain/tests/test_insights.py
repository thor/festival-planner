import pytest

from festival_planner.domain.insights import (
    FlagKind,
    diff,
    flags,
    inferred_seen,
    suggest_comparisons,
)
from festival_planner.domain.planning import (
    Comparison,
    PlanningInputs,
    Preferences,
    Ticket,
)

from .builders import at, entry, request, screening


def withdrawn(s):
    return s.model_copy(update={"withdrawn": True})


def test_diff_lists_added_and_removed_and_the_score_delta():
    req = request(
        screening("a", "10:00", "12:00"),
        screening("b", "14:00", "16:00"),
        screening("c", "18:00", "20:00"),
        preferences=Preferences(buffer_minutes=0, programme_entry_weights={"c": 3.0}),
        active_schedule=frozenset({"a", "b"}),
    )
    result = diff(req, frozenset({"b", "c"}), [Ticket(screening_id="a")])
    assert result.added == frozenset({"c"})
    assert result.removed == frozenset({"a"})
    assert result.score_delta == pytest.approx(2.0)
    assert result.dropped_tickets == frozenset({"a"})


def test_without_an_active_schedule_everything_is_added():
    req = request(screening("a", "10:00", "12:00"))
    result = diff(req, frozenset({"a"}), [])
    assert (result.added, result.removed, result.score_delta) == (
        frozenset({"a"}),
        frozenset(),
        1.0,
    )


def test_flags():
    screenings = [
        withdrawn(screening("gone", "10:00", "12:00")),
        screening("here", "14:00", "16:00"),
    ]
    found = flags(
        screenings,
        PlanningInputs(screening_commitments=frozenset({"gone"})),
        [
            Ticket(screening_id="gone"),
            Ticket(screening_id="here"),
            Ticket(screening_id="elsewhere"),
        ],
        active=frozenset({"gone"}),
    )
    assert [(f.kind, f.target_id) for f in found] == [
        (FlagKind.WITHDRAWN_COMMITMENT, "gone"),
        (FlagKind.WITHDRAWN_TICKET, "gone"),
        (FlagKind.UNSCHEDULED_TICKET, "here"),
        (FlagKind.WITHDRAWN_IN_SCHEDULE, "gone"),
    ]


def test_a_film_commitment_with_only_withdrawn_screenings_is_flagged():
    found = flags(
        [withdrawn(screening("s", "10:00", "12:00", entry_id="e"))],
        PlanningInputs(film_commitments=frozenset({"e"})),
        [],
        active=frozenset(),
    )
    assert [(f.kind, f.target_id) for f in found] == [
        (FlagKind.WITHDRAWN_COMMITMENT, "e")
    ]


def test_suggests_conflicting_pairs_closest_weights_first():
    req = request(
        screening("a", "14:00", "16:00"),
        screening("b", "15:00", "17:00"),
        screening("c", "18:00", "20:00"),
        screening("d", "19:00", "21:00"),
        preferences=Preferences(
            buffer_minutes=0,
            programme_entry_weights={"a": 2.0, "b": 1.0, "c": 1.2, "d": 1.1},
        ),
    )
    suggestions = suggest_comparisons(req, frozenset({"a", "c"}))
    assert [(s.scheduled, s.other) for s in suggestions] == [("c", "d"), ("a", "b")]
    assert suggestions[0].weight_gap == pytest.approx(0.1)


def test_pairs_already_compared_are_not_suggested():
    req = request(
        screening("a", "14:00", "16:00"),
        screening("b", "15:00", "17:00"),
        preferences=Preferences(
            buffer_minutes=0, comparisons=(Comparison(preferred="a", other="b"),)
        ),
    )
    assert suggest_comparisons(req, frozenset({"a"})) == ()


def test_suggestions_are_limited():
    req = request(
        screening("a", "14:00", "16:00"),
        screening("b", "15:00", "17:00"),
        screening("c", "15:30", "17:00"),
    )
    assert len(suggest_comparisons(req, frozenset({"a"}), limit=1)) == 1


def test_ended_screenings_make_their_films_seen_unless_dismissed():
    screenings = [
        screening("past", "10:00", "12:00"),
        screening("dismissed", "10:00", "12:00"),
        screening("future", "18:00", "20:00"),
        withdrawn(screening("gone", "10:00", "12:00")),
    ]
    entries = {s.programme_entry_id: entry(s.programme_entry_id) for s in screenings}
    seen = inferred_seen(screenings, entries, frozenset({"dismissed"}), at("13:00"))
    assert seen == frozenset({"film-past"})
