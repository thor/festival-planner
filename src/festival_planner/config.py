"""Configuration management for loading and validating YAML files."""

from pathlib import Path
from typing import Optional, TypeVar, Type
import yaml
from pydantic import BaseModel

from .models import (
    FilmList,
    SeenFilmList,
    FilmWeightList,
    CinemaConfig,
    ScheduleConfig,
    Film,
    SeenFilm,
    FilmWeight,
)

CINEMAS_FILE = "cinemas.yaml"
SEEN_FILMS_FILE = "seen_films.yaml"
FILM_WEIGHTS_FILE = "film_weights.yaml"
PREFERENCES_FILE = "preferences.yaml"
FILMS_FILE = "films.yaml"

T = TypeVar('T', bound=BaseModel)


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
        self.cinemas_path = self.config_dir / CINEMAS_FILE
        self.seen_films_path = self.config_dir / SEEN_FILMS_FILE
        self.film_weights_path = self.config_dir / FILM_WEIGHTS_FILE
        self.preferences_path = self.config_dir / PREFERENCES_FILE
        self.films_path = self.data_dir / FILMS_FILE

    def _load_yaml_model(
        self,
        model_class: Type[T],
        default_path: Path,
        filepath: Optional[Path] = None,
    ) -> T:
        """Generic YAML model loader with validation.

        Args:
            model_class: Pydantic model class to instantiate
            default_path: Default file path if filepath is None
            filepath: Optional custom filepath

        Returns:
            Instance of model_class, empty if file doesn't exist or is empty
        """
        target_path = filepath if filepath is not None else default_path

        if not target_path.exists():
            return model_class()

        with open(target_path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            return model_class()

        return model_class(**data)

    def load_films(self, filepath: Optional[Path] = None) -> FilmList:
        """Load films from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to data/films.yaml

        Returns:
            FilmList containing all films
        """
        return self._load_yaml_model(
            FilmList, self.films_path, filepath
        )

    def load_seen_films(self, filepath: Optional[Path] = None) -> SeenFilmList:
        """Load seen/ignored films from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to config/seen_films.yaml

        Returns:
            SeenFilmList containing all seen films
        """
        return self._load_yaml_model(
            SeenFilmList, self.seen_films_path, filepath
        )

    def load_cinema_config(self, filepath: Optional[Path] = None) -> CinemaConfig:
        """Load cinema configuration from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to config/cinemas.yaml

        Returns:
            CinemaConfig containing travel times
        """
        return self._load_yaml_model(
            CinemaConfig, self.cinemas_path, filepath
        )

    def load_schedule_config(self, filepath: Optional[Path] = None) -> ScheduleConfig:
        """Load schedule configuration from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to config/preferences.yaml

        Returns:
            ScheduleConfig with optimization preferences
        """
        return self._load_yaml_model(
            ScheduleConfig, self.preferences_path, filepath
        )

    def load_film_weights(self, filepath: Optional[Path] = None) -> FilmWeightList:
        """Load film weight overrides from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to config/film_weights.yaml

        Returns:
            FilmWeightList containing all custom weight overrides
        """
        return self._load_yaml_model(
            FilmWeightList, self.film_weights_path, filepath
        )

    def save_films(self, film_list: FilmList, filepath: Optional[Path] = None) -> None:
        """Save films to YAML file.

        Args:
            film_list: FilmList to save
            filepath: Optional custom filepath, defaults to data/films.yaml
        """
        if filepath is None:
            filepath = self.films_path

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
            filepath: Optional custom filepath, defaults to config/seen_films.yaml
        """
        if filepath is None:
            filepath = self.seen_films_path

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            yaml.dump(
                seen_list.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def save_film_weights(
        self, weight_list: FilmWeightList, filepath: Optional[Path] = None
    ) -> None:
        """Save film weight overrides to YAML file.

        Args:
            weight_list: FilmWeightList to save
            filepath: Optional custom filepath, defaults to config/film_weights.yaml
        """
        if filepath is None:
            filepath = self.film_weights_path

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            yaml.dump(
                weight_list.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    def get_valid_cinemas(self, cinema_config: CinemaConfig) -> set[str]:
        """Extract valid cinema names from cinema configuration.

        Args:
            cinema_config: CinemaConfig containing travel times

        Returns:
            Set of valid cinema names
        """
        cinemas = set()
        for travel_time in cinema_config.travel_times:
            cinemas.add(travel_time.from_cinema)
            cinemas.add(travel_time.to_cinema)
        return cinemas

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
        cinemas = self.get_valid_cinemas(cinema_config)

        for cinema in cinemas:
            travel_matrix[(cinema, cinema)] = 0

        return travel_matrix

    def filter_relevant_films(
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

    def apply_weight_overrides(
        self, films: list[Film], weight_overrides: list[FilmWeight]
    ) -> list[Film]:
        """Apply custom weight overrides to films.
        
        Supports both film-level (all screenings) and screening-level (specific) overrides.
        Screening-level overrides take precedence over film-level overrides.

        Args:
            films: List of films to modify
            weight_overrides: List of custom weight overrides

        Returns:
            List of films with overridden weights applied
        """
        # Build lookup maps
        # Screening-level: (title, start_time) -> weight
        screening_override_map = {
            (w.title, w.start_time): w.weight
            for w in weight_overrides
            if w.start_time is not None
        }
        
        # Film-level: title -> weight
        film_override_map = {
            w.title: w.weight for w in weight_overrides if w.start_time is None
        }

        # Apply overrides (screening-level takes precedence)
        modified_films = []
        for film in films:
            screening_key = (film.title, film.start_time)
            
            # Check screening-level override first
            if screening_key in screening_override_map:
                film_dict = film.model_dump()
                film_dict['preference_weight'] = screening_override_map[screening_key]
                modified_film = Film(**film_dict)
                modified_films.append(modified_film)
            # Then check film-level override
            elif film.title in film_override_map:
                film_dict = film.model_dump()
                film_dict['preference_weight'] = film_override_map[film.title]
                modified_film = Film(**film_dict)
                modified_films.append(modified_film)
            else:
                modified_films.append(film)

        return modified_films
