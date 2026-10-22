"""Ingesting festival data from external sources.

Sources describe what they found in plain values (`Source*`); the use-cases
reconcile that with what is stored, keeping ids stable across re-ingestion.
"""

import datetime
import uuid
import zoneinfo
from collections.abc import Callable, Iterable, Mapping
from types import TracebackType
from typing import Protocol, Self

from pydantic import AwareDatetime, Field, model_validator

from .festival import Festival, FestivalId, FestivalSeries
from .programme import (
    Event,
    Film,
    ProgrammeEntry,
    Screening,
    Venue,
    title_key,
    venue_name_key,
)
from .travel import DEFAULT_TRANSPORT_MODE, Route, TransportMode
from .values import Slug, TimeZone, Value

# --- What sources report ---------------------------------------------------


class SourceSeries(Value):
    slug: Slug
    name: str


class SourceFestival(Value):
    """A Festival as a ProgrammeSource describes it. Missing dates are derived
    from the Screenings' festival-local days."""

    slug: Slug
    name: str
    time_zone: TimeZone
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    series: SourceSeries | None = None


class SourceScreening(Value):
    venue_name: str
    """The name the source uses; resolved through Venue names and aliases."""
    start_time: AwareDatetime
    end_time: AwareDatetime
    auditorium: str | None = None
    ticket_url: str | None = None
    events: tuple[Event, ...] = ()

    @model_validator(mode="after")
    def _ends_after_it_starts(self) -> Self:
        if self.end_time < self.start_time:
            raise ValueError("A screening cannot end before it starts")
        return self


class SourceEntry(Value):
    source_key: str = Field(min_length=1)
    """Identifies the Programme Entry within its Festival across re-ingestion."""
    title: str
    year: int | None = None
    country: str | None = None
    url: str | None = None
    screenings: tuple[SourceScreening, ...] = ()


class SourceProgramme(Value):
    festival: SourceFestival
    entries: tuple[SourceEntry, ...]

    @model_validator(mode="after")
    def _source_keys_are_unique(self) -> Self:
        seen: set[str] = set()
        for entry in self.entries:
            if entry.source_key in seen:
                raise ValueError(f"Duplicate source key {entry.source_key!r}")
            seen.add(entry.source_key)
        return self


class SourceVenue(Value):
    name: str
    aliases: frozenset[str] = frozenset()


class SourceRoute(Value):
    """A Route between Venues identified by name or alias."""

    from_venue: str
    to_venue: str
    mode: TransportMode
    minutes: int = Field(ge=0)


# --- Driven ports ----------------------------------------------------------


class ProgrammeSource(Protocol):
    """Port: fetches one Festival's programme, e.g. by scraping its website."""

    def fetch(self) -> SourceProgramme: ...


class VenueSource(Protocol):
    """Port: the Venues known in advance of any Festival."""

    def venues(self) -> tuple[SourceVenue, ...]: ...


class RouteProvider(Protocol):
    """Port: precalculated Routes between the given Venues."""

    def routes(self, venues: tuple[Venue, ...]) -> tuple[SourceRoute, ...]: ...


class FestivalRepository(Protocol):
    def by_slug(self, slug: str) -> Festival | None: ...
    def save(self, festival: Festival) -> None: ...
    def series_by_slug(self, slug: str) -> FestivalSeries | None: ...
    def save_series(self, series: FestivalSeries) -> None: ...


class VenueRepository(Protocol):
    def all(self) -> tuple[Venue, ...]: ...
    def save(self, venue: Venue) -> None:
        """Insert or update by id, replacing the aliases."""
        ...


class RouteRepository(Protocol):
    def all(self) -> tuple[Route, ...]: ...
    def replace_all(self, routes: Iterable[Route]) -> None: ...


class FilmRepository(Protocol):
    def find(self, title: str, year: int) -> Film | None:
        """A Film whose `title_key` and year match, if any."""
        ...

    def save(self, film: Film) -> None: ...


class ProgrammeRepository(Protocol):
    def entries(self, festival_id: FestivalId) -> Mapping[str, ProgrammeEntry]:
        """The Festival's Programme Entries by source key."""
        ...

    def save_entry(
        self, festival_id: FestivalId, source_key: str, entry: ProgrammeEntry
    ) -> None: ...

    def screenings(self, festival_id: FestivalId) -> tuple[Screening, ...]:
        """All the Festival's Screenings, Withdrawn ones included."""
        ...

    def save_screening(self, screening: Screening) -> None:
        """Insert or update by id, replacing the Events."""
        ...


class UnitOfWork(Protocol):
    """Port: one transaction over the repositories. Leaving the context
    without `commit()` rolls back."""

    festivals: FestivalRepository
    venues: VenueRepository
    routes: RouteRepository
    films: FilmRepository
    programme: ProgrammeRepository

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
    def commit(self) -> None: ...


# --- Errors and reports ----------------------------------------------------


class IngestionError(Exception):
    """Ingestion was aborted; nothing was stored."""


class UnknownVenuesError(IngestionError):
    def __init__(self, names: Iterable[str]):
        self.names = tuple(sorted(set(names)))
        super().__init__(f"Unknown venues: {', '.join(map(repr, self.names))}")


class AmbiguousVenueNameError(IngestionError):
    def __init__(self, name: str, venue_names: Iterable[str]):
        self.name = name
        super().__init__(
            f"Venue name {name!r} is used by several venues: "
            f"{', '.join(sorted(venue_names))}"
        )


class IncompleteRoutesError(IngestionError):
    def __init__(self, mode: TransportMode, missing: Iterable[tuple[str, str]]):
        self.missing = tuple(sorted(missing))
        pairs = ", ".join(f"{a} → {b}" for a, b in self.missing)
        super().__init__(f"No {mode!r} route for: {pairs}")


class VenueIngestion(Value):
    venues_created: int = 0
    venues_updated: int = 0
    routes: int = 0


class ProgrammeIngestion(Value):
    festival_slug: str
    films_created: int = 0
    entries_created: int = 0
    entries_updated: int = 0
    screenings_created: int = 0
    screenings_updated: int = 0
    screenings_withdrawn: int = 0


# --- Helpers ---------------------------------------------------------------


class VenueDirectory:
    """Resolves the names sources use to Venues, by name or alias."""

    def __init__(self, venues: Iterable[Venue]):
        self._by_key: dict[str, Venue] = {}
        for venue in venues:
            for name in (venue.name, *venue.aliases):
                key = venue_name_key(name)
                other = self._by_key.setdefault(key, venue)
                if other.id != venue.id:
                    raise AmbiguousVenueNameError(key, (other.name, venue.name))

    def resolve(self, name: str) -> Venue | None:
        return self._by_key.get(venue_name_key(name))


# --- Use-cases -------------------------------------------------------------


def new_id() -> str:
    return str(uuid.uuid4())


def ingest_venues(
    uow: UnitOfWork,
    venue_source: VenueSource,
    route_provider: RouteProvider,
    *,
    default_mode: TransportMode = DEFAULT_TRANSPORT_MODE,
    new_id: Callable[[], str] = new_id,
) -> VenueIngestion:
    """Create or update Venues (matched by name), then replace all Routes.

    Every ordered pair of distinct Venues needs a Route in `default_mode`.
    Venues the source no longer lists are kept.
    """
    created = updated = 0
    with uow:
        existing = {venue_name_key(v.name): v for v in uow.venues.all()}
        for described in venue_source.venues():
            key = venue_name_key(described.name)
            old = existing.get(key)
            venue = Venue(
                id=old.id if old else new_id(),
                name=described.name,
                aliases=described.aliases,
            )
            if venue != old:
                uow.venues.save(venue)
                existing[key] = venue
                if old:
                    updated += 1
                else:
                    created += 1
        venues = tuple(existing.values())
        directory = VenueDirectory(venues)
        source_routes = route_provider.routes(venues)
        unknown = [
            name
            for r in source_routes
            for name in (r.from_venue, r.to_venue)
            if directory.resolve(name) is None
        ]
        if unknown:
            raise UnknownVenuesError(unknown)
        routes: dict[tuple[str, str, TransportMode], Route] = {}
        for r in source_routes:
            a, b = directory.resolve(r.from_venue), directory.resolve(r.to_venue)
            assert a is not None and b is not None
            if a.id != b.id:
                routes[a.id, b.id, r.mode] = Route(
                    from_venue_id=a.id, to_venue_id=b.id, mode=r.mode, minutes=r.minutes
                )
        missing = [
            (a.name, b.name)
            for a in venues
            for b in venues
            if a.id != b.id and (a.id, b.id, default_mode) not in routes
        ]
        if missing:
            raise IncompleteRoutesError(default_mode, missing)
        uow.routes.replace_all(routes.values())
        uow.commit()
    return VenueIngestion(
        venues_created=created, venues_updated=updated, routes=len(routes)
    )


def ingest_programme(
    uow: UnitOfWork, source: ProgrammeSource, *, new_id: Callable[[], str] = new_id
) -> ProgrammeIngestion:
    """Store a Festival's programme, keeping ids stable across re-ingestion.

    Programme Entries are matched by source key, Screenings by (Programme
    Entry, Venue, start time). Screenings no longer in the source become
    Withdrawn. Films are matched by normalised title and year.
    """
    programme = source.fetch()
    counts = dict.fromkeys(
        (
            "films_created",
            "entries_created",
            "entries_updated",
            "screenings_created",
            "screenings_updated",
            "screenings_withdrawn",
        ),
        0,
    )
    with uow:
        directory = VenueDirectory(uow.venues.all())
        unknown = [
            s.venue_name
            for e in programme.entries
            for s in e.screenings
            if directory.resolve(s.venue_name) is None
        ]
        if unknown:
            raise UnknownVenuesError(unknown)
        festival = _store_festival(uow, programme, new_id)

        def film_for(entry: SourceEntry) -> str:
            if entry.year is not None and (
                film := uow.films.find(entry.title, entry.year)
            ):
                return film.id
            film = Film(id=new_id(), title=entry.title, year=entry.year)
            uow.films.save(film)
            counts["films_created"] += 1
            return film.id

        stored_entries = uow.programme.entries(festival.id)
        stored_screenings = {
            (s.programme_entry_id, s.venue_id, s.start_time): s
            for s in uow.programme.screenings(festival.id)
        }
        current: set[tuple[str, str, datetime.datetime]] = set()
        for described in programme.entries:
            old = stored_entries.get(described.source_key)
            same_work = old is not None and (title_key(old.title), old.year) == (
                title_key(described.title),
                described.year,
            )
            entry = ProgrammeEntry(
                id=old.id if old else new_id(),
                film_id=old.film_id if old and same_work else film_for(described),
                title=described.title,
                year=described.year,
                country=described.country,
                url=described.url,
            )
            if entry != old:
                uow.programme.save_entry(festival.id, described.source_key, entry)
                counts["entries_updated" if old else "entries_created"] += 1
            for s in described.screenings:
                venue = directory.resolve(s.venue_name)
                assert venue is not None
                key = (entry.id, venue.id, s.start_time)
                if key in current:
                    continue
                current.add(key)
                previous = stored_screenings.get(key)
                screening = Screening(
                    id=previous.id if previous else new_id(),
                    programme_entry_id=entry.id,
                    venue_id=venue.id,
                    start_time=s.start_time,
                    end_time=s.end_time,
                    auditorium=s.auditorium,
                    ticket_url=s.ticket_url,
                    events=s.events,
                )
                if screening != previous:
                    uow.programme.save_screening(screening)
                    counts[
                        "screenings_updated" if previous else "screenings_created"
                    ] += 1
        for key, screening in stored_screenings.items():
            if key not in current and not screening.withdrawn:
                uow.programme.save_screening(
                    screening.model_copy(update={"withdrawn": True})
                )
                counts["screenings_withdrawn"] += 1
        uow.commit()
    return ProgrammeIngestion(festival_slug=festival.slug, **counts)


def _store_festival(
    uow: UnitOfWork, programme: SourceProgramme, new_id: Callable[[], str]
) -> Festival:
    """Create or update the Festival (by slug) and its Festival Series."""
    described = programme.festival
    series_id = None
    if described.series:
        old_series = uow.festivals.series_by_slug(described.series.slug)
        series = FestivalSeries(
            id=old_series.id if old_series else new_id(),
            slug=described.series.slug,
            name=described.series.name,
        )
        if series != old_series:
            uow.festivals.save_series(series)
        series_id = series.id
    zone = zoneinfo.ZoneInfo(described.time_zone)
    days = sorted(
        s.start_time.astimezone(zone).date()
        for e in programme.entries
        for s in e.screenings
    )
    start = described.start_date or (days[0] if days else None)
    end = described.end_date or (days[-1] if days else None)
    if start is None or end is None:
        raise IngestionError(
            f"Cannot tell when {described.slug!r} takes place: "
            "no dates and no screenings"
        )
    old = uow.festivals.by_slug(described.slug)
    festival = Festival(
        id=old.id if old else new_id(),
        slug=described.slug,
        name=described.name,
        start_date=start,
        end_date=end,
        time_zone=described.time_zone,
        series_id=series_id,
    )
    if festival != old:
        uow.festivals.save(festival)
    return festival
