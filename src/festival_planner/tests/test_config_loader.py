"""High-level tests for configuration loader with XDG path support."""

import tempfile
from pathlib import Path
from typing import Iterator

import pytest
from ruamel.yaml import YAML

from festival_planner.config import (
    CONFIG_FILE,
    PREFERENCES_FILE,
    FILMS_FILE,
    ConfigLoader,
    FilmPreferences,
)
from festival_planner.models import Film, FilmList, SeenFilm, FilmWeight
from festival_planner.path_providers import XDGPathProvider, PathProvider


class MockPathProvider(PathProvider):
    """Mock path provider for testing without filesystem dependencies."""

    def __init__(self, base_dir: Path):
        """Initialize mock provider with a base directory."""
        self.base_dir = base_dir
        self.config_home_dir = base_dir / "config"
        self.data_home_dir = base_dir / "data"
        self.state_home_dir = base_dir / "state"
        self.cache_home_dir = base_dir / "cache"
        self.system_config_dir = base_dir / "etc" / "xdg"
        self.system_data_dir = base_dir / "usr" / "share"

    def get_config_home(self) -> Path:
        return self.config_home_dir

    def get_config_dirs(self) -> list[Path]:
        return [self.config_home_dir, self.system_config_dir]

    def get_data_home(self) -> Path:
        return self.data_home_dir

    def get_data_dirs(self) -> list[Path]:
        return [self.data_home_dir, self.system_data_dir]

    def get_state_home(self) -> Path:
        return self.state_home_dir

    def get_cache_home(self) -> Path:
        return self.cache_home_dir


@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_provider(temp_dir: Path) -> MockPathProvider:
    """Create a mock path provider with temporary directories."""
    return MockPathProvider(temp_dir)


@pytest.fixture
def yaml_writer() -> YAML:
    """Create a YAML writer for test files."""
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.sort_keys = False
    return yaml


class TestXDGPathProvider:
    """Tests for XDG path provider essentials."""

    def test_xdg_defaults(self) -> None:
        """Test XDG default paths follow specification."""
        provider = XDGPathProvider("test-app")
        
        assert provider.get_config_home() == Path.home() / ".config" / "test-app"
        assert provider.get_data_home() == Path.home() / ".local" / "share" / "test-app"
        assert provider.get_cache_home() == Path.home() / ".cache" / "test-app"
        assert provider.get_state_home() == Path.home() / ".local" / "state" / "test-app"

    def test_xdg_respects_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test XDG respects environment variable overrides."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        monkeypatch.setenv("XDG_DATA_HOME", "/custom/data")
        
        provider = XDGPathProvider("test-app")
        
        assert provider.get_config_home() == Path("/custom/config/test-app")
        assert provider.get_data_home() == Path("/custom/data/test-app")

    def test_includes_cwd_fallback(self) -> None:
        """Test that search paths include ./config and ./data as fallback."""
        provider = XDGPathProvider("test-app")
        
        assert Path.cwd() / "config" in provider.get_config_dirs()
        assert Path.cwd() / "data" in provider.get_data_dirs()


class TestConfigLoaderWithPathProvider:
    """Tests for ConfigLoader with path provider integration."""

    def test_loader_uses_default_xdg_provider(self) -> None:
        """Test that loader creates XDG provider by default."""
        loader = ConfigLoader()
        
        assert loader.path_provider is not None
        assert isinstance(loader.path_provider, XDGPathProvider)

    def test_loader_accepts_custom_provider(self, mock_provider: MockPathProvider) -> None:
        """Test that loader accepts injected path provider."""
        loader = ConfigLoader(path_provider=mock_provider)
        
        assert loader.config_write_dir == mock_provider.get_config_home()
        assert loader.data_write_dir == mock_provider.get_data_home()
        assert loader.config_search_dirs == mock_provider.get_config_dirs()
        assert loader.data_search_dirs == mock_provider.get_data_dirs()

    def test_backward_compatibility_with_explicit_dirs(
        self, temp_dir: Path
    ) -> None:
        """Test backward compatibility with explicit directory parameters."""
        config_dir = temp_dir / "config"
        data_dir = temp_dir / "data"
        
        loader = ConfigLoader(config_dir=config_dir, data_dir=data_dir)
        
        assert loader.config_write_dir == config_dir
        assert loader.data_write_dir == data_dir
        assert loader.config_search_dirs == [config_dir]
        assert loader.data_search_dirs == [data_dir]


class TestConfigLoaderFileOperations:
    """Tests for ConfigLoader file reading and writing operations."""

    def test_search_path_priority(
        self,
        mock_provider: MockPathProvider,
        yaml_writer: YAML,
    ) -> None:
        """Test that primary location takes precedence over system fallback."""
        # Create config in both locations with different values
        primary_dir = mock_provider.get_config_home()
        primary_dir.mkdir(parents=True, exist_ok=True)
        
        system_dir = mock_provider.system_config_dir
        system_dir.mkdir(parents=True, exist_ok=True)
        
        # Primary config with buffer_time = 15
        for dir_path, buffer_time in [(primary_dir, 15), (system_dir, 999)]:
            config_file = dir_path / CONFIG_FILE
            with open(config_file, "w") as f:
                yaml_writer.dump(
                    {
                        "cinemas": {"travel_times": []},
                        "schedule": {"buffer_time_minutes": buffer_time},
                    },
                    f,
                )
            
            prefs_file = dir_path / PREFERENCES_FILE
            with open(prefs_file, "w") as f:
                yaml_writer.dump({"seen": [], "weights": []}, f)
        
        # Load config - should use primary (15), not system (999)
        loader = ConfigLoader(path_provider=mock_provider)
        config = loader.load_config()
        
        assert config.schedule.buffer_time_minutes == 15

    def test_save_to_primary_write_directory(
        self,
        mock_provider: MockPathProvider,
    ) -> None:
        """Test that saves always go to primary (writable) directories."""
        loader = ConfigLoader(path_provider=mock_provider)
        
        # Save preferences
        prefs = FilmPreferences(
            seen=[SeenFilm(title="Seen Film", date=None)],
            weights=[FilmWeight(title="Important Film", weight=1.0)],
        )
        loader.save_preferences(prefs)
        
        # Save films
        from datetime import datetime
        film_list = FilmList(
            films=[
                Film(
                    title="New Film",
                    country="Norway",
                    year=2025,
                    start_time=datetime(2025, 11, 10, 18, 0),
                    end_time=datetime(2025, 11, 10, 20, 0),
                    cinema="Vika",
                )
            ]
        )
        loader.save_films(film_list)
        
        # Verify files are in primary locations (not system)
        assert (mock_provider.get_config_home() / PREFERENCES_FILE).exists()
        assert (mock_provider.get_data_home() / FILMS_FILE).exists()
        assert not (mock_provider.system_config_dir / PREFERENCES_FILE).exists()
        assert not (mock_provider.system_data_dir / FILMS_FILE).exists()

    def test_load_missing_files_returns_defaults(
        self,
        mock_provider: MockPathProvider,
    ) -> None:
        """Test that missing files return sensible defaults."""
        loader = ConfigLoader(path_provider=mock_provider)
        
        config = loader.load_config()
        film_list = loader.load_films()
        
        # Should return empty/default values, not errors
        assert len(config.films.seen) == 0
        assert len(config.films.weights) == 0
        assert len(film_list.films) == 0


class TestConfigLoaderFiltering:
    """Tests for ConfigLoader film filtering and weight operations."""

    def test_filter_seen_films(self) -> None:
        """Test filtering of seen films (all screenings and specific dates)."""
        from datetime import datetime, date
        
        loader = ConfigLoader()
        
        films = [
            Film(
                title="Seen All",
                country="Test",
                year=2024,
                date=date(2024, 11, 8),
                start_time=datetime(2024, 11, 8, 14, 0),
                end_time=datetime(2024, 11, 8, 16, 0),
                cinema="Vika",
            ),
            Film(
                title="Seen Specific",
                country="Test",
                year=2024,
                date=date(2024, 11, 8),
                start_time=datetime(2024, 11, 8, 14, 0),
                end_time=datetime(2024, 11, 8, 16, 0),
                cinema="Vika",
            ),
            Film(
                title="Seen Specific",
                country="Test",
                year=2024,
                date=date(2024, 11, 9),
                start_time=datetime(2024, 11, 9, 14, 0),
                end_time=datetime(2024, 11, 9, 16, 0),
                cinema="Vika",
            ),
            Film(
                title="Unseen",
                country="Test",
                year=2024,
                date=date(2024, 11, 8),
                start_time=datetime(2024, 11, 8, 18, 0),
                end_time=datetime(2024, 11, 8, 20, 0),
                cinema="Vega",
            ),
        ]
        
        seen = [
            SeenFilm(title="Seen All", date=None),  # All screenings
            SeenFilm(title="Seen Specific", date=date(2024, 11, 8)),  # Specific date
        ]
        
        result = loader.filter_relevant_films(films, seen)
        
        assert len(result) == 2  # "Seen Specific" on Nov 9 + "Unseen"
        assert "Unseen" in [f.title for f in result]
        assert any(f.title == "Seen Specific" and f.date == date(2024, 11, 9) for f in result)

    def test_weight_override_precedence(self) -> None:
        """Test weight override precedence: screening-specific > film-level."""
        from datetime import datetime
        
        loader = ConfigLoader()
        
        start_time = datetime(2024, 11, 8, 14, 0)
        
        films = [
            Film(
                title="Film",
                country="Test",
                year=2024,
                start_time=start_time,
                end_time=datetime(2024, 11, 8, 16, 0),
                cinema="Vika",
                preference_weight=0.0,
            ),
            Film(
                title="Film",
                country="Test",
                year=2024,
                start_time=datetime(2024, 11, 9, 14, 0),
                end_time=datetime(2024, 11, 9, 16, 0),
                cinema="Vega",
                preference_weight=0.0,
            ),
        ]
        
        weights = [
            FilmWeight(title="Film", weight=0.5, start_time=None),  # All screenings
            FilmWeight(title="Film", weight=0.9, start_time=start_time),  # Specific
        ]
        
        result = loader.apply_weight_overrides(films, weights)
        
        # First screening should use specific weight, second uses film-level
        assert result[0].preference_weight == 0.9
        assert result[1].preference_weight == 0.5


class TestConfigLoaderIntegration:
    """End-to-end integration tests."""

    def test_complete_workflow(
        self,
        mock_provider: MockPathProvider,
        yaml_writer: YAML,
    ) -> None:
        """Test complete workflow: setup, load, filter, apply weights, save."""
        from datetime import datetime, date
        
        # Set up initial configuration
        config_dir = mock_provider.get_config_home()
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # Create config files
        config_file = config_dir / CONFIG_FILE
        with open(config_file, "w") as f:
            yaml_writer.dump(
                {
                    "cinemas": {"travel_times": []},
                    "schedule": {"buffer_time_minutes": 15},
                },
                f,
            )
        
        prefs_file = config_dir / PREFERENCES_FILE
        with open(prefs_file, "w") as f:
            yaml_writer.dump(
                {
                    "seen": [{"title": "Seen Film", "date": None}],
                    "weights": [{"title": "Important Film", "weight": 1.0}],
                },
                f,
            )
        
        # Create films file
        data_dir = mock_provider.get_data_home()
        data_dir.mkdir(parents=True, exist_ok=True)
        
        films_file = data_dir / FILMS_FILE
        with open(films_file, "w") as f:
            yaml_writer.dump(
                {
                    "films": [
                        {
                            "title": "Seen Film",
                            "country": "Norway",
                            "year": 2024,
                            "date": "2024-11-08",
                            "start_time": "2024-11-08T14:00:00",
                            "end_time": "2024-11-08T16:00:00",
                            "cinema": "Vika",
                            "preference_weight": 0.0,
                        },
                        {
                            "title": "Important Film",
                            "country": "Sweden",
                            "year": 2024,
                            "date": "2024-11-08",
                            "start_time": "2024-11-08T18:00:00",
                            "end_time": "2024-11-08T20:00:00",
                            "cinema": "Vega",
                            "preference_weight": 0.0,
                        },
                    ]
                },
                f,
            )
        
        # Initialize loader
        loader = ConfigLoader(path_provider=mock_provider)
        
        # Load everything
        config = loader.load_config()
        all_films = loader.load_films()
        
        # Filter seen films
        relevant_films = loader.filter_relevant_films(
            all_films.films, config.films.seen
        )
        
        # Apply weights
        weighted_films = loader.apply_weight_overrides(
            relevant_films, config.films.weights
        )
        
        # Verify results
        assert len(all_films.films) == 2
        assert len(relevant_films) == 1  # Seen film filtered out
        assert relevant_films[0].title == "Important Film"
        assert weighted_films[0].preference_weight == 1.0  # Weight applied
        
        # Save updated preferences
        new_prefs = FilmPreferences(
            seen=config.films.seen + [SeenFilm(title="Important Film", date=None)],
            weights=config.films.weights,
        )
        loader.save_preferences(new_prefs)
        
        # Verify saved
        saved_prefs_file = config_dir / PREFERENCES_FILE
        assert saved_prefs_file.exists()
        
        with open(saved_prefs_file, "r") as f:
            saved_data = yaml_writer.load(f)
        
        assert len(saved_data["seen"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
