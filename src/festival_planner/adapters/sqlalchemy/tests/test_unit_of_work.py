import datetime
import zoneinfo

import pytest

from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.domain.festival import Festival, FestivalId
from festival_planner.domain.ingestion import (
    ProgrammeIngestion,
    SourceEntry,
    SourceFestival,
    SourceProgramme,
    SourceRoute,
    SourceScreening,
    SourceVenue,
    UnitOfWork,
    VenueIngestion,
    ingest_programme,
    ingest_venues,
)
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
from festival_planner.domain.travel import DEFAULT_TRANSPORT_MODE, Route

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


def test_leaving_without_commit_rolls_back(engine):
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.venues.save(Venue(id=VenueId("v"), name="Vika"))
    with SqlAlchemyUnitOfWork(engine) as uow:
        assert uow.venues.all() == ()


def test_an_exception_rolls_back(engine):
    with pytest.raises(RuntimeError), SqlAlchemyUnitOfWork(engine) as uow:
        uow.venues.save(Venue(id=VenueId("v"), name="Vika"))
        raise RuntimeError("boom")
    with SqlAlchemyUnitOfWork(engine) as uow:
        assert uow.venues.all() == ()


def test_a_unit_of_work_can_be_used_again(engine):
    uow = SqlAlchemyUnitOfWork(engine)
    with uow:
        uow.venues.save(Venue(id=VenueId("v"), name="Vika"))
        uow.commit()
    with uow:
        assert [v.name for v in uow.venues.all()] == ["Vika"]


def test_ingesting_and_withdrawing_by_hand_through_the_real_unit_of_work(engine):
    """The flow the ingestion use-cases drive: store a programme in one unit of
    work, then reconcile it in another."""
    t18 = datetime.datetime(2025, 11, 8, 18, 0, tzinfo=OSLO)
    vika = Venue(id=VenueId("vika"), name="Vika", aliases=frozenset({"Vika Kino"}))
    vega = Venue(id=VenueId("vega"), name="Vega")
    festival = Festival(
        id=FestivalId("f"),
        slug="fests-2025",
        name="Fests 2025",
        start_date=datetime.date(2025, 11, 6),
        end_date=datetime.date(2025, 11, 16),
        time_zone="Europe/Oslo",
    )
    film = Film(id=FilmId("m"), title="Fallen Leaves", year=2023)
    entry = ProgrammeEntry(
        id=ProgrammeEntryId("e"), film_id=FilmId("m"), title="Fallen Leaves", year=2023
    )
    at_vika, at_vega = (
        Screening(
            id=ScreeningId(f"s-{venue.id}"),
            programme_entry_id=ProgrammeEntryId("e"),
            venue_id=venue.id,
            start_time=start,
            end_time=start + datetime.timedelta(hours=2),
        )
        for venue, start in ((vika, t18), (vega, t18 + datetime.timedelta(days=1)))
    )
    routes = [
        Route(
            from_venue_id=VenueId(a),
            to_venue_id=VenueId(b),
            mode="walk+e-scooter",
            minutes=12,
        )
        for a, b in (("vika", "vega"), ("vega", "vika"))
    ]

    uow: UnitOfWork = SqlAlchemyUnitOfWork(engine)
    with uow:
        uow.venues.save(vika)
        uow.venues.save(vega)
        uow.routes.replace_all(routes)
        uow.festivals.save(festival)
        assert uow.films.find("Fallen Leaves", 2023) is None
        uow.films.save(film)
        assert uow.films.find("Fallen Leaves", 2023) == film
        uow.programme.save_entry(FestivalId("f"), "film/fallen-leaves", entry)
        uow.programme.save_screening(at_vika)
        uow.programme.save_screening(at_vega)
        uow.commit()

    with uow:
        assert uow.programme.entries(FestivalId("f")) == {"film/fallen-leaves": entry}
        stored = uow.programme.screenings(FestivalId("f"))
        assert stored == (at_vika, at_vega)
        uow.programme.save_screening(stored[1].model_copy(update={"withdrawn": True}))
        uow.commit()

    with uow:
        assert uow.programme.screenings(FestivalId("f")) == (
            at_vika,
            at_vega.model_copy(update={"withdrawn": True}),
        )
        assert uow.festivals.by_slug("fests-2025") == festival
        assert uow.routes.all() == tuple(sorted(routes, key=lambda r: r.from_venue_id))


class StaticVenues:
    """VenueSource and RouteProvider: Vika (alias "Vika Kino") and Vega."""

    def venues(self) -> tuple[SourceVenue, ...]:
        return (
            SourceVenue(name="Vika", aliases=frozenset({"Vika Kino"})),
            SourceVenue(name="Vega"),
        )

    def routes(self, venues: tuple[Venue, ...]) -> tuple[SourceRoute, ...]:
        return tuple(
            SourceRoute(
                from_venue=a, to_venue=b, mode=DEFAULT_TRANSPORT_MODE, minutes=12
            )
            for a, b in (("Vika Kino", "Vega"), ("Vega", "Vika"))
        )


class StaticProgramme:
    """ProgrammeSource: Fallen Leaves at 18:00 Oslo time at each named venue."""

    def __init__(self, *venue_names: str):
        start = datetime.datetime(2025, 11, 8, 18, 0, tzinfo=OSLO)
        self.programme = SourceProgramme(
            festival=SourceFestival(
                slug="fests-2025", name="Fests 2025", time_zone="Europe/Oslo"
            ),
            entries=(
                SourceEntry(
                    source_key="film/fallen-leaves",
                    title="Fallen Leaves",
                    year=2023,
                    screenings=tuple(
                        SourceScreening(
                            venue_name=name,
                            start_time=start,
                            end_time=start + datetime.timedelta(hours=2),
                        )
                        for name in venue_names
                    ),
                ),
            ),
        )

    def fetch(self) -> SourceProgramme:
        return self.programme


def test_use_cases_run_against_sqlite(engine):
    uow = SqlAlchemyUnitOfWork(engine)

    def screening_ids() -> list[str]:
        with uow:
            festival = uow.festivals.by_slug("fests-2025")
            assert festival is not None
            return sorted(s.id for s in uow.programme.screenings(festival.id))

    venues = ingest_venues(uow, StaticVenues(), StaticVenues())
    first = ingest_programme(uow, StaticProgramme("Vika Kino", "Vega"))
    ids_after_first = screening_ids()
    second = ingest_programme(uow, StaticProgramme("Vika Kino", "Vega"))
    ids_after_second = screening_ids()
    third = ingest_programme(uow, StaticProgramme("Vika Kino"))

    assert venues == VenueIngestion(venues_created=2, routes=2)
    assert first.screenings_created == 2
    assert second == ProgrammeIngestion(festival_slug="fests-2025")
    assert ids_after_second == ids_after_first
    assert third == ProgrammeIngestion(
        festival_slug="fests-2025", screenings_withdrawn=1
    )
