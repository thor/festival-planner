"""Configuration management for loading and validating YAML files."""

from pathlib import Path
from typing import Optional
import yaml

from .models import (
    FilmList,
    SeenFilmList,
    CinemaConfig,
    ScheduleConfig,
    Film,
    SeenFilm,
)


class ConfigLoader:
    """Loads and validates configuration files."""

    def __init__(self, config_dir: Path, data_dir: Path):
        """Initialize the configuration loader.

        Args:
            config_dir: Directory containing configuration files
            data_dir: Directory containing data files
        """
        self.config_dir = config_dir
        self.data_dir = data_dir

    def load_films(self, filepath: Optional[Path] = None) -> FilmList:
        """Load films from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to data/films.yaml

        Returns:
            FilmList containing all films
        """
        if filepath is None:
            filepath = self.data_dir / "films.yaml"

        if not filepath.exists():
            return FilmList(films=[])

        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            return FilmList(films=[])

        return FilmList(**data)

    def load_seen_films(self, filepath: Optional[Path] = None) -> SeenFilmList:
        """Load seen/ignored films from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to data/seen_films.yaml

        Returns:
            SeenFilmList containing all seen films
        """
        if filepath is None:
            filepath = self.data_dir / "seen_films.yaml"

        if not filepath.exists():
            return SeenFilmList(seen=[])

        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            return SeenFilmList(seen=[])

        return SeenFilmList(**data)

    def load_cinema_config(self, filepath: Optional[Path] = None) -> CinemaConfig:
        """Load cinema configuration from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to config/cinemas.yaml

        Returns:
            CinemaConfig containing travel times
        """
        if filepath is None:
            filepath = self.config_dir / "cinemas.yaml"

        if not filepath.exists():
            return CinemaConfig(travel_times=[])

        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            return CinemaConfig(travel_times=[])

        return CinemaConfig(**data)

    def load_schedule_config(self, filepath: Optional[Path] = None) -> ScheduleConfig:
        """Load schedule configuration from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to config/preferences.yaml

        Returns:
            ScheduleConfig with optimization preferences
        """
        if filepath is None:
            filepath = self.config_dir / "preferences.yaml"

        if not filepath.exists():
            return ScheduleConfig()

        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            return ScheduleConfig()

        return ScheduleConfig(**data)

    def save_films(self, film_list: FilmList, filepath: Optional[Path] = None) -> None:
        """Save films to YAML file.

        Args:
            film_list: FilmList to save
            filepath: Optional custom filepath, defaults to data/films.yaml
        """
        if filepath is None:
            filepath = self.data_dir / "films.yaml"

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            yaml.dump(
                film_list.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def save_seen_films(
        self, seen_list: SeenFilmList, filepath: Optional[Path] = None
    ) -> None:
        """Save seen films to YAML file.

        Args:
            seen_list: SeenFilmList to save
            filepath: Optional custom filepath, defaults to data/seen_films.yaml
        """
        if filepath is None:
            filepath = self.data_dir / "seen_films.yaml"

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            yaml.dump(
                seen_list.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def build_travel_time_matrix(
        self, cinema_config: CinemaConfig
    ) -> dict[tuple[str, str], int]:
        """Build a travel time matrix from cinema configuration.

        Args:
            cinema_config: CinemaConfig containing travel times

        Returns:
            Dictionary mapping (from_cinema, to_cinema) tuples to travel time in minutes
        """
        travel_matrix = {}

        # Add all defined travel times
        for travel_time in cinema_config.travel_times:
            travel_matrix[(travel_time.from_cinema, travel_time.to_cinema)] = (
                travel_time.minutes
            )

        # Add zero travel time for same cinema
        cinemas = set()
        for travel_time in cinema_config.travel_times:
            cinemas.add(travel_time.from_cinema)
            cinemas.add(travel_time.to_cinema)

        for cinema in cinemas:
            travel_matrix[(cinema, cinema)] = 0

        return travel_matrix

    def filter_unseen_films(
        self, films: list[Film], seen_films: list[SeenFilm]
    ) -> list[Film]:
        """Filter out films that have been seen.

        Args:
            films: List of all films
            seen_films: List of seen films

        Returns:
            List of films that haven't been seen
        """
        # Build a set of seen film identifiers
        seen_all_screenings = set()  # Films where all screenings should be ignored
        seen_specific = set()  # (title, date) pairs for specific screenings

        for seen in seen_films:
            if seen.date is None:
                seen_all_screenings.add(seen.title)
            else:
                seen_specific.add((seen.title, seen.date))

        # Filter films
        unseen_films = []
        for film in films:
            if film.title in seen_all_screenings:
                continue
            if (film.title, film.date) in seen_specific:
                continue
            unseen_films.append(film)

        return unseen_films
