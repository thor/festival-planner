import datetime

from festival_planner.adapters.json_files.solve_request import (
    dump_solve_request,
    load_solve_request,
)
from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event
from festival_planner.domain.tests.builders import DAY, at, entry, request, screening
from festival_planner.domain.travel import Route


def test_round_trips_every_field(tmp_path):
    original = request(
        screening(
            "a", "14:00", "16:00", events=(Event("Panel", at("16:15"), at("17:00")),)
        ),
        screening("b", "18:00", "20:00", venue="B"),
        entries=(entry("a", year=1960), entry("b")),
        routes=(Route("A", "B", "bike", 8),),
        preferences=Preferences(
            buffer_minutes=10,
            venue_buffer_minutes={"A": 20},
            start_date=DAY,
            end_date=DAY + datetime.timedelta(days=2),
            programme_entry_weights={"a": 2.0},
            screening_weights={"b": 0.5},
            year_weights={1960: 0.3},
            event_weight=0.4,
            attend_events=True,
            transport_mode="bike",
        ),
        screening_commitments=frozenset({"a"}),
        film_commitments=frozenset({"b"}),
        excluded_screenings=frozenset({"x"}),
        excluded_programme_entries=frozenset({"y"}),
        seen_films=frozenset({"film-z"}),
        active_schedule=frozenset({"a"}),
        now=at("12:00"),
        time_limit_seconds=5.0,
    )
    path = tmp_path / "request.json"

    dump_solve_request(original, path)

    assert load_solve_request(path) == original
