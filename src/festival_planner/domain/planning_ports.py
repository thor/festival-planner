"""Driven ports for planning."""

from typing import Protocol

from .drafts import Draft, DraftId, Schedule
from .festival import FestivalId
from .ingestion import UnitOfWork
from .planning import PlanningInputs, Ticket
from .programme import FilmId, ScreeningId
from .users import UserId, UserRepository


class PlanningRepository(Protocol):
    def inputs(self, user_id: UserId, festival_id: FestivalId) -> PlanningInputs:
        """The accepted inputs; empty `PlanningInputs()` if none yet."""
        ...

    def save_inputs(
        self, user_id: UserId, festival_id: FestivalId, inputs: PlanningInputs
    ) -> None: ...

    def active_schedule(
        self, user_id: UserId, festival_id: FestivalId
    ) -> Schedule | None: ...

    def active_schedules(self, user_id: UserId) -> tuple[Schedule, ...]:
        """The Active Schedule of each Festival the User has one for."""
        ...

    def schedules(
        self, user_id: UserId, festival_id: FestivalId
    ) -> tuple[Schedule, ...]:
        """The history, oldest first; the last is Active."""
        ...

    def save_schedule(self, schedule: Schedule) -> None: ...
    def draft(self, draft_id: DraftId) -> Draft | None: ...

    def drafts(self, user_id: UserId, festival_id: FestivalId) -> tuple[Draft, ...]:
        """Oldest first."""
        ...

    def solving_drafts(self) -> tuple[Draft, ...]:
        """Every User's Drafts with status SOLVING."""
        ...

    def save_draft(self, draft: Draft) -> None: ...
    def delete_draft(self, draft_id: DraftId) -> None: ...


class TicketRepository(Protocol):
    def tickets(self, user_id: UserId) -> tuple[Ticket, ...]: ...
    def save(self, user_id: UserId, ticket: Ticket) -> None: ...
    def delete(self, user_id: UserId, screening_id: ScreeningId) -> None: ...


class SeenRepository(Protocol):
    def films(self, user_id: UserId) -> frozenset[FilmId]:
        """Films marked Seen by hand."""
        ...

    def mark(self, user_id: UserId, film_id: FilmId) -> None: ...
    def unmark(self, user_id: UserId, film_id: FilmId) -> None: ...

    def dismissals(self, user_id: UserId) -> frozenset[ScreeningId]:
        """Active Schedule Screenings the User says they did not attend."""
        ...

    def dismiss(self, user_id: UserId, screening_id: ScreeningId) -> None: ...
    def restore(self, user_id: UserId, screening_id: ScreeningId) -> None: ...


class DraftSolvedNotifier(Protocol):
    """Port: told whenever a Draft finishes solving (later: a subscription)."""

    def draft_solved(self, draft: Draft) -> None: ...


class PlanningUnitOfWork(UnitOfWork, Protocol):
    @property
    def users(self) -> UserRepository: ...
    @property
    def planning(self) -> PlanningRepository: ...
    @property
    def tickets(self) -> TicketRepository: ...
    @property
    def seen(self) -> SeenRepository: ...
