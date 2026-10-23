"""The Planner on the real SQLite stack, with background jobs."""

import datetime
import zoneinfo

from festival_planner.adapters.in_process.jobs import ThreadPoolJobRunner
from festival_planner.adapters.in_process.notifications import NullDraftSolvedNotifier
from festival_planner.adapters.solver.cpsat import CpSatScheduleSolver
from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.domain.change_sets import ChangeSet, SetProgrammeEntryWeight
from festival_planner.domain.drafts import DraftStatus
from festival_planner.domain.ingestion import (
    SourceEntry,
    SourceFestival,
    SourceProgramme,
    SourceRoute,
    SourceScreening,
    SourceVenue,
    ingest_programme,
    ingest_venues,
)
from festival_planner.domain.planner import Planner
from festival_planner.domain.travel import DEFAULT_TRANSPORT_MODE
from festival_planner.domain.users import LOCAL_ISSUER, user_for

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


def at(hour: int) -> datetime.datetime:
    return datetime.datetime(2030, 11, 8, hour, tzinfo=OSLO)


class Venues:
    def venues(self):
        return (SourceVenue(name="Vika"), SourceVenue(name="Vega"))

    def routes(self, venues):
        return tuple(
            SourceRoute(
                from_venue=a, to_venue=b, mode=DEFAULT_TRANSPORT_MODE, minutes=15
            )
            for a, b in (("Vika", "Vega"), ("Vega", "Vika"))
        )


class Programme:
    def fetch(self):
        return SourceProgramme(
            festival=SourceFestival(
                slug="fest-2030", name="Fest", time_zone="Europe/Oslo"
            ),
            entries=tuple(
                SourceEntry(
                    source_key=key,
                    title=key,
                    screenings=(
                        SourceScreening(
                            venue_name=venue, start_time=at(h), end_time=at(h + 2)
                        ),
                    ),
                )
                for key, venue, h in (
                    ("a", "Vika", 14),
                    ("b", "Vega", 15),
                    ("c", "Vika", 18),
                )
            ),
        )


def test_drafts_solve_in_the_background_and_can_be_accepted(engine):
    ingest_venues(SqlAlchemyUnitOfWork(engine), Venues(), Venues())
    ingest_programme(SqlAlchemyUnitOfWork(engine), Programme())
    user = user_for(SqlAlchemyUnitOfWork(engine), LOCAL_ISSUER, "tester")
    jobs = ThreadPoolJobRunner()
    try:
        planner = Planner(
            lambda: SqlAlchemyUnitOfWork(engine),
            CpSatScheduleSolver(),
            jobs,
            NullDraftSolvedNotifier(),
            clock=lambda: datetime.datetime.now(datetime.UTC),
            wait_seconds=30,
        )
        with SqlAlchemyUnitOfWork(engine) as uow:
            festival = uow.festivals.by_slug("fest-2030")
            assert festival is not None
            b_id = uow.programme.entries(festival.id)["b"].id
        views = [
            planner.create_draft(
                user.id,
                "fest-2030",
                ChangeSet(
                    items=(SetProgrammeEntryWeight(programme_entry_id=b_id, weight=w),)
                ),
            )
            for w in (2.0, 3.0)
        ]
        assert all(v.draft.status is DraftStatus.READY for v in views)
        schedule = planner.accept(user.id, views[0].draft.id)
        assert len(schedule.screening_ids) == 2
        assert planner.draft(user.id, views[1].draft.id).stale
    finally:
        jobs.shutdown()
