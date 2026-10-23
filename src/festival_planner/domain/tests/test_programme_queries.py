import datetime
import zoneinfo
from typing import NoReturn

import pytest

from festival_planner.domain.festival import (
    Festival,
    FestivalId,
    FestivalSeries,
    FestivalSeriesId,
)
from festival_planner.domain.ingestion import UnitOfWork
from festival_planner.domain.programme import (
    Film,
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
)
from festival_planner.domain.programme_queries import ProgrammeQueries

from .fakes import InMemoryUnitOfWork

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


def _at(hour: int) -> datetime.datetime:
    return datetime.datetime(2025, 11, 8, hour, tzinfo=OSLO)


SERIES = FestivalSeries(id=FestivalSeriesId("series"), slug="a-fests", name="A Fests")
FESTIVAL_A = Festival(
    id=FestivalId("a"),
    slug="a-fest",
    name="A Fest",
    start_date=datetime.date(2025, 11, 1),
    end_date=datetime.date(2025, 11, 10),
    time_zone="Europe/Oslo",
    series_id=FestivalSeriesId("series"),
)
FESTIVAL_B = Festival(
    id=FestivalId("b"),
    slug="b-fest",
    name="B Fest",
    start_date=datetime.date(2025, 11, 20),
    end_date=datetime.date(2025, 11, 30),
    time_zone="Europe/Oslo",
)
VENUE = Venue(id=VenueId("v"), name="Venue")
FILM_APPLE = Film(id=FilmId("f-apple"), title="apple")

ENTRY_APPLE = ProgrammeEntry(
    id=ProgrammeEntryId("apple"), film_id=FilmId("f-apple"), title="apple"
)
ENTRY_BANANA = ProgrammeEntry(
    id=ProgrammeEntryId("banana"), film_id=FilmId("f-banana"), title="Banana"
)
ENTRY_OEDIPUS = ProgrammeEntry(
    id=ProgrammeEntryId("oedipus"), film_id=FilmId("f-oedipus"), title="Ödipus"
)

SCREENING_ACTIVE = Screening(
    id=ScreeningId("active"),
    programme_entry_id=ProgrammeEntryId("apple"),
    venue_id=VenueId("v"),
    start_time=_at(18),
    end_time=_at(20),
)
SCREENING_WITHDRAWN = Screening(
    id=ScreeningId("withdrawn"),
    programme_entry_id=ProgrammeEntryId("banana"),
    venue_id=VenueId("v"),
    start_time=_at(21),
    end_time=_at(22),
    withdrawn=True,
)
SCREENING_EARLY = Screening(
    id=ScreeningId("early"),
    programme_entry_id=ProgrammeEntryId("apple"),
    venue_id=VenueId("v"),
    start_time=_at(16),
    end_time=_at(17),
)


def _seeded_uow() -> InMemoryUnitOfWork:
    """Seeded out of the expected output order, so a test that only reflects
    insertion order (instead of actually sorting) fails."""
    uow = InMemoryUnitOfWork()
    with uow:
        uow.festivals.save_series(SERIES)
        uow.festivals.save(FESTIVAL_B)
        uow.festivals.save(FESTIVAL_A)
        uow.venues.save(VENUE)
        uow.films.save(FILM_APPLE)
        for entry in (ENTRY_OEDIPUS, ENTRY_BANANA, ENTRY_APPLE):
            uow.programme.save_entry(FestivalId("a"), entry.id, entry)
        uow.programme.save_screening(SCREENING_WITHDRAWN)
        uow.programme.save_screening(SCREENING_ACTIVE)
        uow.programme.save_screening(SCREENING_EARLY)
        uow.commit()
    return uow


@pytest.fixture
def queries() -> ProgrammeQueries:
    uow = _seeded_uow()
    return ProgrammeQueries(lambda: uow)


def test_festivals_are_ordered_by_start_date(queries: ProgrammeQueries):
    assert [f.slug for f in queries.festivals()] == ["a-fest", "b-fest"]


def test_an_unknown_festival_slug_is_none(queries: ProgrammeQueries):
    assert queries.festival("nope") is None
    assert queries.festival("a-fest") == FESTIVAL_A


def test_programme_entries_are_ordered_by_title_ignoring_case(
    queries: ProgrammeQueries,
):
    entries = queries.programme_entries(FestivalId("a"))
    assert [e.title for e in entries] == ["apple", "Banana", "Ödipus"]


def test_withdrawn_screenings_are_left_out_unless_asked(queries: ProgrammeQueries):
    active_only = queries.screenings(FestivalId("a"), include_withdrawn=False)
    assert [s.id for s in active_only] == ["early", "active"]
    both = queries.screenings(FestivalId("a"), include_withdrawn=True)
    assert [s.id for s in both] == ["early", "active", "withdrawn"]


def test_screenings_of_entries_cover_every_requested_entry(queries: ProgrammeQueries):
    result = queries.screenings_of_entries(
        [ProgrammeEntryId("apple"), ProgrammeEntryId("oedipus")],
        include_withdrawn=True,
    )
    assert set(result) == {ProgrammeEntryId("apple"), ProgrammeEntryId("oedipus")}
    assert [s.id for s in result[ProgrammeEntryId("apple")]] == ["early", "active"]
    assert result[ProgrammeEntryId("oedipus")] == ()


def test_screenings_of_entries_excludes_withdrawn_unless_asked(
    queries: ProgrammeQueries,
):
    result = queries.screenings_of_entries(
        [ProgrammeEntryId("banana")], include_withdrawn=False
    )
    assert result[ProgrammeEntryId("banana")] == ()
    result = queries.screenings_of_entries(
        [ProgrammeEntryId("banana")], include_withdrawn=True
    )
    assert [s.id for s in result[ProgrammeEntryId("banana")]] == ["withdrawn"]


def _never(*_: object) -> NoReturn:
    pytest.fail("opened a unit of work for an empty id collection")


def _no_uow() -> UnitOfWork:
    return _never()


def test_festivals_by_id_skips_unknown_ids(queries: ProgrammeQueries):
    result = queries.festivals_by_id([FestivalId("a"), FestivalId("missing")])
    assert result == {FestivalId("a"): FESTIVAL_A}


def test_festivals_by_id_with_no_ids_does_not_query():
    result = ProgrammeQueries(_no_uow).festivals_by_id([])
    assert result == {}


def test_series_by_id_skips_unknown_ids(queries: ProgrammeQueries):
    result = queries.series_by_id([FestivalSeriesId("series"), FestivalSeriesId("x")])
    assert result == {FestivalSeriesId("series"): SERIES}


def test_series_by_id_with_no_ids_does_not_query():
    result = ProgrammeQueries(_no_uow).series_by_id([])
    assert result == {}


def test_venues_by_id_skips_unknown_ids(queries: ProgrammeQueries):
    result = queries.venues_by_id([VenueId("v"), VenueId("x")])
    assert result == {VenueId("v"): VENUE}


def test_venues_by_id_with_no_ids_does_not_query():
    result = ProgrammeQueries(_no_uow).venues_by_id([])
    assert result == {}


def test_films_by_id_skips_unknown_ids(queries: ProgrammeQueries):
    result = queries.films_by_id([FilmId("f-apple"), FilmId("missing")])
    assert result == {FilmId("f-apple"): FILM_APPLE}


def test_films_by_id_with_no_ids_does_not_query():
    result = ProgrammeQueries(_no_uow).films_by_id([])
    assert result == {}


def test_programme_entries_by_id_skips_unknown_ids(queries: ProgrammeQueries):
    result = queries.programme_entries_by_id(
        [ProgrammeEntryId("apple"), ProgrammeEntryId("missing")]
    )
    assert result == {ProgrammeEntryId("apple"): ENTRY_APPLE}


def test_programme_entries_by_id_with_no_ids_does_not_query():
    result = ProgrammeQueries(_no_uow).programme_entries_by_id([])
    assert result == {}


def test_screenings_by_id_includes_withdrawn_and_skips_unknown_ids(
    queries: ProgrammeQueries,
):
    result = queries.screenings_by_id([ScreeningId("withdrawn"), ScreeningId("x")])
    assert result == {ScreeningId("withdrawn"): SCREENING_WITHDRAWN}


def test_screenings_by_id_with_no_ids_does_not_query():
    result = ProgrammeQueries(_no_uow).screenings_by_id([])
    assert result == {}


def test_screenings_of_entries_with_no_ids_does_not_query():
    result = ProgrammeQueries(_no_uow).screenings_of_entries([], include_withdrawn=True)
    assert result == {}


def test_venues_are_ordered_by_name_then_id():
    uow = _seeded_uow()
    with uow:
        uow.venues.save(Venue(id=VenueId("a-venue"), name="Venue"))
        uow.commit()
    q = ProgrammeQueries(lambda: uow)
    assert [v.id for v in q.venues()] == ["a-venue", "v"]
