"""Ingesting festival data from external sources.

Sources describe what they found in plain values (`Source*`); the use-cases
reconcile that with what is stored, keeping ids stable across re-ingestion.
"""

import datetime
from collections.abc import Iterable, Mapping
from types import TracebackType
from typing import Protocol, Self

from pydantic import AwareDatetime, Field, model_validator

from .festival import Festival, FestivalId, FestivalSeries
from .programme import Event, Film, ProgrammeEntry, Screening, Venue, venue_name_key
from .travel import Route, TransportMode
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
