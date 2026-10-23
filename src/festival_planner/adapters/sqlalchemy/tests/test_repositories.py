import datetime
import zoneinfo
from collections.abc import Callable

import pytest
from sqlalchemy.exc import IntegrityError

from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.domain.festival import Festival, FestivalSeries
from festival_planner.domain.programme import (
    Event,
    Film,
    ProgrammeEntry,
    Screening,
    Venue,
)
from festival_planner.domain.travel import Route

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")
T18 = datetime.datetime(2025, 11, 8, 18, 0, tzinfo=OSLO)
SERIES = FestivalSeries(id="s", slug="fests", name="Fests")
FESTIVAL = Festival(
    id="f",
    slug="fests-2025",
    name="Fests 2025",
    start_date=datetime.date(2025, 11, 6),
    end_date=datetime.date(2025, 11, 16),
    time_zone="Europe/Oslo",
    series_id="s",
)
VIKA = Venue(id="vika", name="Vika", aliases=frozenset({"Vika Kino", "vika"}))
FILM = Film(id="m", title="Fallen Leaves", year=2023)
ENTRY = ProgrammeEntry(
    id="e", film_id="m", title="Fallen Leaves", year=2023, country="FI", url="https://x"
)
SCREENING = Screening(
    id="sc",
    programme_entry_id="e",
    venue_id="vika",
    start_time=T18,
    end_time=T18 + datetime.timedelta(hours=2),
    auditorium="3",
    events=(
        Event(description="Q&A"),
        Event(
            description="Panel",
            start_time=T18 + datetime.timedelta(hours=2),
            end_time=T18 + datetime.timedelta(hours=3),
        ),
    ),
)


@pytest.fixture
def stored(engine):
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.festivals.save_series(SERIES)
        uow.festivals.save(FESTIVAL)
        uow.venues.save(VIKA)
        uow.films.save(FILM)
        uow.programme.save_entry("f", "film/fallen-leaves", ENTRY)
        uow.programme.save_screening(SCREENING)
        uow.commit()
    return engine


def read[T](engine, query: Callable[[SqlAlchemyUnitOfWork], T]) -> T:
    with SqlAlchemyUnitOfWork(engine) as uow:
        return query(uow)


def test_festival_and_series_round_trip(stored):
    assert read(stored, lambda uow: uow.festivals.by_slug("fests-2025")) == FESTIVAL
    assert read(stored, lambda uow: uow.festivals.series_by_slug("fests")) == SERIES
    assert read(stored, lambda uow: uow.festivals.by_slug("nope")) is None
    assert read(stored, lambda uow: uow.festivals.series_by_slug("nope")) is None


def test_saving_a_festival_again_updates_it(stored):
    with SqlAlchemyUnitOfWork(stored) as uow:
        uow.festivals.save(FESTIVAL.model_copy(update={"name": "Renamed"}))
        uow.commit()
    festival = read(stored, lambda uow: uow.festivals.by_slug("fests-2025"))
    assert festival is not None and festival.name == "Renamed"


def test_venue_aliases_are_replaced(stored):
    renamed = VIKA.model_copy(update={"aliases": frozenset({"Vika 1", "vika"})})
    with SqlAlchemyUnitOfWork(stored) as uow:
        uow.venues.save(renamed)
        uow.commit()
    assert read(stored, lambda uow: uow.venues.all()) == (renamed,)


def test_saving_an_unchanged_venue_is_harmless(stored):
    with SqlAlchemyUnitOfWork(stored) as uow:
        uow.venues.all()
        uow.venues.save(VIKA)
        uow.commit()
    assert read(stored, lambda uow: uow.venues.all()) == (VIKA,)


def test_venues_are_ordered_by_name(stored):
    with SqlAlchemyUnitOfWork(stored) as uow:
        uow.venues.save(Venue(id="a", name="Amalie"))
        uow.commit()
    names = read(stored, lambda uow: [v.name for v in uow.venues.all()])
    assert names == ["Amalie", "Vika"]


def test_routes_are_replaced_wholesale(stored):
    vega = Venue(id="vega", name="Vega")
    first = Route(from_venue_id="vika", to_venue_id="vega", mode="walk", minutes=15)
    second = Route(from_venue_id="vega", to_venue_id="vika", mode="walk", minutes=16)
    for routes in ([first], [second]):
        with SqlAlchemyUnitOfWork(stored) as uow:
            uow.venues.save(vega)
            uow.routes.replace_all(routes)
            uow.commit()
    assert read(stored, lambda uow: uow.routes.all()) == (second,)


def test_routes_can_be_replaced_by_themselves_after_reading(stored):
    route = Route(from_venue_id="vika", to_venue_id="vega", mode="walk", minutes=15)
    with SqlAlchemyUnitOfWork(stored) as uow:
        uow.venues.save(Venue(id="vega", name="Vega"))
        uow.routes.replace_all([route])
        uow.commit()
    with SqlAlchemyUnitOfWork(stored) as uow:
        uow.routes.replace_all(uow.routes.all())
        uow.commit()
    assert read(stored, lambda uow: uow.routes.all()) == (route,)


def test_films_are_found_by_normalised_title_and_year(stored):
    assert read(stored, lambda uow: uow.films.find("fallen  LEAVES", 2023)) == FILM
    assert read(stored, lambda uow: uow.films.find("Fallen Leaves", 2024)) is None


def test_entries_are_keyed_by_source_key_per_festival(stored):
    assert read(stored, lambda uow: uow.programme.entries("f")) == {
        "film/fallen-leaves": ENTRY
    }
    assert read(stored, lambda uow: uow.programme.entries("other")) == {}


def test_saving_an_entry_again_updates_it(stored):
    changed = ENTRY.model_copy(update={"country": "SE", "url": None})
    with SqlAlchemyUnitOfWork(stored) as uow:
        uow.programme.save_entry("f", "film/fallen-leaves", changed)
        uow.commit()
    assert read(stored, lambda uow: uow.programme.entries("f")) == {
        "film/fallen-leaves": changed
    }


def test_screenings_round_trip_with_events_as_utc_instants(stored):
    [screening] = read(stored, lambda uow: uow.programme.screenings("f"))
    assert screening == SCREENING
    assert screening.start_time.tzinfo == datetime.UTC
    event_start = screening.events[1].start_time
    assert event_start is not None and event_start.tzinfo == datetime.UTC


def test_screenings_belong_to_their_festival(stored):
    assert read(stored, lambda uow: uow.programme.screenings("other")) == ()


def test_saving_a_screening_replaces_its_events_and_keeps_withdrawn(stored):
    changed = SCREENING.model_copy(
        update={"events": (Event(description="Intro"),), "withdrawn": True}
    )
    with SqlAlchemyUnitOfWork(stored) as uow:
        uow.programme.save_screening(changed)
        uow.commit()
    assert read(stored, lambda uow: uow.programme.screenings("f")) == (changed,)


def test_a_second_screening_with_the_same_natural_key_is_rejected(stored):
    with SqlAlchemyUnitOfWork(stored) as uow, pytest.raises(IntegrityError):
        uow.programme.save_screening(
            SCREENING.model_copy(update={"id": "other", "events": ()})
        )
