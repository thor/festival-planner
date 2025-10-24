"""Pydantic models for festival planner data structures."""

import datetime
from typing import Optional, ClassVar
from pydantic import BaseModel, Field, field_validator, ValidationInfo, ConfigDict


def build_normalization_map(cinema_aliases: dict[str, list[str]]) -> dict[str, str]:
    """Build a normalization map from cinema aliases configuration.

    Args:
        cinema_aliases: Dict mapping canonical names to list of aliases

    Returns:
        Dict mapping all aliases (lowercase) to canonical names
    """
    normalization_map = {}
    for canonical_name, aliases in cinema_aliases.items():
        # Map each alias to the canonical name (case-insensitive)
        for alias in aliases:
            normalization_map[alias.lower().strip()] = canonical_name
        # Also map the canonical name itself (case-insensitive)
        normalization_map[canonical_name.lower().strip()] = canonical_name
    return normalization_map


class Film(BaseModel):
    """Represents a film screening at a festival."""

    title: str = Field(..., description="Film title")
    country: str = Field(..., description="Country of origin")
    start_time: datetime.datetime = Field(..., description="Screening start time")
    end_time: datetime.datetime = Field(..., description="Screening end time")
    cinema: str = Field(..., description="Cinema/venue name")
    auditorium: Optional[str] = Field(
        None, description="Auditorium number or name (None if unknown)"
    )
    special_notes: Optional[str] = Field(
        None, description="Special event information (Q&A, premiere, etc.)"
    )
    preference_weight: float = Field(
        1.0, description="Preference weight (positive or negative relative to default)"
    )

    # Class variable to store valid cinemas for validation
    _valid_cinemas: ClassVar[Optional[set[str]]] = None
    _normalization_map: ClassVar[dict[str, str]] = {}

    @classmethod
    def set_valid_cinemas(cls, valid_cinemas: set[str]) -> None:
        """Set the list of valid cinema names for validation.

        Args:
            valid_cinemas: Set of valid cinema names
        """
        cls._valid_cinemas = valid_cinemas

    @classmethod
    def set_normalization_map(cls, normalization_map: dict[str, str]) -> None:
        """Set the cinema name normalization map.

        Args:
            normalization_map: Dict mapping aliases (lowercase) to canonical names
        """
        cls._normalization_map = normalization_map

    @field_validator("cinema")
    @classmethod
    def validate_cinema(cls, v: str, info: ValidationInfo) -> str:
        """Validate and normalize cinema name.

        Args:
            v: Cinema name
            info: Validation info

        Returns:
            Normalized cinema name

        Raises:
            ValueError: If cinema is not in the valid list
        """
        # Normalize the cinema name using the normalization map
        v_lower = v.lower().strip()
        normalized = cls._normalization_map.get(v_lower, v)

        # Validate against valid cinemas if set
        if cls._valid_cinemas is not None and normalized not in cls._valid_cinemas:
            raise ValueError(
                f"Cinema '{v}' (normalized to '{normalized}') is not in the valid cinema list: {sorted(cls._valid_cinemas)}"
            )

        return normalized

    @property
    def date(self) -> datetime.date:
        """Get the date of the screening."""
        return self.start_time.date()

    @property
    def duration_minutes(self) -> int:
        """Get the duration of the film in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)


class Cinema(BaseModel):
    """Represents a cinema/venue."""

    name: str = Field(..., description="Cinema name")
    location: Optional[str] = Field(None, description="Location identifier or address")


class TravelTime(BaseModel):
    """Represents travel time between two cinemas."""

    model_config = ConfigDict(populate_by_name=True)

    from_cinema: str = Field(..., alias="from", description="Origin cinema name")
    to_cinema: str = Field(..., alias="to", description="Destination cinema name")
    minutes: int = Field(..., description="Travel time in minutes")


class SeenFilm(BaseModel):
    """Represents a film that has been seen or should be ignored."""

    title: str
    date: Optional[datetime.date] = None


class ScheduleConfig(BaseModel):
    """Configuration for the schedule optimizer."""

    buffer_time_minutes: int = 15
    start_date: Optional[datetime.date] = None
    end_date: Optional[datetime.date] = None


class FilmList(BaseModel):
    """Container for a list of films."""

    films: list[Film] = Field(
        default_factory=list, description="List of film screenings"
    )


class SeenFilmList(BaseModel):
    """Container for a list of seen films."""

    seen: list[SeenFilm] = Field(
        default_factory=list, description="List of seen or ignored films"
    )


class CinemaConfig(BaseModel):
    """Configuration for cinemas and travel times."""

    cinema_aliases: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Cinema name aliases mapping (canonical name -> list of aliases)",
    )
    travel_times: list[TravelTime] = Field(
        default_factory=list, description="Travel times between cinemas"
    )


class ScheduledFilm(BaseModel):
    """Represents a film in an optimized schedule."""

    film: Film
    arrival_time: datetime.datetime = Field(
        ..., description="Recommended arrival time (including buffer)"
    )
