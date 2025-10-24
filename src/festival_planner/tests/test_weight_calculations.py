"""Test weight calculation logic for film scheduling."""

import datetime
import pytest
from pathlib import Path

from festival_planner.models import Film, ScheduleConfig
from festival_planner.solver import FestivalScheduleSolver


def test_base_weight():
    """Test that base weight is correctly applied."""
    config = ScheduleConfig(buffer_time_minutes=15)
    solver = FestivalScheduleSolver(films=[], travel_time_matrix={}, config=config)

    film = Film(
        title="Test Film",
        country="Test",
        year=2025,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        preference_weight=0.0,
    )

    # Base weight should be 1.0 (base) + 0.0 (preference) = 1.0
    weight = solver._calculate_film_weight(film)
    assert weight == 1.0


def test_preference_weight():
    """Test that preference weight is correctly applied."""
    config = ScheduleConfig(buffer_time_minutes=15)
    solver = FestivalScheduleSolver(films=[], travel_time_matrix={}, config=config)

    film = Film(
        title="Test Film",
        country="Test",
        year=2025,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        preference_weight=0.5,
    )

    # Weight should be 1.0 (base) + 0.5 (preference) = 1.5
    weight = solver._calculate_film_weight(film)
    assert weight == 1.5


def test_year_weight_adjustment():
    """Test that year-based weight adjustment is correctly applied."""
    config = ScheduleConfig(
        buffer_time_minutes=15,
        year_weights={1960: 0.3, 1985: 0.2},
    )
    solver = FestivalScheduleSolver(films=[], travel_time_matrix={}, config=config)

    # Film from 1960 should get +0.3 boost
    film_1960 = Film(
        title="1960 Film",
        country="Test",
        year=1960,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        preference_weight=0.0,
    )

    weight = solver._calculate_film_weight(film_1960)
    assert weight == 1.3  # 1.0 (base) + 0.0 (preference) + 0.3 (year)

    # Film from 2025 (not in year_weights) should not get boost
    film_2025 = Film(
        title="2025 Film",
        country="Test",
        year=2025,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        preference_weight=0.0,
    )

    weight = solver._calculate_film_weight(film_2025)
    assert weight == 1.0  # 1.0 (base) + 0.0 (preference)


def test_special_notes_weight():
    """Test that special notes weight adjustment is correctly applied."""
    config = ScheduleConfig(
        buffer_time_minutes=15,
        special_notes_weight=0.5,
    )
    solver = FestivalScheduleSolver(films=[], travel_time_matrix={}, config=config)

    # Film with special notes should get +0.5 boost
    film_special = Film(
        title="Special Event",
        country="Test",
        year=2025,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        special_notes="Q&A with director",
        preference_weight=0.0,
    )

    weight = solver._calculate_film_weight(film_special)
    assert weight == 1.5  # 1.0 (base) + 0.0 (preference) + 0.5 (special)

    # Film without special notes should not get boost
    film_regular = Film(
        title="Regular Screening",
        country="Test",
        year=2025,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        special_notes=None,
        preference_weight=0.0,
    )

    weight = solver._calculate_film_weight(film_regular)
    assert weight == 1.0  # 1.0 (base) + 0.0 (preference)


def test_combined_weights():
    """Test that all weight adjustments combine correctly."""
    config = ScheduleConfig(
        buffer_time_minutes=15,
        year_weights={1960: 0.3, 1985: 0.2},
        special_notes_weight=0.5,
    )
    solver = FestivalScheduleSolver(films=[], travel_time_matrix={}, config=config)

    # Film with everything: preference + year + special notes
    film = Film(
        title="Special 1960 Film",
        country="Test",
        year=1960,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        special_notes="Director Q&A",
        preference_weight=0.2,
    )

    weight = solver._calculate_film_weight(film)
    # 1.0 (base) + 0.2 (preference) + 0.3 (year) + 0.5 (special) = 2.0
    assert weight == 2.0


def test_negative_weights():
    """Test that negative weight adjustments work correctly."""
    config = ScheduleConfig(
        buffer_time_minutes=15,
        year_weights={2025: -0.2},  # Decrease priority for recent films
        special_notes_weight=-0.1,  # Decrease priority for special events
    )
    solver = FestivalScheduleSolver(films=[], travel_time_matrix={}, config=config)

    film = Film(
        title="Recent Special Event",
        country="Test",
        year=2025,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        special_notes="Special screening",
        preference_weight=0.0,
    )

    weight = solver._calculate_film_weight(film)
    # 1.0 (base) + 0.0 (preference) - 0.2 (year) - 0.1 (special) = 0.7
    assert weight == pytest.approx(0.7)


def test_film_without_year():
    """Test that films without year information are handled correctly."""
    config = ScheduleConfig(
        buffer_time_minutes=15,
        year_weights={1960: 0.3},
    )
    solver = FestivalScheduleSolver(films=[], travel_time_matrix={}, config=config)

    film = Film(
        title="Film Without Year",
        country="Test",
        year=None,
        start_time=datetime.datetime(2025, 11, 8, 14, 0),
        end_time=datetime.datetime(2025, 11, 8, 16, 0),
        cinema="Vika",
        preference_weight=0.0,
    )

    weight = solver._calculate_film_weight(film)
    # Should only have base weight since year is None
    assert weight == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

