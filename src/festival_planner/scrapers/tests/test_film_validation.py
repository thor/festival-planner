"""Tests for cinema normalisation of scraped film lists."""

import datetime
from pathlib import Path

import pytest

from festival_planner.config import ConfigLoader
from festival_planner.models import (
    CinemaConfig,
    Film,
    FilmList,
    build_normalization_map,
    normalise_cinemas,
)


@pytest.fixture
def cinemas() -> CinemaConfig:
    fixtures_dir = Path(__file__).parents[2] / "tests" / "fixtures"
    loader = ConfigLoader(
        config_dir=fixtures_dir / "config", data_dir=fixtures_dir / "data"
    )
    return loader.load_config().cinemas


def film(cinema: str) -> Film:
    return Film(
        title="T",
        country="NO",
        cinema=cinema,
        start_time=datetime.datetime(2025, 11, 8, 18),
        end_time=datetime.datetime(2025, 11, 8, 20),
    )


def test_aliases_are_mapped_to_canonical_names(cinemas):
    result = normalise_cinemas(
        FilmList(films=[film("Vika Kino"), film("vika"), film("vega scene")]), cinemas
    )
    assert [f.cinema for f in result.films] == ["Vika", "Vika", "Vega"]


def test_canonical_names_pass_through(cinemas):
    result = normalise_cinemas(FilmList(films=[film("Cinemateket")]), cinemas)
    assert [f.cinema for f in result.films] == ["Cinemateket"]


def test_unknown_cinemas_are_dropped(cinemas):
    result = normalise_cinemas(
        FilmList(films=[film("Vika"), film("Unknown Kino"), film("VIKA KINO")]),
        cinemas,
    )
    assert [f.cinema for f in result.films] == ["Vika", "Vika"]


def test_without_cinema_config_nothing_changes():
    films = FilmList(films=[film("Vika Kino"), film("Unknown Kino")])
    result = normalise_cinemas(films, CinemaConfig())
    assert [f.cinema for f in result.films] == ["Vika Kino", "Unknown Kino"]


def test_film_accepts_any_cinema_name():
    assert film("Anything").cinema == "Anything"


class TestNormalizationMapBuilding:
    """Test the build_normalization_map function."""

    def test_build_normalization_map(self):
        """Test that build_normalization_map creates correct mappings."""
        aliases = {
            "Vika": ["Vika Kino", "vika", "vika kino"],
            "Cinemateket": ["cinemateket"],
            "Vega": ["vega", "vega scene"],
        }

        norm_map = build_normalization_map(aliases)

        # Check that all aliases map to canonical names
        assert norm_map["vika kino"] == "Vika"
        assert norm_map["vika"] == "Vika"
        assert norm_map["cinemateket"] == "Cinemateket"
        assert norm_map["vega"] == "Vega"
        assert norm_map["vega scene"] == "Vega"

        # Check that canonical names map to themselves
        assert norm_map["vika"] == "Vika"  # Already lowercase
        assert norm_map["cinemateket"] == "Cinemateket"
        assert norm_map["vega"] == "Vega"

    def test_case_insensitive_normalization_map(self):
        """Test that normalization map is case-insensitive."""
        aliases = {
            "Vika": ["Vika Kino"],
        }

        norm_map = build_normalization_map(aliases)

        # All should be lowercase keys
        assert "vika kino" in norm_map
        assert "VIKA KINO" not in norm_map
        assert norm_map["vika kino"] == "Vika"

    def test_empty_aliases(self):
        """Test that empty aliases dict returns empty map."""
        norm_map = build_normalization_map({})
        assert norm_map == {}
