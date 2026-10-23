"""The ingestion repository ports over SQLAlchemy rows.

Rows have no relationships between parent tables, so the session does not
order their inserts by foreign key: every write flushes, so that rows saved
earlier are in the database before rows that refer to them, constraint
violations surface at the call, and later queries in the same unit of work see
the rows.
"""

from collections.abc import Iterable, Mapping

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...domain.festival import Festival, FestivalId, FestivalSeries, FestivalSeriesId
from ...domain.programme import (
    EntryDetails,
    Event,
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
from ...domain.travel import Route
from .tables import (
    FestivalRow,
    FestivalSeriesRow,
    FilmRow,
    ProgrammeEntryRow,
    RouteRow,
    ScreeningEventRow,
    ScreeningRow,
    VenueAliasRow,
    VenueRow,
)


class SqlAlchemyFestivalRepository:
    def __init__(self, session: Session):
        self._session = session

    def by_slug(self, slug: str) -> Festival | None:
        row = self._session.scalars(
            select(FestivalRow).where(FestivalRow.slug == slug)
        ).one_or_none()
        return None if row is None else _festival(row)

    def save(self, festival: Festival) -> None:
        row = self._session.get(FestivalRow, festival.id) or FestivalRow(id=festival.id)
        row.slug = festival.slug
        row.name = festival.name
        row.start_date = festival.start_date
        row.end_date = festival.end_date
        row.time_zone = festival.time_zone
        row.series_id = festival.series_id
        self._session.add(row)
        self._session.flush()

    def by_id(self, festival_id: FestivalId) -> Festival | None:
        row = self._session.get(FestivalRow, festival_id)
        return None if row is None else _festival(row)

    def all(self) -> tuple[Festival, ...]:
        rows = self._session.scalars(select(FestivalRow))
        return tuple(_festival(row) for row in rows)

    def by_ids(self, ids: Iterable[FestivalId]) -> tuple[Festival, ...]:
        wanted = sorted(set(ids))
        if not wanted:
            return ()
        rows = self._session.scalars(
            select(FestivalRow).where(FestivalRow.id.in_(wanted))
        )
        return tuple(_festival(row) for row in rows)

    def series_by_slug(self, slug: str) -> FestivalSeries | None:
        row = self._session.scalars(
            select(FestivalSeriesRow).where(FestivalSeriesRow.slug == slug)
        ).one_or_none()
        return None if row is None else _series(row)

    def series_by_ids(
        self, ids: Iterable[FestivalSeriesId]
    ) -> tuple[FestivalSeries, ...]:
        wanted = sorted(set(ids))
        if not wanted:
            return ()
        rows = self._session.scalars(
            select(FestivalSeriesRow).where(FestivalSeriesRow.id.in_(wanted))
        )
        return tuple(_series(row) for row in rows)

    def save_series(self, series: FestivalSeries) -> None:
        row = self._session.get(FestivalSeriesRow, series.id) or FestivalSeriesRow(
            id=series.id
        )
        row.slug, row.name = series.slug, series.name
        self._session.add(row)
        self._session.flush()


def _series(row: FestivalSeriesRow) -> FestivalSeries:
    return FestivalSeries(id=FestivalSeriesId(row.id), slug=row.slug, name=row.name)


def _festival(row: FestivalRow) -> Festival:
    return Festival(
        id=FestivalId(row.id),
        slug=row.slug,
        name=row.name,
        start_date=row.start_date,
        end_date=row.end_date,
        time_zone=row.time_zone,
        series_id=FestivalSeriesId(row.series_id)
        if row.series_id is not None
        else None,
    )


class SqlAlchemyVenueRepository:
    def __init__(self, session: Session):
        self._session = session

    def all(self) -> tuple[Venue, ...]:
        rows = self._session.scalars(select(VenueRow).order_by(VenueRow.name))
        return tuple(
            Venue(
                id=VenueId(row.id),
                name=row.name,
                aliases=frozenset(a.alias for a in row.aliases),
            )
            for row in rows
        )

    def save(self, venue: Venue) -> None:
        row = self._session.get(VenueRow, venue.id) or VenueRow(id=venue.id)
        row.name = venue.name
        # Keep the alias rows that stay, so their primary keys are not deleted
        # and re-inserted in one flush.
        kept = [a for a in row.aliases if a.alias in venue.aliases]
        known = {a.alias for a in kept}
        row.aliases = kept + [
            VenueAliasRow(alias=alias)
            for alias in sorted(venue.aliases)
            if alias not in known
        ]
        self._session.add(row)
        self._session.flush()


class SqlAlchemyRouteRepository:
    def __init__(self, session: Session):
        self._session = session

    def all(self) -> tuple[Route, ...]:
        rows = self._session.scalars(
            select(RouteRow).order_by(
                RouteRow.from_venue_id, RouteRow.to_venue_id, RouteRow.mode
            )
        )
        return tuple(
            Route(
                from_venue_id=VenueId(row.from_venue_id),
                to_venue_id=VenueId(row.to_venue_id),
                mode=row.mode,
                minutes=row.minutes,
            )
            for row in rows
        )

    def replace_all(self, routes: Iterable[Route]) -> None:
        routes = tuple(routes)  # may be a view of the rows deleted next
        self._session.execute(delete(RouteRow))
        self._session.add_all(
            RouteRow(
                from_venue_id=r.from_venue_id,
                to_venue_id=r.to_venue_id,
                mode=r.mode,
                minutes=r.minutes,
            )
            for r in routes
        )
        self._session.flush()


class SqlAlchemyFilmRepository:
    def __init__(self, session: Session):
        self._session = session

    def find(self, title: str, year: int) -> Film | None:
        row = self._session.scalars(
            select(FilmRow)
            .where(FilmRow.match_key == title_key(title), FilmRow.year == year)
            .order_by(FilmRow.id)
            .limit(1)
        ).first()
        return (
            None
            if row is None
            else Film(id=FilmId(row.id), title=row.title, year=row.year)
        )

    def by_id(self, film_id: FilmId) -> Film | None:
        row = self._session.get(FilmRow, film_id)
        return (
            None
            if row is None
            else Film(id=FilmId(row.id), title=row.title, year=row.year)
        )

    def by_ids(self, ids: Iterable[FilmId]) -> tuple[Film, ...]:
        wanted = sorted(set(ids))
        if not wanted:
            return ()
        rows = self._session.scalars(select(FilmRow).where(FilmRow.id.in_(wanted)))
        return tuple(
            Film(id=FilmId(row.id), title=row.title, year=row.year) for row in rows
        )

    def save(self, film: Film) -> None:
        row = self._session.get(FilmRow, film.id) or FilmRow(id=film.id)
        row.title, row.year, row.match_key = (
            film.title,
            film.year,
            title_key(film.title),
        )
        self._session.add(row)
        self._session.flush()


class SqlAlchemyProgrammeRepository:
    def __init__(self, session: Session):
        self._session = session

    def entries(self, festival_id: FestivalId) -> Mapping[str, ProgrammeEntry]:
        rows = self._session.scalars(
            select(ProgrammeEntryRow)
            .where(ProgrammeEntryRow.festival_id == festival_id)
            .order_by(ProgrammeEntryRow.source_key)
        )
        return {row.source_key: _entry(row) for row in rows}

    def entries_by_id(
        self, ids: Iterable[ProgrammeEntryId]
    ) -> tuple[ProgrammeEntry, ...]:
        rows = self._session.scalars(
            select(ProgrammeEntryRow)
            .where(ProgrammeEntryRow.id.in_(sorted(set(ids))))
            .order_by(ProgrammeEntryRow.id)
        )
        return tuple(_entry(row) for row in rows)

    def screenings_by_id(self, ids: Iterable[ScreeningId]) -> tuple[Screening, ...]:
        wanted = sorted(set(ids))
        if not wanted:
            return ()
        rows = self._session.scalars(
            select(ScreeningRow)
            .where(ScreeningRow.id.in_(wanted))
            .order_by(ScreeningRow.start_time, ScreeningRow.id)
        )
        return tuple(_screening(row) for row in rows)

    def screenings_of_entries(
        self, ids: Iterable[ProgrammeEntryId]
    ) -> tuple[Screening, ...]:
        wanted = sorted(set(ids))
        if not wanted:
            return ()
        rows = self._session.scalars(
            select(ScreeningRow)
            .where(ScreeningRow.programme_entry_id.in_(wanted))
            .order_by(ScreeningRow.start_time, ScreeningRow.id)
        )
        return tuple(_screening(row) for row in rows)

    def save_entry(
        self, festival_id: FestivalId, source_key: str, entry: ProgrammeEntry
    ) -> None:
        row = self._session.get(ProgrammeEntryRow, entry.id) or ProgrammeEntryRow(
            id=entry.id
        )
        row.festival_id, row.source_key = festival_id, source_key
        row.film_id = entry.film_id
        row.title = entry.title
        row.year = entry.year
        row.country = entry.country
        row.url = entry.url
        # Detail columns are named after EntryDetails' fields.
        for field, value in entry.details.model_dump().items():
            setattr(row, field, value)
        self._session.add(row)
        self._session.flush()

    def screenings(self, festival_id: FestivalId) -> tuple[Screening, ...]:
        rows = self._session.scalars(
            select(ScreeningRow)
            .join(
                ProgrammeEntryRow,
                ScreeningRow.programme_entry_id == ProgrammeEntryRow.id,
            )
            .where(ProgrammeEntryRow.festival_id == festival_id)
            .order_by(ScreeningRow.start_time, ScreeningRow.id)
        )
        return tuple(_screening(row) for row in rows)

    def save_screening(self, screening: Screening) -> None:
        row = self._session.get(ScreeningRow, screening.id) or ScreeningRow(
            id=screening.id
        )
        row.programme_entry_id = screening.programme_entry_id
        row.venue_id = screening.venue_id
        row.start_time = screening.start_time
        row.end_time = screening.end_time
        row.auditorium = screening.auditorium
        row.ticket_url = screening.ticket_url
        row.withdrawn = screening.withdrawn
        row.events = [
            ScreeningEventRow(
                position=position,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
            )
            for position, event in enumerate(screening.events)
        ]
        self._session.add(row)
        self._session.flush()


def _entry(row: ProgrammeEntryRow) -> ProgrammeEntry:
    return ProgrammeEntry(
        id=ProgrammeEntryId(row.id),
        film_id=FilmId(row.film_id),
        title=row.title,
        year=row.year,
        country=row.country,
        url=row.url,
        details=EntryDetails.model_validate(row, from_attributes=True),
    )


def _screening(row: ScreeningRow) -> Screening:
    return Screening(
        id=ScreeningId(row.id),
        programme_entry_id=ProgrammeEntryId(row.programme_entry_id),
        venue_id=VenueId(row.venue_id),
        start_time=row.start_time,
        end_time=row.end_time,
        auditorium=row.auditorium,
        ticket_url=row.ticket_url,
        withdrawn=row.withdrawn,
        events=tuple(
            Event(
                description=e.description,
                start_time=e.start_time,
                end_time=e.end_time,
            )
            for e in row.events
        ),
    )
