"""Test cases for cinema and auditorium parsing logic."""

import pytest
from pathlib import Path
from festival_planner.scrapers.filmfrasor import FilmfrasorScraper
from festival_planner.models import Film, build_normalization_map
from festival_planner.config import ConfigLoader


class TestCinemaAndAuditoriumParsing:
    """Test the _split_cinema_and_auditorium method."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create a scraper instance for testing
        self.scraper = FilmfrasorScraper()

        # Load cinema config from actual config file for normalization testing
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

    # Test cases for Vika Kino normalization
    def test_vika_kino_normalized_to_vika(self):
        """Test that 'Vika Kino' is normalized to just 'Vika'."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Vika Kino")
        assert cinema == "Vika"
        assert auditorium is None

    def test_vika_kino_with_number(self):
        """Test that 'Vika Kino 3' becomes cinema='Vika', auditorium='3'."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Vika Kino 3")
        assert cinema == "Vika"
        assert auditorium == "3"

    def test_vika_kino_case_insensitive(self):
        """Test that 'VIKA KINO' is normalized (case insensitive)."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("VIKA KINO")
        assert cinema == "Vika"
        assert auditorium is None

    def test_vika_with_number(self):
        """Test that 'Vika 3' becomes cinema='Vika', auditorium='3'."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Vika 3")
        assert cinema == "Vika"
        assert auditorium == "3"

    def test_vika_alone(self):
        """Test that 'Vika' without auditorium returns None."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Vika")
        assert cinema == "Vika"
        assert auditorium is None

    # Test cases for Cinemateket auditorium parsing
    def test_cinemateket_with_named_auditorium(self):
        """Test that 'Cinemateket Lillebil' becomes cinema='Cinemateket', auditorium='Lillebil'."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Cinemateket Lillebil")
        assert cinema == "Cinemateket"
        assert auditorium == "Lillebil"

    def test_cinemateket_with_tancred(self):
        """Test that 'Cinemateket Tancred' becomes cinema='Cinemateket', auditorium='Tancred'."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Cinemateket Tancred")
        assert cinema == "Cinemateket"
        assert auditorium == "Tancred"

    def test_cinemateket_with_usf(self):
        """Test that 'Cinemateket USF' becomes cinema='Cinemateket', auditorium='USF'."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Cinemateket USF")
        assert cinema == "Cinemateket"
        assert auditorium == "USF"

    def test_cinemateket_with_main(self):
        """Test that 'Cinemateket Main' becomes cinema='Cinemateket', auditorium='Main'."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Cinemateket Main")
        assert cinema == "Cinemateket"
        assert auditorium == "Main"

    def test_cinemateket_alone(self):
        """Test that 'Cinemateket' without auditorium returns None."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Cinemateket")
        assert cinema == "Cinemateket"
        assert auditorium is None

    def test_cinemateket_case_insensitive(self):
        """Test that 'cinemateket lillebil' works (case insensitive)."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("cinemateket lillebil")
        assert cinema == "Cinemateket"
        assert auditorium == "lillebil"

    # Test cases for Vega
    def test_vega_with_number(self):
        """Test that 'Vega 2' becomes cinema='Vega', auditorium='2'."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Vega 2")
        assert cinema == "Vega"
        assert auditorium == "2"

    def test_vega_alone(self):
        """Test that 'Vega' without auditorium returns None."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Vega")
        assert cinema == "Vega"
        assert auditorium is None

    def test_vega_scene(self):
        """Test that 'Vega Scene' is treated as cinema without auditorium."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Vega Scene")
        assert cinema == "Vega Scene"
        assert auditorium is None

    # Test cases for no auditorium (None/null)
    def test_unknown_cinema_no_number(self):
        """Test that cinema without number returns None for auditorium."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Some Cinema")
        assert cinema == "Some Cinema"
        assert auditorium is None

    def test_empty_string(self):
        """Test that empty string returns empty cinema and None auditorium."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("")
        assert cinema == ""
        assert auditorium is None

    def test_whitespace_only(self):
        """Test that whitespace-only string returns empty cinema and None auditorium."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("   ")
        assert cinema == ""
        assert auditorium is None

    # Edge cases
    def test_cinema_with_multiple_words_and_number(self):
        """Test cinema name with multiple words followed by number."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Some Long Cinema Name 5")
        assert cinema == "Some Long Cinema Name"
        assert auditorium == "5"

    def test_cinema_with_number_in_name(self):
        """Test cinema with number in name (not at end)."""
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Cinema 21 Oslo")
        assert cinema == "Cinema 21 Oslo"
        assert auditorium is None

    def test_cinemateket_with_multi_word_auditorium(self):
        """Test Cinemateket with multi-word auditorium name."""
        # Only takes first word after Cinemateket
        cinema, auditorium = self.scraper._split_cinema_and_auditorium("Cinemateket Store Sal")
        assert cinema == "Cinemateket"
        assert auditorium == "Store Sal"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])

