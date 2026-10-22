import datetime
import zoneinfo

import pytest

from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.domain.festival import Festival
from festival_planner.domain.ingestion import UnitOfWork
from festival_planner.domain.programme import Film, ProgrammeEntry, Screening, Venue
from festival_planner.domain.travel import Route

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


def test_leaving_without_commit_rolls_back(engine):
    with SqlAlchemyUnitOfWork(engine) as uow:
        uow.venues.save(Venue(id="v", name="Vika"))
    with SqlAlchemyUnitOfWork(engine) as uow:
        assert uow.venues.all() == ()


def test_an_exception_rolls_back(engine):
    with pytest.raises(RuntimeError), SqlAlchemyUnitOfWork(engine) as uow:
        uow.venues.save(Venue(id="v", name="Vika"))
        raise RuntimeError("boom")
    with SqlAlchemyUnitOfWork(engine) as uow:
        assert uow.venues.all() == ()


def test_a_unit_of_work_can_be_used_again(engine):
    uow = SqlAlchemyUnitOfWork(engine)
    with uow:
        uow.venues.save(Venue(id="v", name="Vika"))
        uow.commit()
    with uow:
        assert [v.name for v in uow.venues.all()] == ["Vika"]


def test_ingesting_and_withdrawing_by_hand_through_the_real_unit_of_work(engine):
    """The flow the ingestion use-cases drive: store a programme in one unit of
    work, then reconcile it in another."""
    t18 = datetime.datetime(2025, 11, 8, 18, 0, tzinfo=OSLO)
    vika = Venue(id="vika", name="Vika", aliases=frozenset({"Vika Kino"}))
    vega = Venue(id="vega", name="Vega")
    festival = Festival(
        id="f",
        slug="fests-2025",
        name="Fests 2025",
        start_date=datetime.date(2025, 11, 6),
        end_date=datetime.date(2025, 11, 16),
        time_zone="Europe/Oslo",
    )
    film = Film(id="m", title="Fallen Leaves", year=2023)
    entry = ProgrammeEntry(id="e", film_id="m", title="Fallen Leaves", year=2023)
    at_vika, at_vega = (
        Screening(
            id=f"s-{venue.id}",
            programme_entry_id="e",
            venue_id=venue.id,
            start_time=start,
            end_time=start + datetime.timedelta(hours=2),
        )
        for venue, start in ((vika, t18), (vega, t18 + datetime.timedelta(days=1)))
    )
    routes = [
        Route(from_venue_id=a, to_venue_id=b, mode="walk+e-scooter", minutes=12)
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
        uow.programme.save_entry("f", "film/fallen-leaves", entry)
        uow.programme.save_screening(at_vika)
        uow.programme.save_screening(at_vega)
        uow.commit()

    with uow:
        assert uow.programme.entries("f") == {"film/fallen-leaves": entry}
        stored = uow.programme.screenings("f")
        assert stored == (at_vika, at_vega)
        uow.programme.save_screening(stored[1].model_copy(update={"withdrawn": True}))
        uow.commit()

    with uow:
        assert uow.programme.screenings("f") == (
            at_vika,
            at_vega.model_copy(update={"withdrawn": True}),
        )
        assert uow.festivals.by_slug("fests-2025") == festival
        assert uow.routes.all() == tuple(sorted(routes, key=lambda r: r.from_venue_id))
