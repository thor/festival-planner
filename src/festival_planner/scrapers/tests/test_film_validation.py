"""Test cases for Film model cinema validation and normalization."""

import pytest
from pathlib import Path
from datetime import datetime
from pydantic import ValidationError
from festival_planner.models import Film, build_normalization_map
from festival_planner.config import ConfigLoader


class TestFilmCinemaValidation:
    """Test Film model cinema validation with config-based normalization."""

    def setup_method(self):
        """Set up test fixtures by loading actual config."""
        # Load cinema config from actual config file
        project_root = Path(__file__).parent.parent.parent.parent.parent
        config_dir = project_root / "config"
        data_dir = project_root / "data"
        loader = ConfigLoader(config_dir, data_dir)
        cinema_config = loader.load_cinema_config()

        # Set up normalization map from config
        if cinema_config.cinema_aliases:
            normalization_map = build_normalization_map(cinema_config.cinema_aliases)
            Film.set_normalization_map(normalization_map)

        # Set up valid cinemas
        valid_cinemas = loader.get_valid_cinemas(cinema_config)
        Film.set_valid_cinemas(valid_cinemas)

    def test_vika_kino_normalized_in_film_model(self):
        """Test that 'Vika Kino' in Film is normalized to 'Vika'."""
        film = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 18, 0),
            end_time=datetime(2025, 11, 8, 20, 0),
            cinema="Vika Kino",
            auditorium="3",
        )
        assert film.cinema == "Vika"

    def test_vika_lowercase_normalized(self):
        """Test that 'vika' (lowercase) is normalized to 'Vika'."""
        film = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 18, 0),
            end_time=datetime(2025, 11, 8, 20, 0),
            cinema="vika",
            auditorium="2",
        )
        assert film.cinema == "Vika"

    def test_cinemateket_lowercase_normalized(self):
        """Test that 'cinemateket' (lowercase) is normalized to 'Cinemateket'."""
        film = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 18, 0),
            end_time=datetime(2025, 11, 8, 20, 0),
            cinema="cinemateket",
            auditorium="Main",
        )
        assert film.cinema == "Cinemateket"

    def test_vega_scene_normalized(self):
        """Test that 'Vega Scene' is normalized to 'Vega'."""
        film = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 18, 0),
            end_time=datetime(2025, 11, 8, 20, 0),
            cinema="Vega Scene",
            auditorium=None,
        )
        assert film.cinema == "Vega"

    def test_canonical_name_accepted(self):
        """Test that canonical names (Vika, Vega, Cinemateket) are accepted."""
        film1 = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 18, 0),
            end_time=datetime(2025, 11, 8, 20, 0),
            cinema="Vika",
            auditorium="1",
        )
        assert film1.cinema == "Vika"

        film2 = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 19, 0),
            end_time=datetime(2025, 11, 8, 21, 0),
            cinema="Vega",
            auditorium="2",
        )
        assert film2.cinema == "Vega"

        film3 = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 20, 0),
            end_time=datetime(2025, 11, 8, 22, 0),
            cinema="Cinemateket",
            auditorium=None,
        )
        assert film3.cinema == "Cinemateket"

    def test_invalid_cinema_rejected(self):
        """Test that invalid cinema names are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Film(
                title="Test Film",
                country="Norway",
                start_time=datetime(2025, 11, 8, 18, 0),
                end_time=datetime(2025, 11, 8, 20, 0),
                cinema="Unknown Cinema",
                auditorium="1",
            )

        error = exc_info.value
        assert "not in the valid cinema list" in str(error)

    def test_auditorium_can_be_none(self):
        """Test that auditorium can be None."""
        film = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 18, 0),
            end_time=datetime(2025, 11, 8, 20, 0),
            cinema="Vika",
            auditorium=None,
        )
        assert film.auditorium is None

    def test_auditorium_with_string(self):
        """Test that auditorium can be a string."""
        film = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 18, 0),
            end_time=datetime(2025, 11, 8, 20, 0),
            cinema="Cinemateket",
            auditorium="Lillebil",
        )
        assert film.auditorium == "Lillebil"

    def test_mixed_case_alias_normalized(self):
        """Test that mixed case aliases work properly."""
        film = Film(
            title="Test Film",
            country="Norway",
            start_time=datetime(2025, 11, 8, 18, 0),
            end_time=datetime(2025, 11, 8, 20, 0),
            cinema="VIKA KINO",  # All caps
            auditorium="3",
        )
        assert film.cinema == "Vika"


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


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
