from festival_planner.adapters.yaml_files.venues import CinemaConfigVenues
from festival_planner.models import CinemaConfig, TravelTime


def travel(a: str, b: str, minutes: int) -> TravelTime:
    return TravelTime(from_cinema=a, to_cinema=b, minutes=minutes)


cinemas = CinemaConfig(
    cinema_aliases={"Vika": ["Vika Kino"], "Vega": ["vega scene"]},
    travel_times=[travel("Vika", "Vega", 15), travel("Vega", "Cinemateket", 20)],
)


def test_venues_are_the_canonical_names_with_aliases_plus_travel_time_endpoints():
    venues = CinemaConfigVenues(cinemas).venues()
    assert {(v.name, v.aliases) for v in venues} == {
        ("Vika", frozenset({"Vika Kino"})),
        ("Vega", frozenset({"vega scene"})),
        ("Cinemateket", frozenset()),
    }


def test_travel_times_apply_both_ways_unless_the_reverse_is_configured():
    routes = CinemaConfigVenues(cinemas).routes(venues=())
    assert {(r.from_venue, r.to_venue, r.minutes) for r in routes} == {
        ("Vika", "Vega", 15),
        ("Vega", "Vika", 15),
        ("Vega", "Cinemateket", 20),
        ("Cinemateket", "Vega", 20),
    }
    assert {r.mode for r in routes} == {"walk+e-scooter"}


def test_a_configured_reverse_travel_time_wins():
    config = CinemaConfig(
        travel_times=[travel("Vika", "Vega", 15), travel("Vega", "Vika", 10)]
    )
    routes = CinemaConfigVenues(config).routes(venues=())
    assert {(r.from_venue, r.to_venue, r.minutes) for r in routes} == {
        ("Vika", "Vega", 15),
        ("Vega", "Vika", 10),
    }


def test_the_transport_mode_can_be_chosen():
    routes = CinemaConfigVenues(cinemas, mode="walk").routes(venues=())
    assert {r.mode for r in routes} == {"walk"}


def test_self_routes_are_ignored():
    config = CinemaConfig(travel_times=[travel("Klingenberg", "Klingenberg", 0)])
    assert CinemaConfigVenues(config).routes(venues=()) == ()


def test_travel_time_endpoints_that_are_aliases_become_their_canonical_venue():
    config = CinemaConfig(
        cinema_aliases={"Vika": ["Vika Kino"]},
        travel_times=[travel("vika kino", "Vega", 15)],
    )
    source = CinemaConfigVenues(config)
    assert {(v.name, v.aliases) for v in source.venues()} == {
        ("Vika", frozenset({"Vika Kino"})),
        ("Vega", frozenset()),
    }
    assert {(r.from_venue, r.to_venue) for r in source.routes(venues=())} == {
        ("Vika", "Vega"),
        ("Vega", "Vika"),
    }


def test_an_alias_and_its_canonical_name_are_the_same_route_endpoint():
    config = CinemaConfig(
        cinema_aliases={"Vika": ["Vika Kino"]},
        travel_times=[travel("Vika Kino", "Vega", 15), travel("Vega", "Vika", 10)],
    )
    routes = CinemaConfigVenues(config).routes(venues=())
    assert {(r.from_venue, r.to_venue, r.minutes) for r in routes} == {
        ("Vika", "Vega", 15),
        ("Vega", "Vika", 10),
    }
