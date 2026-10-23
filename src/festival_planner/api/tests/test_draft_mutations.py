import datetime
import logging
from collections.abc import Iterable
from typing import Any

import pytest
from starlette.testclient import TestClient

from festival_planner.api.errors import ChangeSetProblemCode
from festival_planner.api.ids import encode
from festival_planner.api.tests.support import ALICE, BOB, api_client, gql
from festival_planner.domain.change_sets import ProblemCode
from festival_planner.domain.festival import Festival, FestivalId
from festival_planner.domain.programme import Film, FilmId, Venue, VenueId
from festival_planner.domain.tests.builders import entry, screening
from festival_planner.domain.tests.fakes import DeferredJobRunner, InMemoryUnitOfWork

DAY = datetime.date(2030, 11, 8)
F = FestivalId("f")
FESTIVAL_ID = encode("Festival", F)


def _seeded() -> InMemoryUnitOfWork:
    uow = InMemoryUnitOfWork()
    with uow:
        uow.festivals.save(
            Festival(
                id=F,
                slug="fest-2030",
                name="Fest",
                start_date=DAY,
                end_date=DAY,
                time_zone="Europe/Oslo",
            )
        )
        uow.venues.save(Venue(id=VenueId("A"), name="A"))
        for e in ("a", "b"):
            uow.films.save(Film(id=FilmId(f"film-{e}"), title=e))
            uow.programme.save_entry(F, e, entry(e))
        uow.programme.save_screening(screening("a", "14:00", "16:00", day=DAY))
        uow.programme.save_screening(screening("b", "18:00", "20:00", day=DAY))
        uow.commit()
    return uow


@pytest.fixture
def client() -> Iterable[TestClient]:
    with api_client(_seeded()) as c:
        yield c


NOT_SIGNED_IN = "... on NotSignedIn { message } "
NOT_FOUND = "... on NotFound { message } "
INVALID = "... on InvalidChangeSet { problems { code items message } } "

CREATE = (
    "mutation ($input: CreateDraftInput!) { createDraft(input: $input) { "
    "__typename ... on DraftResult { draft { id status festival { slug } "
    "changeSet { __typename } } } " + INVALID + NOT_FOUND + NOT_SIGNED_IN + "} }"
)
RESOLVE = (
    "mutation ($input: DraftInput!) { resolveDraft(input: $input) { "
    "__typename ... on DraftResult { draft { id status notes } } "
    "... on DraftStillSolving { message } "
    + INVALID
    + NOT_FOUND
    + NOT_SIGNED_IN
    + "} }"
)
ACCEPT = (
    "mutation ($input: DraftInput!) { acceptDraft(input: $input) { "
    "__typename ... on ScheduleResult { schedule { number screenings { id } } } "
    "... on DraftNotAcceptable { message } " + NOT_FOUND + NOT_SIGNED_IN + "} }"
)
DISCARD = (
    "mutation ($input: DraftInput!) { discardDraft(input: $input) { "
    "__typename ... on Discarded { draftId } " + NOT_FOUND + NOT_SIGNED_IN + "} }"
)
ON_DRAFT = pytest.mark.parametrize(
    "mutation", [RESOLVE, ACCEPT, DISCARD], ids=["resolve", "accept", "discard"]
)
DRAFT_NODE = "query ($id: ID!) { node(id: $id) { id } }"


def _commit(screening_id: str) -> dict[str, Any]:
    return {
        "addScreeningCommitment": {"screeningId": encode("Screening", screening_id)}
    }


def _create(
    client: TestClient,
    change_set: list[dict[str, Any]] | None = None,
    *,
    festival_id: str = FESTIVAL_ID,
    token: str | None = ALICE,
) -> dict[str, Any]:
    variables = {"input": {"festivalId": festival_id, "changeSet": change_set or []}}
    return gql(client, CREATE, variables, token=token)["createDraft"]


def _draft_id(
    client: TestClient, change_set: list[dict[str, Any]] | None = None
) -> str:
    result = _create(client, change_set)
    assert result["__typename"] == "DraftResult", result
    return result["draft"]["id"]


def _on_draft(
    client: TestClient, mutation: str, draft_id: str, *, token: str = ALICE
) -> dict[str, Any]:
    data = gql(client, mutation, {"input": {"draftId": draft_id}}, token=token)
    [result] = data.values()
    return result


def test_creating_a_draft_signed_out_is_not_signed_in(client: TestClient):
    assert _create(client, token=None) == {
        "__typename": "NotSignedIn",
        "message": "Sign in to do this",
    }


def test_creating_a_draft_returns_it_solved(client: TestClient):
    result = _create(client, [_commit("a")])
    assert result["__typename"] == "DraftResult"
    draft = result["draft"]
    assert draft["status"] == "READY"
    assert draft["festival"] == {"slug": "fest-2030"}
    assert draft["changeSet"] == [{"__typename": "AddScreeningCommitment"}]
    node = gql(client, DRAFT_NODE, {"id": draft["id"]}, token=ALICE)["node"]
    assert node == {"id": draft["id"]}


def test_creating_a_draft_with_an_unknown_screening_is_invalid(client: TestClient):
    result = _create(client, [_commit("zzz")])
    assert result["__typename"] == "InvalidChangeSet"
    [problem] = result["problems"]
    assert problem["code"] == "UNKNOWN_ID"
    assert problem["items"] == [0]


def test_a_raw_domain_id_is_an_unknown_id(client: TestClient):
    raw = {"addScreeningCommitment": {"screeningId": "a"}}
    result = _create(client, [raw])
    assert result["__typename"] == "InvalidChangeSet"
    [problem] = result["problems"]
    assert (problem["code"], problem["items"]) == ("UNKNOWN_ID", [0])


def test_an_explicit_null_weight_resets(client: TestClient):
    entry_id = encode("ProgrammeEntry", "a")
    weight = {"setProgrammeEntryWeight": {"programmeEntryId": entry_id, "weight": 2.0}}
    accepted = _on_draft(client, ACCEPT, _draft_id(client, [weight]))
    assert accepted["__typename"] == "ScheduleResult"
    reset = {"setProgrammeEntryWeight": {"programmeEntryId": entry_id, "weight": None}}
    query = (
        "mutation ($input: CreateDraftInput!) { createDraft(input: $input) { "
        "... on DraftResult { draft { changeSet { "
        "... on SetProgrammeEntryWeight { programmeEntry { id } weight } } } } } }"
    )
    variables = {"input": {"festivalId": FESTIVAL_ID, "changeSet": [reset]}}
    draft = gql(client, query, variables, token=ALICE)["createDraft"]["draft"]
    assert draft["changeSet"] == [{"programmeEntry": {"id": entry_id}, "weight": None}]


def test_an_invalid_item_is_an_invalid_change_set(client: TestClient):
    date_range = {"setDateRange": {"startDate": "2030-11-09", "endDate": "2030-11-08"}}
    result = _create(client, [_commit("a"), date_range])
    assert result["__typename"] == "InvalidChangeSet"
    [problem] = result["problems"]
    assert (problem["code"], problem["items"]) == ("INVALID_ITEM", [1])


@pytest.mark.parametrize(
    "item",
    [{}, {**_commit("a"), "setEventWeight": {"weight": 1.0}}],
    ids=["none", "two"],
)
def test_an_item_with_two_fields_or_none_is_a_validation_error(
    client: TestClient, item: dict[str, Any], caplog: pytest.LogCaptureFixture
):
    with caplog.at_level(logging.DEBUG):
        response = client.post(
            "/graphql",
            json={
                "query": CREATE,
                "variables": {
                    "input": {"festivalId": FESTIVAL_ID, "changeSet": [item]}
                },
            },
            headers={"Authorization": f"Bearer {ALICE}"},
        )
    assert response.status_code == 200
    body = response.json()
    [error] = body["errors"]
    assert "exactly one key" in error["message"]
    assert body["data"] is None
    assert not [r for r in caplog.records if r.exc_info]


@pytest.mark.parametrize(
    "festival_id", ["garbage", encode("Venue", "A"), encode("Festival", "nope")]
)
def test_creating_a_draft_for_an_unknown_festival_is_not_found(
    client: TestClient, festival_id: str
):
    result = _create(client, festival_id=festival_id)
    assert result["__typename"] == "NotFound"
    assert result["message"]


def test_a_still_solving_draft_cannot_be_resolved():
    with api_client(_seeded(), job_runner=DeferredJobRunner()) as client:
        result = _create(client)
        assert result["draft"]["status"] == "SOLVING"
        resolved = _on_draft(client, RESOLVE, result["draft"]["id"])
    assert resolved["__typename"] == "DraftStillSolving"
    assert resolved["message"]


def test_resolving_solves_the_draft_again(client: TestClient):
    draft_id = _draft_id(client, [_commit("a")])
    resolved = _on_draft(client, RESOLVE, draft_id)
    assert resolved == {
        "__typename": "DraftResult",
        "draft": {"id": draft_id, "status": "READY", "notes": []},
    }


def test_accepting_returns_the_schedule_and_removes_the_draft(client: TestClient):
    draft_id = _draft_id(client, [_commit("a")])
    accepted = _on_draft(client, ACCEPT, draft_id)
    assert accepted["__typename"] == "ScheduleResult"
    assert accepted["schedule"]["number"] == 1
    assert {"id": encode("Screening", "a")} in accepted["schedule"]["screenings"]
    assert gql(client, DRAFT_NODE, {"id": draft_id}, token=ALICE)["node"] is None


def test_accepting_a_stale_draft_is_not_acceptable(client: TestClient):
    first, second = _draft_id(client), _draft_id(client, [_commit("a")])
    assert _on_draft(client, ACCEPT, first)["__typename"] == "ScheduleResult"
    result = _on_draft(client, ACCEPT, second)
    assert result["__typename"] == "DraftNotAcceptable"
    assert "Stale" in result["message"]


def test_discarding_removes_the_draft(client: TestClient):
    draft_id = _draft_id(client)
    assert _on_draft(client, DISCARD, draft_id) == {
        "__typename": "Discarded",
        "draftId": draft_id,
    }
    assert gql(client, DRAFT_NODE, {"id": draft_id}, token=ALICE)["node"] is None
    assert _on_draft(client, DISCARD, draft_id)["__typename"] == "NotFound"


@ON_DRAFT
def test_another_users_draft_is_not_found(client: TestClient, mutation: str):
    draft_id = _draft_id(client)
    assert _on_draft(client, mutation, draft_id, token=BOB)["__typename"] == "NotFound"
    assert gql(client, DRAFT_NODE, {"id": draft_id}, token=ALICE)["node"] is not None


@ON_DRAFT
@pytest.mark.parametrize("draft_id", ["garbage", encode("Schedule", "x")])
def test_an_undecodable_draft_id_is_not_found(
    client: TestClient, mutation: str, draft_id: str
):
    assert _on_draft(client, mutation, draft_id)["__typename"] == "NotFound"


@ON_DRAFT
def test_draft_mutations_signed_out_are_not_signed_in(
    client: TestClient, mutation: str
):
    data = gql(client, mutation, {"input": {"draftId": "x"}})
    [result] = data.values()
    assert result["__typename"] == "NotSignedIn"


def test_the_problem_codes_match_the_domain():
    assert [m.value for m in ChangeSetProblemCode] == [m.value for m in ProblemCode]
