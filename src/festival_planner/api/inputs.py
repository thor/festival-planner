"""GraphQL inputs, and turning Change Set item inputs into a domain Change Set.

Ids are opaque global ids. One that does not decode to the expected type,
such as a raw domain id, is an UNKNOWN_ID problem of its item; it is never
looked up as a domain id.
"""

import dataclasses
import datetime
from typing import Any

import pydantic
import strawberry

from ..domain import change_sets as cs
from .ids import decode

RESET = "Null or left out resets the setting to its default."


def _or_none[T](value: T | None) -> T | None:
    """`None` for a field the client left out (UNSET)."""
    return None if value is strawberry.UNSET else value


# --- Shared references -----------------------------------------------------


@strawberry.input(description="A Screening, by id.")
class ScreeningInput:
    screening_id: strawberry.ID


@strawberry.input(description="A Programme Entry, by id.")
class ProgrammeEntryInput:
    programme_entry_id: strawberry.ID


@strawberry.input(description="A Film, by id.")
class FilmInput:
    film_id: strawberry.ID


@strawberry.input(description="A Draft, by id.")
class DraftInput:
    draft_id: strawberry.ID


# --- Preferences items -----------------------------------------------------


@strawberry.input
class SetProgrammeEntryWeightInput:
    programme_entry_id: strawberry.ID
    weight: float | None = strawberry.field(default=strawberry.UNSET, description=RESET)


@strawberry.input
class SetScreeningWeightInput:
    screening_id: strawberry.ID
    weight: float | None = strawberry.field(default=strawberry.UNSET, description=RESET)


@strawberry.input
class SetYearWeightInput:
    year: int
    weight: float | None = strawberry.field(default=strawberry.UNSET, description=RESET)


@strawberry.input(description="The general buffer, or with a Venue that Venue's.")
class SetBufferInput:
    venue_id: strawberry.ID | None = strawberry.UNSET
    minutes: int | None = strawberry.field(default=strawberry.UNSET, description=RESET)


@strawberry.input(description="The Festival Days the User can go.")
class SetDaysInput:
    days: list[datetime.date] | None = strawberry.field(
        default=strawberry.UNSET,
        description="At least one, in the Festival's time zone. " + RESET,
    )


@strawberry.input
class SetEventWeightInput:
    weight: float | None = strawberry.field(default=strawberry.UNSET, description=RESET)


@strawberry.input
class SetAttendEventsInput:
    attend: bool | None = strawberry.field(default=strawberry.UNSET, description=RESET)


@strawberry.input
class SetTransportModeInput:
    mode: str | None = strawberry.field(default=strawberry.UNSET, description=RESET)


@strawberry.input
class SetComparisonWeightInput:
    weight: float | None = strawberry.field(default=strawberry.UNSET, description=RESET)


@strawberry.input(description="Replaces any earlier Comparison of the same pair.")
class RecordComparisonInput:
    preferred_id: strawberry.ID
    other_id: strawberry.ID


# --- Change Set items ------------------------------------------------------


@strawberry.input(
    one_of=True, description="One change a Change Set proposes: exactly one field."
)
class ChangeSetItemInput:
    """One field per domain item kind, named after the kind."""

    add_screening_commitment: ScreeningInput | None = strawberry.UNSET
    release_screening_commitment: ScreeningInput | None = strawberry.UNSET
    add_film_commitment: ProgrammeEntryInput | None = strawberry.UNSET
    release_film_commitment: ProgrammeEntryInput | None = strawberry.UNSET
    add_excluded_screening: ScreeningInput | None = strawberry.UNSET
    remove_excluded_screening: ScreeningInput | None = strawberry.UNSET
    add_excluded_programme_entry: ProgrammeEntryInput | None = strawberry.UNSET
    remove_excluded_programme_entry: ProgrammeEntryInput | None = strawberry.UNSET
    set_programme_entry_weight: SetProgrammeEntryWeightInput | None = strawberry.UNSET
    set_screening_weight: SetScreeningWeightInput | None = strawberry.UNSET
    set_year_weight: SetYearWeightInput | None = strawberry.UNSET
    set_buffer: SetBufferInput | None = strawberry.UNSET
    set_days: SetDaysInput | None = strawberry.UNSET
    set_event_weight: SetEventWeightInput | None = strawberry.UNSET
    set_attend_events: SetAttendEventsInput | None = strawberry.UNSET
    set_transport_mode: SetTransportModeInput | None = strawberry.UNSET
    set_comparison_weight: SetComparisonWeightInput | None = strawberry.UNSET
    record_comparison: RecordComparisonInput | None = strawberry.UNSET


@strawberry.input
class CreateDraftInput:
    festival_id: strawberry.ID
    change_set: list[ChangeSetItemInput] = strawberry.field(default_factory=list)


class _Ids:
    """Decodes one item's ids, noting each that is not of its expected type."""

    def __init__(self) -> None:
        self.unknown: list[str] = []
        """A description of each id that did not decode."""

    def __call__(self, field: str, global_id: strawberry.ID, type_name: str) -> str:
        """The domain id; "" if it did not decode (the item is then dropped)."""
        domain_id = decode(global_id, type_name)
        if domain_id is None:
            self.unknown.append(f"{field} {global_id!r} is not a {type_name} id")
        return domain_id or ""


def _fields(value: Any, ids: _Ids) -> dict[str, Any]:
    """The domain fields of one item kind's input, ids decoded."""
    match value:
        case ScreeningInput():
            return {"screening_id": ids("screeningId", value.screening_id, "Screening")}
        case ProgrammeEntryInput():
            return {
                "programme_entry_id": ids(
                    "programmeEntryId", value.programme_entry_id, "ProgrammeEntry"
                )
            }
        case SetProgrammeEntryWeightInput():
            return {
                "programme_entry_id": ids(
                    "programmeEntryId", value.programme_entry_id, "ProgrammeEntry"
                ),
                "weight": _or_none(value.weight),
            }
        case SetScreeningWeightInput():
            return {
                "screening_id": ids("screeningId", value.screening_id, "Screening"),
                "weight": _or_none(value.weight),
            }
        case SetYearWeightInput():
            return {"year": value.year, "weight": _or_none(value.weight)}
        case SetBufferInput():
            venue_id = _or_none(value.venue_id)
            return {
                "venue_id": None
                if venue_id is None
                else ids("venueId", venue_id, "Venue"),
                "minutes": _or_none(value.minutes),
            }
        case SetDaysInput():
            days = _or_none(value.days)
            return {"days": None if days is None else tuple(days)}
        case SetEventWeightInput() | SetComparisonWeightInput():
            return {"weight": _or_none(value.weight)}
        case SetAttendEventsInput():
            return {"attend": _or_none(value.attend)}
        case SetTransportModeInput():
            return {"mode": _or_none(value.mode)}
        case RecordComparisonInput():
            return {
                "preferred": ids("preferredId", value.preferred_id, "ProgrammeEntry"),
                "other": ids("otherId", value.other_id, "ProgrammeEntry"),
            }
        case _:
            raise TypeError(f"Not a Change Set item input: {value!r}")


_ITEMS: dict[str, type[cs.ChangeSetItem]] = {
    t.model_fields["kind"].default: t
    for t in (
        cs.AddScreeningCommitment,
        cs.ReleaseScreeningCommitment,
        cs.AddFilmCommitment,
        cs.ReleaseFilmCommitment,
        cs.AddExcludedScreening,
        cs.RemoveExcludedScreening,
        cs.AddExcludedProgrammeEntry,
        cs.RemoveExcludedProgrammeEntry,
        cs.SetProgrammeEntryWeight,
        cs.SetScreeningWeight,
        cs.SetYearWeight,
        cs.SetBuffer,
        cs.SetDays,
        cs.SetEventWeight,
        cs.SetAttendEvents,
        cs.SetTransportMode,
        cs.SetComparisonWeight,
        cs.RecordComparison,
    )
}
"""Each domain item class by its kind, which is also its input field's name."""


class _NotOneField(Exception):
    """An item input with no field set, or several (possible only from Python)."""


def _given(item: ChangeSetItemInput) -> tuple[str, Any]:
    """The one field set, as (kind, value)."""
    given = [
        (field.name, value)
        for field in dataclasses.fields(item)
        if (value := getattr(item, field.name)) is not None
        and value is not strawberry.UNSET
    ]
    if len(given) != 1:
        raise _NotOneField(f"exactly one field must be set, not {len(given)}")
    return given[0]


def _reason(error: pydantic.ValidationError) -> str:
    return "; ".join(e["msg"] for e in error.errors())


def _problem(code: cs.ProblemCode, index: int, message: str) -> cs.ChangeSetProblem:
    return cs.ChangeSetProblem(
        code=code, items=(index,), message=f"Item {index}: {message}"
    )


def to_change_set(items: list[ChangeSetItemInput]) -> cs.ChangeSet:
    """The domain Change Set, or `InvalidChangeSetError` with an UNKNOWN_ID
    problem per id that does not decode, and an INVALID_ITEM problem per other
    item that is not valid on its own."""
    converted: list[cs.ChangeSetItem] = []
    found: list[cs.ChangeSetProblem] = []
    for index, item in enumerate(items):
        try:
            kind, value = _given(item)
        except _NotOneField as e:
            found.append(_problem(cs.ProblemCode.INVALID_ITEM, index, str(e)))
            continue
        ids = _Ids()
        fields = _fields(value, ids)
        if ids.unknown:
            # Not validated: a check such as "compares two entries" would
            # run against ids that mean nothing.
            found.extend(
                _problem(cs.ProblemCode.UNKNOWN_ID, index, f"({kind}) {unknown}")
                for unknown in ids.unknown
            )
            continue
        try:
            converted.append(_ITEMS[kind].model_validate(fields))
        except pydantic.ValidationError as e:
            found.append(
                _problem(cs.ProblemCode.INVALID_ITEM, index, f"({kind}) {_reason(e)}")
            )
    if found:
        raise cs.InvalidChangeSetError(found)
    return cs.ChangeSet(items=tuple(converted))
