"""In-memory implementations of the repository ports, for use-case tests."""

import copy
import itertools
from collections.abc import Callable, Iterable, Mapping
from types import TracebackType
from typing import Self

from festival_planner.domain.drafts import Draft, DraftStatus, Schedule
from festival_planner.domain.festival import Festival, FestivalSeries
from festival_planner.domain.planning import PlanningInputs, Ticket
from festival_planner.domain.programme import (
    Film,
    ProgrammeEntry,
    Screening,
    Venue,
    title_key,
)
from festival_planner.domain.travel import Route
from festival_planner.domain.users import User


def sequential_ids() -> Callable[[], str]:
    """A deterministic `new_id`: "id-1", "id-2", ..."""
    counter = itertools.count(1)
    return lambda: f"id-{next(counter)}"


class _State:
    def __init__(self) -> None:
        self.series: dict[str, FestivalSeries] = {}
        self.festivals: dict[str, Festival] = {}
        self.venues: dict[str, Venue] = {}
        self.routes: list[Route] = []
        self.films: dict[str, Film] = {}
        self.entries: dict[str, tuple[str, str, ProgrammeEntry]] = {}
        """entry id -> (festival id, source key, entry)"""
        self.screenings: dict[str, Screening] = {}
        self.users: dict[str, User] = {}
        self.inputs: dict[tuple[str, str], PlanningInputs] = {}
        self.schedules: dict[str, Schedule] = {}
        self.drafts: dict[str, Draft] = {}
        self.tickets: dict[tuple[str, str], Ticket] = {}
        self.seen: set[tuple[str, str]] = set()
        self.dismissals: set[tuple[str, str]] = set()


class InMemoryUnitOfWork:
    """Works on a copy of `stored`; `commit()` makes the copy the stored state."""

    def __init__(self) -> None:
        self.stored = _State()
        self.committed = False

    def __enter__(self) -> Self:
        self._work = copy.deepcopy(self.stored)
        self.festivals = _Festivals(self._work)
        self.venues = _Venues(self._work)
        self.routes = _Routes(self._work)
        self.films = _Films(self._work)
        self.programme = _Programme(self._work)
        self.users = _Users(self._work)
        self.planning = _Planning(self._work)
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


class _Festivals:
    def __init__(self, state: _State) -> None:
        self.s = state

    def by_id(self, festival_id: str) -> Festival | None:
        return self.s.festivals.get(festival_id)

    def by_slug(self, slug: str) -> Festival | None:
        return next((f for f in self.s.festivals.values() if f.slug == slug), None)

    def save(self, festival: Festival) -> None:
        self.s.festivals[festival.id] = festival

    def series_by_slug(self, slug: str) -> FestivalSeries | None:
        return next((x for x in self.s.series.values() if x.slug == slug), None)

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

    def by_id(self, film_id: str) -> Film | None:
        return self.s.films.get(film_id)

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

    def entries(self, festival_id: str) -> Mapping[str, ProgrammeEntry]:
        return {key: e for fid, key, e in self.s.entries.values() if fid == festival_id}

    def save_entry(
        self, festival_id: str, source_key: str, entry: ProgrammeEntry
    ) -> None:
        self.s.entries[entry.id] = (festival_id, source_key, entry)

    def screenings(self, festival_id: str) -> tuple[Screening, ...]:
        ids = {e.id for fid, _, e in self.s.entries.values() if fid == festival_id}
        return tuple(
            s for s in self.s.screenings.values() if s.programme_entry_id in ids
        )

    def save_screening(self, screening: Screening) -> None:
        self.s.screenings[screening.id] = screening

    def screenings_by_id(self, ids: Iterable[str]) -> tuple[Screening, ...]:
        return tuple(
            self.s.screenings[i] for i in sorted(set(ids)) if i in self.s.screenings
        )

    def entries_by_id(self, ids: Iterable[str]) -> tuple[ProgrammeEntry, ...]:
        return tuple(
            self.s.entries[i][2] for i in sorted(set(ids)) if i in self.s.entries
        )


class _Users:
    def __init__(self, state: _State) -> None:
        self.s = state

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
        self.s.users[user.id] = user


class _Planning:
    def __init__(self, state: _State) -> None:
        self.s = state

    def inputs(self, user_id: str, festival_id: str) -> PlanningInputs:
        return self.s.inputs.get((user_id, festival_id), PlanningInputs())

    def save_inputs(
        self, user_id: str, festival_id: str, inputs: PlanningInputs
    ) -> None:
        self.s.inputs[user_id, festival_id] = inputs

    def schedules(self, user_id: str, festival_id: str) -> tuple[Schedule, ...]:
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

    def active_schedule(self, user_id: str, festival_id: str) -> Schedule | None:
        history = self.schedules(user_id, festival_id)
        return history[-1] if history else None

    def active_schedules(self, user_id: str) -> tuple[Schedule, ...]:
        festivals = sorted(
            {s.festival_id for s in self.s.schedules.values() if s.user_id == user_id}
        )
        return tuple(
            active for f in festivals if (active := self.active_schedule(user_id, f))
        )

    def save_schedule(self, schedule: Schedule) -> None:
        self.s.schedules[schedule.id] = schedule

    def draft(self, draft_id: str) -> Draft | None:
        return self.s.drafts.get(draft_id)

    def drafts(self, user_id: str, festival_id: str) -> tuple[Draft, ...]:
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

    def delete_draft(self, draft_id: str) -> None:
        self.s.drafts.pop(draft_id, None)


class _Tickets:
    def __init__(self, state: _State) -> None:
        self.s = state

    def tickets(self, user_id: str) -> tuple[Ticket, ...]:
        return tuple(t for (u, _), t in sorted(self.s.tickets.items()) if u == user_id)

    def save(self, user_id: str, ticket: Ticket) -> None:
        self.s.tickets[user_id, ticket.screening_id] = ticket

    def delete(self, user_id: str, screening_id: str) -> None:
        self.s.tickets.pop((user_id, screening_id), None)


class _Seen:
    def __init__(self, state: _State) -> None:
        self.s = state

    def films(self, user_id: str) -> frozenset[str]:
        return frozenset(f for u, f in self.s.seen if u == user_id)

    def mark(self, user_id: str, film_id: str) -> None:
        self.s.seen.add((user_id, film_id))

    def unmark(self, user_id: str, film_id: str) -> None:
        self.s.seen.discard((user_id, film_id))

    def dismissals(self, user_id: str) -> frozenset[str]:
        return frozenset(s for u, s in self.s.dismissals if u == user_id)

    def dismiss(self, user_id: str, screening_id: str) -> None:
        self.s.dismissals.add((user_id, screening_id))

    def restore(self, user_id: str, screening_id: str) -> None:
        self.s.dismissals.discard((user_id, screening_id))
