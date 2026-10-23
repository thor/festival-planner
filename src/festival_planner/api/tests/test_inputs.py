import datetime
import typing

import pytest
import strawberry

from festival_planner.api import inputs as i
from festival_planner.api.ids import encode
from festival_planner.domain import change_sets as cs
from festival_planner.domain.programme import ProgrammeEntryId, ScreeningId, VenueId

S = strawberry.ID(encode("Screening", "s"))
E = strawberry.ID(encode("ProgrammeEntry", "e"))
E2 = strawberry.ID(encode("ProgrammeEntry", "e2"))
V = strawberry.ID(encode("Venue", "v"))
D1 = datetime.date(2030, 11, 8)
D2 = datetime.date(2030, 11, 9)

SID = ScreeningId("s")
EID = ProgrammeEntryId("e")

CASES: list[tuple[i.ChangeSetItemInput, cs.ChangeSetItem]] = [
    (
        i.ChangeSetItemInput(add_screening_commitment=i.ScreeningInput(screening_id=S)),
        cs.AddScreeningCommitment(screening_id=SID),
    ),
    (
        i.ChangeSetItemInput(
            release_screening_commitment=i.ScreeningInput(screening_id=S)
        ),
        cs.ReleaseScreeningCommitment(screening_id=SID),
    ),
    (
        i.ChangeSetItemInput(
            add_film_commitment=i.ProgrammeEntryInput(programme_entry_id=E)
        ),
        cs.AddFilmCommitment(programme_entry_id=EID),
    ),
    (
        i.ChangeSetItemInput(
            release_film_commitment=i.ProgrammeEntryInput(programme_entry_id=E)
        ),
        cs.ReleaseFilmCommitment(programme_entry_id=EID),
    ),
    (
        i.ChangeSetItemInput(add_excluded_screening=i.ScreeningInput(screening_id=S)),
        cs.AddExcludedScreening(screening_id=SID),
    ),
    (
        i.ChangeSetItemInput(
            remove_excluded_screening=i.ScreeningInput(screening_id=S)
        ),
        cs.RemoveExcludedScreening(screening_id=SID),
    ),
    (
        i.ChangeSetItemInput(
            add_excluded_programme_entry=i.ProgrammeEntryInput(programme_entry_id=E)
        ),
        cs.AddExcludedProgrammeEntry(programme_entry_id=EID),
    ),
    (
        i.ChangeSetItemInput(
            remove_excluded_programme_entry=i.ProgrammeEntryInput(programme_entry_id=E)
        ),
        cs.RemoveExcludedProgrammeEntry(programme_entry_id=EID),
    ),
    (
        i.ChangeSetItemInput(
            set_programme_entry_weight=i.SetProgrammeEntryWeightInput(
                programme_entry_id=E, weight=2.0
            )
        ),
        cs.SetProgrammeEntryWeight(programme_entry_id=EID, weight=2.0),
    ),
    (
        i.ChangeSetItemInput(
            set_screening_weight=i.SetScreeningWeightInput(screening_id=S, weight=0.5)
        ),
        cs.SetScreeningWeight(screening_id=SID, weight=0.5),
    ),
    (
        i.ChangeSetItemInput(
            set_year_weight=i.SetYearWeightInput(year=1999, weight=1.5)
        ),
        cs.SetYearWeight(year=1999, weight=1.5),
    ),
    (
        i.ChangeSetItemInput(set_buffer=i.SetBufferInput(venue_id=V, minutes=20)),
        cs.SetBuffer(venue_id=VenueId("v"), minutes=20),
    ),
    (
        i.ChangeSetItemInput(
            set_date_range=i.SetDateRangeInput(start_date=D1, end_date=D2)
        ),
        cs.SetDateRange(start_date=D1, end_date=D2),
    ),
    (
        i.ChangeSetItemInput(set_event_weight=i.SetEventWeightInput(weight=3.0)),
        cs.SetEventWeight(weight=3.0),
    ),
    (
        i.ChangeSetItemInput(set_attend_events=i.SetAttendEventsInput(attend=False)),
        cs.SetAttendEvents(attend=False),
    ),
    (
        i.ChangeSetItemInput(set_transport_mode=i.SetTransportModeInput(mode="bike")),
        cs.SetTransportMode(mode="bike"),
    ),
    (
        i.ChangeSetItemInput(
            set_comparison_weight=i.SetComparisonWeightInput(weight=4.0)
        ),
        cs.SetComparisonWeight(weight=4.0),
    ),
    (
        i.ChangeSetItemInput(
            record_comparison=i.RecordComparisonInput(preferred_id=E, other_id=E2)
        ),
        cs.RecordComparison(preferred=EID, other=ProgrammeEntryId("e2")),
    ),
]


def _kinds() -> list[str]:
    union = typing.get_args(cs.ChangeSetItem)[0]
    return [t.model_fields["kind"].default for t in typing.get_args(union)]


def test_every_domain_item_kind_has_a_case():
    assert sorted(expected.kind for _, expected in CASES) == sorted(_kinds())


@pytest.mark.parametrize(
    ("item", "expected"), CASES, ids=[expected.kind for _, expected in CASES]
)
def test_each_input_field_maps_to_its_domain_item(
    item: i.ChangeSetItemInput, expected: cs.ChangeSetItem
):
    assert i.to_change_set([item]) == cs.ChangeSet(items=(expected,))


def test_a_null_weight_resets():
    item = i.ChangeSetItemInput(
        set_programme_entry_weight=i.SetProgrammeEntryWeightInput(programme_entry_id=E)
    )
    assert i.to_change_set([item]).items == (
        cs.SetProgrammeEntryWeight(programme_entry_id=EID, weight=None),
    )


def test_unset_preferences_reset():
    items = [
        i.ChangeSetItemInput(set_buffer=i.SetBufferInput()),
        i.ChangeSetItemInput(set_date_range=i.SetDateRangeInput()),
    ]
    assert i.to_change_set(items).items == (
        cs.SetBuffer(venue_id=None, minutes=None),
        cs.SetDateRange(start_date=None, end_date=None),
    )


def test_an_invalid_item_is_an_invalid_item_problem():
    items = [
        i.ChangeSetItemInput(add_screening_commitment=i.ScreeningInput(screening_id=S)),
        i.ChangeSetItemInput(
            set_date_range=i.SetDateRangeInput(start_date=D2, end_date=D1)
        ),
    ]
    with pytest.raises(cs.InvalidChangeSetError) as raised:
        i.to_change_set(items)
    [problem] = raised.value.problems
    assert problem.code is cs.ProblemCode.INVALID_ITEM
    assert problem.items == (1,)
    assert "cannot end before it starts" in problem.message


def test_every_invalid_item_is_reported():
    items = [
        i.ChangeSetItemInput(set_buffer=i.SetBufferInput(minutes=-1)),
        i.ChangeSetItemInput(
            record_comparison=i.RecordComparisonInput(preferred_id=E, other_id=E)
        ),
    ]
    with pytest.raises(cs.InvalidChangeSetError) as raised:
        i.to_change_set(items)
    assert [p.items for p in raised.value.problems] == [(0,), (1,)]
    assert {p.code for p in raised.value.problems} == {cs.ProblemCode.INVALID_ITEM}


@pytest.mark.parametrize(
    "item",
    [
        i.ChangeSetItemInput(),
        i.ChangeSetItemInput(
            add_screening_commitment=i.ScreeningInput(screening_id=S),
            set_event_weight=i.SetEventWeightInput(weight=1.0),
        ),
    ],
    ids=["none", "two"],
)
def test_an_item_needs_exactly_one_field(item: i.ChangeSetItemInput):
    with pytest.raises(cs.InvalidChangeSetError) as raised:
        i.to_change_set([item])
    [problem] = raised.value.problems
    assert (problem.code, problem.items) == (cs.ProblemCode.INVALID_ITEM, (0,))


@pytest.mark.parametrize(
    "raw",
    ["s", "not-a-global-id", encode("Venue", "s")],
    ids=["raw-domain-id", "garbage", "wrong-type"],
)
def test_an_id_that_does_not_decode_is_an_unknown_id(raw: str):
    items = [
        i.ChangeSetItemInput(set_event_weight=i.SetEventWeightInput(weight=1.0)),
        i.ChangeSetItemInput(
            add_screening_commitment=i.ScreeningInput(screening_id=strawberry.ID(raw))
        ),
    ]
    with pytest.raises(cs.InvalidChangeSetError) as raised:
        i.to_change_set(items)
    [problem] = raised.value.problems
    assert (problem.code, problem.items) == (cs.ProblemCode.UNKNOWN_ID, (1,))
    assert "screeningId" in problem.message
    assert repr(raw) in problem.message


def test_unknown_ids_and_invalid_items_are_reported_together():
    items = [
        i.ChangeSetItemInput(
            record_comparison=i.RecordComparisonInput(
                preferred_id=strawberry.ID("e"), other_id=E
            )
        ),
        i.ChangeSetItemInput(set_buffer=i.SetBufferInput(minutes=-1)),
        i.ChangeSetItemInput(
            record_comparison=i.RecordComparisonInput(
                preferred_id=strawberry.ID("x"), other_id=strawberry.ID("y")
            )
        ),
    ]
    with pytest.raises(cs.InvalidChangeSetError) as raised:
        i.to_change_set(items)
    assert [(p.code, p.items) for p in raised.value.problems] == [
        (cs.ProblemCode.UNKNOWN_ID, (0,)),
        (cs.ProblemCode.INVALID_ITEM, (1,)),
        (cs.ProblemCode.UNKNOWN_ID, (2,)),
        (cs.ProblemCode.UNKNOWN_ID, (2,)),
    ]
