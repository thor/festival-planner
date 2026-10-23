"""Terse builders for domain values in tests."""

import datetime
import zoneinfo
from collections.abc import Iterable

from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import (
    Event,
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
)
from festival_planner.domain.solving import SolveRequest
from festival_planner.domain.travel import Route, RouteTable

DAY = datetime.date(2025, 11, 8)
ZONE = "Europe/Oslo"


def at(hhmm: str, day: datetime.date = DAY) -> datetime.datetime:
    """`at("18:30")` is 18:30 Oslo time on `DAY`."""
    return datetime.datetime.combine(
        day, datetime.time.fromisoformat(hhmm), tzinfo=zoneinfo.ZoneInfo(ZONE)
    )


def entry(
    id: str, *, film_id: str | None = None, year: int | None = None
) -> ProgrammeEntry:
    return ProgrammeEntry(
        id=ProgrammeEntryId(id),
        film_id=FilmId(film_id or f"film-{id}"),
        title=id,
        year=year,
    )


def screening(
    id: str,
    start: str,
    end: str,
    *,
    entry_id: str | None = None,
    venue: str = "A",
    day: datetime.date = DAY,
    events: tuple[Event, ...] = (),
) -> Screening:
    return Screening(
        id=ScreeningId(id),
        programme_entry_id=ProgrammeEntryId(entry_id or id),
        venue_id=VenueId(venue),
        start_time=at(start, day),
        end_time=at(end, day),
        events=events,
    )


def request(
    *screenings: Screening,
    entries: tuple[ProgrammeEntry, ...] | None = None,
    routes: tuple[Route, ...] = (),
    preferences: Preferences | None = None,
    time_zone: str = ZONE,
    screening_commitments: Iterable[str] = (),
    film_commitments: Iterable[str] = (),
    excluded_screenings: Iterable[str] = (),
    excluded_programme_entries: Iterable[str] = (),
    seen_films: Iterable[str] = (),
    active_schedule: Iterable[str] = (),
    now: datetime.datetime | None = None,
    time_limit_seconds: float = 60.0,
) -> SolveRequest:
    """A SolveRequest whose entries default to one per distinct entry id."""
    if entries is None:
        entry_ids = dict.fromkeys(s.programme_entry_id for s in screenings)
        entries = tuple(entry(entry_id) for entry_id in entry_ids)
    venue_ids = dict.fromkeys(s.venue_id for s in screenings)
    return SolveRequest(
        venues=tuple(Venue(id=v, name=v) for v in venue_ids),
        programme_entries=entries,
        screenings=screenings,
        time_zone=time_zone,
        routes=RouteTable(routes=routes),
        preferences=preferences or Preferences(buffer_minutes=0),
        screening_commitments=frozenset(ScreeningId(i) for i in screening_commitments),
        film_commitments=frozenset(ProgrammeEntryId(i) for i in film_commitments),
        excluded_screenings=frozenset(ScreeningId(i) for i in excluded_screenings),
        excluded_programme_entries=frozenset(
            ProgrammeEntryId(i) for i in excluded_programme_entries
        ),
        seen_films=frozenset(FilmId(i) for i in seen_films),
        active_schedule=frozenset(ScreeningId(i) for i in active_schedule),
        now=now,
        time_limit_seconds=time_limit_seconds,
    )
