import datetime
import zoneinfo

import pytest
from sqlalchemy import select
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from festival_planner.adapters.sqlalchemy.tables import (
    FestivalRow,
    FilmRow,
    ProgrammeEntryRow,
    ScreeningRow,
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
