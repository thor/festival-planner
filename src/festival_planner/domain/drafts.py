"""Drafts and accepted Schedules."""

import enum
from typing import NewType

from pydantic import AwareDatetime

from .change_sets import ChangeSet
from .festival import FestivalId
from .programme import ScreeningId
from .solving import ScheduledScreening
from .users import UserId
from .values import Value

DraftId = NewType("DraftId", str)
ScheduleId = NewType("ScheduleId", str)


class DraftStatus(enum.StrEnum):
    SOLVING = "SOLVING"
    READY = "READY"
    INFEASIBLE = "INFEASIBLE"
    FAILED = "FAILED"
    """The solver crashed, or found no Schedule within the time limit."""


class Schedule(Value):
    """An accepted Schedule. The one with the highest `number` for a (User,
    Festival) is the Active Schedule; the others form the history."""

    id: ScheduleId
    user_id: UserId
    festival_id: FestivalId
    number: int
    screening_ids: frozenset[ScreeningId]
    score: float
    change_set: ChangeSet
    """The Change Set whose acceptance produced this Schedule."""
    accepted_at: AwareDatetime


class Draft(Value):
    """A proposed Schedule: a Change Set and the Schedule solved from it."""

    id: DraftId
    user_id: UserId
    festival_id: FestivalId
    change_set: ChangeSet
    base_schedule_id: ScheduleId | None
    """The Active Schedule when the Change Set was made or last re-solved."""
    created_at: AwareDatetime
    status: DraftStatus = DraftStatus.SOLVING
    attempt: int = 1
    """Increases on every re-solve, so results of an older solve are ignored."""
    scheduled: tuple[ScheduledScreening, ...] = ()
    score: float = 0.0
    reasons: tuple[str, ...] = ()
    """Why the Draft is INFEASIBLE or FAILED."""
    notes: tuple[str, ...] = ()
    """What re-solving changed in the Change Set."""
    solved_at: AwareDatetime | None = None

    @property
    def screening_ids(self) -> frozenset[ScreeningId]:
        return frozenset(s.screening_id for s in self.scheduled)

    def is_stale(self, active: Schedule | None) -> bool:
        """Whether the Active Schedule changed since this Draft was based on it."""
        return self.base_schedule_id != (active.id if active else None)
