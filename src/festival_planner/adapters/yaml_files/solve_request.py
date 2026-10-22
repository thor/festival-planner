"""Build a SolveRequest from the legacy YAML films, config and preferences.

The YAML files identify everything by title, so titles become ids: one
Programme Entry and one Film per title, and one Venue per cinema name.
"""

import itertools

from ...config import Config
from ...domain.planning import Preferences
from ...domain.programme import Event, ProgrammeEntry, Screening, Venue
from ...domain.solving import SolveRequest
from ...domain.travel import Route, RouteTable
from ...models import Film

LEGACY_DEFAULT_TRAVEL_MINUTES = 30
"""Travel time assumed between cinemas without a configured travel time."""


def screening_id(film: Film) -> str:
    return f"{film.title} @ {film.start_time.isoformat()} @ {film.cinema}"


def build_solve_request(films: list[Film], config: Config) -> SolveRequest:
    """Translate legacy YAML inputs into a self-contained SolveRequest."""
    entries: dict[str, ProgrammeEntry] = {}
    for film in films:
        entries.setdefault(
            film.title,
            ProgrammeEntry(
                id=film.title,
                film_id=film.title,
                title=film.title,
                year=film.year,
                country=film.country,
                url=film.url,
            ),
        )
    venue_ids = list(dict.fromkeys(film.cinema for film in films))
    seen = config.films.seen
    excluded_on_date = {(s.title, s.date) for s in seen if s.date is not None}

    return SolveRequest(
        venues=tuple(Venue(id=v, name=v) for v in venue_ids),
        programme_entries=tuple(entries.values()),
        screenings=tuple(_screening(film) for film in films),
        routes=_route_table(config, venue_ids),
        preferences=_preferences(films, config),
        excluded_screenings=frozenset(
            screening_id(film)
            for film in films
            if (film.title, film.date) in excluded_on_date
        ),
        seen_films=frozenset(s.title for s in seen if s.date is None),
    )


def _screening(film: Film) -> Screening:
    return Screening(
        id=screening_id(film),
        programme_entry_id=film.title,
        venue_id=film.cinema,
        start_time=film.start_time,
        end_time=film.end_time,
        auditorium=film.auditorium,
        ticket_url=film.ticket_url,
        events=(Event(film.special_notes),) if film.special_notes else (),
    )


def _route_table(config: Config, venue_ids: list[str]) -> RouteTable:
    """Configured travel times work in both directions unless the reverse is
    configured separately; unconfigured pairs get the legacy default."""
    minutes = {
        (t.from_cinema, t.to_cinema): t.minutes for t in config.cinemas.travel_times
    }
    for (a, b), m in list(minutes.items()):
        minutes.setdefault((b, a), m)
    for a, b in itertools.permutations(venue_ids, 2):
        minutes.setdefault((a, b), LEGACY_DEFAULT_TRAVEL_MINUTES)
    table = RouteTable()
    return RouteTable(
        routes=tuple(
            Route(a, b, table.default_mode, m)
            for (a, b), m in minutes.items()
            if a != b
        )
    )


def _preferences(films: list[Film], config: Config) -> Preferences:
    """Screening overrides beat title overrides, which beat a scraped
    `preference_weight`, matching the legacy precedence."""
    overrides = config.films.weights
    title_weights = {w.title: w.weight for w in overrides if w.start_time is None}
    start_weights = {
        (w.title, w.start_time): w.weight for w in overrides if w.start_time is not None
    }
    screening_weights: dict[str, float] = {}
    for film in films:
        if (film.title, film.start_time) in start_weights:
            screening_weights[screening_id(film)] = start_weights[
                (film.title, film.start_time)
            ]
        elif film.title not in title_weights and film.preference_weight != 1.0:
            screening_weights[screening_id(film)] = film.preference_weight

    return Preferences(
        buffer_minutes=config.schedule.buffer_time_minutes,
        start_date=config.schedule.start_date,
        end_date=config.schedule.end_date,
        programme_entry_weights=title_weights,
        screening_weights=screening_weights,
        year_weights=config.priority.year_weights,
        event_weight=config.priority.special_notes_weight,
    )
