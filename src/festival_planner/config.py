"""Configuration management for loading and validating YAML files."""

from pathlib import Path
from typing import Optional, TypeVar, Type
from warnings import deprecated
from ruamel.yaml import YAML
import yaml
from pydantic import BaseModel, Field

from .models import (
    FilmList,
    PriorityConfig,
    CinemaConfig,
    ScheduleConfig,
    Film,
    SeenFilm,
    FilmWeight,
)

# Configuration file
CONFIG_FILE = "config.yaml"
"""User-edited configuration file."""
PREFERENCES_FILE = "preferences.yaml"
"""Tool-maintained preferences for solving the scheduling problem."""

# Data file
FILMS_FILE = "films.yaml"
"""Scraped data file."""

T = TypeVar("T", bound=BaseModel)


def _load_yaml_model(
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
        yaml = YAML()
        data = yaml.load(f)

    if data is None:
        return model_class()

    return model_class(**data)


class FilmPreferences(BaseModel):
    seen: list[SeenFilm] = Field(
        default_factory=list, description="List of seen or ignored films"
    )
    weights: list[FilmWeight] = Field(
        default_factory=list, description="List of custom film weight overrides"
    )


class Config(BaseModel):
    films: FilmPreferences = Field(
        default_factory=FilmPreferences,
        json_schema_extra={"source_file": PREFERENCES_FILE, "source_key": False},
    )
    cinemas: CinemaConfig = Field(
        default_factory=CinemaConfig,
        json_schema_extra={"source_file": CONFIG_FILE},
    )
    schedule: ScheduleConfig = Field(
        default_factory=ScheduleConfig,
        json_schema_extra={"source_file": CONFIG_FILE},
    )
    priority: PriorityConfig = Field(
        default_factory=PriorityConfig,
        json_schema_extra={"source_file": CONFIG_FILE},
    )


class Data(BaseModel):
    films: FilmList = Field(default_factory=FilmList)


class ConfigLoader:
    """Loads and validates configuration files."""

    def __init__(
        self, config_dir: Optional[Path] = None, data_dir: Optional[Path] = None
    ):
        """Initialize the configuration loader.

        Args:
            config_dir: Directory containing configuration files
            data_dir: Directory containing data files
        """
        default_config_dir, default_data_dir = get_default_paths()
        if config_dir is None:
            config_dir = default_config_dir
        if data_dir is None:
            data_dir = default_data_dir
        self.config_dir = config_dir
        self.data_dir = data_dir
        self.config_path = self.config_dir / CONFIG_FILE
        self.preferences_path = self.config_dir / PREFERENCES_FILE
        self.films_path = self.data_dir / FILMS_FILE

    def load_config(self) -> Config:
        """Load configuration from YAML file."""
        return self.load_composite_config()

    def load_composite_config(self, filepath: Optional[Path] = None) -> Config:
        """Load configuration from multiple files based on model field metadata.

        Reads field metadata from the Config model to determine which file each field
        should be loaded from. The metadata is defined in the model using Field's
        json_schema_extra parameter with keys:
        - source_file: The filename to load from (relative to config_dir)
        - source_key: Optional alternative YAML key if it differs from the field name

        Returns:
            Config containing merged configuration from all specified files

        Example:
            class Config(BaseModel):
                films: FilmPreferences = Field(
                    default_factory=FilmPreferences,
                    json_schema_extra={"source_file": "preferences.yaml"}
                )
                scheduling: ScheduleConfig = Field(
                    default_factory=ScheduleConfig,
                    json_schema_extra={
                        "source_file": "config.yaml",
                        "source_key": "preferences"  # YAML uses different key
                    }
                )

            loader = ConfigLoader()
            config = loader.load_composite_config()
        """
        # Extract file sources and key mappings from model metadata
        field_sources: dict[str, tuple[Path, Optional[str]]] = {}

        for field_name, field_info in Config.model_fields.items():
            # Get metadata from json_schema_extra
            extra = field_info.json_schema_extra or {}

            if isinstance(extra, dict):
                source_file = extra.get("source_file")
                source_key = extra.get("source_key")

                if source_file and isinstance(source_file, str):
                    filepath = self.config_dir / source_file
                    validated_key = source_key if isinstance(source_key, str) else None
                    field_sources[field_name] = (filepath, validated_key)
                else:
                    # Default to config.yaml if no source specified
                    field_sources[field_name] = (self.config_path, None)
            else:
                # Default to config.yaml if no metadata
                field_sources[field_name] = (self.config_path, None)

        # Cache to avoid multiple reads of the same file, again and again
        file_data_cache: dict[Path, dict] = {}
        for filepath, _ in field_sources.values():
            if filepath in file_data_cache:
                continue

            if not filepath.exists():
                file_data_cache[filepath] = {}
                continue

            with open(filepath, "r") as f:
                yaml_loader = YAML()
                file_data_cache[filepath] = yaml_loader.load(f) or {}

        # Get the unique combinations as we won't load the same data twice
        # Extract relevant fields from loaded data
        config_data = {}
        sourced = set()
        for field_name, (filepath, source_key) in field_sources.items():
            file_data = file_data_cache[filepath]

            # Use source_key if specified, otherwise use field_name
            yaml_key = source_key if source_key else field_name
            if (filepath, yaml_key) in sourced:
                print("skipping duplicate", filepath, source_key)
                continue

            sourced.add((filepath, yaml_key))
            if yaml_key in file_data:
                config_data[field_name] = file_data[yaml_key]
                continue

            config_data[field_name] = file_data

        return Config(**config_data)

    def load_films(self, filepath: Optional[Path] = None) -> FilmList:
        """Load films from YAML file.

        Args:
            filepath: Optional custom filepath, defaults to data/films.yaml

        Returns:
            FilmList containing all films
        """
        return _load_yaml_model(FilmList, self.films_path, filepath)

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

    def save_preferences(
        self, preferences: FilmPreferences, filepath: Optional[Path] = None
    ) -> None:
        """Save film preferences to YAML file.

        Args:
            preferences: FilmPreferences to save
            filepath: Optional custom filepath, defaults to config/preferences.yaml
        """
        if filepath is None:
            filepath = self.preferences_path

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w") as f:
            yaml.dump(
                preferences.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

    @deprecated("Use CinemaConfig.get_valid_cinemas() instead")
    def get_valid_cinemas(self, cinema_config: CinemaConfig) -> set[str]:
        return cinema_config.get_valid_cinemas()

    @deprecated("Use CinemaConfig.build_travel_time_matrix() instead")
    def build_travel_time_matrix(
        self, cinema_config: CinemaConfig
    ) -> dict[tuple[str, str], int]:
        return cinema_config.build_travel_time_matrix()

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
                film_dict["preference_weight"] = screening_override_map[screening_key]
                modified_film = Film(**film_dict)
                modified_films.append(modified_film)
            # Then check film-level override
            elif film.title in film_override_map:
                film_dict = film.model_dump()
                film_dict["preference_weight"] = film_override_map[film.title]
                modified_film = Film(**film_dict)
                modified_films.append(modified_film)
            else:
                modified_films.append(film)

        return modified_films


def get_default_paths():
    """Get default paths for config and data directories."""
    cwd = Path.cwd()
    return cwd / "config", cwd / "data"
