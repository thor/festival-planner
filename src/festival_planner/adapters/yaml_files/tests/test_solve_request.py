import datetime

from festival_planner.adapters.yaml_files.solve_request import (
    LEGACY_DEFAULT_TRAVEL_MINUTES,
    build_solve_request,
    screening_id,
)
from festival_planner.config import Config, FilmPreferences
from festival_planner.models import (
    CinemaConfig,
    Film,
    FilmWeight,
    PriorityConfig,
    ScheduleConfig,
    SeenFilm,
    TravelTime,
)

DAY = datetime.date(2025, 11, 8)


def film(
    title: str, hour: int, cinema: str = "Vika", day: datetime.date = DAY, **kwargs
) -> Film:
    start = datetime.datetime.combine(day, datetime.time(hour))
    return Film(
        title=title,
        country="Norway",
        start_time=start,
        end_time=start + datetime.timedelta(hours=2),
        cinema=cinema,
        **kwargs,
    )


def test_titles_become_programme_entries_and_films():
    a1, a2 = film("A", 12, year=1960, url="https://a"), film("A", 18)
    request = build_solve_request([a1, a2], Config())

    (entry,) = request.programme_entries
    assert (entry.id, entry.film_id, entry.year, entry.url) == (
        "A",
        "A",
        1960,
        "https://a",
    )
    assert [s.id for s in request.screenings] == [screening_id(a1), screening_id(a2)]
    assert {s.programme_entry_id for s in request.screenings} == {"A"}


def test_special_notes_become_an_event():
    request = build_solve_request([film("A", 12, special_notes="Q&A")], Config())
    assert request.screenings[0].events[0].description == "Q&A"


def test_seen_without_date_marks_film_seen_and_with_date_excludes_screenings():
    next_day = DAY + datetime.timedelta(days=1)
    a, b1, b2 = film("A", 12), film("B", 12), film("B", 12, day=next_day)
    config = Config(
        films=FilmPreferences(seen=[SeenFilm(title="A"), SeenFilm(title="B", date=DAY)])
    )
    request = build_solve_request([a, b1, b2], config)
    assert request.seen_films == {"A"}
    assert request.excluded_screenings == {screening_id(b1)}


def test_weight_precedence_matches_legacy_behaviour():
    a1, a2 = film("A", 12, preference_weight=3.0), film("A", 18)
    b = film("B", 12, preference_weight=3.0)
    config = Config(
        films=FilmPreferences(
            weights=[
                FilmWeight(title="A", weight=0.5),
                FilmWeight(title="A", start_time=a2.start_time, weight=2.0),
            ]
        )
    )
    preferences = build_solve_request([a1, a2, b], config).preferences
    assert preferences.programme_entry_weights == {"A": 0.5}
    assert preferences.screening_weights == {
        screening_id(a2): 2.0,
        screening_id(b): 3.0,
    }


def test_schedule_and_priority_config_become_preferences():
    config = Config(
        schedule=ScheduleConfig(buffer_time_minutes=20, start_date=DAY),
        priority=PriorityConfig(year_weights={1960: 0.3}, special_notes_weight=0.5),
    )
    preferences = build_solve_request([], config).preferences
    assert preferences.buffer_minutes == 20
    assert preferences.start_date == DAY
    assert preferences.year_weights == {1960: 0.3}
    assert preferences.event_weight == 0.5


def test_travel_times_are_symmetric_and_missing_pairs_get_default():
    config = Config(
        cinemas=CinemaConfig(
            travel_times=[TravelTime(from_cinema="Vika", to_cinema="Vega", minutes=15)]
        )
    )
    films = [film("A", 12, "Vika"), film("B", 15, "Vega"), film("C", 18, "Cinemateket")]
    routes = build_solve_request(films, config).routes
    assert routes.minutes("Vika", "Vega", None) == 15
    assert routes.minutes("Vega", "Vika", None) == 15
    assert routes.minutes("Vika", "Cinemateket", None) == LEGACY_DEFAULT_TRAVEL_MINUTES


def test_duplicate_film_rows_are_dropped_keeping_the_first():
    a = film("A", 12)
    request = build_solve_request([a, a.model_copy(), film("A", 18)], Config())
    assert [s.id for s in request.screenings] == [
        screening_id(a),
        screening_id(film("A", 18)),
    ]
