import datetime
import zoneinfo

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from festival_planner.adapters.sqlalchemy.tables import (
    FestivalRow,
    FilmRow,
    ProgrammeEntryRow,
    ScheduleRow,
    ScreeningRow,
    UserRow,
    VenueRow,
)

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


def _screening(session, start):
    session.add_all(
        [
            FestivalRow(
                id="f",
                slug="f-2025",
                name="F",
                start_date=datetime.date(2025, 11, 6),
                end_date=datetime.date(2025, 11, 16),
                time_zone="Europe/Oslo",
            ),
            FilmRow(id="m", title="A", year=2025, match_key="a"),
            VenueRow(id="v", name="Vika"),
            ProgrammeEntryRow(
                id="e", festival_id="f", source_key="film/a", film_id="m", title="A"
            ),
        ]
    )
    # Rows have no relationships between them, so the unit of work does not
    # order their inserts by foreign key: flush the parents first.
    session.flush()
    session.add(
        ScreeningRow(
            id="s",
            programme_entry_id="e",
            venue_id="v",
            start_time=start,
            end_time=start + datetime.timedelta(hours=2),
        )
    )
    session.commit()


def test_times_are_stored_as_utc_and_read_back_aware(engine):
    with Session(engine) as session:
        _screening(session, datetime.datetime(2025, 11, 8, 18, 0, tzinfo=OSLO))
    with Session(engine) as session:
        row = session.scalars(select(ScreeningRow)).one()
        assert row.start_time.tzinfo == datetime.UTC
        assert row.start_time == datetime.datetime(
            2025, 11, 8, 17, 0, tzinfo=datetime.UTC
        )
        assert row.withdrawn is False


def test_naive_times_are_rejected(engine):
    with Session(engine) as session, pytest.raises(StatementError, match="naive"):
        _screening(session, datetime.datetime(2025, 11, 8, 18, 0))


def test_a_user_is_unique_per_issuer_and_subject(engine):
    with Session(engine) as session:
        session.add_all(
            [
                UserRow(id="u1", issuer="local", subject="thor"),
                UserRow(id="u2", issuer="local", subject="thor"),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_a_schedule_number_is_unique_per_user_and_festival(engine):
    with Session(engine) as session:
        session.add(UserRow(id="u", issuer="local", subject="thor"))
        session.add(
            FestivalRow(
                id="f",
                slug="f",
                name="F",
                time_zone="Europe/Oslo",
                start_date=datetime.date(2025, 11, 1),
                end_date=datetime.date(2025, 11, 9),
            )
        )
        session.flush()
        now = datetime.datetime(2025, 11, 1, tzinfo=datetime.UTC)
        for schedule_id in ("s1", "s2"):
            session.add(
                ScheduleRow(
                    id=schedule_id,
                    user_id="u",
                    festival_id="f",
                    number=1,
                    score=0.0,
                    change_set="{}",
                    accepted_at=now,
                )
            )
        with pytest.raises(IntegrityError):
            session.commit()
