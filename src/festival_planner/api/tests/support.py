"""Helpers for API tests: an app over the in-memory fakes, and a GraphQL call."""

import datetime
from collections.abc import Mapping
from typing import Any

from starlette.testclient import TestClient

from festival_planner.api.app import ApiDependencies, create_app
from festival_planner.domain.identity import Identity, InvalidTokenError
from festival_planner.domain.jobs import JobRunner
from festival_planner.domain.planner import Planner
from festival_planner.domain.programme_queries import ProgrammeQueries
from festival_planner.domain.solving import ScheduleSolver
from festival_planner.domain.tests.fakes import (
    GreedySolver,
    InlineJobRunner,
    InMemoryUnitOfWork,
    RecordingNotifier,
    TickingClock,
    sequential_ids,
)
from festival_planner.domain.users import user_for

ALICE = "alice-token"
BOB = "bob-token"

DEFAULT_TOKENS: Mapping[str, Identity] = {
    ALICE: Identity(issuer="local", subject="alice"),
    BOB: Identity(issuer="local", subject="bob"),
}


class FakeVerifier:
    """A TokenVerifier backed by a dict of token to Identity."""

    def __init__(self, tokens: Mapping[str, Identity]) -> None:
        self.tokens = dict(tokens)
        self.verified: list[str] = []

    def verify(self, token: str) -> Identity:
        self.verified.append(token)
        try:
            return self.tokens[token]
        except KeyError:
            raise InvalidTokenError("unknown token") from None


def dependencies(
    uow: InMemoryUnitOfWork,
    *,
    tokens: Mapping[str, Identity] = DEFAULT_TOKENS,
    job_runner: JobRunner | None = None,
    solver: ScheduleSolver | None = None,
) -> ApiDependencies:
    """ApiDependencies over the in-memory fake."""
    planner = Planner(
        lambda: uow,
        solver or GreedySolver(),
        job_runner or InlineJobRunner(),
        RecordingNotifier(),
        clock=TickingClock(datetime.datetime(2026, 1, 1, 9, tzinfo=datetime.UTC)),
        new_id=sequential_ids(),
    )
    return ApiDependencies(
        planner=planner,
        programme=ProgrammeQueries(lambda: uow),
        verifier=FakeVerifier(tokens),
        users=lambda i: user_for(uow, i.issuer, i.subject),
    )


def api_client(
    uow: InMemoryUnitOfWork,
    *,
    tokens: Mapping[str, Identity] = DEFAULT_TOKENS,
    job_runner: JobRunner | None = None,
    solver: ScheduleSolver | None = None,
) -> TestClient:
    """A TestClient on the API over the in-memory fake."""
    return TestClient(
        create_app(
            dependencies(uow, tokens=tokens, job_runner=job_runner, solver=solver)
        )
    )


def gql(
    client: TestClient,
    query: str,
    variables: Mapping[str, Any] | None = None,
    *,
    token: str | None = None,
) -> dict[str, Any]:
    """The `data` of a GraphQL call that must succeed with no errors."""
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    response = client.post(
        "/graphql",
        json={"query": query, "variables": dict(variables or {})},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "errors" not in body, body["errors"]
    return body["data"]
