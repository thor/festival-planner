import pytest

from festival_planner.domain.travel import MissingRouteError, Route, RouteTable


def test_same_venue_needs_no_travel():
    assert RouteTable().minutes("A", "A", None) == 0


def test_uses_route_for_chosen_mode():
    table = RouteTable(
        routes=(
            Route(
                from_venue_id="A", to_venue_id="B", mode="walk+e-scooter", minutes=10
            ),
            Route(from_venue_id="A", to_venue_id="B", mode="bike", minutes=7),
        )
    )
    assert table.minutes("A", "B", "bike") == 7


def test_falls_back_to_default_mode():
    table = RouteTable(
        routes=(
            Route(
                from_venue_id="A", to_venue_id="B", mode="walk+e-scooter", minutes=10
            ),
        )
    )
    assert table.minutes("A", "B", "bike") == 10


def test_routes_are_one_directional():
    table = RouteTable(
        routes=(
            Route(
                from_venue_id="A", to_venue_id="B", mode="walk+e-scooter", minutes=10
            ),
        )
    )
    with pytest.raises(MissingRouteError):
        table.minutes("B", "A", None)
