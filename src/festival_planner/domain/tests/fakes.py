"""In-memory implementations of the repository ports, for use-case tests."""

import copy
import datetime
import itertools
from collections.abc import Callable, Iterable, Mapping
from types import TracebackType
from typing import Self

from festival_planner.domain.drafts import (
    Draft,
    DraftId,
    DraftStatus,
    Schedule,
    ScheduleId,
)
from festival_planner.domain.festival import (
    Festival,
    FestivalId,
    FestivalSeries,
    FestivalSeriesId,
)
from festival_planner.domain.planning import PlanningInputs, Ticket
from festival_planner.domain.planning_ports import ConflictError
from festival_planner.domain.programme import (
    Film,
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
    title_key,
)
from festival_planner.domain.solving import (
    ScheduledScreening,
    SolveRequest,
    SolveResult,
    SolveStatus,
    formulate,
)
from festival_planner.domain.travel import Route
from festival_planner.domain.users import User, UserId


def sequential_ids() -> Callable[[], str]:
    """A deterministic `new_id`: "id-1", "id-2", ..."""
    counter = itertools.count(1)
    return lambda: f"id-{next(counter)}"


class _State:
    def __init__(self) -> None:
        self.series: dict[FestivalSeriesId, FestivalSeries] = {}
        self.festivals: dict[FestivalId, Festival] = {}
        self.venues: dict[VenueId, Venue] = {}
        self.routes: list[Route] = []
        self.films: dict[FilmId, Film] = {}
        self.entries: dict[
            ProgrammeEntryId, tuple[FestivalId, str, ProgrammeEntry]
        ] = {}
        """entry id -> (festival id, source key, entry)"""
        self.screenings: dict[ScreeningId, Screening] = {}
        self.users: dict[UserId, User] = {}
        self.inputs: dict[tuple[UserId, FestivalId], PlanningInputs] = {}
        self.schedules: dict[ScheduleId, Schedule] = {}
        self.drafts: dict[DraftId, Draft] = {}
        self.tickets: dict[tuple[UserId, ScreeningId], Ticket] = {}
        self.seen: set[tuple[UserId, FilmId]] = set()
        self.dismissals: set[tuple[UserId, ScreeningId]] = set()


Hook = Callable[[_State], None]


class InMemoryUnitOfWork:
    """Works on a copy of `stored`; `commit()` makes the copy the stored state.

    `hooks` maps a repository method ("planning.inputs", "users.save", ...) to
    a function run once, on the working state, just before that method's next
    call; see `concurrently`."""

    def __init__(self) -> None:
        self.stored = _State()
        self.committed = False
        self.hooks: dict[str, Hook] = {}

    def _fire(self, name: str) -> None:
        if (hook := self.hooks.pop(name, None)) is not None:
            hook(self._work)

    def __enter__(self) -> Self:
        self._work = copy.deepcopy(self.stored)
        self.festivals = _Festivals(self._work)
        self.venues = _Venues(self._work)
        self.routes = _Routes(self._work)
        self.films = _Films(self._work)
        self.programme = _Programme(self._work)
        self.users = _Users(self._work, self._fire)
        self.planning = _Planning(self._work, self._fire)
        self.tickets = _Tickets(self._work)
        self.seen = _Seen(self._work)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del self._work

    def commit(self) -> None:
        self.stored = copy.deepcopy(self._work)
        self.committed = True


def concurrently(uow: InMemoryUnitOfWork, change: Hook) -> Hook:
    """A hook for `uow.hooks`: another unit of work commits `change`, visible
    to the running one too (as under read-committed isolation)."""

    def hook(work: _State) -> None:
        change(uow.stored)
        change(work)

    return hook


class _Festivals:
    def __init__(self, state: _State) -> None:
        self.s = state

    def by_id(self, festival_id: FestivalId) -> Festival | None:
        return self.s.festivals.get(festival_id)

    def by_slug(self, slug: str) -> Festival | None:
        return next((f for f in self.s.festivals.values() if f.slug == slug), None)

    def all(self) -> tuple[Festival, ...]:
        return tuple(self.s.festivals.values())

    def by_ids(self, ids: Iterable[FestivalId]) -> tuple[Festival, ...]:
        wanted = frozenset(ids)
        return tuple(f for f in self.s.festivals.values() if f.id in wanted)

    def save(self, festival: Festival) -> None:
        self.s.festivals[festival.id] = festival

    def series_by_slug(self, slug: str) -> FestivalSeries | None:
        return next((x for x in self.s.series.values() if x.slug == slug), None)

    def series_by_ids(
        self, ids: Iterable[FestivalSeriesId]
    ) -> tuple[FestivalSeries, ...]:
        wanted = frozenset(ids)
        return tuple(s for s in self.s.series.values() if s.id in wanted)

    def save_series(self, series: FestivalSeries) -> None:
        self.s.series[series.id] = series


class _Venues:
    def __init__(self, state: _State) -> None:
        self.s = state

    def all(self) -> tuple[Venue, ...]:
        return tuple(self.s.venues.values())

    def save(self, venue: Venue) -> None:
        self.s.venues[venue.id] = venue


class _Routes:
    def __init__(self, state: _State) -> None:
        self.s = state

    def all(self) -> tuple[Route, ...]:
        return tuple(self.s.routes)

    def replace_all(self, routes: Iterable[Route]) -> None:
        self.s.routes = list(routes)


class _Films:
    def __init__(self, state: _State) -> None:
        self.s = state

    def by_id(self, film_id: FilmId) -> Film | None:
        return self.s.films.get(film_id)

    def by_ids(self, ids: Iterable[FilmId]) -> tuple[Film, ...]:
        wanted = frozenset(ids)
        return tuple(f for f in self.s.films.values() if f.id in wanted)

    def find(self, title: str, year: int) -> Film | None:
        return next(
            (
                f
                for f in self.s.films.values()
                if title_key(f.title) == title_key(title) and f.year == year
            ),
            None,
        )

    def save(self, film: Film) -> None:
        self.s.films[film.id] = film


class _Programme:
    def __init__(self, state: _State) -> None:
        self.s = state

    def entries(self, festival_id: FestivalId) -> Mapping[str, ProgrammeEntry]:
        return {key: e for fid, key, e in self.s.entries.values() if fid == festival_id}

    def save_entry(
        self, festival_id: FestivalId, source_key: str, entry: ProgrammeEntry
    ) -> None:
        self.s.entries[entry.id] = (festival_id, source_key, entry)

    def screenings(self, festival_id: FestivalId) -> tuple[Screening, ...]:
        ids = {e.id for fid, _, e in self.s.entries.values() if fid == festival_id}
        return tuple(
            s for s in self.s.screenings.values() if s.programme_entry_id in ids
        )

    def save_screening(self, screening: Screening) -> None:
        self.s.screenings[screening.id] = screening

    def screenings_by_id(self, ids: Iterable[ScreeningId]) -> tuple[Screening, ...]:
        return tuple(
            self.s.screenings[i] for i in sorted(set(ids)) if i in self.s.screenings
        )

    def entries_by_id(
        self, ids: Iterable[ProgrammeEntryId]
    ) -> tuple[ProgrammeEntry, ...]:
        return tuple(
            self.s.entries[i][2] for i in sorted(set(ids)) if i in self.s.entries
        )

    def screenings_of_entries(
        self, ids: Iterable[ProgrammeEntryId]
    ) -> tuple[Screening, ...]:
        wanted = frozenset(ids)
        return tuple(
            s for s in self.s.screenings.values() if s.programme_entry_id in wanted
        )


class _Users:
    def __init__(self, state: _State, fire: Callable[[str], None]) -> None:
        self.s = state
        self._fire = fire

    def by_identity(self, issuer: str, subject: str) -> User | None:
        return next(
            (
                u
                for u in self.s.users.values()
                if (u.issuer, u.subject) == (issuer, subject)
            ),
            None,
        )

    def save(self, user: User) -> None:
        self._fire("users.save")
        if any(
            (u.issuer, u.subject) == (user.issuer, user.subject) and u.id != user.id
            for u in self.s.users.values()
        ):
            raise ConflictError(f"A User for {user.issuer}/{user.subject} exists")
        self.s.users[user.id] = user


class _Planning:
    def __init__(self, state: _State, fire: Callable[[str], None]) -> None:
        self.s = state
        self._fire = fire

    def inputs(self, user_id: UserId, festival_id: FestivalId) -> PlanningInputs:
        self._fire("planning.inputs")
        return self.s.inputs.get((user_id, festival_id), PlanningInputs())

    def save_inputs(
        self, user_id: UserId, festival_id: FestivalId, inputs: PlanningInputs
    ) -> None:
        self.s.inputs[user_id, festival_id] = inputs

    def schedules(
        self, user_id: UserId, festival_id: FestivalId
    ) -> tuple[Schedule, ...]:
        return tuple(
            sorted(
                (
                    s
                    for s in self.s.schedules.values()
                    if (s.user_id, s.festival_id) == (user_id, festival_id)
                ),
                key=lambda s: s.number,
            )
        )

    def active_schedule(
        self, user_id: UserId, festival_id: FestivalId
    ) -> Schedule | None:
        history = self.schedules(user_id, festival_id)
        return history[-1] if history else None

    def active_schedules(self, user_id: UserId) -> tuple[Schedule, ...]:
        festivals = sorted(
            {s.festival_id for s in self.s.schedules.values() if s.user_id == user_id}
        )
        return tuple(
            active for f in festivals if (active := self.active_schedule(user_id, f))
        )

    def save_schedule(self, schedule: Schedule) -> None:
        key = (schedule.user_id, schedule.festival_id, schedule.number)
        if any(
            (s.user_id, s.festival_id, s.number) == key and s.id != schedule.id
            for s in self.s.schedules.values()
        ):
            raise ConflictError(f"Schedule number {schedule.number} exists")
        self.s.schedules[schedule.id] = schedule

    def schedule(self, schedule_id: ScheduleId) -> Schedule | None:
        return self.s.schedules.get(schedule_id)

    def draft(self, draft_id: DraftId, *, for_update: bool = False) -> Draft | None:
        return self.s.drafts.get(draft_id)

    def drafts(self, user_id: UserId, festival_id: FestivalId) -> tuple[Draft, ...]:
        return tuple(
            sorted(
                (
                    d
                    for d in self.s.drafts.values()
                    if (d.user_id, d.festival_id) == (user_id, festival_id)
                ),
                key=lambda d: (d.created_at, d.id),
            )
        )

    def solving_drafts(self) -> tuple[Draft, ...]:
        return tuple(
            d for d in self.s.drafts.values() if d.status is DraftStatus.SOLVING
        )

    def save_draft(self, draft: Draft) -> None:
        self.s.drafts[draft.id] = draft

    def delete_draft(self, draft_id: DraftId) -> None:
        self.s.drafts.pop(draft_id, None)


class _Tickets:
    def __init__(self, state: _State) -> None:
        self.s = state

    def tickets(self, user_id: UserId) -> tuple[Ticket, ...]:
        return tuple(t for (u, _), t in sorted(self.s.tickets.items()) if u == user_id)

    def save(self, user_id: UserId, ticket: Ticket) -> None:
        self.s.tickets[user_id, ticket.screening_id] = ticket

    def delete(self, user_id: UserId, screening_id: ScreeningId) -> None:
        self.s.tickets.pop((user_id, screening_id), None)


class _Seen:
    def __init__(self, state: _State) -> None:
        self.s = state

    def films(self, user_id: UserId) -> frozenset[FilmId]:
        return frozenset(f for u, f in self.s.seen if u == user_id)

    def mark(self, user_id: UserId, film_id: FilmId) -> None:
        self.s.seen.add((user_id, film_id))

    def unmark(self, user_id: UserId, film_id: FilmId) -> None:
        self.s.seen.discard((user_id, film_id))

    def dismissals(self, user_id: UserId) -> frozenset[ScreeningId]:
        return frozenset(s for u, s in self.s.dismissals if u == user_id)

    def dismiss(self, user_id: UserId, screening_id: ScreeningId) -> None:
        self.s.dismissals.add((user_id, screening_id))

    def restore(self, user_id: UserId, screening_id: ScreeningId) -> None:
        self.s.dismissals.discard((user_id, screening_id))


class GreedySolver:
    """A deterministic stand-in for CP-SAT: required Screenings first, then by
    weight (highest first) and id, skipping whatever conflicts."""

    def solve(self, request: SolveRequest) -> SolveResult:
        f = formulate(request)
        if f.unsatisfiable:
            return SolveResult(status=SolveStatus.INFEASIBLE, reasons=f.unsatisfiable)
        conflicts = set(f.conflicts) | {(b, a) for a, b in f.conflicts}
        groups = [*f.exactly_one, *f.at_most_one]
        chosen: list[ScreeningId] = []
        for s in sorted(
            f.candidates, key=lambda s: (s.id not in f.required, -f.weights[s.id], s.id)
        ):
            fits = all((s.id, c) not in conflicts for c in chosen) and not any(
                s.id in g and any(c in g for c in chosen) for g in groups
            )
            if fits:
                chosen.append(s.id)
            elif s.id in f.required:
                return SolveResult(
                    status=SolveStatus.INFEASIBLE, reasons=(f"{s.id} does not fit",)
                )
        if any(not g & set(chosen) for g in f.exactly_one):
            return SolveResult(
                status=SolveStatus.INFEASIBLE,
                reasons=("A Film Commitment does not fit",),
            )
        scheduled = tuple(
            ScheduledScreening(
                screening_id=s.id, arrival_time=s.start_time, weight=f.weights[s.id]
            )
            for s in sorted(f.candidates, key=lambda s: (s.start_time, s.id))
            if s.id in chosen
        )
        return SolveResult(
            status=SolveStatus.OPTIMAL,
            scheduled=scheduled,
            objective=sum(f.weights[i] for i in chosen),
        )


class FailingSolver:
    def solve(self, request: SolveRequest) -> SolveResult:
        raise RuntimeError("solver exploded")


class _Finished:
    def wait(self, timeout: float | None = None) -> bool:
        return True


class InlineJobRunner:
    def submit(self, work: Callable[[], None]) -> _Finished:
        work()
        return _Finished()


class _Pending:
    def __init__(self, runner: "DeferredJobRunner") -> None:
        self._runner = runner

    def wait(self, timeout: float | None = None) -> bool:
        return not self._runner.pending


class DeferredJobRunner:
    """Holds work until `run_all()`, like a busy background runner."""

    def __init__(self) -> None:
        self.pending: list[Callable[[], None]] = []

    def submit(self, work: Callable[[], None]) -> _Pending:
        self.pending.append(work)
        return _Pending(self)

    def run_all(self) -> None:
        while self.pending:
            self.pending.pop(0)()


class RecordingNotifier:
    def __init__(self) -> None:
        self.solved: list[Draft] = []

    def draft_solved(self, draft: Draft) -> None:
        self.solved.append(draft)


class TickingClock:
    """Each call is one minute after the previous one."""

    def __init__(self, start: datetime.datetime) -> None:
        self.now = start

    def __call__(self) -> datetime.datetime:
        self.now += datetime.timedelta(minutes=1)
        return self.now
