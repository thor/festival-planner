"""Festival programme: what is shown, where and when."""

import datetime
from typing import Self

from pydantic import model_validator

from .values import Value

VenueId = str
FilmId = str
ProgrammeEntryId = str
ScreeningId = str


class Venue(Value):
    """A fixed physical place where screenings take place."""

    id: VenueId
    name: str


class ProgrammeEntry(Value):
    """A Film as presented in one Festival's programme."""

    id: ProgrammeEntryId
    film_id: FilmId
    title: str
    year: int | None = None
    country: str | None = None
    url: str | None = None


class Event(Value):
    """Something belonging to a Screening beyond the film itself.

    Without times, the Event happens within the Screening. With times, it is
    separately timed (e.g. a panel after the film).
    """

    description: str
    start_time: datetime.datetime | None = None
    end_time: datetime.datetime | None = None

    @model_validator(mode="after")
    def _times_form_an_interval(self) -> Self:
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("An Event needs both start_time and end_time, or neither")
        if self.start_time and self.end_time and self.end_time < self.start_time:
            raise ValueError("An Event cannot end before it starts")
        return self

    @property
    def is_separately_timed(self) -> bool:
        return self.end_time is not None


class Screening(Value):
    """A single showing of a Programme Entry at a given time and Venue."""

    id: ScreeningId
    programme_entry_id: ProgrammeEntryId
    venue_id: VenueId
    start_time: datetime.datetime
    end_time: datetime.datetime
    auditorium: str | None = None
    ticket_url: str | None = None
    events: tuple[Event, ...] = ()

    @model_validator(mode="after")
    def _ends_after_it_starts(self) -> Self:
        if self.end_time < self.start_time:
            raise ValueError(f"Screening {self.id!r} cannot end before it starts")
        return self

    def starts_at(self, *, include_events: bool) -> datetime.datetime:
        """When the Screening starts, optionally including separately timed Events."""
        if not include_events:
            return self.start_time
        event_starts = [e.start_time for e in self.events if e.start_time is not None]
        return min([self.start_time, *event_starts])

    def ends_at(self, *, include_events: bool) -> datetime.datetime:
        """When the Screening ends, optionally including separately timed Events."""
        if not include_events:
            return self.end_time
        event_ends = [e.end_time for e in self.events if e.end_time is not None]
        return max([self.end_time, *event_ends])
