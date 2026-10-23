"""The planning repository ports over SQLAlchemy rows. Every write flushes
(see `repositories.py`)."""

import json

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...domain.change_sets import ChangeSet
from ...domain.drafts import Draft, DraftId, DraftStatus, Schedule, ScheduleId
from ...domain.festival import FestivalId
from ...domain.planning import PlanningInputs, Preferences, Ticket
from ...domain.planning_ports import ConflictError
from ...domain.programme import FilmId, ProgrammeEntryId, ScreeningId
from ...domain.solving import ScheduledScreening
from ...domain.users import User, UserId
from .tables import (
    PLANNING_TARGET_KINDS,
    DraftRow,
    DraftScreeningRow,
    PlanningInputsRow,
    PlanningTargetRow,
    ScheduleRow,
    ScheduleScreeningRow,
    SeenDismissalRow,
    SeenRow,
    TicketRow,
    UserRow,
)


class SqlAlchemyUserRepository:
    def __init__(self, session: Session):
        self._session = session

    def by_identity(self, issuer: str, subject: str) -> User | None:
        row = self._session.scalars(
            select(UserRow).where(UserRow.issuer == issuer, UserRow.subject == subject)
        ).one_or_none()
        return (
            None
            if row is None
            else User(id=UserId(row.id), issuer=row.issuer, subject=row.subject)
        )

    def save(self, user: User) -> None:
        row = self._session.get(UserRow, user.id) or UserRow(id=user.id)
        row.issuer, row.subject = user.issuer, user.subject
        self._session.add(row)
        _flush_or_conflict(self._session)


class SqlAlchemyPlanningRepository:
    def __init__(self, session: Session):
        self._session = session

    def inputs(self, user_id: UserId, festival_id: FestivalId) -> PlanningInputs:
        row = self._session.get(PlanningInputsRow, (user_id, festival_id))
        targets = self._session.scalars(
            select(PlanningTargetRow).where(
                PlanningTargetRow.user_id == user_id,
                PlanningTargetRow.festival_id == festival_id,
            )
        )
        sets: dict[str, set[str]] = {kind: set() for kind in PLANNING_TARGET_KINDS}
        for target in targets:
            sets[target.kind].add(target.target_id)
        return PlanningInputs(
            screening_commitments=frozenset(
                ScreeningId(i) for i in sets["screening_commitments"]
            ),
            film_commitments=frozenset(
                ProgrammeEntryId(i) for i in sets["film_commitments"]
            ),
            excluded_screenings=frozenset(
                ScreeningId(i) for i in sets["excluded_screenings"]
            ),
            excluded_programme_entries=frozenset(
                ProgrammeEntryId(i) for i in sets["excluded_programme_entries"]
            ),
            preferences=(
                Preferences.model_validate_json(row.preferences)
                if row
                else Preferences()
            ),
        )

    def save_inputs(
        self, user_id: UserId, festival_id: FestivalId, inputs: PlanningInputs
    ) -> None:
        row = self._session.get(
            PlanningInputsRow, (user_id, festival_id)
        ) or PlanningInputsRow(user_id=user_id, festival_id=festival_id)
        row.preferences = inputs.preferences.model_dump_json()
        self._session.add(row)
        self._session.execute(
            delete(PlanningTargetRow).where(
                PlanningTargetRow.user_id == user_id,
                PlanningTargetRow.festival_id == festival_id,
            )
        )
        self._session.add_all(
            PlanningTargetRow(
                user_id=user_id, festival_id=festival_id, kind=kind, target_id=i
            )
            for kind in PLANNING_TARGET_KINDS
            for i in sorted(getattr(inputs, kind))
        )
        _flush_or_conflict(self._session)

    def schedules(
        self, user_id: UserId, festival_id: FestivalId
    ) -> tuple[Schedule, ...]:
        rows = self._session.scalars(
            select(ScheduleRow)
            .where(
                ScheduleRow.user_id == user_id, ScheduleRow.festival_id == festival_id
            )
            .order_by(ScheduleRow.number)
        )
        return tuple(_schedule(row) for row in rows)

    def active_schedule(
        self, user_id: UserId, festival_id: FestivalId
    ) -> Schedule | None:
        row = self._session.scalars(
            select(ScheduleRow)
            .where(
                ScheduleRow.user_id == user_id, ScheduleRow.festival_id == festival_id
            )
            .order_by(ScheduleRow.number.desc())
            .limit(1)
        ).first()
        return None if row is None else _schedule(row)

    def active_schedules(self, user_id: UserId) -> tuple[Schedule, ...]:
        rows = self._session.scalars(
            select(ScheduleRow)
            .where(ScheduleRow.user_id == user_id)
            .order_by(ScheduleRow.festival_id, ScheduleRow.number)
        )
        latest: dict[str, ScheduleRow] = {}
        for row in rows:
            latest[row.festival_id] = row
        return tuple(_schedule(row) for row in latest.values())

    def save_schedule(self, schedule: Schedule) -> None:
        row = self._session.get(ScheduleRow, schedule.id) or ScheduleRow(id=schedule.id)
        row.user_id, row.festival_id = schedule.user_id, schedule.festival_id
        row.number, row.score = schedule.number, schedule.score
        row.change_set = schedule.change_set.model_dump_json()
        row.accepted_at = schedule.accepted_at
        kept = [s for s in row.screenings if s.screening_id in schedule.screening_ids]
        known = {s.screening_id for s in kept}
        row.screenings = kept + [
            ScheduleScreeningRow(screening_id=i)
            for i in sorted(schedule.screening_ids - known)
        ]
        self._session.add(row)
        _flush_or_conflict(self._session)

    def schedule(self, schedule_id: ScheduleId) -> Schedule | None:
        row = self._session.get(ScheduleRow, schedule_id)
        return None if row is None else _schedule(row)

    def draft(self, draft_id: DraftId, *, for_update: bool = False) -> Draft | None:
        row = self._session.get(DraftRow, draft_id, with_for_update=for_update)
        return None if row is None else _draft(row)

    def drafts(self, user_id: UserId, festival_id: FestivalId) -> tuple[Draft, ...]:
        rows = self._session.scalars(
            select(DraftRow)
            .where(DraftRow.user_id == user_id, DraftRow.festival_id == festival_id)
            .order_by(DraftRow.created_at, DraftRow.id)
        )
        return tuple(_draft(row) for row in rows)

    def solving_drafts(self) -> tuple[Draft, ...]:
        rows = self._session.scalars(
            select(DraftRow)
            .where(DraftRow.status == DraftStatus.SOLVING.value)
            .order_by(DraftRow.created_at, DraftRow.id)
        )
        return tuple(_draft(row) for row in rows)

    def save_draft(self, draft: Draft) -> None:
        row = self._session.get(DraftRow, draft.id) or DraftRow(id=draft.id)
        row.user_id, row.festival_id = draft.user_id, draft.festival_id
        row.base_schedule_id = draft.base_schedule_id
        row.status, row.attempt = draft.status.value, draft.attempt
        row.change_set = draft.change_set.model_dump_json()
        row.score = draft.score
        row.reasons, row.notes = (
            json.dumps(list(draft.reasons)),
            json.dumps(list(draft.notes)),
        )
        row.created_at, row.solved_at = draft.created_at, draft.solved_at
        # Replace the scheduled rows in two flushes, so primary keys that stay
        # are deleted before they are inserted again.
        row.scheduled = []
        self._session.add(row)
        self._session.flush()
        row.scheduled = [
            DraftScreeningRow(
                screening_id=s.screening_id,
                position=position,
                arrival_time=s.arrival_time,
                weight=s.weight,
            )
            for position, s in enumerate(draft.scheduled)
        ]
        self._session.flush()

    def delete_draft(self, draft_id: DraftId) -> None:
        if (row := self._session.get(DraftRow, draft_id)) is not None:
            self._session.delete(row)
            self._session.flush()


def _flush_or_conflict(session: Session) -> None:
    """Flush; a unique key taken by a concurrent write is a `ConflictError`."""
    try:
        session.flush()
    except IntegrityError as e:
        raise ConflictError(str(e.orig)) from e


def _schedule(row: ScheduleRow) -> Schedule:
    return Schedule(
        id=ScheduleId(row.id),
        user_id=UserId(row.user_id),
        festival_id=FestivalId(row.festival_id),
        number=row.number,
        screening_ids=frozenset(ScreeningId(s.screening_id) for s in row.screenings),
        score=row.score,
        change_set=ChangeSet.model_validate_json(row.change_set),
        accepted_at=row.accepted_at,
    )


def _draft(row: DraftRow) -> Draft:
    return Draft(
        id=DraftId(row.id),
        user_id=UserId(row.user_id),
        festival_id=FestivalId(row.festival_id),
        change_set=ChangeSet.model_validate_json(row.change_set),
        base_schedule_id=ScheduleId(row.base_schedule_id)
        if row.base_schedule_id is not None
        else None,
        created_at=row.created_at,
        status=DraftStatus(row.status),
        attempt=row.attempt,
        scheduled=tuple(
            ScheduledScreening(
                screening_id=ScreeningId(s.screening_id),
                arrival_time=s.arrival_time,
                weight=s.weight,
            )
            for s in row.scheduled
        ),
        score=row.score,
        reasons=tuple(json.loads(row.reasons)),
        notes=tuple(json.loads(row.notes)),
        solved_at=row.solved_at,
    )


class SqlAlchemyTicketRepository:
    def __init__(self, session: Session):
        self._session = session

    def tickets(self, user_id: UserId) -> tuple[Ticket, ...]:
        rows = self._session.scalars(
            select(TicketRow)
            .where(TicketRow.user_id == user_id)
            .order_by(TicketRow.screening_id)
        )
        return tuple(
            Ticket(
                screening_id=ScreeningId(r.screening_id),
                exchangeable=r.exchangeable,
                refundable=r.refundable,
            )
            for r in rows
        )

    def save(self, user_id: UserId, ticket: Ticket) -> None:
        row = self._session.get(TicketRow, (user_id, ticket.screening_id)) or TicketRow(
            user_id=user_id, screening_id=ticket.screening_id
        )
        row.exchangeable, row.refundable = ticket.exchangeable, ticket.refundable
        self._session.add(row)
        self._session.flush()

    def delete(self, user_id: UserId, screening_id: ScreeningId) -> None:
        self._session.execute(
            delete(TicketRow).where(
                TicketRow.user_id == user_id, TicketRow.screening_id == screening_id
            )
        )
        self._session.flush()


class SqlAlchemySeenRepository:
    def __init__(self, session: Session):
        self._session = session

    def films(self, user_id: UserId) -> frozenset[FilmId]:
        return frozenset(
            FilmId(f)
            for f in self._session.scalars(
                select(SeenRow.film_id).where(SeenRow.user_id == user_id)
            )
        )

    def mark(self, user_id: UserId, film_id: FilmId) -> None:
        if self._session.get(SeenRow, (user_id, film_id)) is None:
            self._session.add(
                SeenRow(user_id=user_id, film_id=film_id, source="manual")
            )
            self._session.flush()

    def unmark(self, user_id: UserId, film_id: FilmId) -> None:
        self._session.execute(
            delete(SeenRow).where(
                SeenRow.user_id == user_id, SeenRow.film_id == film_id
            )
        )
        self._session.flush()

    def dismissals(self, user_id: UserId) -> frozenset[ScreeningId]:
        return frozenset(
            ScreeningId(s)
            for s in self._session.scalars(
                select(SeenDismissalRow.screening_id).where(
                    SeenDismissalRow.user_id == user_id
                )
            )
        )

    def dismiss(self, user_id: UserId, screening_id: ScreeningId) -> None:
        if self._session.get(SeenDismissalRow, (user_id, screening_id)) is None:
            self._session.add(
                SeenDismissalRow(user_id=user_id, screening_id=screening_id)
            )
            self._session.flush()

    def restore(self, user_id: UserId, screening_id: ScreeningId) -> None:
        self._session.execute(
            delete(SeenDismissalRow).where(
                SeenDismissalRow.user_id == user_id,
                SeenDismissalRow.screening_id == screening_id,
            )
        )
        self._session.flush()
