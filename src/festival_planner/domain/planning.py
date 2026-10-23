"""A User's planning inputs: Preferences, Comparisons, commitments and Tickets."""

import datetime
from collections.abc import Iterable, Mapping
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


def days_in_order(days: Iterable[datetime.date]) -> tuple[datetime.date, ...]:
    """`days` sorted, once each; at least one, as no days at all means nothing."""
    ordered = tuple(sorted(set(days)))
    if not ordered:
        raise ValueError("Pick at least one day, or none to mean every day")
    return ordered


def days_between(start: datetime.date, end: datetime.date) -> tuple[datetime.date, ...]:
    """Every day from `start` to `end`, both included."""
    return tuple(
        start + datetime.timedelta(days=n) for n in range((end - start).days + 1)
    )


class Preferences(Value):
    """A User's settings that shape their Schedules for a Festival."""

    buffer_minutes: int = 15
    venue_buffer_minutes: Mapping[VenueId, int] = Field(default_factory=dict)
    days: tuple[datetime.date, ...] | None = None
    """The Festival Days the User can go, in order; None means every day."""
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

    @field_validator("days")
    @classmethod
    def _days_in_order(
        cls, days: tuple[datetime.date, ...] | None
    ) -> tuple[datetime.date, ...] | None:
        return None if days is None else days_in_order(days)

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
        """Whether `day` is one of the days the User can go."""
        return self.days is None or day in self.days


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
