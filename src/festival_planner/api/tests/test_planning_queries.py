import datetime
from collections.abc import Iterable
from typing import Any

import pytest
from starlette.testclient import TestClient

from festival_planner.api.app import ApiDependencies, create_app
from festival_planner.api.ids import encode
from festival_planner.api.planning_types import DraftStatus, FlagKind
from festival_planner.api.tests.support import (
    ALICE,
    BOB,
    DEFAULT_TOKENS,
    dependencies,
    gql,
)
from festival_planner.domain import drafts, insights
from festival_planner.domain.change_sets import (
    AddExcludedProgrammeEntry,
    AddExcludedScreening,
    AddFilmCommitment,
    AddScreeningCommitment,
    ChangeSet,
    ChangeSetItem,
    RecordComparison,
    ReleaseFilmCommitment,
    ReleaseScreeningCommitment,
    RemoveExcludedProgrammeEntry,
    RemoveExcludedScreening,
    SetAttendEvents,
    SetBuffer,
    SetComparisonWeight,
    SetDays,
    SetEventWeight,
    SetProgrammeEntryWeight,
    SetScreeningWeight,
    SetTransportMode,
    SetYearWeight,
)
from festival_planner.domain.drafts import DraftId
from festival_planner.domain.festival import Festival, FestivalId
from festival_planner.domain.insights import DraftDiff
from festival_planner.domain.planning import Ticket
from festival_planner.domain.programme import (
    Film,
    FilmId,
    ProgrammeEntryId,
    ScreeningId,
    Venue,
    VenueId,
)
from festival_planner.domain.tests.builders import entry, screening
from festival_planner.domain.tests.fakes import InMemoryUnitOfWork
from festival_planner.domain.users import UserId

DAY = datetime.date(2030, 11, 8)
"""After the support clock (2026), so no Screening has started yet."""
SLUG = "fest-2030"
F = FestivalId("f")
FESTIVAL_ID = encode("Festival", F)
A = VenueId("A")


def _seeded() -> InMemoryUnitOfWork:
    """A Festival with a, b (conflicting) and c, d (later, conflicting)."""
    uow = InMemoryUnitOfWork()
    with uow:
        uow.festivals.save(
            Festival(
                id=F,
                slug=SLUG,
                name="Fest",
                start_date=DAY,
                end_date=DAY,
                time_zone="Europe/Oslo",
            )
        )
        uow.venues.save(Venue(id=A, name="A"))
        for e in ("a", "b", "c", "d"):
            uow.films.save(Film(id=FilmId(f"film-{e}"), title=e))
            uow.programme.save_entry(F, e, entry(e))
        for s in (
            screening("a", "14:00", "16:00", day=DAY),
            screening("b", "15:00", "17:00", day=DAY),
            screening("c", "18:00", "20:00", day=DAY),
            screening("d", "19:00", "21:00", day=DAY),
        ):
            uow.programme.save_screening(s)
        uow.commit()
    return uow


@pytest.fixture
def deps() -> ApiDependencies:
    return dependencies(_seeded())


@pytest.fixture
def client(deps: ApiDependencies) -> Iterable[TestClient]:
    with TestClient(create_app(deps)) as c:
        yield c


def _alice(deps: ApiDependencies) -> UserId:
    return deps.users(DEFAULT_TOKENS[ALICE]).id


def _items(*items: ChangeSetItem) -> ChangeSet:
    return ChangeSet(items=items)


def _commit(screening_id: str) -> AddScreeningCommitment:
    return AddScreeningCommitment(screening_id=ScreeningId(screening_id))


def _sid(screening_id: str) -> str:
    return encode("Screening", screening_id)


def _eid(entry_id: str) -> str:
    return encode("ProgrammeEntry", entry_id)


def _ids(*screening_ids: str) -> list[dict[str, str]]:
    return [{"id": _sid(i)} for i in screening_ids]


def _planning(client: TestClient, selection: str) -> dict[str, Any]:
    query = (
        "query ($f: ID!) { viewer { planning(festivalId: $f) { " + selection + " } } }"
    )
    data = gql(client, query, {"f": FESTIVAL_ID}, token=ALICE)
    return data["viewer"]["planning"]


DRAFT_FIELDS = """
id status stale score reasons notes createdAt solvedAt
festival { slug }
changeSet {
  __typename
  ... on AddScreeningCommitment { screening { id } }
}
screenings { screening { id } arrivalTime weight }
"""


def test_planning_without_any_activity(client: TestClient):
    planning = _planning(
        client,
        """
        festival { id slug }
        activeSchedule { id }
        schedules { edges { node { id } } }
        drafts { id }
        flags { kind }
        comparisonSuggestions { weightGap }
        inputs {
          screeningCommitments { id }
          filmCommitments { id }
          excludedScreenings { id }
          excludedProgrammeEntries { id }
          preferences {
            bufferMinutes venueBuffers { minutes } days
            programmeEntryWeights { weight } screeningWeights { weight }
            yearWeights { year } eventWeight attendEvents transportMode
            comparisonWeight comparisons { preferred { id } }
          }
        }
        """,
    )
    assert planning == {
        "festival": {"id": FESTIVAL_ID, "slug": SLUG},
        "activeSchedule": None,
        "schedules": {"edges": []},
        "drafts": [],
        "flags": [],
        "comparisonSuggestions": [],
        "inputs": {
            "screeningCommitments": [],
            "filmCommitments": [],
            "excludedScreenings": [],
            "excludedProgrammeEntries": [],
            "preferences": {
                "bufferMinutes": 15,
                "venueBuffers": [],
                "days": None,
                "programmeEntryWeights": [],
                "screeningWeights": [],
                "yearWeights": [],
                "eventWeight": 0.0,
                "attendEvents": False,
                "transportMode": None,
                "comparisonWeight": 0.5,
                "comparisons": [],
            },
        },
    }


def test_a_draft_shows_status_change_set_screenings_and_diff(
    deps: ApiDependencies, client: TestClient
):
    view = deps.planner.create_draft(_alice(deps), SLUG, _items(_commit("b")))
    draft_id = encode("Draft", view.draft.id)

    planning = _planning(
        client,
        "drafts { "
        + DRAFT_FIELDS
        + " diff { added { id } removed { id } scoreDelta droppedTickets { id } } }",
    )

    [draft] = planning["drafts"]
    assert draft["id"] == draft_id
    assert draft["status"] == "READY"
    assert draft["stale"] is False
    assert draft["festival"] == {"slug": SLUG}
    assert draft["changeSet"] == [
        {"__typename": "AddScreeningCommitment", "screening": {"id": _sid("b")}}
    ]
    assert draft["screenings"] == [
        {
            "screening": {"id": _sid("b")},
            "arrivalTime": "2030-11-08T15:00:00+01:00",
            "weight": 1.0,
        },
        {
            "screening": {"id": _sid("c")},
            "arrivalTime": "2030-11-08T18:00:00+01:00",
            "weight": 1.0,
        },
    ]
    assert draft["score"] == view.draft.score
    assert draft["reasons"] == [] and draft["notes"] == []
    assert draft["createdAt"] is not None and draft["solvedAt"] is not None
    assert draft["diff"]["added"] == _ids("b", "c")
    assert draft["diff"]["removed"] == []
    assert draft["diff"]["droppedTickets"] == []

    by_node = gql(
        client,
        "query ($id: ID!) { node(id: $id) { ... on Draft { id status } } }",
        {"id": draft_id},
        token=ALICE,
    )
    assert by_node == {"node": {"id": draft_id, "status": "READY"}}


def test_the_diff_is_only_computed_when_asked(
    deps: ApiDependencies, client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    deps.planner.create_draft(_alice(deps), SLUG, _items(_commit("b")))
    draft_diff = deps.planner.draft_diff
    calls: list[DraftId] = []

    def spy(user_id: UserId, draft_id: DraftId) -> DraftDiff | None:
        calls.append(draft_id)
        return draft_diff(user_id, draft_id)

    monkeypatch.setattr(deps.planner, "draft_diff", spy)

    _planning(client, "drafts { " + DRAFT_FIELDS + " }")
    assert calls == []

    planning = _planning(client, "drafts { diff { added { id } } }")
    assert len(calls) == 1
    assert planning["drafts"] == [{"diff": {"added": _ids("b", "c")}}]


def test_accepting_makes_the_active_schedule_and_history(
    deps: ApiDependencies, client: TestClient
):
    alice = _alice(deps)
    first = deps.planner.create_draft(alice, SLUG)
    deps.planner.accept(alice, first.draft.id)

    planning = _planning(
        client,
        """
        activeSchedule {
          id number score acceptedAt festival { slug }
          screenings { id }
          changeSet { __typename }
        }
        schedules { edges { node { id number } } }
        drafts { id }
        """,
    )

    active = planning["activeSchedule"]
    assert active["number"] == 1
    assert active["festival"] == {"slug": SLUG}
    assert active["screenings"] == _ids("a", "c")
    assert active["changeSet"] == []
    assert active["acceptedAt"] is not None
    assert planning["schedules"]["edges"] == [
        {"node": {"id": active["id"], "number": 1}}
    ]
    assert planning["drafts"] == []


def test_a_sibling_draft_is_stale_once_another_is_accepted(
    deps: ApiDependencies, client: TestClient
):
    alice = _alice(deps)
    sibling = deps.planner.create_draft(alice, SLUG, _items(_commit("b")))
    accepted = deps.planner.create_draft(alice, SLUG)
    deps.planner.accept(alice, accepted.draft.id)

    planning = _planning(
        client,
        "drafts { id stale diff { added { id } removed { id } } } "
        "schedules { edges { node { number } } }",
    )

    assert planning["drafts"] == [
        {
            "id": encode("Draft", sibling.draft.id),
            "stale": True,
            "diff": {"added": _ids("b"), "removed": _ids("a")},
        }
    ]
    assert planning["schedules"]["edges"] == [{"node": {"number": 1}}]


NODE_QUERY = """
query ($draft: ID!, $schedule: ID!) {
  draft: node(id: $draft) { id }
  schedule: node(id: $schedule) { id }
}
"""


def test_another_users_draft_and_schedule_are_null(
    deps: ApiDependencies, client: TestClient
):
    alice = _alice(deps)
    accepted = deps.planner.create_draft(alice, SLUG)
    schedule = deps.planner.accept(alice, accepted.draft.id)
    draft = deps.planner.create_draft(alice, SLUG, _items(_commit("b")))
    ids = {
        "draft": encode("Draft", draft.draft.id),
        "schedule": encode("Schedule", schedule.id),
    }

    assert gql(client, NODE_QUERY, ids, token=ALICE) == {
        "draft": {"id": ids["draft"]},
        "schedule": {"id": ids["schedule"]},
    }
    assert gql(client, NODE_QUERY, ids, token=BOB) == {
        "draft": None,
        "schedule": None,
    }
    assert gql(client, NODE_QUERY, ids) == {"draft": None, "schedule": None}
    unknown = {
        "draft": encode("Draft", "nope"),
        "schedule": encode("Schedule", "nope"),
    }
    assert gql(client, NODE_QUERY, unknown, token=ALICE) == {
        "draft": None,
        "schedule": None,
    }


@pytest.mark.parametrize(
    "festival_id",
    ["!!", encode("Venue", A), encode("Festival", "nope")],
)
def test_planning_of_a_garbage_festival_id_is_null(
    client: TestClient, festival_id: str
):
    data = gql(
        client,
        "query ($f: ID!) { viewer { planning(festivalId: $f) { drafts { id } } } }",
        {"f": festival_id},
        token=ALICE,
    )
    assert data == {"viewer": {"planning": None}}


def test_inputs_show_commitments_and_preferences(
    deps: ApiDependencies, client: TestClient
):
    alice = _alice(deps)
    view = deps.planner.create_draft(
        alice,
        SLUG,
        _items(
            _commit("b"),
            SetProgrammeEntryWeight(
                programme_entry_id=ProgrammeEntryId("d"), weight=2.0
            ),
            RecordComparison(
                preferred=ProgrammeEntryId("d"), other=ProgrammeEntryId("c")
            ),
            SetBuffer(venue_id=A, minutes=5),
        ),
    )
    deps.planner.accept(alice, view.draft.id)

    planning = _planning(
        client,
        """
        inputs {
          screeningCommitments { id }
          filmCommitments { id }
          preferences {
            bufferMinutes
            venueBuffers { venue { id } minutes }
            programmeEntryWeights { programmeEntry { id } weight }
            comparisons { preferred { id } other { id } }
          }
        }
        activeSchedule {
          changeSet {
            __typename
            ... on AddScreeningCommitment { screening { id } }
            ... on SetProgrammeEntryWeight { programmeEntry { id } weight }
            ... on RecordComparison { preferred { id } other { id } }
            ... on SetBuffer { venue { id } minutes }
          }
        }
        """,
    )

    assert planning["inputs"] == {
        "screeningCommitments": _ids("b"),
        "filmCommitments": [],
        "preferences": {
            "bufferMinutes": 15,
            "venueBuffers": [{"venue": {"id": encode("Venue", A)}, "minutes": 5}],
            "programmeEntryWeights": [
                {"programmeEntry": {"id": _eid("d")}, "weight": 2.0}
            ],
            "comparisons": [
                {"preferred": {"id": _eid("d")}, "other": {"id": _eid("c")}}
            ],
        },
    }
    assert planning["activeSchedule"]["changeSet"] == [
        {"__typename": "AddScreeningCommitment", "screening": {"id": _sid("b")}},
        {
            "__typename": "SetProgrammeEntryWeight",
            "programmeEntry": {"id": _eid("d")},
            "weight": 2.0,
        },
        {
            "__typename": "RecordComparison",
            "preferred": {"id": _eid("d")},
            "other": {"id": _eid("c")},
        },
        {
            "__typename": "SetBuffer",
            "venue": {"id": encode("Venue", A)},
            "minutes": 5,
        },
    ]


def test_flags_and_comparison_suggestions(deps: ApiDependencies, client: TestClient):
    alice = _alice(deps)
    view = deps.planner.create_draft(alice, SLUG)
    deps.planner.accept(alice, view.draft.id)  # a and c
    deps.planner.record_ticket(alice, Ticket(screening_id=ScreeningId("b")))

    planning = _planning(
        client,
        """
        flags { kind message screening { id } programmeEntry { id } }
        comparisonSuggestions { scheduled { id } other { id } weightGap }
        limited: comparisonSuggestions(limit: 1) { scheduled { id } }
        """,
    )

    assert planning["flags"] == [
        {
            "kind": "UNSCHEDULED_TICKET",
            "message": "A ticketed Screening is not in the Active Schedule",
            "screening": {"id": _sid("b")},
            "programmeEntry": None,
        }
    ]
    expected = deps.planner.suggest_comparisons(alice, SLUG)
    assert len(expected) == 2
    assert planning["comparisonSuggestions"] == [
        {
            "scheduled": {"id": _eid(s.scheduled)},
            "other": {"id": _eid(s.other)},
            "weightGap": s.weight_gap,
        }
        for s in expected
    ]
    assert planning["limited"] == [{"scheduled": {"id": _eid(expected[0].scheduled)}}]


def test_viewer_tickets_and_seen_films(deps: ApiDependencies, client: TestClient):
    alice = _alice(deps)
    deps.planner.record_ticket(
        alice, Ticket(screening_id=ScreeningId("c"), exchangeable=True)
    )
    deps.planner.record_ticket(
        alice, Ticket(screening_id=ScreeningId("b"), refundable=True)
    )
    deps.planner.mark_seen(alice, FilmId("film-d"))
    deps.planner.mark_seen(alice, FilmId("film-a"))
    query = """
    { viewer {
        tickets { screening { id } exchangeable refundable }
        seenFilms { id title }
    } }
    """

    data = gql(client, query, token=ALICE)

    assert data["viewer"] == {
        "tickets": [
            {"screening": {"id": _sid("b")}, "exchangeable": False, "refundable": True},
            {"screening": {"id": _sid("c")}, "exchangeable": True, "refundable": False},
        ],
        "seenFilms": [
            {"id": encode("Film", "film-a"), "title": "a"},
            {"id": encode("Film", "film-d"), "title": "d"},
        ],
    }
    assert gql(client, query, token=BOB)["viewer"] == {
        "tickets": [],
        "seenFilms": [],
    }


@pytest.mark.parametrize(
    ("api_enum", "domain_enum"),
    [(DraftStatus, drafts.DraftStatus), (FlagKind, insights.FlagKind)],
)
def test_the_graphql_enums_match_the_domain(api_enum: Any, domain_enum: Any):
    assert [m.value for m in api_enum] == [m.value for m in domain_enum]


def _entry_id(entry_id: str) -> ProgrammeEntryId:
    return ProgrammeEntryId(entry_id)


def test_a_withdrawn_film_commitment_flags_its_programme_entry():
    uow = _seeded()
    s1 = screening("s1", "22:00", "23:30", entry_id="e1", day=DAY)
    with uow:
        uow.films.save(Film(id=FilmId("film-e1"), title="e1"))
        uow.programme.save_entry(F, "e1", entry("e1"))
        uow.programme.save_screening(s1)
        uow.commit()
    deps = dependencies(uow)
    alice = _alice(deps)
    view = deps.planner.create_draft(
        alice, SLUG, _items(AddFilmCommitment(programme_entry_id=_entry_id("e1")))
    )
    deps.planner.accept(alice, view.draft.id)
    with uow:
        uow.programme.save_screening(s1.model_copy(update={"withdrawn": True}))
        uow.commit()

    with TestClient(create_app(deps)) as client:
        planning = _planning(
            client, "flags { kind screening { id } programmeEntry { id } }"
        )

    assert planning["flags"] == [
        {
            "kind": "WITHDRAWN_COMMITMENT",
            "screening": None,
            "programmeEntry": {"id": _eid("e1")},
        },
        {
            "kind": "WITHDRAWN_IN_SCHEDULE",
            "screening": {"id": _sid("s1")},
            "programmeEntry": None,
        },
    ]


EVERY_ITEM = """
drafts {
  changeSet {
    __typename
    ... on AddScreeningCommitment { screening { id } }
    ... on ReleaseScreeningCommitment { screening { id } }
    ... on AddFilmCommitment { programmeEntry { id } }
    ... on ReleaseFilmCommitment { programmeEntry { id } }
    ... on AddExcludedScreening { screening { id } }
    ... on RemoveExcludedScreening { screening { id } }
    ... on AddExcludedProgrammeEntry { programmeEntry { id } }
    ... on RemoveExcludedProgrammeEntry { programmeEntry { id } }
    ... on SetProgrammeEntryWeight { programmeEntry { id } entryWeight: weight }
    ... on SetScreeningWeight { screening { id } screeningWeight: weight }
    ... on SetYearWeight { year yearWeight: weight }
    ... on SetBuffer { venue { id } minutes }
    ... on SetDays { days }
    ... on SetEventWeight { eventWeight: weight }
    ... on SetAttendEvents { attend }
    ... on SetTransportMode { mode }
    ... on SetComparisonWeight { comparisonWeight: weight }
    ... on RecordComparison { preferred { id } other { id } }
  }
}
"""


def test_a_change_set_shows_every_item_kind(deps: ApiDependencies, client: TestClient):
    alice = _alice(deps)
    base = deps.planner.create_draft(
        alice,
        SLUG,
        _items(
            _commit("a"),
            AddFilmCommitment(programme_entry_id=_entry_id("c")),
            AddExcludedScreening(screening_id=ScreeningId("b")),
            AddExcludedProgrammeEntry(programme_entry_id=_entry_id("d")),
        ),
    )
    deps.planner.accept(alice, base.draft.id)
    deps.planner.create_draft(
        alice,
        SLUG,
        _items(
            ReleaseScreeningCommitment(screening_id=ScreeningId("a")),
            ReleaseFilmCommitment(programme_entry_id=_entry_id("c")),
            RemoveExcludedScreening(screening_id=ScreeningId("b")),
            RemoveExcludedProgrammeEntry(programme_entry_id=_entry_id("d")),
            _commit("b"),
            AddFilmCommitment(programme_entry_id=_entry_id("d")),
            AddExcludedScreening(screening_id=ScreeningId("a")),
            AddExcludedProgrammeEntry(programme_entry_id=_entry_id("c")),
            SetProgrammeEntryWeight(programme_entry_id=_entry_id("a"), weight=2.0),
            SetScreeningWeight(screening_id=ScreeningId("c"), weight=1.5),
            SetYearWeight(year=2030, weight=0.5),
            SetBuffer(venue_id=A, minutes=5),
            SetDays(days=(DAY,)),
            SetEventWeight(weight=0.25),
            SetAttendEvents(attend=True),
            SetTransportMode(mode="walk"),
            SetComparisonWeight(weight=1.0),
            RecordComparison(preferred=_entry_id("b"), other=_entry_id("d")),
        ),
    )

    [draft] = _planning(client, EVERY_ITEM)["drafts"]

    day = DAY.isoformat()
    assert draft["changeSet"] == [
        {"__typename": "ReleaseScreeningCommitment", "screening": {"id": _sid("a")}},
        {"__typename": "ReleaseFilmCommitment", "programmeEntry": {"id": _eid("c")}},
        {"__typename": "RemoveExcludedScreening", "screening": {"id": _sid("b")}},
        {
            "__typename": "RemoveExcludedProgrammeEntry",
            "programmeEntry": {"id": _eid("d")},
        },
        {"__typename": "AddScreeningCommitment", "screening": {"id": _sid("b")}},
        {"__typename": "AddFilmCommitment", "programmeEntry": {"id": _eid("d")}},
        {"__typename": "AddExcludedScreening", "screening": {"id": _sid("a")}},
        {
            "__typename": "AddExcludedProgrammeEntry",
            "programmeEntry": {"id": _eid("c")},
        },
        {
            "__typename": "SetProgrammeEntryWeight",
            "programmeEntry": {"id": _eid("a")},
            "entryWeight": 2.0,
        },
        {
            "__typename": "SetScreeningWeight",
            "screening": {"id": _sid("c")},
            "screeningWeight": 1.5,
        },
        {"__typename": "SetYearWeight", "year": 2030, "yearWeight": 0.5},
        {
            "__typename": "SetBuffer",
            "venue": {"id": encode("Venue", A)},
            "minutes": 5,
        },
        {"__typename": "SetDays", "days": [day]},
        {"__typename": "SetEventWeight", "eventWeight": 0.25},
        {"__typename": "SetAttendEvents", "attend": True},
        {"__typename": "SetTransportMode", "mode": "walk"},
        {"__typename": "SetComparisonWeight", "comparisonWeight": 1.0},
        {
            "__typename": "RecordComparison",
            "preferred": {"id": _eid("b")},
            "other": {"id": _eid("d")},
        },
    ]


def test_tickets_and_seen_films_of_unknown_things_are_dropped():
    uow = _seeded()
    deps = dependencies(uow)
    alice = _alice(deps)
    deps.planner.record_ticket(alice, Ticket(screening_id=ScreeningId("b")))
    deps.planner.record_ticket(alice, Ticket(screening_id=ScreeningId("c")))
    deps.planner.mark_seen(alice, FilmId("film-a"))
    deps.planner.mark_seen(alice, FilmId("film-d"))
    del uow.stored.screenings[ScreeningId("b")]
    del uow.stored.films[FilmId("film-a")]

    with TestClient(create_app(deps)) as client:
        data = gql(
            client,
            "{ viewer { tickets { screening { id } } seenFilms { id } } }",
            token=ALICE,
        )

    assert data["viewer"] == {
        "tickets": [{"screening": {"id": _sid("c")}}],
        "seenFilms": [{"id": encode("Film", "film-d")}],
    }
