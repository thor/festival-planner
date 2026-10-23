"""Filmfrasor (Films from the South) as a ProgrammeSource, over the legacy scraper."""

import zoneinfo
from collections.abc import Iterable, Sequence
from pathlib import Path
from urllib.parse import urlsplit

from ...domain.ingestion import (
    SourceEntry,
    SourceFestival,
    SourceProgramme,
    SourceScreening,
    SourceSeries,
)
from ...domain.programme import EntryDetails, Event, title_key
from ...models import Film
from ...scrapers.filmfrasor import FilmfrasorScraper

FESTIVAL_TIME_ZONE = "Europe/Oslo"
LANGUAGES = frozenset({"no", "en"})
SERIES = SourceSeries(slug="films-from-the-south", name="Films from the South")


class FilmfrasorProgrammeSource:
    """ProgrammeSource: scrapes one year's programme from filmfrasor.no."""

    def __init__(
        self,
        year: int,
        *,
        known_venue_names: Iterable[str],
        cache_dir: Path | None = None,
        force_refresh: bool = False,
    ):
        self._year = year
        self._scraper = FilmfrasorScraper(
            cache_dir=cache_dir,
            year=year,
            force_refresh=force_refresh,
            known_venue_names=known_venue_names,
        )

    def fetch(self) -> SourceProgramme:
        return programme_from_films(self._scraper.scrape().films, self._year)


def programme_from_films(films: Sequence[Film], year: int) -> SourceProgramme:
    """The programme as described by the scraper's rows, one per screening.

    The rows' naive times are festival-local; rows of the same film page
    become one Programme Entry.
    """
    zone = zoneinfo.ZoneInfo(FESTIVAL_TIME_ZONE)
    rows_by_key: dict[str, list[Film]] = {}
    for film in films:
        rows_by_key.setdefault(_source_key(film), []).append(film)
    return SourceProgramme(
        festival=SourceFestival(
            slug=f"films-from-the-south-{year}",
            name=f"Films from the South {year}",
            time_zone=FESTIVAL_TIME_ZONE,
            series=SERIES,
        ),
        entries=tuple(_entry(key, rows, zone) for key, rows in rows_by_key.items()),
    )


def _source_key(film: Film) -> str:
    """The film page's path without its language prefix, e.g. "film/fallen-leaves"."""
    if not film.url:
        return f"title:{title_key(film.title)}"
    parts = [p for p in urlsplit(film.url).path.split("/") if p]
    if parts and parts[0] in LANGUAGES:
        parts = parts[1:]
    return "/".join(parts)


def _entry(key: str, rows: list[Film], zone: zoneinfo.ZoneInfo) -> SourceEntry:
    first = rows[0]
    return SourceEntry(
        source_key=key,
        title=first.title,
        year=first.year,
        country=first.country,
        url=first.url,
        details=(
            EntryDetails(**first.details.model_dump())
            if first.details
            else EntryDetails()
        ),
        screenings=tuple(
            SourceScreening(
                venue_name=r.cinema,
                start_time=r.start_time.replace(tzinfo=zone),
                end_time=r.end_time.replace(tzinfo=zone),
                auditorium=r.auditorium,
                ticket_url=r.ticket_url,
                events=(Event(description=r.special_notes),) if r.special_notes else (),
            )
            for r in rows
        ),
    )
