"""A User's planning inputs: Preferences."""

import datetime
from collections.abc import Mapping

from pydantic import Field

from .programme import ProgrammeEntryId, ScreeningId, VenueId
from .travel import TransportMode
from .values import Value


class Preferences(Value):
    """A User's settings that shape their Schedules for a Festival."""

    buffer_minutes: int = 15
    venue_buffer_minutes: Mapping[VenueId, int] = Field(default_factory=dict)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    programme_entry_weights: Mapping[ProgrammeEntryId, float] = Field(
        default_factory=dict
    )
    screening_weights: Mapping[ScreeningId, float] = Field(default_factory=dict)
    year_weights: Mapping[int, float] = Field(default_factory=dict)
    event_weight: float = 0.0
    attend_events: bool = False
    transport_mode: TransportMode | None = None

    def buffer_for(self, venue_id: VenueId) -> int:
        """Minutes to arrive before a Screening at `venue_id`."""
        return self.venue_buffer_minutes.get(venue_id, self.buffer_minutes)

    def covers(self, day: datetime.date) -> bool:
        """Whether `day` falls inside the preferred date range."""
        if self.start_date is not None and day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date
