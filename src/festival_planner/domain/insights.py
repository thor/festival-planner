"""Read-side planning: diffs, flags, Comparison suggestions, inferred Seen."""

import datetime
import enum
from collections import defaultdict
from collections.abc import Iterable, Mapping

from .planning import PlanningInputs, Ticket
from .programme import FilmId, ProgrammeEntry, ProgrammeEntryId, Screening, ScreeningId
from .solving import SolveRequest, formulate, score
from .values import Value


class DraftDiff(Value):
    """A Draft's Schedule against the Active Schedule."""

    added: frozenset[ScreeningId]
    removed: frozenset[ScreeningId]
    score_delta: float
    """Draft score minus the Active Schedule's, both under the Draft's Preferences."""
    dropped_tickets: frozenset[ScreeningId]
    """Removed Screenings the User holds a Ticket for."""


def diff(
    request: SolveRequest, scheduled: frozenset[ScreeningId], tickets: Iterable[Ticket]
) -> DraftDiff:
    active = request.active_schedule
    removed = active - scheduled
    return DraftDiff(
        added=scheduled - active,
        removed=removed,
        score_delta=score(request, scheduled) - score(request, active),
        dropped_tickets=frozenset(t.screening_id for t in tickets) & removed,
    )


class FlagKind(enum.StrEnum):
    WITHDRAWN_COMMITMENT = "WITHDRAWN_COMMITMENT"
    WITHDRAWN_TICKET = "WITHDRAWN_TICKET"
    UNSCHEDULED_TICKET = "UNSCHEDULED_TICKET"
    WITHDRAWN_IN_SCHEDULE = "WITHDRAWN_IN_SCHEDULE"


class Flag(Value):
    """Something in a User's planning that needs their attention."""

    kind: FlagKind
    target_id: str
    """The Screening or (for Film Commitments) Programme Entry concerned."""
    message: str


def flags(
    screenings: Iterable[Screening],
    inputs: PlanningInputs,
    tickets: Iterable[Ticket],
    active: frozenset[ScreeningId],
) -> tuple[Flag, ...]:
    """Flags for one Festival, given its Screenings (Withdrawn included)."""
    by_id = {s.id: s for s in screenings}
    gone = {i for i, s in by_id.items() if s.withdrawn}
    by_entry: defaultdict[ProgrammeEntryId, list[Screening]] = defaultdict(list)
    for s in by_id.values():
        by_entry[s.programme_entry_id].append(s)
    found = [
        Flag(
            kind=FlagKind.WITHDRAWN_COMMITMENT,
            target_id=i,
            message=f"Committed Screening {i!r} was withdrawn",
        )
        for i in inputs.screening_commitments & gone
    ]
    found += [
        Flag(
            kind=FlagKind.WITHDRAWN_COMMITMENT,
            target_id=e,
            message=f"Every Screening of committed programme entry {e!r} was withdrawn",
        )
        for e in inputs.film_commitments
        if by_entry.get(e) and all(s.withdrawn for s in by_entry[e])
    ]
    for ticket in tickets:
        i = ticket.screening_id
        if i not in by_id:
            continue
        if i in gone:
            found.append(
                Flag(
                    kind=FlagKind.WITHDRAWN_TICKET,
                    target_id=i,
                    message=f"Ticketed Screening {i!r} was withdrawn",
                )
            )
        elif i not in active:
            found.append(
                Flag(
                    kind=FlagKind.UNSCHEDULED_TICKET,
                    target_id=i,
                    message=f"Ticketed Screening {i!r} is not in the Active Schedule",
                )
            )
    found += [
        Flag(
            kind=FlagKind.WITHDRAWN_IN_SCHEDULE,
            target_id=i,
            message=f"Scheduled Screening {i!r} was withdrawn",
        )
        for i in active & gone
    ]
    order = list(FlagKind)
    return tuple(sorted(found, key=lambda f: (order.index(f.kind), f.target_id)))


class ComparisonSuggestion(Value):
    """Two Programme Entries whose Screenings competed; one won."""

    scheduled: ProgrammeEntryId
    other: ProgrammeEntryId
    weight_gap: float


def suggest_comparisons(
    request: SolveRequest, scheduled: frozenset[ScreeningId], limit: int = 10
) -> tuple[ComparisonSuggestion, ...]:
    """Pairs that conflicted in a solve of `request` where exactly one was
    scheduled and the User has not compared them, closest calls first."""
    formulation = formulate(request)
    entry_of = {s.id: s.programme_entry_id for s in formulation.candidates}
    compared = {c.pair for c in request.preferences.comparisons}
    best: dict[frozenset[str], ComparisonSuggestion] = {}
    for a, b in formulation.conflicts:
        if (a in scheduled) == (b in scheduled):
            continue
        won, lost = (a, b) if a in scheduled else (b, a)
        pair = frozenset((entry_of[won], entry_of[lost]))
        if len(pair) < 2 or pair in compared:
            continue
        suggestion = ComparisonSuggestion(
            scheduled=entry_of[won],
            other=entry_of[lost],
            weight_gap=abs(formulation.weights[won] - formulation.weights[lost]),
        )
        if pair not in best or suggestion.weight_gap < best[pair].weight_gap:
            best[pair] = suggestion
    ranked = sorted(best.values(), key=lambda s: (s.weight_gap, s.scheduled, s.other))
    return tuple(ranked[:limit])


def inferred_seen(
    screenings: Iterable[Screening],
    entries: Mapping[ProgrammeEntryId, ProgrammeEntry],
    dismissed: frozenset[ScreeningId],
    now: datetime.datetime,
) -> frozenset[FilmId]:
    """Films Seen because a Screening in an Active Schedule has ended.

    Callers pass the Screenings of the User's Active Schedules."""
    return frozenset(
        entries[s.programme_entry_id].film_id
        for s in screenings
        if not s.withdrawn
        and s.id not in dismissed
        and s.end_time <= now
        and s.programme_entry_id in entries
    )
