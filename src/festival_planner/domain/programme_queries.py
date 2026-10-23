"""ProgrammeQueries: the read side of festival data.

The GraphQL API reads festival data only through here, never through the
ingestion ports directly; its DataLoaders batch through the `*_by_id`
methods. Each call opens its own unit of work.
"""

from collections.abc import Callable, Iterable, Mapping

from .festival import Festival, FestivalId, FestivalSeries, FestivalSeriesId
from .ingestion import UnitOfWork
from .programme import (
    Film,
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
    title_key,
)


class ProgrammeQueries:
    def __init__(self, unit_of_work: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work = unit_of_work

    def festivals(self) -> tuple[Festival, ...]:
        with self._unit_of_work() as uow:
            return tuple(
                sorted(uow.festivals.all(), key=lambda f: (f.start_date, f.slug))
            )

    def festival(self, slug: str) -> Festival | None:
        with self._unit_of_work() as uow:
            return uow.festivals.by_slug(slug)

    def festivals_by_id(
        self, ids: Iterable[FestivalId]
    ) -> Mapping[FestivalId, Festival]:
        wanted = frozenset(ids)
        if not wanted:
            return {}
        with self._unit_of_work() as uow:
            return {f.id: f for f in uow.festivals.by_ids(wanted)}

    def series_by_id(
        self, ids: Iterable[FestivalSeriesId]
    ) -> Mapping[FestivalSeriesId, FestivalSeries]:
        wanted = frozenset(ids)
        if not wanted:
            return {}
        with self._unit_of_work() as uow:
            return {s.id: s for s in uow.festivals.series_by_ids(wanted)}

    def venues(self) -> tuple[Venue, ...]:
        with self._unit_of_work() as uow:
            return tuple(sorted(uow.venues.all(), key=lambda v: (v.name, v.id)))

    def venues_by_id(self, ids: Iterable[VenueId]) -> Mapping[VenueId, Venue]:
        wanted = frozenset(ids)
        if not wanted:
            return {}
        with self._unit_of_work() as uow:
            return {v.id: v for v in uow.venues.all() if v.id in wanted}

    def films_by_id(self, ids: Iterable[FilmId]) -> Mapping[FilmId, Film]:
        wanted = frozenset(ids)
        if not wanted:
            return {}
        with self._unit_of_work() as uow:
            return {f.id: f for f in uow.films.by_ids(wanted)}

    def programme_entries(self, festival_id: FestivalId) -> tuple[ProgrammeEntry, ...]:
        with self._unit_of_work() as uow:
            entries = uow.programme.entries(festival_id).values()
            return tuple(sorted(entries, key=lambda e: (title_key(e.title), e.id)))

    def programme_entries_by_id(
        self, ids: Iterable[ProgrammeEntryId]
    ) -> Mapping[ProgrammeEntryId, ProgrammeEntry]:
        wanted = frozenset(ids)
        if not wanted:
            return {}
        with self._unit_of_work() as uow:
            return {e.id: e for e in uow.programme.entries_by_id(wanted)}

    def screenings(
        self, festival_id: FestivalId, *, include_withdrawn: bool
    ) -> tuple[Screening, ...]:
        with self._unit_of_work() as uow:
            screenings = uow.programme.screenings(festival_id)
        if not include_withdrawn:
            screenings = tuple(s for s in screenings if not s.withdrawn)
        return tuple(sorted(screenings, key=lambda s: (s.start_time, s.id)))

    def screenings_by_id(
        self, ids: Iterable[ScreeningId]
    ) -> Mapping[ScreeningId, Screening]:
        wanted = frozenset(ids)
        if not wanted:
            return {}
        with self._unit_of_work() as uow:
            return {s.id: s for s in uow.programme.screenings_by_id(wanted)}

    def screenings_of_entries(
        self, ids: Iterable[ProgrammeEntryId], *, include_withdrawn: bool
    ) -> Mapping[ProgrammeEntryId, tuple[Screening, ...]]:
        wanted = frozenset(ids)
        if not wanted:
            return {}
        with self._unit_of_work() as uow:
            screenings = uow.programme.screenings_of_entries(wanted)
        if not include_withdrawn:
            screenings = tuple(s for s in screenings if not s.withdrawn)
        by_entry: dict[ProgrammeEntryId, list[Screening]] = {i: [] for i in wanted}
        for s in screenings:
            by_entry[s.programme_entry_id].append(s)
        return {
            entry_id: tuple(sorted(group, key=lambda s: (s.start_time, s.id)))
            for entry_id, group in by_entry.items()
        }
