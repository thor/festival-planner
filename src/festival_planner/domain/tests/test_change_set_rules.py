import datetime

import pytest

from festival_planner.domain.change_sets import (
    AddExcludedScreening,
    AddFilmCommitment,
    AddScreeningCommitment,
    ChangeSet,
    InvalidChangeSetError,
    ProblemCode,
    ProgrammeIndex,
    RecordComparison,
    ReleaseFilmCommitment,
    ReleaseScreeningCommitment,
    RemoveExcludedScreening,
    SetBuffer,
    SetDateRange,
    SetProgrammeEntryWeight,
    SetYearWeight,
    apply,
    check,
    problems,
    rebase,
)
from festival_planner.domain.planning import Comparison, PlanningInputs, Preferences
from festival_planner.domain.programme import Venue

from .builders import entry, screening

PROGRAMME = ProgrammeIndex.of(
    entries=[entry("e1"), entry("e2")],
    screenings=[
        screening("s1", "14:00", "16:00", entry_id="e1"),
        screening("s2", "18:00", "20:00", entry_id="e1"),
        screening("s3", "18:00", "20:00", entry_id="e2"),
    ],
    venues=[Venue(id="A", name="A")],
)


def codes(
    change_set: ChangeSet, base: PlanningInputs = PlanningInputs()
) -> list[ProblemCode]:
    return [p.code for p in problems(change_set, base, PROGRAMME)]


def cs(*items) -> ChangeSet:
    return ChangeSet(items=items)


def test_a_sound_change_set_has_no_problems():
    change_set = cs(
        AddScreeningCommitment(screening_id="s1"),
        AddFilmCommitment(programme_entry_id="e2"),
        SetYearWeight(year=2025, weight=0.2),
        SetBuffer(venue_id="A", minutes=5),
        RecordComparison(preferred="e1", other="e2"),
    )
    assert codes(change_set) == []
    check(change_set, PlanningInputs(), PROGRAMME)


def test_unknown_ids_are_problems():
    assert codes(cs(AddScreeningCommitment(screening_id="nope"))) == [
        ProblemCode.UNKNOWN_ID
    ]
    assert codes(cs(SetBuffer(venue_id="nowhere", minutes=5))) == [
        ProblemCode.UNKNOWN_ID
    ]
    assert codes(cs(RecordComparison(preferred="e1", other="nope"))) == [
        ProblemCode.UNKNOWN_ID
    ]


@pytest.mark.parametrize(
    "items",
    [
        (
            AddScreeningCommitment(screening_id="s1"),
            AddScreeningCommitment(screening_id="s1"),
        ),
        (
            SetProgrammeEntryWeight(programme_entry_id="e1", weight=2.0),
            SetProgrammeEntryWeight(programme_entry_id="e1", weight=3.0),
        ),
        (
            RecordComparison(preferred="e1", other="e2"),
            RecordComparison(preferred="e2", other="e1"),
        ),
        (SetBuffer(minutes=5), SetBuffer(minutes=10)),
    ],
)
def test_two_items_for_one_target_conflict(items):
    assert ProblemCode.CONFLICTING_ITEMS in codes(cs(*items))


def test_buffers_of_different_venues_do_not_conflict():
    assert codes(cs(SetBuffer(minutes=5), SetBuffer(venue_id="A", minutes=10))) == []


def test_releasing_what_is_not_committed_is_a_no_op():
    assert codes(cs(ReleaseScreeningCommitment(screening_id="s1"))) == [
        ProblemCode.NO_OP
    ]


def test_adding_what_is_there_is_a_no_op():
    base = PlanningInputs(film_commitments=frozenset({"e1"}))
    assert codes(cs(AddFilmCommitment(programme_entry_id="e1")), base) == [
        ProblemCode.NO_OP
    ]


def test_setting_a_preference_to_its_current_value_is_a_no_op():
    assert codes(cs(SetBuffer(minutes=Preferences().buffer_minutes))) == [
        ProblemCode.NO_OP
    ]
    assert codes(cs(SetProgrammeEntryWeight(programme_entry_id="e1", weight=None))) == [
        ProblemCode.NO_OP
    ]


def test_committing_and_excluding_one_screening_is_a_problem():
    change_set = cs(
        AddScreeningCommitment(screening_id="s1"),
        AddExcludedScreening(screening_id="s1"),
    )
    assert codes(change_set) == [ProblemCode.COMMITTED_AND_EXCLUDED]


def test_committing_to_something_excluded_needs_its_removal():
    base = PlanningInputs(excluded_screenings=frozenset({"s1"}))
    assert codes(cs(AddScreeningCommitment(screening_id="s1")), base) == [
        ProblemCode.COMMITTED_AND_EXCLUDED
    ]
    both = cs(
        AddScreeningCommitment(screening_id="s1"),
        RemoveExcludedScreening(screening_id="s1"),
    )
    assert codes(both, base) == []


def test_two_screening_commitments_of_one_entry_are_a_problem():
    base = PlanningInputs(screening_commitments=frozenset({"s1"}))
    assert codes(cs(AddScreeningCommitment(screening_id="s2")), base) == [
        ProblemCode.TWO_SCREENING_COMMITMENTS
    ]


def test_check_raises_with_every_problem():
    with pytest.raises(InvalidChangeSetError) as raised:
        check(
            cs(
                ReleaseFilmCommitment(programme_entry_id="e1"),
                AddScreeningCommitment(screening_id="x"),
            ),
            PlanningInputs(),
            PROGRAMME,
        )
    assert [p.items for p in raised.value.problems] == [(0,), (1,)]


def test_apply_changes_commitments_excluded_and_preferences():
    base = PlanningInputs(
        screening_commitments=frozenset({"s1"}),
        preferences=Preferences(comparisons=(Comparison(preferred="e2", other="e1"),)),
    )
    result = apply(
        cs(
            ReleaseScreeningCommitment(screening_id="s1"),
            AddExcludedScreening(screening_id="s2"),
            SetProgrammeEntryWeight(programme_entry_id="e1", weight=2.0),
            SetDateRange(start_date=datetime.date(2025, 11, 8), end_date=None),
            RecordComparison(preferred="e1", other="e2"),
        ),
        base,
    )
    assert result.screening_commitments == frozenset()
    assert result.excluded_screenings == frozenset({"s2"})
    assert result.preferences.programme_entry_weights == {"e1": 2.0}
    assert result.preferences.start_date == datetime.date(2025, 11, 8)
    assert result.preferences.comparisons == (Comparison(preferred="e1", other="e2"),)


def test_resetting_a_setting_restores_its_default():
    base = PlanningInputs(
        preferences=Preferences(buffer_minutes=30, venue_buffer_minutes={"A": 5})
    )
    result = apply(
        cs(SetBuffer(minutes=None), SetBuffer(venue_id="A", minutes=None)), base
    )
    assert result.preferences == Preferences()


def test_rebase_drops_items_that_became_no_ops():
    base = PlanningInputs(screening_commitments=frozenset({"s1"}))
    change_set = cs(
        AddScreeningCommitment(screening_id="s1"),
        AddFilmCommitment(programme_entry_id="e2"),
    )
    rebased, notes = rebase(change_set, base, PROGRAMME)
    assert rebased == cs(AddFilmCommitment(programme_entry_id="e2"))
    assert len(notes) == 1 and "add_screening_commitment" in notes[0]


def test_rebase_refuses_contradictions_with_the_new_base():
    base = PlanningInputs(excluded_screenings=frozenset({"s1"}))
    with pytest.raises(InvalidChangeSetError):
        rebase(cs(AddScreeningCommitment(screening_id="s1")), base, PROGRAMME)
