import datetime

import pytest

from festival_planner.domain.ingestion import (
    IngestionError,
    ProgrammeIngestion,
    SourceEntry,
    SourceFestival,
    SourceProgramme,
    SourceScreening,
    SourceSeries,
    UnknownVenuesError,
    ingest_programme,
)
from festival_planner.domain.programme import Event, Venue

from .builders import at
from .fakes import InMemoryUnitOfWork
from .fakes import sequential_ids as ids


class StaticSource:
    def __init__(self, programme: SourceProgramme):
        self.programme = programme

    def fetch(self) -> SourceProgramme:
        return self.programme


FESTIVAL = SourceFestival(
    slug="fests-2025",
    name="Fests 2025",
    time_zone="Europe/Oslo",
    series=SourceSeries(slug="fests", name="Fests"),
)


def programme(*entries: SourceEntry, festival=FESTIVAL) -> StaticSource:
    return StaticSource(SourceProgramme(festival=festival, entries=entries))


def show(start="18:00", end="20:00", venue="Vika Kino", **kw) -> SourceScreening:
    return SourceScreening(
        venue_name=venue, start_time=at(start), end_time=at(end), **kw
    )


def entry(key="film/a", title="A", year=2025, *screenings) -> SourceEntry:
    return SourceEntry(
        source_key=key, title=title, year=year, screenings=screenings or (show(),)
    )


@pytest.fixture
def uow():
    uow = InMemoryUnitOfWork()
    uow.stored.venues = {
        "vika": Venue(id="vika", name="Vika", aliases=frozenset({"Vika Kino"})),
        "vega": Venue(id="vega", name="Vega"),
    }
    return uow


def test_first_ingestion_creates_festival_series_films_entries_and_screenings(uow):
    report = ingest_programme(uow, programme(entry()), new_id=ids())
    assert report == ProgrammeIngestion(
        festival_slug="fests-2025",
        films_created=1,
        entries_created=1,
        screenings_created=1,
    )
    assert uow.committed
    [festival] = uow.stored.festivals.values()
    assert festival.series_id == next(iter(uow.stored.series))
    assert (festival.start_date, festival.end_date) == (at("18:00").date(),) * 2
    [screening] = uow.stored.screenings.values()
    assert screening.venue_id == "vika" and not screening.withdrawn


def test_re_ingesting_the_same_programme_changes_nothing(uow):
    ingest_programme(uow, programme(entry()), new_id=ids())
    before = uow.stored.screenings.copy(), uow.stored.entries.copy()
    report = ingest_programme(uow, programme(entry()), new_id=ids())
    assert report == ProgrammeIngestion(festival_slug="fests-2025")
    assert (uow.stored.screenings, uow.stored.entries) == before


def test_entry_ids_survive_a_title_correction(uow):
    ingest_programme(uow, programme(entry(title="A")), new_id=ids())
    [(_, _, old)] = uow.stored.entries.values()
    report = ingest_programme(uow, programme(entry(title="A, revised")), new_id=ids())
    [(_, _, new)] = uow.stored.entries.values()
    assert new.id == old.id and new.title == "A, revised"
    assert report.entries_updated == 1


def test_a_missing_screening_is_withdrawn_and_a_moved_one_is_new(uow):
    ingest_programme(
        uow, programme(entry("film/a", "A", 2025, show("18:00", "20:00"))), new_id=ids()
    )
    [original] = uow.stored.screenings.values()
    report = ingest_programme(
        uow, programme(entry("film/a", "A", 2025, show("21:00", "23:00"))), new_id=ids()
    )
    assert report.screenings_withdrawn == 1 and report.screenings_created == 1
    assert uow.stored.screenings[original.id].withdrawn


def test_a_screening_that_reappears_is_no_longer_withdrawn(uow):
    ingest_programme(uow, programme(entry()), new_id=ids())
    ingest_programme(
        uow, programme(entry("film/a", "A", 2025, show("21:00", "23:00"))), new_id=ids()
    )
    ingest_programme(uow, programme(entry()), new_id=ids())
    assert [
        s.start_time for s in uow.stored.screenings.values() if not s.withdrawn
    ] == [at("18:00")]


def test_auditorium_ticket_url_and_events_update_in_place(uow):
    ingest_programme(uow, programme(entry()), new_id=ids())
    [old] = uow.stored.screenings.values()
    changed = show(
        auditorium="3", ticket_url="https://t", events=(Event(description="Q&A"),)
    )
    report = ingest_programme(
        uow, programme(entry("film/a", "A", 2025, changed)), new_id=ids()
    )
    [new] = uow.stored.screenings.values()
    assert new.id == old.id and new.auditorium == "3"
    assert new.events[0].description == "Q&A"
    assert report.screenings_updated == 1


def test_films_are_shared_by_normalised_title_and_year(uow):
    ingest_programme(
        uow, programme(entry("film/a", "Fallen Leaves", 2023)), new_id=ids()
    )
    other = SourceFestival(slug="other-2025", name="Other", time_zone="Europe/Oslo")
    report = ingest_programme(
        uow, programme(entry("x", "fallen  leaves", 2023), festival=other), new_id=ids()
    )
    assert len(uow.stored.films) == 1 and report.films_created == 0


def test_titles_without_a_year_always_get_a_new_film(uow):
    ingest_programme(
        uow,
        programme(entry("film/a", "Shorts", None), entry("film/b", "Shorts", None)),
        new_id=ids(),
    )
    assert len(uow.stored.films) == 2


def test_unknown_venues_abort_the_ingestion_and_name_every_one(uow):
    source = programme(
        entry("film/a", "A", 2025, show(venue="Nowhere"), show(venue="Elsewhere"))
    )
    with pytest.raises(UnknownVenuesError) as error:
        ingest_programme(uow, source, new_id=ids())
    assert error.value.names == ("Elsewhere", "Nowhere")
    assert not uow.committed and uow.stored.festivals == {}


def test_source_dates_win_over_screening_dates(uow):
    dated = FESTIVAL.model_copy(
        update={
            "start_date": datetime.date(2025, 11, 6),
            "end_date": datetime.date(2025, 11, 16),
        }
    )
    ingest_programme(uow, programme(entry(), festival=dated), new_id=ids())
    [festival] = uow.stored.festivals.values()
    assert (festival.start_date, festival.end_date) == (
        datetime.date(2025, 11, 6),
        datetime.date(2025, 11, 16),
    )


def test_festival_dates_are_festival_local_days():
    uow = InMemoryUnitOfWork()
    uow.stored.venues = {"vika": Venue(id="vika", name="Vika Kino")}
    # 00:30 in Oslo is still the previous day in UTC.
    ingest_programme(
        uow,
        programme(entry("film/a", "A", 2025, show("00:30", "02:00"))),
        new_id=ids(),
    )
    [festival] = uow.stored.festivals.values()
    assert festival.start_date == at("00:30").date()


def test_a_festival_without_dates_or_screenings_is_rejected(uow):
    with pytest.raises(IngestionError, match="fests-2025"):
        ingest_programme(uow, programme(), new_id=ids())
    assert not uow.committed


def test_duplicate_screenings_in_the_source_are_stored_once(uow):
    ingest_programme(
        uow, programme(entry("film/a", "A", 2025, show(), show())), new_id=ids()
    )
    assert len(uow.stored.screenings) == 1
