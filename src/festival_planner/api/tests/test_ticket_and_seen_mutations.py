import datetime
from collections.abc import Iterable
from typing import Any

import pytest
from starlette.testclient import TestClient

from festival_planner.api.ids import encode
from festival_planner.api.tests.support import ALICE, api_client, gql
from festival_planner.domain.change_sets import ChangeSet
from festival_planner.domain.drafts import Schedule, ScheduleId
from festival_planner.domain.festival import Festival, FestivalId
from festival_planner.domain.programme import Film, FilmId, ScreeningId, Venue, VenueId
from festival_planner.domain.tests.builders import DAY as PAST_DAY
from festival_planner.domain.tests.builders import entry, screening
from festival_planner.domain.tests.fakes import InMemoryUnitOfWork
from festival_planner.domain.users import user_for

FUTURE_DAY = PAST_DAY.replace(year=PAST_DAY.year + 5)
F = FestivalId("f")
FESTIVAL_ID = encode("Festival", F)


def _seeded() -> InMemoryUnitOfWork:
    """A Festival with future Screenings a, b, and Alice's Active Schedule
    holding p, an already-ended Screening whose Film is Seen by inference."""
    uow = InMemoryUnitOfWork()
    alice = user_for(uow, "local", "alice")
    with uow:
        uow.festivals.save(
            Festival(
                id=F,
                slug="fest",
                name="Fest",
                start_date=FUTURE_DAY,
                end_date=FUTURE_DAY,
                time_zone="Europe/Oslo",
            )
        )
        uow.venues.save(Venue(id=VenueId("A"), name="A"))
        for e in ("a", "b"):
            uow.films.save(Film(id=FilmId(f"film-{e}"), title=e))
            uow.programme.save_entry(F, e, entry(e))
            uow.programme.save_screening(screening(e, "14:00", "16:00", day=FUTURE_DAY))
        # Before the support clock's 2026-01-01, so this Screening has ended.
        uow.films.save(Film(id=FilmId("film-p"), title="p"))
        uow.programme.save_entry(F, "p", entry("p"))
        uow.programme.save_screening(screening("p", "14:00", "16:00"))
        uow.planning.save_schedule(
            Schedule(
                id=ScheduleId("s1"),
                user_id=alice.id,
                festival_id=F,
                number=1,
                screening_ids=frozenset({ScreeningId("p")}),
                score=0.0,
                change_set=ChangeSet(),
                accepted_at=datetime.datetime(2020, 1, 1, tzinfo=datetime.UTC),
            )
        )
        uow.commit()
    return uow


@pytest.fixture
def client() -> Iterable[TestClient]:
    with api_client(_seeded()) as c:
        yield c


NOT_SIGNED_IN = "... on NotSignedIn { message } "
NOT_FOUND = "... on NotFound { message } "

RECORD_TICKET = (
    "mutation ($input: RecordTicketInput!) { recordTicket(input: $input) { "
    "__typename ... on TicketResult { ticket { "
    "screening { id } exchangeable refundable } } " + NOT_FOUND + NOT_SIGNED_IN + "} }"
)
REMOVE_TICKET = (
    "mutation ($input: ScreeningInput!) { removeTicket(input: $input) { "
    "__typename ... on ScreeningResult { screening { id } } "
    + NOT_FOUND
    + NOT_SIGNED_IN
    + "} }"
)
MARK_SEEN = (
    "mutation ($input: FilmInput!) { markSeen(input: $input) { "
    "__typename ... on FilmResult { film { id } } " + NOT_FOUND + NOT_SIGNED_IN + "} }"
)
UNMARK_SEEN = (
    "mutation ($input: FilmInput!) { unmarkSeen(input: $input) { "
    "__typename ... on FilmResult { film { id } } " + NOT_FOUND + NOT_SIGNED_IN + "} }"
)
DISMISS_INFERRED_SEEN = (
    "mutation ($input: ScreeningInput!) { dismissInferredSeen(input: $input) { "
    "__typename ... on ScreeningResult { screening { id } } "
    + NOT_FOUND
    + NOT_SIGNED_IN
    + "} }"
)
RESTORE_INFERRED_SEEN = (
    "mutation ($input: ScreeningInput!) { restoreInferredSeen(input: $input) { "
    "__typename ... on ScreeningResult { screening { id } } "
    + NOT_FOUND
    + NOT_SIGNED_IN
    + "} }"
)
VIEWER_TICKETS = "{ viewer { tickets { screening { id } exchangeable refundable } } }"
VIEWER_SEEN = "{ viewer { seenFilms { id } } }"


def _result(data: dict[str, Any]) -> dict[str, Any]:
    [result] = data.values()
    return result


def test_recording_a_ticket_shows_on_the_viewer(client: TestClient):
    screening_id = encode("Screening", "a")
    result = gql(
        client, RECORD_TICKET, {"input": {"screeningId": screening_id}}, token=ALICE
    )["recordTicket"]
    assert result == {
        "__typename": "TicketResult",
        "ticket": {
            "screening": {"id": screening_id},
            "exchangeable": False,
            "refundable": False,
        },
    }
    tickets = gql(client, VIEWER_TICKETS, token=ALICE)["viewer"]["tickets"]
    assert tickets == [
        {"screening": {"id": screening_id}, "exchangeable": False, "refundable": False}
    ]


def test_recording_a_ticket_twice_updates_its_flags(client: TestClient):
    screening_id = encode("Screening", "a")
    gql(client, RECORD_TICKET, {"input": {"screeningId": screening_id}}, token=ALICE)
    variables = {
        "input": {"screeningId": screening_id, "exchangeable": True, "refundable": True}
    }
    result = gql(client, RECORD_TICKET, variables, token=ALICE)["recordTicket"]
    assert result == {
        "__typename": "TicketResult",
        "ticket": {
            "screening": {"id": screening_id},
            "exchangeable": True,
            "refundable": True,
        },
    }
    tickets = gql(client, VIEWER_TICKETS, token=ALICE)["viewer"]["tickets"]
    assert tickets == [
        {"screening": {"id": screening_id}, "exchangeable": True, "refundable": True}
    ]


def test_removing_a_ticket(client: TestClient):
    screening_id = encode("Screening", "a")
    gql(client, RECORD_TICKET, {"input": {"screeningId": screening_id}}, token=ALICE)
    result = gql(
        client, REMOVE_TICKET, {"input": {"screeningId": screening_id}}, token=ALICE
    )["removeTicket"]
    assert result == {
        "__typename": "ScreeningResult",
        "screening": {"id": screening_id},
    }
    assert gql(client, VIEWER_TICKETS, token=ALICE)["viewer"]["tickets"] == []


def test_marking_and_unmarking_seen(client: TestClient):
    film_id = encode("Film", "film-a")
    film_p_id = encode("Film", "film-p")  # already Seen by inference (Screening p)
    marked = gql(client, MARK_SEEN, {"input": {"filmId": film_id}}, token=ALICE)[
        "markSeen"
    ]
    assert marked == {"__typename": "FilmResult", "film": {"id": film_id}}
    assert gql(client, VIEWER_SEEN, token=ALICE)["viewer"]["seenFilms"] == [
        {"id": film_id},
        {"id": film_p_id},
    ]

    unmarked = gql(client, UNMARK_SEEN, {"input": {"filmId": film_id}}, token=ALICE)[
        "unmarkSeen"
    ]
    assert unmarked == {"__typename": "FilmResult", "film": {"id": film_id}}
    assert gql(client, VIEWER_SEEN, token=ALICE)["viewer"]["seenFilms"] == [
        {"id": film_p_id}
    ]


def test_dismissing_and_restoring_inferred_seen(client: TestClient):
    film_id = encode("Film", "film-p")
    assert gql(client, VIEWER_SEEN, token=ALICE)["viewer"]["seenFilms"] == [
        {"id": film_id}
    ]

    screening_id = encode("Screening", "p")
    dismissed = gql(
        client,
        DISMISS_INFERRED_SEEN,
        {"input": {"screeningId": screening_id}},
        token=ALICE,
    )["dismissInferredSeen"]
    assert dismissed == {
        "__typename": "ScreeningResult",
        "screening": {"id": screening_id},
    }
    assert gql(client, VIEWER_SEEN, token=ALICE)["viewer"]["seenFilms"] == []

    restored = gql(
        client,
        RESTORE_INFERRED_SEEN,
        {"input": {"screeningId": screening_id}},
        token=ALICE,
    )["restoreInferredSeen"]
    assert restored == {
        "__typename": "ScreeningResult",
        "screening": {"id": screening_id},
    }
    assert gql(client, VIEWER_SEEN, token=ALICE)["viewer"]["seenFilms"] == [
        {"id": film_id}
    ]


UNKNOWN_SCREENING = encode("Screening", "zzz")
UNKNOWN_FILM = encode("Film", "zzz")

# Four ways an id can fail to name the expected thing: malformed, a raw
# domain id (never looked up as one), the wrong Node type, or a well-formed
# id of the right type that simply does not exist.
BAD_SCREENING_IDS = [
    ("garbage", "garbage"),
    ("raw_domain_id", "a"),
    ("wrong_type", encode("Film", "film-a")),
    ("unknown", UNKNOWN_SCREENING),
]
BAD_FILM_IDS = [
    ("garbage", "garbage"),
    ("raw_domain_id", "film-a"),
    ("wrong_type", encode("Screening", "a")),
    ("unknown", UNKNOWN_FILM),
]
SCREENING_MUTATIONS = [
    ("recordTicket", RECORD_TICKET, "screeningId"),
    ("removeTicket", REMOVE_TICKET, "screeningId"),
    ("dismissInferredSeen", DISMISS_INFERRED_SEEN, "screeningId"),
    ("restoreInferredSeen", RESTORE_INFERRED_SEEN, "screeningId"),
]
FILM_MUTATIONS = [
    ("markSeen", MARK_SEEN, "filmId"),
    ("unmarkSeen", UNMARK_SEEN, "filmId"),
]

UNKNOWN_ID_CASES = [
    (mutation, field, bad_id)
    for _, mutation, field in SCREENING_MUTATIONS
    for _, bad_id in BAD_SCREENING_IDS
] + [
    (mutation, field, bad_id)
    for _, mutation, field in FILM_MUTATIONS
    for _, bad_id in BAD_FILM_IDS
]
UNKNOWN_ID_IDS = [
    f"{name}-{case_name}"
    for name, _, _ in SCREENING_MUTATIONS
    for case_name, _ in BAD_SCREENING_IDS
] + [
    f"{name}-{case_name}"
    for name, _, _ in FILM_MUTATIONS
    for case_name, _ in BAD_FILM_IDS
]


@pytest.mark.parametrize(
    ("mutation", "field", "bad_id"), UNKNOWN_ID_CASES, ids=UNKNOWN_ID_IDS
)
def test_unknown_ids_are_not_found(
    client: TestClient, mutation: str, field: str, bad_id: str
):
    result = _result(gql(client, mutation, {"input": {field: bad_id}}, token=ALICE))
    assert result["__typename"] == "NotFound"


SIGNED_OUT_CASES = [
    (RECORD_TICKET, {"screeningId": encode("Screening", "a")}),
    (REMOVE_TICKET, {"screeningId": encode("Screening", "a")}),
    (MARK_SEEN, {"filmId": encode("Film", "film-a")}),
    (UNMARK_SEEN, {"filmId": encode("Film", "film-a")}),
    (DISMISS_INFERRED_SEEN, {"screeningId": encode("Screening", "a")}),
    (RESTORE_INFERRED_SEEN, {"screeningId": encode("Screening", "a")}),
]
SIGNED_OUT_IDS = [
    "recordTicket",
    "removeTicket",
    "markSeen",
    "unmarkSeen",
    "dismissInferredSeen",
    "restoreInferredSeen",
]


@pytest.mark.parametrize(("mutation", "input_"), SIGNED_OUT_CASES, ids=SIGNED_OUT_IDS)
def test_signed_out_is_not_signed_in(
    client: TestClient, mutation: str, input_: dict[str, Any]
):
    result = _result(gql(client, mutation, {"input": input_}))
    assert result["__typename"] == "NotSignedIn"
