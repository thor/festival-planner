import pytest

from festival_planner.domain.ingestion import (
    IncompleteRoutesError,
    SourceRoute,
    SourceVenue,
    UnknownVenuesError,
    VenueIngestion,
    ingest_venues,
)
from festival_planner.domain.programme import Venue
from festival_planner.domain.travel import DEFAULT_TRANSPORT_MODE as WALK

from .fakes import InMemoryUnitOfWork
from .fakes import sequential_ids as ids


class Static:
    def __init__(self, venues, routes):
        self._venues, self._routes = venues, routes

    def venues(self):
        return self._venues

    def routes(self, venues: tuple[Venue, ...]):
        return self._routes


VENUES = (
    SourceVenue(name="Vika", aliases=frozenset({"Vika Kino"})),
    SourceVenue(name="Vega"),
)
BOTH_WAYS = (
    SourceRoute(from_venue="Vika Kino", to_venue="Vega", mode=WALK, minutes=15),
    SourceRoute(from_venue="Vega", to_venue="Vika", mode=WALK, minutes=15),
)


def test_creates_venues_with_aliases_and_routes_between_their_ids():
    uow, source = InMemoryUnitOfWork(), Static(VENUES, BOTH_WAYS)
    report = ingest_venues(uow, source, source, new_id=ids())
    assert report == VenueIngestion(venues_created=2, routes=2)
    assert uow.committed
    by_name = {v.name: v for v in uow.stored.venues.values()}
    assert by_name["Vika"].aliases == frozenset({"Vika Kino"})
    assert {(r.from_venue_id, r.to_venue_id) for r in uow.stored.routes} == {
        (by_name["Vika"].id, by_name["Vega"].id),
        (by_name["Vega"].id, by_name["Vika"].id),
    }


def test_re_ingesting_keeps_venue_ids_and_updates_aliases():
    uow, source = InMemoryUnitOfWork(), Static(VENUES, BOTH_WAYS)
    ingest_venues(uow, source, source, new_id=ids())
    old_ids = set(uow.stored.venues)
    renamed = (
        SourceVenue(name="vika", aliases=frozenset({"Vika Kino", "Vika 1"})),
        VENUES[1],
    )
    report = ingest_venues(uow, Static(renamed, BOTH_WAYS), source, new_id=ids())
    assert set(uow.stored.venues) == old_ids and report.venues_updated == 1
    assert report.venues_created == 0


def test_missing_default_mode_routes_abort():
    uow, source = InMemoryUnitOfWork(), Static(VENUES, BOTH_WAYS[:1])
    with pytest.raises(IncompleteRoutesError, match="Vega → Vika"):
        ingest_venues(uow, source, source, new_id=ids())
    assert uow.stored.venues == {} and not uow.committed


def test_routes_to_unknown_venues_abort():
    bad = BOTH_WAYS + (
        SourceRoute(from_venue="Vega", to_venue="Atlantis", mode=WALK, minutes=1),
    )
    uow, source = InMemoryUnitOfWork(), Static(VENUES, bad)
    with pytest.raises(UnknownVenuesError, match="Atlantis"):
        ingest_venues(uow, source, source, new_id=ids())
    assert not uow.committed
