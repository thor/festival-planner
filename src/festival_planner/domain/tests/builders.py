"""Terse builders for domain values in tests."""

import datetime
import zoneinfo

from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event, ProgrammeEntry, Screening, Venue
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
    return ProgrammeEntry(id=id, film_id=film_id or f"film-{id}", title=id, year=year)


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
        id=id,
        programme_entry_id=entry_id or id,
        venue_id=venue,
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
    **kwargs,
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
        **kwargs,
    )
