"""Festival programme: what is shown, where and when."""

import datetime
from dataclasses import dataclass

VenueId = str
FilmId = str
ProgrammeEntryId = str
ScreeningId = str


@dataclass(frozen=True, slots=True)
class Venue:
    """A fixed physical place where screenings take place."""

    id: VenueId
    name: str


@dataclass(frozen=True, slots=True)
class ProgrammeEntry:
    """A Film as presented in one Festival's programme."""

    id: ProgrammeEntryId
    film_id: FilmId
    title: str
    year: int | None = None
    country: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Event:
    """Something belonging to a Screening beyond the film itself.

    Without times, the Event happens within the Screening. With times, it is
    separately timed (e.g. a panel after the film).
    """

    description: str
    start_time: datetime.datetime | None = None
    end_time: datetime.datetime | None = None

    def __post_init__(self) -> None:
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("An Event needs both start_time and end_time, or neither")

    @property
    def is_separately_timed(self) -> bool:
        return self.end_time is not None


@dataclass(frozen=True, slots=True)
class Screening:
    """A single showing of a Programme Entry at a given time and Venue."""

    id: ScreeningId
    programme_entry_id: ProgrammeEntryId
    venue_id: VenueId
    start_time: datetime.datetime
    end_time: datetime.datetime
    auditorium: str | None = None
    ticket_url: str | None = None
    events: tuple[Event, ...] = ()

    def ends_at(self, *, include_events: bool) -> datetime.datetime:
        """When the Screening ends, optionally including separately timed Events."""
        if not include_events:
            return self.end_time
        event_ends = [e.end_time for e in self.events if e.end_time is not None]
        return max([self.end_time, *event_ends])
