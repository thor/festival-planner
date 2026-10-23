"""Change Sets: what a Draft proposes to change in a User's planning inputs."""

import datetime
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .programme import ProgrammeEntryId, ScreeningId, VenueId
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
    weight: float | None


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
