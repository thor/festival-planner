"""Solving: turning a self-contained solve request into a Schedule.

`formulate` holds all scheduling rules as pure Python. A `ScheduleSolver`
adapter only has to optimise the resulting `Formulation`.
"""

import datetime
import enum
import itertools
from collections import defaultdict
from collections.abc import Mapping
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


@dataclass(frozen=True)
class Formulation:
    """The optimisation problem derived from a solve request."""

    candidates: tuple[Screening, ...]
    weights: Mapping[ScreeningId, float]
    required: frozenset[ScreeningId]
    exactly_one: tuple[frozenset[ScreeningId], ...]
    at_most_one: tuple[frozenset[ScreeningId], ...]
    conflicts: frozenset[tuple[ScreeningId, ScreeningId]]
    unsatisfiable: tuple[str, ...]


def formulate(request: SolveRequest) -> Formulation:
    """Apply the scheduling rules to `request`.

    Rules, in order of precedence:
    - Screenings that started before `now` are fixed: kept and required if in
      the Active Schedule, dropped otherwise. Fixed Screenings never conflict
      with each other.
    - Screening Commitments are required, regardless of exclusions, Seen or
      the date range.
    - Excluded Screenings and Programme Entries are dropped.
    - Screenings of Seen Films are dropped unless committed to.
    - Screenings outside the preferred date range are dropped.
    - Each Film Commitment needs exactly one of its remaining Screenings.
    - At most one Screening per Programme Entry.
    - Two Screenings conflict when neither can be reached from the other in
      time, given travel and the arrival buffer.
    """
    preferences = request.preferences
    entries = {e.id: e for e in request.programme_entries}
    unsatisfiable: list[str] = []
    candidates: list[Screening] = []
    required: set[ScreeningId] = set()
    fixed: set[ScreeningId] = set()

    for screening in request.screenings:
        entry = entries[screening.programme_entry_id]
        committed = screening.id in request.screening_commitments
        if request.now is not None and screening.start_time < request.now:
            if screening.id in request.active_schedule:
                candidates.append(screening)
                required.add(screening.id)
                fixed.add(screening.id)
            elif committed:
                unsatisfiable.append(
                    f"Committed screening {screening.id!r} has already started"
                )
            continue
        if committed:
            candidates.append(screening)
            required.add(screening.id)
            continue
        if (
            screening.id in request.excluded_screenings
            or entry.id in request.excluded_programme_entries
        ):
            continue
        if (
            entry.film_id in request.seen_films
            and entry.id not in request.film_commitments
        ):
            continue
        if not preferences.covers(screening.start_time.date()):
            continue
        candidates.append(screening)

    by_entry: defaultdict[ProgrammeEntryId, set[ScreeningId]] = defaultdict(set)
    for screening in candidates:
        by_entry[screening.programme_entry_id].add(screening.id)

    exactly_one: list[frozenset[ScreeningId]] = []
    for entry_id in sorted(request.film_commitments):
        options = by_entry.get(entry_id)
        if not options:
            unsatisfiable.append(
                f"Film commitment {entry_id!r} has no schedulable screening"
            )
            continue
        exactly_one.append(frozenset(options))

    return Formulation(
        candidates=tuple(candidates),
        weights={
            s.id: screening_weight(s, entries[s.programme_entry_id], preferences)
            for s in candidates
        },
        required=frozenset(required),
        exactly_one=tuple(exactly_one),
        at_most_one=tuple(frozenset(ids) for ids in by_entry.values() if len(ids) > 1),
        conflicts=_conflicts(candidates, fixed, request.routes, preferences),
        unsatisfiable=tuple(unsatisfiable),
    )


def _conflicts(
    screenings: list[Screening],
    fixed: set[ScreeningId],
    routes: RouteTable,
    preferences: Preferences,
) -> frozenset[tuple[ScreeningId, ScreeningId]]:
    """Conflicting pairs; fixed Screenings are history and never conflict."""
    conflicts = set()
    for a, b in itertools.combinations(screenings, 2):
        if a.id in fixed and b.id in fixed:
            continue
        if not (
            _reachable(a, b, routes, preferences)
            or _reachable(b, a, routes, preferences)
        ):
            conflicts.add((a.id, b.id))
    return frozenset(conflicts)


def _reachable(
    first: Screening, second: Screening, routes: RouteTable, preferences: Preferences
) -> bool:
    """Whether one can attend `first` and still arrive in time for `second`."""
    travel = routes.minutes(first.venue_id, second.venue_id, preferences.transport_mode)
    needed = datetime.timedelta(
        minutes=travel + preferences.buffer_for(second.venue_id)
    )
    leaves = first.ends_at(include_events=preferences.attend_events)
    return leaves + needed <= second.start_time
