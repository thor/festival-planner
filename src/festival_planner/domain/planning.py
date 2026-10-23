"""A User's planning inputs: Preferences, Comparisons, commitments and Tickets."""

import datetime
from collections.abc import Mapping
from typing import Self

from pydantic import Field, field_validator, model_validator

from .programme import ProgrammeEntryId, ScreeningId, VenueId
from .travel import TransportMode
from .values import Value


class Comparison(Value):
    """A User's statement that they would rather watch `preferred` than `other`."""

    preferred: ProgrammeEntryId
    other: ProgrammeEntryId

    @model_validator(mode="after")
    def _compares_two_entries(self) -> Self:
        if self.preferred == self.other:
            raise ValueError(f"Cannot compare {self.preferred!r} with itself")
        return self

    @property
    def pair(self) -> frozenset[ProgrammeEntryId]:
        return frozenset((self.preferred, self.other))


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
    comparison_weight: float = Field(default=0.5, ge=0)
    """How strongly Comparisons shift Programme Entry weights."""
    comparisons: tuple[Comparison, ...] = ()

    @field_validator("comparisons")
    @classmethod
    def _one_comparison_per_pair(
        cls, comparisons: tuple[Comparison, ...]
    ) -> tuple[Comparison, ...]:
        pairs: set[frozenset[str]] = set()
        for comparison in comparisons:
            if comparison.pair in pairs:
                raise ValueError(f"Several comparisons of {sorted(comparison.pair)}")
            pairs.add(comparison.pair)
        return tuple(sorted(comparisons, key=lambda c: (c.preferred, c.other)))

    def buffer_for(self, venue_id: VenueId) -> int:
        """Minutes to arrive before a Screening at `venue_id`."""
        return self.venue_buffer_minutes.get(venue_id, self.buffer_minutes)

    def covers(self, day: datetime.date) -> bool:
        """Whether `day` falls inside the preferred date range."""
        if self.start_date is not None and day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date


class PlanningInputs(Value):
    """A User's accepted commitments, Excluded and Preferences for one Festival."""

    screening_commitments: frozenset[ScreeningId] = frozenset()
    film_commitments: frozenset[ProgrammeEntryId] = frozenset()
    excluded_screenings: frozenset[ScreeningId] = frozenset()
    excluded_programme_entries: frozenset[ProgrammeEntryId] = frozenset()
    preferences: Preferences = Field(default_factory=Preferences)


class Ticket(Value):
    """A User's record that they hold a ticket for a Screening."""

    screening_id: ScreeningId
    exchangeable: bool = False
    refundable: bool = False
