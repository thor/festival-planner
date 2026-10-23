"""The API end to end: the real server on a SQLite file, with local tokens."""

import datetime
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from sqlalchemy import Engine
from starlette.testclient import TestClient

from festival_planner.adapters.in_process.jobs import ImmediateJobRunner
from festival_planner.adapters.in_process.notifications import NullDraftSolvedNotifier
from festival_planner.adapters.local_issuer.issuer import LocalIssuer
from festival_planner.adapters.solver.cpsat import CpSatScheduleSolver
from festival_planner.adapters.sqlalchemy.database import create_engine_for, migrate
from festival_planner.adapters.sqlalchemy.tests.test_planner_on_sqlite import (
    Programme,
    Venues,
)
from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.api.ids import encode
from festival_planner.api.server import build_server
from festival_planner.api.tests.support import gql
from festival_planner.domain.change_sets import ChangeSet
from festival_planner.domain.drafts import Draft, DraftId, DraftStatus
from festival_planner.domain.festival import FestivalId
from festival_planner.domain.ingestion import ingest_programme, ingest_venues
from festival_planner.domain.planner import Planner
from festival_planner.domain.solving import SolveRequest, SolveResult
from festival_planner.domain.users import LOCAL_ISSUER, User, user_for

SLUG = "fest-2030"
SUBJECT = "thor"

CREATE = (
    "mutation ($input: CreateDraftInput!) { createDraft(input: $input) { "
    "__typename ... on DraftResult { draft { id status } } } }"
)
ACCEPT = (
    "mutation ($input: DraftInput!) { acceptDraft(input: $input) { "
    "__typename ... on ScheduleResult { schedule { number } } } }"
)
DRAFT_STATUS = "query ($id: ID!) { node(id: $id) { ... on Draft { status } } }"
PLANNING = (
    "query ($festivalId: ID!) { viewer { planning(festivalId: $festivalId) { "
    "activeSchedule { number } drafts { id } } } }"
)


class _Setup:
    """A migrated SQLite file with a Festival and Venues, and a local issuer."""

    def __init__(self, tmp_path: Path) -> None:
        self.database = tmp_path / "db.sqlite"
        self.issuer = LocalIssuer(tmp_path / "issuer")
        self.issuer.init()
        self.environ = {
            "FESTIVAL_PLANNER_ISSUERS": json.dumps(
                [self.issuer.trusted_issuer().model_dump(mode="json")]
            )
        }
        engine = self.engine()
        try:
            migrate(engine)
            ingest_venues(SqlAlchemyUnitOfWork(engine), Venues(), Venues())
            ingest_programme(SqlAlchemyUnitOfWork(engine), Programme())
            with SqlAlchemyUnitOfWork(engine) as uow:
                festival = uow.festivals.by_slug(SLUG)
                assert festival is not None
                self.festival_id: FestivalId = festival.id
        finally:
            engine.dispose()

    def engine(self) -> Engine:
        return create_engine_for(f"sqlite:///{self.database}")

    def user(self, engine: Engine) -> User:
        return user_for(SqlAlchemyUnitOfWork(engine), LOCAL_ISSUER, SUBJECT)

    def token(self) -> str:
        return self.issuer.issue(SUBJECT)

    @property
    def festival_global_id(self) -> str:
        return encode("Festival", self.festival_id)


def _create_draft(client: TestClient, setup: _Setup, token: str) -> dict[str, Any]:
    data = gql(
        client,
        CREATE,
        {"input": {"festivalId": setup.festival_global_id}},
        token=token,
    )
    result = data["createDraft"]
    assert result["__typename"] == "DraftResult", result
    return result["draft"]


def _poll_until_ready(client: TestClient, draft_id: str, token: str) -> None:
    """Polls `node(id)` every 50 ms, for at most 10 s, until READY."""
    deadline = time.monotonic() + 10
    status = None
    while time.monotonic() < deadline:
        node = gql(client, DRAFT_STATUS, {"id": draft_id}, token=token)["node"]
        assert node is not None, f"Draft {draft_id} is not visible"
        status = node["status"]
        if status == "READY":
            return
        time.sleep(0.05)
    raise AssertionError(f"Draft {draft_id} is still {status} after 10 s")


def test_a_draft_is_created_polled_and_accepted(tmp_path: Path):
    setup = _Setup(tmp_path)
    token = setup.token()
    app = build_server(str(setup.database), setup.environ, draft_wait_seconds=0)
    with TestClient(app) as c:
        draft = _create_draft(c, setup, token)
        assert draft["status"] in ("SOLVING", "READY")
        _poll_until_ready(c, draft["id"], token)

        accepted = gql(c, ACCEPT, {"input": {"draftId": draft["id"]}}, token=token)
        assert accepted["acceptDraft"]["__typename"] == "ScheduleResult"

        planning = gql(
            c, PLANNING, {"festivalId": setup.festival_global_id}, token=token
        )
        assert planning["viewer"]["planning"]["activeSchedule"] == {"number": 1}


class _GatedSolver:
    """CP-SAT, but only once `gate` is set; sets `started` when called."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.gate = threading.Event()
        self._solver = CpSatScheduleSolver()

    def solve(self, request: SolveRequest) -> SolveResult:
        self.started.set()
        self.gate.wait(timeout=30)
        return self._solver.solve(request)


def test_a_slow_solve_does_not_block_other_requests(tmp_path: Path):
    setup = _Setup(tmp_path)
    token = setup.token()
    solver = _GatedSolver()
    app = build_server(
        str(setup.database), setup.environ, draft_wait_seconds=5, solver=solver
    )
    # One TestClient: its portal runs both requests on the same event loop.
    with TestClient(app) as c, ThreadPoolExecutor(max_workers=1) as pool:
        try:
            created = pool.submit(_create_draft, c, setup, token)
            assert solver.started.wait(timeout=10), "the solve never started"

            began = time.monotonic()
            festivals = gql(c, "{ festivals { slug } }")
            elapsed = time.monotonic() - began

            assert festivals == {"festivals": [{"slug": SLUG}]}
            assert elapsed < 1, f"took {elapsed:.2f} s"
            assert not created.done(), "createDraft did not wait for the solve"
        finally:
            solver.gate.set()
        assert created.result(timeout=30)["status"] == "READY"


def test_drafts_left_solving_are_resumed_at_startup(tmp_path: Path):
    setup = _Setup(tmp_path)
    engine = setup.engine()
    try:
        user = setup.user(engine)
        draft_id = DraftId("left-solving")
        with SqlAlchemyUnitOfWork(engine) as uow:
            uow.planning.save_draft(
                Draft(
                    id=draft_id,
                    user_id=user.id,
                    festival_id=setup.festival_id,
                    change_set=ChangeSet(),
                    base_schedule_id=None,
                    created_at=datetime.datetime.now(datetime.UTC),
                    status=DraftStatus.SOLVING,
                )
            )
            uow.commit()
    finally:
        engine.dispose()

    token = setup.token()
    app = build_server(str(setup.database), setup.environ)
    with TestClient(app) as c:
        _poll_until_ready(c, encode("Draft", draft_id), token)


def test_the_cli_user_and_a_local_token_are_one_user(tmp_path: Path):
    setup = _Setup(tmp_path)
    engine = setup.engine()
    try:
        user = setup.user(engine)
        planner = Planner(
            lambda: SqlAlchemyUnitOfWork(engine),
            CpSatScheduleSolver(),
            ImmediateJobRunner(),
            NullDraftSolvedNotifier(),
            clock=lambda: datetime.datetime.now(datetime.UTC),
        )
        view = planner.create_draft(user.id, SLUG)
    finally:
        engine.dispose()

    app = build_server(str(setup.database), setup.environ)
    with TestClient(app) as c:
        planning = gql(
            c, PLANNING, {"festivalId": setup.festival_global_id}, token=setup.token()
        )
    drafts = planning["viewer"]["planning"]["drafts"]
    assert drafts == [{"id": encode("Draft", view.draft.id)}]
