"""Change Sets: what a Draft proposes to change in a User's planning inputs."""

import datetime
import enum
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .planning import Comparison, PlanningInputs, Preferences
from .programme import (
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
)
from .travel import TransportMode
from .values import Value

# --- Commitments and Excluded ----------------------------------------------


class AddScreeningCommitment(Value):
    kind: Literal["add_screening_commitment"] = "add_screening_commitment"
    screening_id: ScreeningId


class ReleaseScreeningCommitment(Value):
    kind: Literal["release_screening_commitment"] = "release_screening_commitment"
    screening_id: ScreeningId


class AddFilmCommitment(Value):
    kind: Literal["add_film_commitment"] = "add_film_commitment"
    programme_entry_id: ProgrammeEntryId


class ReleaseFilmCommitment(Value):
    kind: Literal["release_film_commitment"] = "release_film_commitment"
    programme_entry_id: ProgrammeEntryId


class AddExcludedScreening(Value):
    kind: Literal["add_excluded_screening"] = "add_excluded_screening"
    screening_id: ScreeningId


class RemoveExcludedScreening(Value):
    kind: Literal["remove_excluded_screening"] = "remove_excluded_screening"
    screening_id: ScreeningId


class AddExcludedProgrammeEntry(Value):
    kind: Literal["add_excluded_programme_entry"] = "add_excluded_programme_entry"
    programme_entry_id: ProgrammeEntryId


class RemoveExcludedProgrammeEntry(Value):
    kind: Literal["remove_excluded_programme_entry"] = "remove_excluded_programme_entry"
    programme_entry_id: ProgrammeEntryId


# --- Preferences: `None` resets a setting to its default -------------------


class SetProgrammeEntryWeight(Value):
    kind: Literal["set_programme_entry_weight"] = "set_programme_entry_weight"
    programme_entry_id: ProgrammeEntryId
    weight: float | None


class SetScreeningWeight(Value):
    kind: Literal["set_screening_weight"] = "set_screening_weight"
    screening_id: ScreeningId
    weight: float | None


class SetYearWeight(Value):
    kind: Literal["set_year_weight"] = "set_year_weight"
    year: int
    weight: float | None


class SetBuffer(Value):
    """The general buffer, or with `venue_id` that Venue's buffer."""

    kind: Literal["set_buffer"] = "set_buffer"
    venue_id: VenueId | None = None
    minutes: int | None = Field(default=None, ge=0)


class SetDateRange(Value):
    kind: Literal["set_date_range"] = "set_date_range"
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None

    @model_validator(mode="after")
    def _ends_after_it_starts(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("A date range cannot end before it starts")
        return self


class SetEventWeight(Value):
    kind: Literal["set_event_weight"] = "set_event_weight"
    weight: float | None


class SetAttendEvents(Value):
    kind: Literal["set_attend_events"] = "set_attend_events"
    attend: bool | None


class SetTransportMode(Value):
    kind: Literal["set_transport_mode"] = "set_transport_mode"
    mode: TransportMode | None


class SetComparisonWeight(Value):
    kind: Literal["set_comparison_weight"] = "set_comparison_weight"
    weight: float | None = Field(ge=0)


class RecordComparison(Value):
    """Replaces any earlier Comparison of the same two Programme Entries."""

    kind: Literal["record_comparison"] = "record_comparison"
    preferred: ProgrammeEntryId
    other: ProgrammeEntryId

    @model_validator(mode="after")
    def _compares_two_entries(self) -> Self:
        if self.preferred == self.other:
            raise ValueError(f"Cannot compare {self.preferred!r} with itself")
        return self


ChangeSetItem = Annotated[
    AddScreeningCommitment
    | ReleaseScreeningCommitment
    | AddFilmCommitment
    | ReleaseFilmCommitment
    | AddExcludedScreening
    | RemoveExcludedScreening
    | AddExcludedProgrammeEntry
    | RemoveExcludedProgrammeEntry
    | SetProgrammeEntryWeight
    | SetScreeningWeight
    | SetYearWeight
    | SetBuffer
    | SetDateRange
    | SetEventWeight
    | SetAttendEvents
    | SetTransportMode
    | SetComparisonWeight
    | RecordComparison,
    Field(discriminator="kind"),
]


class ChangeSet(Value):
    """The changes a Draft proposes, in order."""

    items: tuple[ChangeSetItem, ...] = ()


# --- Rules -----------------------------------------------------------------


@dataclass(frozen=True)
class ProgrammeIndex:
    """The ids a Festival's Change Sets may refer to."""

    entry_of: Mapping[ScreeningId, ProgrammeEntryId]
    programme_entries: frozenset[ProgrammeEntryId]
    venues: frozenset[VenueId]

    @classmethod
    def of(
        cls,
        entries: Iterable[ProgrammeEntry],
        screenings: Iterable[Screening],
        venues: Iterable[Venue],
    ) -> "ProgrammeIndex":
        return cls(
            entry_of={s.id: s.programme_entry_id for s in screenings},
            programme_entries=frozenset(e.id for e in entries),
            venues=frozenset(v.id for v in venues),
        )


class ProblemCode(enum.StrEnum):
    UNKNOWN_ID = "UNKNOWN_ID"
    CONFLICTING_ITEMS = "CONFLICTING_ITEMS"
    NO_OP = "NO_OP"
    COMMITTED_AND_EXCLUDED = "COMMITTED_AND_EXCLUDED"
    TWO_SCREENING_COMMITMENTS = "TWO_SCREENING_COMMITMENTS"


class ChangeSetProblem(Value):
    code: ProblemCode
    items: tuple[int, ...]
    """Indexes of the items involved, if any."""
    message: str


class InvalidChangeSetError(Exception):
    def __init__(self, problems: Iterable[ChangeSetProblem]):
        self.problems = tuple(problems)
        super().__init__("; ".join(p.message for p in self.problems))


_COLLECTIONS: dict[type, tuple[str, bool]] = {
    AddScreeningCommitment: ("screening_commitments", True),
    ReleaseScreeningCommitment: ("screening_commitments", False),
    AddFilmCommitment: ("film_commitments", True),
    ReleaseFilmCommitment: ("film_commitments", False),
    AddExcludedScreening: ("excluded_screenings", True),
    RemoveExcludedScreening: ("excluded_screenings", False),
    AddExcludedProgrammeEntry: ("excluded_programme_entries", True),
    RemoveExcludedProgrammeEntry: ("excluded_programme_entries", False),
}
"""Commitment and Excluded items: (PlanningInputs field, adds?)."""


def _collection_id(item: ChangeSetItem) -> str:
    """The Screening or Programme Entry a commitment or Excluded item is about."""
    return getattr(item, "screening_id", None) or getattr(item, "programme_entry_id")


def _target(item: ChangeSetItem) -> tuple[str, ...]:
    """What `item` changes; two items of one Change Set must not share it."""
    if (collection := _COLLECTIONS.get(type(item))) is not None:
        return (collection[0], _collection_id(item))
    match item:
        case SetProgrammeEntryWeight(programme_entry_id=i):
            return ("programme_entry_weight", i)
        case SetScreeningWeight(screening_id=i):
            return ("screening_weight", i)
        case SetYearWeight(year=year):
            return ("year_weight", str(year))
        case SetBuffer(venue_id=venue_id):
            return ("buffer", venue_id or "")
        case RecordComparison(preferred=a, other=b):
            return ("comparison", *sorted((a, b)))
        case _:
            return (item.kind,)


def _references(item: ChangeSetItem) -> list[tuple[str, str]]:
    """(kind, id) pairs `item` refers to."""
    match item:
        case RecordComparison(preferred=a, other=b):
            return [("programme entry", a), ("programme entry", b)]
        case SetBuffer(venue_id=str() as venue_id):
            return [("venue", venue_id)]
    refs = []
    if (screening_id := getattr(item, "screening_id", None)) is not None:
        refs.append(("screening", screening_id))
    if (entry_id := getattr(item, "programme_entry_id", None)) is not None:
        refs.append(("programme entry", entry_id))
    return refs


def _known(programme: ProgrammeIndex, kind: str, id: str) -> bool:
    match kind:
        case "screening":
            return id in programme.entry_of
        case "programme entry":
            return id in programme.programme_entries
        case _:
            return id in programme.venues


def _default(field: str):
    return Preferences.model_fields[field].get_default(call_default_factory=True)


def _put(mapping: Mapping, key, value) -> dict:
    updated = dict(mapping)
    if value is None:
        updated.pop(key, None)
    else:
        updated[key] = value
    return updated


def _set(preferences: Preferences, item: ChangeSetItem) -> Preferences:
    p = preferences
    match item:
        case SetProgrammeEntryWeight(programme_entry_id=i, weight=w):
            changes = {"programme_entry_weights": _put(p.programme_entry_weights, i, w)}
        case SetScreeningWeight(screening_id=i, weight=w):
            changes = {"screening_weights": _put(p.screening_weights, i, w)}
        case SetYearWeight(year=year, weight=w):
            changes = {"year_weights": _put(p.year_weights, year, w)}
        case SetBuffer(venue_id=None, minutes=m):
            changes = {"buffer_minutes": _default("buffer_minutes") if m is None else m}
        case SetBuffer(venue_id=str() as venue_id, minutes=m):
            changes = {
                "venue_buffer_minutes": _put(p.venue_buffer_minutes, venue_id, m)
            }
        case SetDateRange(start_date=start, end_date=end):
            changes = {"start_date": start, "end_date": end}
        case SetEventWeight(weight=w):
            changes = {"event_weight": _default("event_weight") if w is None else w}
        case SetAttendEvents(attend=a):
            changes = {"attend_events": _default("attend_events") if a is None else a}
        case SetTransportMode(mode=m):
            changes = {"transport_mode": m}
        case SetComparisonWeight(weight=w):
            changes = {
                "comparison_weight": _default("comparison_weight") if w is None else w
            }
        case RecordComparison(preferred=a, other=b):
            comparison = Comparison(preferred=a, other=b)
            changes = {
                "comparisons": (
                    *(c for c in p.comparisons if c.pair != comparison.pair),
                    comparison,
                )
            }
        case _:
            raise AssertionError(f"Not a Preferences item: {item!r}")
    return Preferences.model_validate({**p.model_dump(), **changes})


def _apply_item(item: ChangeSetItem, inputs: PlanningInputs) -> PlanningInputs:
    if (collection := _COLLECTIONS.get(type(item))) is not None:
        field, adds = collection
        current: frozenset[str] = getattr(inputs, field)
        target = _collection_id(item)
        updated = current | {target} if adds else current - {target}
        return inputs.model_copy(update={field: updated})
    return inputs.model_copy(update={"preferences": _set(inputs.preferences, item)})


def apply(change_set: ChangeSet, base: PlanningInputs) -> PlanningInputs:
    """`base` with every item applied in order."""
    inputs = base
    for item in change_set.items:
        inputs = _apply_item(item, inputs)
    return inputs


def problems(
    change_set: ChangeSet, base: PlanningInputs, programme: ProgrammeIndex
) -> tuple[ChangeSetProblem, ...]:
    """Everything wrong with applying `change_set` to `base`."""
    found: list[ChangeSetProblem] = []
    by_target: defaultdict[tuple[str, ...], list[int]] = defaultdict(list)
    touching: defaultdict[str, list[int]] = defaultdict(list)
    for index, item in enumerate(change_set.items):
        for kind, id in _references(item):
            if not _known(programme, kind, id):
                found.append(
                    ChangeSetProblem(
                        code=ProblemCode.UNKNOWN_ID,
                        items=(index,),
                        message=f"Item {index} ({item.kind}): unknown {kind} {id!r}",
                    )
                )
        by_target[_target(item)].append(index)
        if type(item) in _COLLECTIONS:
            touching[_collection_id(item)].append(index)
        if _apply_item(item, base) == base:
            found.append(
                ChangeSetProblem(
                    code=ProblemCode.NO_OP,
                    items=(index,),
                    message=f"Item {index} ({item.kind}) changes nothing",
                )
            )
    for target, indexes in by_target.items():
        if len(indexes) > 1:
            found.append(
                ChangeSetProblem(
                    code=ProblemCode.CONFLICTING_ITEMS,
                    items=tuple(indexes),
                    message=f"Items {indexes} all change {' '.join(target)}",
                )
            )
    result = apply(change_set, base)
    for id in sorted(
        (result.screening_commitments & result.excluded_screenings)
        | (result.film_commitments & result.excluded_programme_entries)
    ):
        found.append(
            ChangeSetProblem(
                code=ProblemCode.COMMITTED_AND_EXCLUDED,
                items=tuple(touching[id]),
                message=f"{id!r} would be both committed to and Excluded",
            )
        )
    by_entry: defaultdict[str, list[str]] = defaultdict(list)
    for screening_id in sorted(result.screening_commitments):
        if (entry_id := programme.entry_of.get(screening_id)) is not None:
            by_entry[entry_id].append(screening_id)
    for entry_id, screening_ids in sorted(by_entry.items()):
        if len(screening_ids) > 1:
            found.append(
                ChangeSetProblem(
                    code=ProblemCode.TWO_SCREENING_COMMITMENTS,
                    items=tuple(i for s in screening_ids for i in touching[s]),
                    message=(
                        f"Several Screening Commitments for programme entry "
                        f"{entry_id!r}: {', '.join(screening_ids)}"
                    ),
                )
            )
    return tuple(found)


def check(
    change_set: ChangeSet, base: PlanningInputs, programme: ProgrammeIndex
) -> None:
    """Raise `InvalidChangeSetError` unless `change_set` applies cleanly to `base`."""
    if found := problems(change_set, base, programme):
        raise InvalidChangeSetError(found)


def rebase(
    change_set: ChangeSet, base: PlanningInputs, programme: ProgrammeIndex
) -> tuple[ChangeSet, tuple[str, ...]]:
    """`change_set` made against a newer `base`: items that now change
    nothing are dropped (with a note); other problems raise."""
    found = problems(change_set, base, programme)
    if blocking := [p for p in found if p.code is not ProblemCode.NO_OP]:
        raise InvalidChangeSetError(blocking)
    dropped = {i for p in found for i in p.items}
    notes = tuple(
        f"Dropped {change_set.items[i].kind} (item {i}): already in effect"
        for i in sorted(dropped)
    )
    kept = tuple(item for i, item in enumerate(change_set.items) if i not in dropped)
    return ChangeSet(items=kept), notes
