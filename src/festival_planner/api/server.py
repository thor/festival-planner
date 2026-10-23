"""Wires the API to the real adapters."""

import datetime
import logging
from collections.abc import Mapping

from starlette.applications import Starlette

from ..adapters.in_process.jobs import ThreadPoolJobRunner
from ..adapters.in_process.notifications import NullDraftSolvedNotifier
from ..adapters.jwt.verifier import (
    ISSUERS_ENV,
    JwtTokenVerifier,
    trusted_issuers_from_env,
)
from ..adapters.solver.cpsat import CpSatScheduleSolver
from ..adapters.sqlalchemy.database import open_database
from ..adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from ..domain.planner import Planner
from ..domain.programme_queries import ProgrammeQueries
from ..domain.solving import ScheduleSolver
from ..domain.users import user_for
from .app import ApiDependencies, create_app

logger = logging.getLogger(__name__)


def build_server(
    database: str | None,
    environ: Mapping[str, str],
    *,
    draft_wait_seconds: float = 2.0,
    solver: ScheduleSolver | None = None,
) -> Starlette:
    """The API on a migrated database, trusting the issuers in `environ`."""
    issuers = trusted_issuers_from_env(environ)
    if not issuers:
        logger.warning(
            "No token issuers are trusted (%s is unset); every token gets 401",
            ISSUERS_ENV,
        )
    verifier = JwtTokenVerifier(issuers)
    engine = open_database(database)
    jobs = ThreadPoolJobRunner()
    planner = Planner(
        lambda: SqlAlchemyUnitOfWork(engine),
        solver or CpSatScheduleSolver(),
        jobs,
        NullDraftSolvedNotifier(),
        clock=lambda: datetime.datetime.now(datetime.UTC),
        wait_seconds=draft_wait_seconds,
    )
    deps = ApiDependencies(
        planner=planner,
        programme=ProgrammeQueries(lambda: SqlAlchemyUnitOfWork(engine)),
        verifier=verifier,
        users=lambda i: user_for(SqlAlchemyUnitOfWork(engine), i.issuer, i.subject),
    )

    def startup() -> None:
        resumed = planner.resume_solving()
        logger.info("Resumed solving %d Draft(s)", resumed)

    def shutdown() -> None:
        try:
            jobs.shutdown(wait=True, cancel_futures=True)
        finally:
            engine.dispose()

    return create_app(deps, on_startup=startup, on_shutdown=shutdown)
