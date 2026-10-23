"""Planning use-cases: Drafts, accepting, Tickets and Seen."""

import datetime
import functools
import logging
from collections.abc import Callable

from .change_sets import ChangeSet, ProgrammeIndex, apply, check, rebase
from .drafts import Draft, DraftId, DraftStatus, Schedule
from .festival import Festival, FestivalId
from .ingestion import new_id as _new_id
from .insights import (
    ComparisonSuggestion,
    DraftDiff,
    Flag,
    diff,
    flags,
    inferred_seen,
    suggest_comparisons,
)
from .jobs import Job, JobRunner
from .planning import Ticket
from .planning_ports import ConflictError, DraftSolvedNotifier, PlanningUnitOfWork
from .programme import FilmId, ScreeningId
from .solving import ScheduleSolver, SolveRequest, SolveResult, SolveStatus
from .travel import RouteTable
from .users import UserId
from .values import Value

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime.datetime]


class PlanningError(Exception):
    """A planning request cannot be carried out."""


class NotFoundError(PlanningError):
    pass


class DraftNotAcceptableError(PlanningError):
    pass


class DraftStillSolvingError(PlanningError):
    pass


class DraftView(Value):
    draft: Draft
    stale: bool
    diff: DraftDiff | None = None
    """For READY Drafts: the Draft against the current Active Schedule."""


class Planner:
    def __init__(
        self,
        unit_of_work: Callable[[], PlanningUnitOfWork],
        solver: ScheduleSolver,
        jobs: JobRunner,
        notifier: DraftSolvedNotifier,
        *,
        clock: Clock,
        new_id: Callable[[], str] = _new_id,
        wait_seconds: float = 2.0,
        time_limit_seconds: float = 30.0,
    ):
        self._uow = unit_of_work
        self._solver = solver
        self._jobs = jobs
        self._notifier = notifier
        self._clock = clock
        self._new_id = new_id
        self._wait_seconds = wait_seconds
        self._time_limit_seconds = time_limit_seconds

    # --- Drafts ------------------------------------------------------------

    def create_draft(
        self,
        user_id: UserId,
        festival_slug: str,
        change_set: ChangeSet | None = None,
    ) -> DraftView:
        change_set = change_set or ChangeSet()
        with self._uow() as uow:
            festival = _festival(uow, festival_slug)
            # The Active Schedule before the inputs: a sibling accepted between
            # the two reads then leaves this Draft Stale, which is safe.
            active = uow.planning.active_schedule(user_id, festival.id)
            check(
                change_set,
                uow.planning.inputs(user_id, festival.id),
                _programme_index(uow, festival.id),
            )
            draft = Draft(
                id=self._new_id(),
                user_id=user_id,
                festival_id=festival.id,
                change_set=change_set,
                base_schedule_id=active.id if active else None,
                created_at=self._clock(),
            )
            uow.planning.save_draft(draft)
            uow.commit()
        self._start(draft).wait(self._wait_seconds)
        return self.draft(user_id, draft.id)

    def resolve(self, user_id: UserId, draft_id: DraftId) -> DraftView:
        """Solve again against the current Active Schedule and inputs."""
        with self._uow() as uow:
            draft = _owned_draft(uow, user_id, draft_id, for_update=True)
            if draft.status is DraftStatus.SOLVING:
                raise DraftStillSolvingError(f"Draft {draft_id!r} is still solving")
            # The Active Schedule before the inputs, as in `create_draft`.
            active = uow.planning.active_schedule(user_id, draft.festival_id)
            change_set, notes = rebase(
                draft.change_set,
                uow.planning.inputs(user_id, draft.festival_id),
                _programme_index(uow, draft.festival_id),
            )
            draft = draft.model_copy(
                update={
                    "change_set": change_set,
                    "notes": notes,
                    "base_schedule_id": active.id if active else None,
                    "status": DraftStatus.SOLVING,
                    "attempt": draft.attempt + 1,
                    "scheduled": (),
                    "score": 0.0,
                    "reasons": (),
                    "solved_at": None,
                }
            )
            uow.planning.save_draft(draft)
            uow.commit()
        self._start(draft).wait(self._wait_seconds)
        return self.draft(user_id, draft.id)

    def accept(self, user_id: UserId, draft_id: DraftId) -> Schedule:
        """Apply the Change Set and make the Draft's Schedule Active, atomically."""
        with self._uow() as uow:
            draft = _owned_draft(uow, user_id, draft_id, for_update=True)
            if draft.status is not DraftStatus.READY:
                raise DraftNotAcceptableError(
                    f"Draft {draft_id!r} is {draft.status}, not READY"
                )
            active = uow.planning.active_schedule(user_id, draft.festival_id)
            if draft.is_stale(active):
                raise DraftNotAcceptableError(
                    f"Draft {draft_id!r} is Stale; re-solve it first"
                )
            inputs = uow.planning.inputs(user_id, draft.festival_id)
            schedule = Schedule(
                id=self._new_id(),
                user_id=user_id,
                festival_id=draft.festival_id,
                # The number follows the Active Schedule this Draft is based
                # on. Its uniqueness per (User, Festival), not the Draft lock,
                # serialises accepting: of two siblings, the second conflicts.
                number=(active.number if active else 0) + 1,
                screening_ids=draft.screening_ids,
                score=draft.score,
                change_set=draft.change_set,
                accepted_at=self._clock(),
            )
            try:
                # The Schedule first, so the number is the first contended
                # write; the inputs' own keys can conflict too, e.g. on a
                # (User, Festival)'s first accept.
                uow.planning.save_schedule(schedule)
                uow.planning.save_inputs(
                    user_id, draft.festival_id, apply(draft.change_set, inputs)
                )
            except ConflictError as e:
                raise DraftNotAcceptableError(
                    "another Draft was accepted meanwhile; re-solve this one"
                ) from e
            uow.planning.delete_draft(draft.id)
            uow.commit()
        return schedule

    def discard(self, user_id: UserId, draft_id: DraftId) -> None:
        with self._uow() as uow:
            _owned_draft(uow, user_id, draft_id, for_update=True)
            uow.planning.delete_draft(draft_id)
            uow.commit()

    def draft(self, user_id: UserId, draft_id: DraftId) -> DraftView:
        with self._uow() as uow:
            return self._view(uow, _owned_draft(uow, user_id, draft_id))

    def drafts(self, user_id: UserId, festival_slug: str) -> tuple[DraftView, ...]:
        with self._uow() as uow:
            festival = _festival(uow, festival_slug)
            return tuple(
                self._view(uow, d) for d in uow.planning.drafts(user_id, festival.id)
            )

    def solve_request(self, user_id: UserId, draft_id: DraftId) -> SolveRequest:
        """The request a Draft is solved from, e.g. to replay it in the CLI."""
        with self._uow() as uow:
            draft = _owned_draft(uow, user_id, draft_id)
            return self._request(uow, user_id, draft.festival_id, draft.change_set)

    def resume_solving(self) -> int:
        """Resubmit Drafts left SOLVING, e.g. by a restart."""
        with self._uow() as uow:
            drafts = uow.planning.solving_drafts()
        for draft in drafts:
            self._start(draft)
        return len(drafts)

    # --- Schedules and read-side -------------------------------------------

    def active_schedule(self, user_id: UserId, festival_slug: str) -> Schedule | None:
        with self._uow() as uow:
            festival = _festival(uow, festival_slug)
            return uow.planning.active_schedule(user_id, festival.id)

    def schedules(self, user_id: UserId, festival_slug: str) -> tuple[Schedule, ...]:
        with self._uow() as uow:
            festival = _festival(uow, festival_slug)
            return uow.planning.schedules(user_id, festival.id)

    def flags(self, user_id: UserId, festival_slug: str) -> tuple[Flag, ...]:
        with self._uow() as uow:
            festival = _festival(uow, festival_slug)
            active = uow.planning.active_schedule(user_id, festival.id)
            return flags(
                uow.programme.screenings(festival.id),
                uow.planning.inputs(user_id, festival.id),
                uow.tickets.tickets(user_id),
                active.screening_ids if active else frozenset(),
            )

    def suggest_comparisons(
        self, user_id: UserId, festival_slug: str, limit: int = 10
    ) -> tuple[ComparisonSuggestion, ...]:
        """From the latest READY Draft, else the Active Schedule."""
        with self._uow() as uow:
            festival = _festival(uow, festival_slug)
            ready = [
                d
                for d in uow.planning.drafts(user_id, festival.id)
                if d.status is DraftStatus.READY
            ]
            if ready:
                latest = max(ready, key=lambda d: (d.solved_at, d.id))
                change_set, scheduled = latest.change_set, latest.screening_ids
            elif active := uow.planning.active_schedule(user_id, festival.id):
                change_set, scheduled = ChangeSet(), active.screening_ids
            else:
                return ()
            request = self._request(uow, user_id, festival.id, change_set)
            return suggest_comparisons(request, scheduled, limit)

    # --- Tickets and Seen --------------------------------------------------

    def record_ticket(self, user_id: UserId, ticket: Ticket) -> None:
        with self._uow() as uow:
            _screening_exists(uow, ticket.screening_id)
            uow.tickets.save(user_id, ticket)
            uow.commit()

    def remove_ticket(self, user_id: UserId, screening_id: ScreeningId) -> None:
        with self._uow() as uow:
            uow.tickets.delete(user_id, screening_id)
            uow.commit()

    def tickets(self, user_id: UserId) -> tuple[Ticket, ...]:
        with self._uow() as uow:
            return uow.tickets.tickets(user_id)

    def mark_seen(self, user_id: UserId, film_id: FilmId) -> None:
        with self._uow() as uow:
            if uow.films.by_id(film_id) is None:
                raise NotFoundError(f"No film {film_id!r}")
            uow.seen.mark(user_id, film_id)
            uow.commit()

    def unmark_seen(self, user_id: UserId, film_id: FilmId) -> None:
        with self._uow() as uow:
            uow.seen.unmark(user_id, film_id)
            uow.commit()

    def dismiss_inferred_seen(self, user_id: UserId, screening_id: ScreeningId) -> None:
        """ "I didn't go": the Screening no longer makes its Film Seen."""
        with self._uow() as uow:
            _screening_exists(uow, screening_id)
            uow.seen.dismiss(user_id, screening_id)
            uow.commit()

    def restore_inferred_seen(self, user_id: UserId, screening_id: ScreeningId) -> None:
        with self._uow() as uow:
            uow.seen.restore(user_id, screening_id)
            uow.commit()

    def seen_films(self, user_id: UserId) -> frozenset[FilmId]:
        with self._uow() as uow:
            return self._seen_films(uow, user_id)

    # --- Internals ---------------------------------------------------------

    def _start(self, draft: Draft) -> Job:
        return self._jobs.submit(
            functools.partial(self._solve, draft.id, draft.attempt)
        )

    def _solve(self, draft_id: DraftId, attempt: int) -> None:
        """The solve job; never raises, a broken job leaves the Draft FAILED."""
        try:
            self._solve_attempt(draft_id, attempt)
        except Exception as e:
            logger.exception("Solve job for draft %s broke", draft_id)
            try:
                self._finish(
                    draft_id,
                    attempt,
                    DraftStatus.FAILED,
                    SolveResult(status=SolveStatus.UNKNOWN),
                    (f"The solve job failed: {e}",),
                )
            except Exception:
                logger.exception("Could not mark draft %s as failed", draft_id)

    def _solve_attempt(self, draft_id: DraftId, attempt: int) -> None:
        """Read, solve outside any transaction, write."""
        with self._uow() as uow:
            draft = uow.planning.draft(draft_id)
            if draft is None or draft.attempt != attempt:
                return
            request = self._request(
                uow, draft.user_id, draft.festival_id, draft.change_set
            )
        try:
            result = self._solver.solve(request)
        except Exception as e:
            logger.exception("Solving draft %s failed", draft_id)
            result = SolveResult(
                status=SolveStatus.UNKNOWN, reasons=(f"The solver failed: {e}",)
            )
        if result.is_solved:
            status = DraftStatus.READY
        elif result.status is SolveStatus.INFEASIBLE:
            status = DraftStatus.INFEASIBLE
        else:
            status = DraftStatus.FAILED
        reasons = result.reasons or (
            ("No Schedule found within the time limit",)
            if status is DraftStatus.FAILED
            else ()
        )
        self._finish(draft_id, attempt, status, result, reasons)

    def _finish(
        self,
        draft_id: DraftId,
        attempt: int,
        status: DraftStatus,
        result: SolveResult,
        reasons: tuple[str, ...],
    ) -> None:
        """Write the outcome unless the Draft was discarded or re-solved meanwhile."""
        with self._uow() as uow:
            current = uow.planning.draft(draft_id, for_update=True)
            if current is None or current.attempt != attempt:
                return
            solved = current.model_copy(
                update={
                    "status": status,
                    "scheduled": result.scheduled,
                    "score": result.objective,
                    "reasons": reasons,
                    "solved_at": self._clock(),
                }
            )
            uow.planning.save_draft(solved)
            uow.commit()
        try:
            self._notifier.draft_solved(solved)
        except Exception:
            # Best effort: the outcome is committed and stays as it is.
            logger.exception("Notifying that draft %s was solved failed", draft_id)

    def _view(self, uow: PlanningUnitOfWork, draft: Draft) -> DraftView:
        active = uow.planning.active_schedule(draft.user_id, draft.festival_id)
        draft_diff = None
        if draft.status is DraftStatus.READY:
            request = self._request(
                uow, draft.user_id, draft.festival_id, draft.change_set
            )
            draft_diff = diff(
                request, draft.screening_ids, uow.tickets.tickets(draft.user_id)
            )
        return DraftView(draft=draft, stale=draft.is_stale(active), diff=draft_diff)

    def _request(
        self,
        uow: PlanningUnitOfWork,
        user_id: UserId,
        festival_id: FestivalId,
        change_set: ChangeSet,
    ) -> SolveRequest:
        """Build the SolveRequest for `change_set` on the User's current inputs."""
        festival = uow.festivals.by_id(festival_id)
        if festival is None:
            raise NotFoundError(f"No festival {festival_id!r}")
        inputs = apply(change_set, uow.planning.inputs(user_id, festival_id))
        active = uow.planning.active_schedule(user_id, festival_id)
        return SolveRequest(
            venues=uow.venues.all(),
            programme_entries=tuple(uow.programme.entries(festival_id).values()),
            screenings=uow.programme.screenings(festival_id),
            time_zone=festival.time_zone,
            routes=RouteTable(routes=uow.routes.all()),
            preferences=inputs.preferences,
            screening_commitments=inputs.screening_commitments,
            film_commitments=inputs.film_commitments,
            excluded_screenings=inputs.excluded_screenings,
            excluded_programme_entries=inputs.excluded_programme_entries,
            seen_films=self._seen_films(uow, user_id),
            active_schedule=active.screening_ids if active else frozenset(),
            now=self._clock(),
            time_limit_seconds=self._time_limit_seconds,
        )

    def _seen_films(
        self, uow: PlanningUnitOfWork, user_id: UserId
    ) -> frozenset[FilmId]:
        scheduled = frozenset().union(
            *(s.screening_ids for s in uow.planning.active_schedules(user_id))
        )
        screenings = uow.programme.screenings_by_id(scheduled)
        entries = {
            e.id: e
            for e in uow.programme.entries_by_id(
                {s.programme_entry_id for s in screenings}
            )
        }
        return uow.seen.films(user_id) | inferred_seen(
            screenings, entries, uow.seen.dismissals(user_id), self._clock()
        )


def _festival(uow: PlanningUnitOfWork, slug: str) -> Festival:
    if (festival := uow.festivals.by_slug(slug)) is None:
        raise NotFoundError(f"No festival {slug!r}")
    return festival


def _owned_draft(
    uow: PlanningUnitOfWork,
    user_id: UserId,
    draft_id: DraftId,
    *,
    for_update: bool = False,
) -> Draft:
    draft = uow.planning.draft(draft_id, for_update=for_update)
    if draft is None or draft.user_id != user_id:
        raise NotFoundError(f"No draft {draft_id!r}")
    return draft


def _screening_exists(uow: PlanningUnitOfWork, screening_id: ScreeningId) -> None:
    if not uow.programme.screenings_by_id([screening_id]):
        raise NotFoundError(f"No screening {screening_id!r}")


def _programme_index(
    uow: PlanningUnitOfWork, festival_id: FestivalId
) -> ProgrammeIndex:
    return ProgrammeIndex.of(
        uow.programme.entries(festival_id).values(),
        uow.programme.screenings(festival_id),
        uow.venues.all(),
    )
