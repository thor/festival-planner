"""Solving: turning a self-contained solve request into a Schedule.

`formulate` holds all scheduling rules as pure Python. A `ScheduleSolver`
adapter only has to optimise the resulting `Formulation`.
"""

import datetime
import enum
import itertools
import zoneinfo
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, Self

from pydantic import AwareDatetime, Field, model_validator

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
from .values import TimeZone, Value

DEFAULT_WEIGHT = 1.0
"""Weight of a Screening without any weight preference."""


class SolveRequest(Value):
    """Everything needed to solve one Schedule, as plain values.

    Ids must be unique per kind, and Screenings must refer to known Programme
    Entries and Venues. Other ids (commitments, exclusions, Seen, Active
    Schedule) may refer to nothing; `formulate` decides what that means.
    """

    venues: tuple[Venue, ...]
    programme_entries: tuple[ProgrammeEntry, ...]
    screenings: tuple[Screening, ...]
    time_zone: TimeZone
    """The Festival's time zone; date ranges are festival-local dates."""
    routes: RouteTable = Field(default_factory=RouteTable)
    preferences: Preferences = Field(default_factory=Preferences)
    screening_commitments: frozenset[ScreeningId] = frozenset()
    film_commitments: frozenset[ProgrammeEntryId] = frozenset()
    excluded_screenings: frozenset[ScreeningId] = frozenset()
    excluded_programme_entries: frozenset[ProgrammeEntryId] = frozenset()
    seen_films: frozenset[FilmId] = frozenset()
    active_schedule: frozenset[ScreeningId] = frozenset()
    now: AwareDatetime | None = None
    time_limit_seconds: float = 60.0

    @model_validator(mode="after")
    def _references_are_sound(self) -> Self:
        for kind, items in (
            ("screening", self.screenings),
            ("programme entry", self.programme_entries),
            ("venue", self.venues),
        ):
            seen: set[str] = set()
            for item in items:
                if item.id in seen:
                    raise ValueError(f"Duplicate {kind} id {item.id!r}")
                seen.add(item.id)
        entry_ids = {e.id for e in self.programme_entries}
        venue_ids = {v.id for v in self.venues}
        for screening in self.screenings:
            if screening.programme_entry_id not in entry_ids:
                raise ValueError(
                    f"Screening {screening.id!r} references unknown programme entry "
                    f"{screening.programme_entry_id!r}"
                )
            if screening.venue_id not in venue_ids:
                raise ValueError(
                    f"Screening {screening.id!r} references unknown venue "
                    f"{screening.venue_id!r}"
                )
        return self

    def local_date(self, instant: datetime.datetime) -> datetime.date:
        """The festival-local calendar day of `instant`."""
        return instant.astimezone(zoneinfo.ZoneInfo(self.time_zone)).date()


class SolveStatus(enum.StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    """The time limit ran out before any Schedule was found."""


class ScheduledScreening(Value):
    screening_id: ScreeningId
    arrival_time: AwareDatetime
    weight: float


class SolveResult(Value):
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
    - Screenings outside the preferred (festival-local) date range are dropped.
    - Each Film Commitment needs exactly one of its remaining Screenings.
    - At most one Screening per Programme Entry.
    - Two Screenings conflict when neither can be reached from the other in
      time, given travel and the arrival buffer.
    """
    preferences = request.preferences
    entries = {e.id: e for e in request.programme_entries}
    unsatisfiable: list[str] = [
        f"Committed screening {screening_id!r} does not exist"
        for screening_id in sorted(
            request.screening_commitments - {s.id for s in request.screenings}
        )
    ]
    unsatisfiable += [
        f"Committed programme entry {entry_id!r} does not exist"
        for entry_id in sorted(request.film_commitments - entries.keys())
    ]
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
        if not preferences.covers(request.local_date(screening.start_time)):
            continue
        candidates.append(screening)

    by_entry: defaultdict[ProgrammeEntryId, set[ScreeningId]] = defaultdict(set)
    for screening in candidates:
        by_entry[screening.programme_entry_id].add(screening.id)

    exactly_one: list[frozenset[ScreeningId]] = []
    for entry_id in sorted(request.film_commitments):
        if entry_id not in entries:
            continue
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
    arrives_by = second.starts_at(include_events=preferences.attend_events)
    return leaves + needed <= arrives_by
