"""Solving: turning a self-contained solve request into a Schedule.

`formulate` holds all scheduling rules as pure Python. A `ScheduleSolver`
adapter only has to optimise the resulting `Formulation`.
"""

import datetime
import enum
from dataclasses import dataclass, field
from typing import Protocol

from .planning import Preferences
from .programme import (
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
)
from .travel import RouteTable

DEFAULT_WEIGHT = 1.0
"""Weight of a Screening without any weight preference."""


@dataclass(frozen=True)
class SolveRequest:
    """Everything needed to solve one Schedule, as plain values."""

    venues: tuple[Venue, ...]
    programme_entries: tuple[ProgrammeEntry, ...]
    screenings: tuple[Screening, ...]
    routes: RouteTable = field(default_factory=RouteTable)
    preferences: Preferences = field(default_factory=Preferences)
    screening_commitments: frozenset[ScreeningId] = frozenset()
    film_commitments: frozenset[ProgrammeEntryId] = frozenset()
    excluded_screenings: frozenset[ScreeningId] = frozenset()
    excluded_programme_entries: frozenset[ProgrammeEntryId] = frozenset()
    seen_films: frozenset[FilmId] = frozenset()
    active_schedule: frozenset[ScreeningId] = frozenset()
    now: datetime.datetime | None = None
    time_limit_seconds: float = 60.0


class SolveStatus(enum.StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    """The time limit ran out before any Schedule was found."""


@dataclass(frozen=True, slots=True)
class ScheduledScreening:
    screening_id: ScreeningId
    arrival_time: datetime.datetime
    weight: float


@dataclass(frozen=True)
class SolveResult:
    status: SolveStatus
    scheduled: tuple[ScheduledScreening, ...] = ()
    objective: float = 0.0
    wall_time_seconds: float = 0.0
    reasons: tuple[str, ...] = ()
    """Why the request cannot be satisfied, when known."""

    @property
    def is_solved(self) -> bool:
        return self.status in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)


class ScheduleSolver(Protocol):
    """Port: produces the best Schedule for a solve request."""

    def solve(self, request: SolveRequest) -> SolveResult: ...


def screening_weight(
    screening: Screening, entry: ProgrammeEntry, preferences: Preferences
) -> float:
    """How much attending `screening` is worth.

    A screening weight overrides a programme entry weight, which overrides
    `DEFAULT_WEIGHT`. Year and Event weights are added on top.
    """
    weight = preferences.screening_weights.get(
        screening.id, preferences.programme_entry_weights.get(entry.id, DEFAULT_WEIGHT)
    )
    if entry.year is not None:
        weight += preferences.year_weights.get(entry.year, 0.0)
    if screening.events:
        weight += preferences.event_weight
    return weight
