"""Pydantic models for festival planner data structures."""

import datetime

from pydantic import AliasChoices, BaseModel, Field

from ._logging import get_logger

logger = get_logger(__name__)


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
    year: int | None = Field(default=None, description="Year of release")
    url: str | None = Field(
        default=None, description="URL to the film's page on the festival website"
    )
    ticket_url: str | None = Field(
        default=None,
        description="URL to the film's ticket page on the festival website",
    )
    start_time: datetime.datetime = Field(..., description="Screening start time")
    end_time: datetime.datetime = Field(..., description="Screening end time")
    cinema: str = Field(..., description="Cinema/venue name")
    auditorium: str | None = Field(
        default=None, description="Auditorium number or name (None if unknown)"
    )
    special_notes: str | None = Field(
        default=None, description="Special event information (Q&A, premiere, etc.)"
    )
    preference_weight: float = Field(
        default=1.0,
        description="Preference weight (positive or negative relative to default)",
    )

    @property
    def date(self) -> datetime.date:
        """Get the date of the screening."""
        return self.start_time.date()

    @property
    def duration_minutes(self) -> int:
        """Get the duration of the film in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)


class TravelTime(BaseModel):
    """Represents travel time between two cinemas."""

    from_cinema: str = Field(
        validation_alias=AliasChoices("from", "from_cinema"),
        description="Origin cinema name",
    )
    to_cinema: str = Field(
        validation_alias=AliasChoices("to", "to_cinema"),
        description="Destination cinema name",
    )
    minutes: int = Field(..., description="Travel time in minutes")


class SeenFilm(BaseModel):
    """Represents a film that has been seen or should be ignored."""

    title: str
    date: datetime.date | None = None


class FilmWeight(BaseModel):
    """Represents a custom weight override for a film or specific screening.

    If start_time is None, the weight applies to all screenings of the film.
    If start_time is provided, it applies only to that specific screening.
    """

    title: str = Field(..., description="Film title")
    start_time: datetime.datetime | None = Field(
        default=None, description="Screening start time (None for film-level weight)"
    )
    weight: float = Field(..., description="Custom weight override")


class ScheduleConfig(BaseModel):
    """Configuration for the schedule optimizer."""

    buffer_time_minutes: int = 15
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    time_zone: str = "Europe/Oslo"
    """The festival's IANA time zone; legacy naive times are interpreted in it."""


class PriorityConfig(BaseModel):
    """Priority for the solver to impact priorities."""

    year_weights: dict[int, float] = Field(
        default_factory=dict,
        description="Weight adjustments for specific years. "
        "Key is year, value is weight to add/subtract.",
    )
    special_notes_weight: float = Field(
        default=0.0,
        description="Weight adjustment for films with special notes/events. "
        "Positive values increase priority, negative values decrease it.",
    )


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


class FilmWeightList(BaseModel):
    """Container for a list of film weight overrides."""

    weights: list[FilmWeight] = Field(
        default_factory=list, description="List of custom film weight overrides"
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

    def build_travel_time_matrix(self) -> dict[tuple[str, str], int]:
        """Build a travel time matrix from cinema configuration.

        Args:
            cinema_config: CinemaConfig containing travel times

        Returns:
            Dictionary mapping (from_cinema, to_cinema) tuples to travel time in minutes
        """
        travel_matrix = {}

        # Add all defined travel times
        for travel_time in self.travel_times:
            travel_matrix[(travel_time.from_cinema, travel_time.to_cinema)] = (
                travel_time.minutes
            )

        # Add zero travel time for same cinema
        cinemas = self.get_valid_cinemas()

        for cinema in cinemas:
            travel_matrix[(cinema, cinema)] = 0

        return travel_matrix

    def get_valid_cinemas(self) -> set[str]:
        """Extract valid cinema names from cinema configuration.

        Args:
            cinema_config: CinemaConfig containing travel times

        Returns:
            Set of valid cinema names
        """
        cinemas = set()
        for travel_time in self.travel_times:
            cinemas.add(travel_time.from_cinema)
            cinemas.add(travel_time.to_cinema)
        return cinemas


def normalise_cinemas(film_list: FilmList, cinemas: CinemaConfig) -> FilmList:
    """Map cinema aliases to canonical names and drop screenings at unknown
    cinemas, logging each. Without any configured cinemas, nothing changes."""
    normalization_map = build_normalization_map(cinemas.cinema_aliases)
    valid = cinemas.get_valid_cinemas() | set(cinemas.cinema_aliases)
    if not valid:
        return film_list
    kept = []
    for film in film_list.films:
        cinema = normalization_map.get(film.cinema.lower().strip(), film.cinema)
        if cinema not in valid:
            logger.warning(
                "Unknown cinema - skipping screening",
                cinema=film.cinema,
                title=film.title,
            )
            continue
        kept.append(film.model_copy(update={"cinema": cinema}))
    return film_list.model_copy(update={"films": kept})
