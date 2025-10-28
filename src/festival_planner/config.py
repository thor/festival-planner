"""Configuration management for loading and validating YAML files."""

from pathlib import Path
from typing import Optional, TypeVar, Type
from ruamel.yaml import YAML
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
from ._logging import get_logger
from .path_providers import PathProvider, create_default_path_provider

# Configuration file
CONFIG_FILE = "config.yaml"
"""User-edited configuration file."""
PREFERENCES_FILE = "preferences.yaml"
"""Tool-maintained preferences for solving the scheduling problem."""

# Data file
FILMS_FILE = "films.yaml"
"""Scraped data file."""

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__)


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


def _find_file_in_search_paths(filename: str, search_paths: list[Path]) -> Optional[Path]:
    """Search for a file in multiple directories.
    
    Args:
        filename: Name of the file to find
        search_paths: List of directories to search in order
        
    Returns:
        Path to the first existing file, or None if not found
    """
    for directory in search_paths:
        filepath = directory / filename
        if filepath.exists():
            return filepath
    return None


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
    """Loads and validates configuration files using XDG Base Directory specification.
    
    Follows SOLID principles:
    - Single Responsibility: Manages configuration file I/O
    - Open/Closed: Extended via PathProvider injection
    - Liskov Substitution: Works with any PathProvider implementation
    - Interface Segregation: Focused on config operations
    - Dependency Inversion: Depends on PathProvider abstraction
    """

    def __init__(
        self,
        path_provider: Optional[PathProvider] = None,
        config_dir: Optional[Path] = None,
        data_dir: Optional[Path] = None,
    ):
        """Initialize the configuration loader.

        Args:
            path_provider: PathProvider for XDG-compliant directory resolution
            config_dir: Optional override for configuration directory (deprecated)
            data_dir: Optional override for data directory (deprecated)
        """
        if path_provider is None:
            path_provider = create_default_path_provider()
        
        self.path_provider = path_provider
        
        # Support legacy config_dir/data_dir parameters for backward compatibility
        # but prefer PathProvider for new code
        if config_dir is not None:
            self.config_write_dir = config_dir
            self.config_search_dirs = [config_dir]
        else:
            self.config_write_dir = path_provider.get_config_home()
            self.config_search_dirs = path_provider.get_config_dirs()
        
        if data_dir is not None:
            self.data_write_dir = data_dir
            self.data_search_dirs = [data_dir]
        else:
            self.data_write_dir = path_provider.get_data_home()
            self.data_search_dirs = path_provider.get_data_dirs()
        
        # Maintain backward compatibility attributes
        self.config_dir = self.config_write_dir
        self.data_dir = self.data_write_dir
        self.config_path = self.config_write_dir / CONFIG_FILE
        self.preferences_path = self.config_write_dir / PREFERENCES_FILE
        self.films_path = self.data_write_dir / FILMS_FILE

    def load_config(self) -> Config:
        """Load configuration from YAML file."""
        return self.load_composite_config()

    def load_composite_config(self, filepath: Optional[Path] = None) -> Config:
        """Load configuration from multiple files based on model field metadata.

        Searches for configuration files in XDG-compliant directories in order:
        1. Primary config directory (for writing)
        2. System-wide config directories (fallback, read-only)

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
        field_sources: dict[str, tuple[str, Optional[str]]] = {}

        for field_name, field_info in Config.model_fields.items():
            # Get metadata from json_schema_extra
            extra = field_info.json_schema_extra or {}

            if isinstance(extra, dict):
                source_file = extra.get("source_file")
                source_key = extra.get("source_key")

                if source_file and isinstance(source_file, str):
                    validated_key = source_key if isinstance(source_key, str) else None
                    field_sources[field_name] = (source_file, validated_key)
                else:
                    # Default to config.yaml if no source specified
                    field_sources[field_name] = (CONFIG_FILE, None)
            else:
                # Default to config.yaml if no metadata
                field_sources[field_name] = (CONFIG_FILE, None)

        # Cache to avoid multiple reads of the same file
        file_data_cache: dict[Path, dict] = {}
        
        # Find and load each unique source file
        unique_files = set(filename for filename, _ in field_sources.values())
        for filename in unique_files:
            # Search for file in XDG directories
            found_path = _find_file_in_search_paths(filename, self.config_search_dirs)
            
            if found_path is None:
                logger.debug(
                    "Config file not found in search paths",
                    filename=filename,
                    search_dirs=[str(d) for d in self.config_search_dirs],
                )
                file_data_cache[filename] = {}
                continue
            
            logger.debug("Loading config file", filepath=str(found_path))
            
            with open(found_path, "r") as f:
                yaml_loader = YAML()
                file_data_cache[filename] = yaml_loader.load(f) or {}

        # Extract relevant fields from loaded data
        config_data = {}
        sourced = set()
        for field_name, (source_file, source_key) in field_sources.items():
            file_data = file_data_cache.get(source_file, {})

            # Use source_key if specified, otherwise use field_name
            yaml_key = source_key if source_key else field_name
            if (source_file, yaml_key) in sourced:
                logger.debug(
                    "Skipping duplicate config key",
                    source_file=source_file,
                    yaml_key=yaml_key,
                )
                continue

            sourced.add((source_file, yaml_key))
            if yaml_key in file_data:
                config_data[field_name] = file_data[yaml_key]
                continue

            config_data[field_name] = file_data

        return Config(**config_data)

    def load_films(self, filepath: Optional[Path] = None) -> FilmList:
        """Load films from YAML file.
        
        Searches for films file in XDG-compliant data directories in order.

        Args:
            filepath: Optional custom filepath, defaults to searching data directories

        Returns:
            FilmList containing all films
        """
        if filepath is not None:
            return _load_yaml_model(FilmList, filepath, filepath)
        
        # Search for films file in data directories
        found_path = _find_file_in_search_paths(FILMS_FILE, self.data_search_dirs)
        
        if found_path is None:
            logger.debug(
                "Films file not found in search paths",
                filename=FILMS_FILE,
                search_dirs=[str(d) for d in self.data_search_dirs],
            )
            return FilmList()
        
        logger.debug("Loading films file", filepath=str(found_path))
        return _load_yaml_model(FilmList, found_path, found_path)

    def save_films(self, film_list: FilmList, filepath: Optional[Path] = None) -> None:
        """Save films to YAML file in writable data directory.
        
        Always writes to the primary data directory (XDG_DATA_HOME), never to
        system-wide directories.

        Args:
            film_list: FilmList to save
            filepath: Optional custom filepath, defaults to primary data directory
        """
        if filepath is None:
            filepath = self.data_write_dir / FILMS_FILE

        filepath.parent.mkdir(parents=True, exist_ok=True)

        yaml_dumper = YAML()
        yaml_dumper.default_flow_style = False
        yaml_dumper.sort_keys = False
        yaml_dumper.allow_unicode = True
        
        logger.debug("Saving films file", filepath=str(filepath))
        
        with open(filepath, "w") as f:
            yaml_dumper.dump(film_list.model_dump(mode="json"), f)

    def save_preferences(
        self, preferences: FilmPreferences, filepath: Optional[Path] = None
    ) -> None:
        """Save film preferences to YAML file in writable config directory.
        
        Always writes to the primary config directory (XDG_CONFIG_HOME), never to
        system-wide directories.

        Args:
            preferences: FilmPreferences to save
            filepath: Optional custom filepath, defaults to primary config directory
        """
        if filepath is None:
            filepath = self.config_write_dir / PREFERENCES_FILE

        filepath.parent.mkdir(parents=True, exist_ok=True)

        yaml_dumper = YAML()
        yaml_dumper.default_flow_style = False
        yaml_dumper.sort_keys = False
        yaml_dumper.allow_unicode = True
        
        logger.debug("Saving preferences file", filepath=str(filepath))
        
        with open(filepath, "w") as f:
            yaml_dumper.dump(preferences.model_dump(mode="json"), f)

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
    """Get default paths for config and data directories.
    
    Returns XDG-compliant paths for configuration and data.
    
    Returns:
        Tuple of (config_home, data_home) paths
    """
    provider = create_default_path_provider()
    return provider.get_config_home(), provider.get_data_home()
