"""In-memory implementations of the repository ports, for use-case tests."""

import copy
import itertools
from collections.abc import Callable, Iterable, Mapping
from typing import Self

from festival_planner.domain.festival import Festival, FestivalSeries
from festival_planner.domain.programme import (
    Film,
    ProgrammeEntry,
    Screening,
    Venue,
    title_key,
)
from festival_planner.domain.travel import Route


def sequential_ids() -> Callable[[], str]:
    """A deterministic `new_id`: "id-1", "id-2", ..."""
    counter = itertools.count(1)
    return lambda: f"id-{next(counter)}"


class _State:
    def __init__(self) -> None:
        self.series: dict[str, FestivalSeries] = {}
        self.festivals: dict[str, Festival] = {}
        self.venues: dict[str, Venue] = {}
        self.routes: list[Route] = []
        self.films: dict[str, Film] = {}
        self.entries: dict[str, tuple[str, str, ProgrammeEntry]] = {}
        """entry id -> (festival id, source key, entry)"""
        self.screenings: dict[str, Screening] = {}


class InMemoryUnitOfWork:
    """Works on a copy of `stored`; `commit()` makes the copy the stored state."""

    def __init__(self) -> None:
        self.stored = _State()
        self.committed = False

    def __enter__(self) -> Self:
        self._work = copy.deepcopy(self.stored)
        self.festivals = _Festivals(self._work)
        self.venues = _Venues(self._work)
        self.routes = _Routes(self._work)
        self.films = _Films(self._work)
        self.programme = _Programme(self._work)
        return self

    def __exit__(self, *exc: object) -> None:
        del self._work

    def commit(self) -> None:
        self.stored = copy.deepcopy(self._work)
        self.committed = True


class _Festivals:
    def __init__(self, state: _State) -> None:
        self.s = state

    def by_slug(self, slug: str) -> Festival | None:
        return next((f for f in self.s.festivals.values() if f.slug == slug), None)

    def save(self, festival: Festival) -> None:
        self.s.festivals[festival.id] = festival

    def series_by_slug(self, slug: str) -> FestivalSeries | None:
        return next((x for x in self.s.series.values() if x.slug == slug), None)

    def save_series(self, series: FestivalSeries) -> None:
        self.s.series[series.id] = series


class _Venues:
    def __init__(self, state: _State) -> None:
        self.s = state

    def all(self) -> tuple[Venue, ...]:
        return tuple(self.s.venues.values())

    def save(self, venue: Venue) -> None:
        self.s.venues[venue.id] = venue


class _Routes:
    def __init__(self, state: _State) -> None:
        self.s = state

    def all(self) -> tuple[Route, ...]:
        return tuple(self.s.routes)

    def replace_all(self, routes: Iterable[Route]) -> None:
        self.s.routes = list(routes)


class _Films:
    def __init__(self, state: _State) -> None:
        self.s = state

    def find(self, title: str, year: int) -> Film | None:
        return next(
            (
                f
                for f in self.s.films.values()
                if title_key(f.title) == title_key(title) and f.year == year
            ),
            None,
        )

    def save(self, film: Film) -> None:
        self.s.films[film.id] = film


class _Programme:
    def __init__(self, state: _State) -> None:
        self.s = state

    def entries(self, festival_id: str) -> Mapping[str, ProgrammeEntry]:
        return {key: e for fid, key, e in self.s.entries.values() if fid == festival_id}

    def save_entry(
        self, festival_id: str, source_key: str, entry: ProgrammeEntry
    ) -> None:
        self.s.entries[entry.id] = (festival_id, source_key, entry)

    def screenings(self, festival_id: str) -> tuple[Screening, ...]:
        ids = {e.id for fid, _, e in self.s.entries.values() if fid == festival_id}
        return tuple(
            s for s in self.s.screenings.values() if s.programme_entry_id in ids
        )

    def save_screening(self, screening: Screening) -> None:
        self.s.screenings[screening.id] = screening
