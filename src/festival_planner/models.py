"""Pydantic models for festival planner data structures."""

import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Film(BaseModel):
    """Represents a film screening at a festival."""

    title: str = Field(..., description="Film title")
    country: str = Field(..., description="Country of origin")
    start_time: datetime.datetime = Field(..., description="Screening start time")
    end_time: datetime.datetime = Field(..., description="Screening end time")
    cinema: str = Field(..., description="Cinema/venue name")
    special_notes: Optional[str] = Field(
        None, description="Special event information (Q&A, premiere, etc.)"
    )
    preference_weight: float = Field(
        1.0, description="Preference weight (positive or negative relative to default)"
    )

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

    from_cinema: str = Field(..., alias="from", description="Origin cinema name")
    to_cinema: str = Field(..., alias="to", description="Destination cinema name")
    minutes: int = Field(..., description="Travel time in minutes")

    class Config:
        populate_by_name = True


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

    travel_times: list[TravelTime] = Field(
        default_factory=list, description="Travel times between cinemas"
    )


class ScheduledFilm(BaseModel):
    """Represents a film in an optimized schedule."""

    film: Film
    arrival_time: datetime.datetime = Field(
        ..., description="Recommended arrival time (including buffer)"
    )
