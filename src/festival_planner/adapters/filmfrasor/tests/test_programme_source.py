import datetime
from pathlib import Path

from festival_planner.adapters.filmfrasor import programme_source
from festival_planner.adapters.filmfrasor.programme_source import (
    FilmfrasorProgrammeSource,
    programme_from_films,
)
from festival_planner.models import Film, FilmList


def row(
    url: str | None = "https://www.filmfrasor.no/no/film/fallen-leaves",
    start: int = 18,
    cinema: str = "Vika Kino",
    notes: str | None = None,
    title: str = "Fallen Leaves",
) -> Film:
    return Film(
        title=title,
        country="FI",
        year=2023,
        url=url,
        cinema=cinema,
        auditorium="3",
        start_time=datetime.datetime(2025, 11, 8, start),
        end_time=datetime.datetime(2025, 11, 8, start + 2),
        special_notes=notes,
    )


def test_festival_and_series_are_named_after_the_year():
    festival = programme_from_films([row()], 2025).festival
    assert (festival.slug, festival.name, festival.time_zone) == (
        "films-from-the-south-2025",
        "Films from the South 2025",
        "Europe/Oslo",
    )
    assert festival.series is not None
    assert festival.series.slug == "films-from-the-south"


def test_rows_of_one_film_page_become_one_entry_keyed_by_its_path_without_language():
    [entry] = programme_from_films([row(start=18), row(start=21)], 2025).entries
    assert entry.source_key == "film/fallen-leaves"
    assert [s.start_time.hour for s in entry.screenings] == [18, 21]


def test_the_same_page_in_another_language_has_the_same_key():
    en = row(url="https://www.filmfrasor.no/en/film/fallen-leaves")
    assert programme_from_films([en], 2025).entries[0].source_key == (
        "film/fallen-leaves"
    )


def test_entry_and_screening_details_are_carried_over():
    [entry] = programme_from_films([row()], 2025).entries
    assert (entry.title, entry.year, entry.country, entry.url) == (
        "Fallen Leaves",
        2023,
        "FI",
        "https://www.filmfrasor.no/no/film/fallen-leaves",
    )
    [screening] = entry.screenings
    assert (screening.venue_name, screening.auditorium) == ("Vika Kino", "3")


def test_times_are_oslo_local():
    [entry] = programme_from_films([row()], 2025).entries
    assert entry.screenings[0].start_time.utcoffset() == datetime.timedelta(hours=1)
    assert entry.screenings[0].end_time.utcoffset() == datetime.timedelta(hours=1)


def test_special_notes_become_an_event_within_the_screening():
    [entry] = programme_from_films([row(notes="Q&A")], 2025).entries
    [event] = entry.screenings[0].events
    assert event.description == "Q&A"
    assert not event.is_separately_timed


def test_screenings_without_special_notes_have_no_events():
    [entry] = programme_from_films([row()], 2025).entries
    assert entry.screenings[0].events == ()


def test_rows_without_url_are_keyed_by_title():
    [entry] = programme_from_films([row(url=None, title="Shorts  I")], 2025).entries
    assert entry.source_key == "title:shorts i"


def test_fetch_scrapes_the_year_with_the_known_venue_names(monkeypatch):
    created: list[dict] = []

    class StubScraper:
        def __init__(self, **kwargs):
            created.append(kwargs)

        def scrape(self) -> FilmList:
            return FilmList(films=[row()])

    monkeypatch.setattr(programme_source, "FilmfrasorScraper", StubScraper)
    source = FilmfrasorProgrammeSource(
        2025, known_venue_names=["Vika Kino"], cache_dir=Path("/tmp/cache")
    )

    programme = source.fetch()

    assert programme.festival.slug == "films-from-the-south-2025"
    assert [e.source_key for e in programme.entries] == ["film/fallen-leaves"]
    [kwargs] = created
    assert kwargs["year"] == 2025
    assert kwargs["cache_dir"] == Path("/tmp/cache")
    assert kwargs["force_refresh"] is False
    assert list(kwargs["known_venue_names"]) == ["Vika Kino"]
