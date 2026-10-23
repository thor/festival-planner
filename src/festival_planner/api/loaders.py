"""The DataLoaders of one request: one per relation, each batch one query."""

from collections.abc import Awaitable, Callable, Hashable, Iterable, Mapping
from typing import Protocol

from strawberry.dataloader import DataLoader

from ..domain.festival import Festival, FestivalId, FestivalSeries, FestivalSeriesId
from ..domain.programme import (
    Film,
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
)
from ..domain.programme_queries import ProgrammeQueries


class Run(Protocol):
    """Runs a blocking call off the event loop, as `Context.run` does."""

    def __call__[**P, T](
        self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs
    ) -> Awaitable[T]: ...


ScreeningsOfEntryKey = tuple[ProgrammeEntryId, bool]
"""A Programme Entry and whether to include Withdrawn Screenings."""


def _by_id[K: Hashable, V](
    run: Run, query: Callable[[Iterable[K]], Mapping[K, V]]
) -> DataLoader[K, V | None]:
    async def load(keys: list[K]) -> list[V | None]:
        found = await run(query, keys)
        return [found.get(k) for k in keys]

    return DataLoader(load_fn=load)


class Loaders:
    """Built per request, so nothing is cached across requests."""

    def __init__(self, programme: ProgrammeQueries, run: Run) -> None:
        self.festival: DataLoader[FestivalId, Festival | None] = _by_id(
            run, programme.festivals_by_id
        )
        self.festival_series: DataLoader[FestivalSeriesId, FestivalSeries | None] = (
            _by_id(run, programme.series_by_id)
        )
        self.venue: DataLoader[VenueId, Venue | None] = _by_id(
            run, programme.venues_by_id
        )
        self.film: DataLoader[FilmId, Film | None] = _by_id(run, programme.films_by_id)
        self.programme_entry: DataLoader[ProgrammeEntryId, ProgrammeEntry | None] = (
            _by_id(run, programme.programme_entries_by_id)
        )
        self.screening: DataLoader[ScreeningId, Screening | None] = _by_id(
            run, programme.screenings_by_id
        )

        async def screenings_of_entries(
            keys: list[ScreeningsOfEntryKey],
        ) -> list[tuple[Screening, ...]]:
            # One query for the whole batch; Withdrawn ones are dropped per key.
            found = await run(
                programme.screenings_of_entries,
                {entry_id for entry_id, _ in keys},
                include_withdrawn=True,
            )
            return [
                tuple(
                    s for s in found[entry_id] if include_withdrawn or not s.withdrawn
                )
                for entry_id, include_withdrawn in keys
            ]

        self.screenings_of_entry: DataLoader[
            ScreeningsOfEntryKey, tuple[Screening, ...]
        ] = DataLoader(load_fn=screenings_of_entries)
