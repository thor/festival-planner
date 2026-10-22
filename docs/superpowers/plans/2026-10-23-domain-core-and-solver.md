# Domain Core and Solver Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a framework-free domain core (programme, travel, preferences, scheduling rules) behind a `ScheduleSolver` port, re-implement the CP-SAT solver as an adapter, and run the CLI's `solve` on a self-contained, JSON-exportable solve request.

**Architecture:** Hexagonal (ports and adapters). `festival_planner.domain` holds frozen dataclasses and pure functions; `formulate()` turns a `SolveRequest` into a `Formulation` (candidates, weights, required screenings, groups, conflicts) so all scheduling rules are testable without OR-Tools. Adapters under `festival_planner.adapters` implement the solver port (CP-SAT) and translate inputs (legacy YAML files, JSON solve requests). The Typer CLI is a driving adapter that renders domain values.

**Tech Stack:** Python 3.13, stdlib dataclasses, OR-Tools CP-SAT 9.15, Pydantic 2 (only in the JSON adapter, via `TypeAdapter`), Typer + Rich, pytest. Tooling via `mise` + `uv`; version control is **jj** (not git).

**Spec:** `docs/superpowers/specs/2026-10-23-graphql-backend-design.md` (roadmap step 1). Vocabulary: `GLOSSARY.md`. Decisions: `docs/adr/0001-hexagonal-architecture.md`.

## Global Constraints

- Nothing in `src/festival_planner/domain/` may import Strawberry, SQLAlchemy, OR-Tools, Pydantic, httpx or any other third-party library; stdlib only.
- Use glossary terms in code: Venue (not cinema), Screening, Programme Entry, Event, Route, Transport Mode, Preferences, Screening Commitment, Film Commitment, Excluded, Seen. The legacy `models.py` / YAML files keep their old names; only adapters translate.
- Default Transport Mode is `"walk+e-scooter"`.
- Routes are one-directional; a missing Route raises `MissingRouteError` in the domain. The legacy YAML adapter keeps the old behaviour (configured travel times work both ways; unconfigured pairs get 30 minutes).
- Domain value objects are `@dataclass(frozen=True)`; collections in them are tuples / frozensets / mappings, never mutated.
- Tests live next to the code in `tests/` sub-packages (existing convention, e.g. `scrapers/tests/`), each with an empty `__init__.py`.
- Run tests with `mise exec -- uv run pytest`; format new files with `mise exec -- uv run ruff format <paths>`. The repo has pre-existing ruff findings; don't fix unrelated ones.
- Commit with `jj commit -m "<message>"` (commits the whole working copy and starts a new empty change). Never use `git commit`. Do not push.
- Intentional behaviour changes vs. the old solver (call them out in review, don't "fix" them): screenings on different calendar days *can* conflict (e.g. 23:00 and 00:10); "at most one screening per film" is now per Programme Entry (legacy: per title, which the YAML adapter maps 1:1).

- Commit messages have no trailers (no `Co-Authored-By` or similar lines).

## Execution Waves

Tasks within a wave touch disjoint files, so each wave runs in parallel in isolated jj workspaces; the results are rebased into one linear history between waves.

| Wave | In parallel | Depends on |
|------|-------------|------------|
| 1 | Task 1 (baseline) · Tasks 2→3 (domain values, solve request, weights) | — |
| 2 | Tasks 4→5 (formulate, CP-SAT) · Task 6 (YAML adapter) · Task 7 (JSON adapter) | wave 1 |
| 3 | Task 8 (CLI, removal of the old solver) | wave 2 |

Directory-scoped "Expected" counts hold regardless of wave; whole-suite counts (Task 1: 51, Task 8: 101) assume all earlier tasks are merged.

## File Structure

```
src/festival_planner/
├── conftest.py                          # NEW  autouse fixture isolating Film class state
├── domain/                              # NEW  framework-free core
│   ├── __init__.py
│   ├── programme.py                     # Venue, ProgrammeEntry, Event, Screening, id aliases
│   ├── travel.py                        # Route, RouteTable, TransportMode, MissingRouteError
│   ├── planning.py                      # Preferences
│   ├── solving.py                       # SolveRequest/Result, ScheduleSolver port, screening_weight, formulate
│   └── tests/ (builders.py + test_*.py)
├── adapters/                            # NEW
│   ├── __init__.py
│   ├── solver/cpsat.py                  # CpSatScheduleSolver (ScheduleSolver port)
│   ├── yaml_files/solve_request.py      # legacy YAML -> SolveRequest
│   ├── json_files/solve_request.py      # SolveRequest <-> JSON
│   └── */tests/
├── cli/solve.py                         # REWRITE renders domain values; --request / --export-request
├── cli/tests/test_solve.py              # NEW  end-to-end CLI tests
├── solver.py                            # DELETE (replaced by adapters/solver/cpsat.py)
├── models.py                            # MODIFY remove ScheduledFilm
└── tests/
    ├── fixtures/config/config.yaml      # NEW  self-contained cinema config for tests
    └── test_weight_calculations.py      # DELETE (replaced by domain/tests/test_weights.py)
```

---

### Task 1: Green test baseline

The suite currently has 25 failures, unrelated to this plan: scraper tests read a `config/` directory removed in commit `482a893`, and `Film` keeps cinema validation in class variables that leak between tests. Fix both so every later task starts green.

**Files:**
- Create: `src/festival_planner/tests/fixtures/config/config.yaml`
- Create: `src/festival_planner/conftest.py`
- Modify: `src/festival_planner/scrapers/tests/test_film_validation.py` (`setup_method`)
- Modify: `src/festival_planner/scrapers/tests/test_cinema_parsing.py` (`setup_method`)

**Interfaces:**
- Consumes: nothing.
- Produces: a passing suite (51 tests); an autouse fixture resetting `Film._valid_cinemas` / `Film._normalization_map`.

- [ ] **Step 1: Confirm the failing baseline**

Run: `mise exec -- uv run pytest -q`
Expected: `25 failed, 26 passed` (errors mention `is not in the valid cinema list: []`).

- [ ] **Step 2: Add a self-contained cinema config fixture**

Create `src/festival_planner/tests/fixtures/config/config.yaml`:

```yaml
# Self-contained cinema configuration for tests.
cinemas:
  cinema_aliases:
    Vika:
      - "Vika Kino"
      - "vika"
      - "vika kino"
    Cinemateket:
      - "cinemateket"
    Vega:
      - "vega"
      - "vega scene"
    Klingenberg:
      - "klingenberg"

  travel_times:
    - from: "Cinemateket"
      to: "Vika"
      minutes: 20
    - from: "Vika"
      to: "Cinemateket"
      minutes: 20
    - from: "Cinemateket"
      to: "Vega"
      minutes: 20
    - from: "Vega"
      to: "Cinemateket"
      minutes: 20
    - from: "Vika"
      to: "Vega"
      minutes: 15
    - from: "Vega"
      to: "Vika"
      minutes: 15
    - from: "Klingenberg"
      to: "Klingenberg"
      minutes: 0

schedule:
  buffer_time_minutes: 15
```

- [ ] **Step 3: Point the scraper tests at the fixture**

In `src/festival_planner/scrapers/tests/test_film_validation.py`, inside `setup_method`, replace:

```python
        # Load cinema config from actual config file
        project_root = Path(__file__).parent.parent.parent.parent.parent
        config_dir = project_root / "config"
        data_dir = project_root / "data"
```

with:

```python
        # Load cinema config from the test fixtures
        fixtures_dir = Path(__file__).parents[2] / "tests" / "fixtures"
        config_dir = fixtures_dir / "config"
        data_dir = fixtures_dir / "data"
```

In `src/festival_planner/scrapers/tests/test_cinema_parsing.py`, inside `setup_method`, replace:

```python
        # Load cinema config from actual config file
        project_root = Path(__file__).parent.parent.parent.parent.parent
        config_dir = project_root / "config"
```

with:

```python
        # Load cinema config from the test fixtures
        config_dir = Path(__file__).parents[2] / "tests" / "fixtures" / "config"
```

- [ ] **Step 4: Isolate `Film`'s class-level validation state**

Create `src/festival_planner/conftest.py`:

```python
"""Shared pytest fixtures."""

import pytest

from festival_planner.models import Film


@pytest.fixture(autouse=True)
def _reset_film_cinema_validation():
    """`Film` keeps cinema validation in class variables; isolate each test."""
    Film._valid_cinemas = None
    Film._normalization_map = {}
    yield
    Film._valid_cinemas = None
    Film._normalization_map = {}
```

- [ ] **Step 5: Run the suite**

Run: `mise exec -- uv run pytest -q`
Expected: `51 passed`

- [ ] **Step 6: Commit**

```bash
jj commit -m "test: make the existing suite self-contained and green"
```

---

### Task 2: Domain programme, travel and Preferences

**Files:**
- Create: `src/festival_planner/domain/__init__.py`
- Create: `src/festival_planner/domain/programme.py`
- Create: `src/festival_planner/domain/travel.py`
- Create: `src/festival_planner/domain/planning.py`
- Create: `src/festival_planner/domain/tests/__init__.py` (empty)
- Create: `src/festival_planner/adapters/__init__.py` (package scaffold, so later parallel tasks never create it twice)
- Test: `src/festival_planner/domain/tests/test_programme.py`, `test_travel.py`, `test_planning.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `programme.py`: id aliases `VenueId = FilmId = ProgrammeEntryId = ScreeningId = str`; `Venue(id, name)`; `ProgrammeEntry(id, film_id, title, year=None, country=None, url=None)`; `Event(description, start_time=None, end_time=None)` with `.is_separately_timed`; `Screening(id, programme_entry_id, venue_id, start_time, end_time, auditorium=None, ticket_url=None, events=())` with `.ends_at(*, include_events: bool) -> datetime`.
  - `travel.py`: `TransportMode = str`; `DEFAULT_TRANSPORT_MODE = "walk+e-scooter"`; `Route(from_venue_id, to_venue_id, mode, minutes)`; `MissingRouteError(LookupError)`; `RouteTable(routes=(), default_mode=DEFAULT_TRANSPORT_MODE)` with `.minutes(from_venue_id, to_venue_id, mode: TransportMode | None) -> int`.
  - `planning.py`: `Preferences(buffer_minutes=15, venue_buffer_minutes={}, start_date=None, end_date=None, programme_entry_weights={}, screening_weights={}, year_weights={}, event_weight=0.0, attend_events=False, transport_mode=None)` with `.buffer_for(venue_id) -> int` and `.covers(day: date) -> bool`.

- [ ] **Step 1: Write the failing tests**

Create `src/festival_planner/domain/tests/__init__.py` (empty).

Create `src/festival_planner/domain/tests/test_programme.py`:

```python
import datetime

import pytest

from festival_planner.domain.programme import Event, Screening


def at(hhmm: str) -> datetime.datetime:
    return datetime.datetime.combine(
        datetime.date(2025, 11, 8), datetime.time.fromisoformat(hhmm)
    )


def screening(*events: Event) -> Screening:
    return Screening(
        id="s",
        programme_entry_id="e",
        venue_id="v",
        start_time=at("14:00"),
        end_time=at("16:00"),
        events=events,
    )


def test_event_needs_both_times_or_neither():
    with pytest.raises(ValueError):
        Event("Panel", start_time=at("16:00"))
    assert not Event("Q&A").is_separately_timed
    assert Event("Panel", at("16:00"), at("17:00")).is_separately_timed


def test_screening_ends_at_its_end_time_by_default():
    panel = Event("Panel", at("16:15"), at("17:00"))
    assert screening(panel).ends_at(include_events=False) == at("16:00")


def test_separately_timed_events_extend_the_screening_when_included():
    panel = Event("Panel", at("16:15"), at("17:00"))
    assert screening(panel).ends_at(include_events=True) == at("17:00")
    assert screening(Event("Q&A")).ends_at(include_events=True) == at("16:00")
```

Create `src/festival_planner/domain/tests/test_travel.py`:

```python
import pytest

from festival_planner.domain.travel import MissingRouteError, Route, RouteTable


def test_same_venue_needs_no_travel():
    assert RouteTable().minutes("A", "A", None) == 0


def test_uses_route_for_chosen_mode():
    table = RouteTable(
        routes=(
            Route("A", "B", "walk+e-scooter", 10),
            Route("A", "B", "bike", 7),
        )
    )
    assert table.minutes("A", "B", "bike") == 7


def test_falls_back_to_default_mode():
    table = RouteTable(routes=(Route("A", "B", "walk+e-scooter", 10),))
    assert table.minutes("A", "B", "bike") == 10


def test_routes_are_one_directional():
    table = RouteTable(routes=(Route("A", "B", "walk+e-scooter", 10),))
    with pytest.raises(MissingRouteError):
        table.minutes("B", "A", None)
```

Create `src/festival_planner/domain/tests/test_planning.py`:

```python
import datetime

from festival_planner.domain.planning import Preferences

DAY = datetime.date(2025, 11, 8)
ONE_DAY = datetime.timedelta(days=1)


def test_venue_buffer_overrides_general_buffer():
    preferences = Preferences(buffer_minutes=15, venue_buffer_minutes={"A": 25})
    assert preferences.buffer_for("A") == 25
    assert preferences.buffer_for("B") == 15


def test_date_range_is_inclusive():
    preferences = Preferences(start_date=DAY, end_date=DAY)
    assert preferences.covers(DAY)
    assert not preferences.covers(DAY - ONE_DAY)
    assert not preferences.covers(DAY + ONE_DAY)


def test_date_range_may_be_open_ended():
    assert Preferences(start_date=DAY).covers(DAY + 365 * ONE_DAY)
    assert Preferences(end_date=DAY).covers(DAY - 365 * ONE_DAY)
    assert Preferences().covers(DAY)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `mise exec -- uv run pytest src/festival_planner/domain -q`
Expected: 3 collection errors, `ModuleNotFoundError: No module named 'festival_planner.domain.programme'` (and `.travel`, `.planning`).

- [ ] **Step 3: Implement the domain modules**

Create `src/festival_planner/domain/__init__.py`:

```python
"""Domain core: festival planning concepts and use-cases, free of frameworks.

Nothing in this package may import Strawberry, SQLAlchemy, OR-Tools, httpx or
other adapter-level libraries. See docs/adr/0001-hexagonal-architecture.md.
"""
```

Create `src/festival_planner/domain/programme.py`:

```python
"""Festival programme: what is shown, where and when."""

import datetime
from dataclasses import dataclass

VenueId = str
FilmId = str
ProgrammeEntryId = str
ScreeningId = str


@dataclass(frozen=True, slots=True)
class Venue:
    """A fixed physical place where screenings take place."""

    id: VenueId
    name: str


@dataclass(frozen=True, slots=True)
class ProgrammeEntry:
    """A Film as presented in one Festival's programme."""

    id: ProgrammeEntryId
    film_id: FilmId
    title: str
    year: int | None = None
    country: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class Event:
    """Something belonging to a Screening beyond the film itself.

    Without times, the Event happens within the Screening. With times, it is
    separately timed (e.g. a panel after the film).
    """

    description: str
    start_time: datetime.datetime | None = None
    end_time: datetime.datetime | None = None

    def __post_init__(self) -> None:
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("An Event needs both start_time and end_time, or neither")

    @property
    def is_separately_timed(self) -> bool:
        return self.end_time is not None


@dataclass(frozen=True, slots=True)
class Screening:
    """A single showing of a Programme Entry at a given time and Venue."""

    id: ScreeningId
    programme_entry_id: ProgrammeEntryId
    venue_id: VenueId
    start_time: datetime.datetime
    end_time: datetime.datetime
    auditorium: str | None = None
    ticket_url: str | None = None
    events: tuple[Event, ...] = ()

    def ends_at(self, *, include_events: bool) -> datetime.datetime:
        """When the Screening ends, optionally including separately timed Events."""
        if not include_events:
            return self.end_time
        event_ends = [e.end_time for e in self.events if e.end_time is not None]
        return max([self.end_time, *event_ends])
```

Create `src/festival_planner/domain/travel.py`:

```python
"""Travel between Venues."""

from dataclasses import dataclass
from functools import cached_property

from .programme import VenueId

TransportMode = str

DEFAULT_TRANSPORT_MODE: TransportMode = "walk+e-scooter"


@dataclass(frozen=True, slots=True)
class Route:
    """A precalculated way of travelling from one Venue to another."""

    from_venue_id: VenueId
    to_venue_id: VenueId
    mode: TransportMode
    minutes: int


class MissingRouteError(LookupError):
    """No Route exists between two Venues in the chosen or default mode."""


@dataclass(frozen=True)
class RouteTable:
    """All known Routes, plus the globally decided default Transport Mode."""

    routes: tuple[Route, ...] = ()
    default_mode: TransportMode = DEFAULT_TRANSPORT_MODE

    @cached_property
    def _minutes_by_key(self) -> dict[tuple[VenueId, VenueId, TransportMode], int]:
        return {
            (r.from_venue_id, r.to_venue_id, r.mode): r.minutes for r in self.routes
        }

    def minutes(
        self, from_venue_id: VenueId, to_venue_id: VenueId, mode: TransportMode | None
    ) -> int:
        """Travel minutes by `mode`, falling back to the default mode."""
        if from_venue_id == to_venue_id:
            return 0
        for candidate in (mode, self.default_mode):
            if candidate is None:
                continue
            key = (from_venue_id, to_venue_id, candidate)
            if key in self._minutes_by_key:
                return self._minutes_by_key[key]
        raise MissingRouteError(
            f"No route from {from_venue_id!r} to {to_venue_id!r} "
            f"by {mode!r} or default {self.default_mode!r}"
        )
```

Create `src/festival_planner/domain/planning.py`:

```python
"""A User's planning inputs: Preferences."""

import datetime
from collections.abc import Mapping
from dataclasses import dataclass, field

from .programme import ProgrammeEntryId, ScreeningId, VenueId
from .travel import TransportMode


@dataclass(frozen=True)
class Preferences:
    """A User's settings that shape their Schedules for a Festival."""

    buffer_minutes: int = 15
    venue_buffer_minutes: Mapping[VenueId, int] = field(default_factory=dict)
    start_date: datetime.date | None = None
    end_date: datetime.date | None = None
    programme_entry_weights: Mapping[ProgrammeEntryId, float] = field(
        default_factory=dict
    )
    screening_weights: Mapping[ScreeningId, float] = field(default_factory=dict)
    year_weights: Mapping[int, float] = field(default_factory=dict)
    event_weight: float = 0.0
    attend_events: bool = False
    transport_mode: TransportMode | None = None

    def buffer_for(self, venue_id: VenueId) -> int:
        """Minutes to arrive before a Screening at `venue_id`."""
        return self.venue_buffer_minutes.get(venue_id, self.buffer_minutes)

    def covers(self, day: datetime.date) -> bool:
        """Whether `day` falls inside the preferred date range."""
        if self.start_date is not None and day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date
```

Create `src/festival_planner/adapters/__init__.py`:

```python
"""Adapters: implementations of domain ports and drivers of domain use-cases."""
```

- [ ] **Step 4: Run the tests**

Run: `mise exec -- uv run pytest src/festival_planner/domain -q`
Expected: `10 passed`

- [ ] **Step 5: Format and commit**

Run: `mise exec -- uv run ruff format src/festival_planner/domain src/festival_planner/adapters`

```bash
jj commit -m "feat(domain): add programme, travel and preferences values"
```

---

### Task 3: Solve request, result, solver port and weights

**Files:**
- Create: `src/festival_planner/domain/solving.py`
- Create: `src/festival_planner/domain/tests/builders.py`
- Test: `src/festival_planner/domain/tests/test_weights.py`

**Interfaces:**
- Consumes: everything Task 2 produces.
- Produces (in `domain/solving.py`):
  - `DEFAULT_WEIGHT = 1.0`
  - `SolveRequest(venues, programme_entries, screenings, routes=RouteTable(), preferences=Preferences(), screening_commitments=frozenset(), film_commitments=frozenset(), excluded_screenings=frozenset(), excluded_programme_entries=frozenset(), seen_films=frozenset(), active_schedule=frozenset(), now=None, time_limit_seconds=60.0)`; all three leading fields are tuples.
  - `SolveStatus` (`StrEnum`: `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `UNKNOWN`)
  - `ScheduledScreening(screening_id, arrival_time, weight)`
  - `SolveResult(status, scheduled=(), objective=0.0, wall_time_seconds=0.0, reasons=())` with `.is_solved`
  - `ScheduleSolver` (`Protocol`): `solve(self, request: SolveRequest) -> SolveResult`
  - `screening_weight(screening, entry, preferences) -> float`
- Produces (test helpers in `domain/tests/builders.py`, reused by later tasks): `DAY = date(2025, 11, 8)`; `at("HH:MM", day=DAY) -> datetime`; `entry(id, *, film_id=None, year=None) -> ProgrammeEntry` (film id defaults to `f"film-{id}"`, title = id); `screening(id, start, end, *, entry_id=None, venue="A", day=DAY, events=()) -> Screening` (entry id defaults to the screening id); `request(*screenings, entries=None, routes=(), preferences=None, **kwargs) -> SolveRequest` (one entry per distinct entry id, one Venue per venue id, `Preferences(buffer_minutes=0)` by default).

- [ ] **Step 1: Write the test builders and failing weight tests**

Create `src/festival_planner/domain/tests/builders.py`:

```python
"""Terse builders for domain values in tests."""

import datetime

from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event, ProgrammeEntry, Screening, Venue
from festival_planner.domain.solving import SolveRequest
from festival_planner.domain.travel import Route, RouteTable

DAY = datetime.date(2025, 11, 8)


def at(hhmm: str, day: datetime.date = DAY) -> datetime.datetime:
    """`at("18:30")` is 18:30 on `DAY`."""
    return datetime.datetime.combine(day, datetime.time.fromisoformat(hhmm))


def entry(
    id: str, *, film_id: str | None = None, year: int | None = None
) -> ProgrammeEntry:
    return ProgrammeEntry(id=id, film_id=film_id or f"film-{id}", title=id, year=year)


def screening(
    id: str,
    start: str,
    end: str,
    *,
    entry_id: str | None = None,
    venue: str = "A",
    day: datetime.date = DAY,
    events: tuple[Event, ...] = (),
) -> Screening:
    return Screening(
        id=id,
        programme_entry_id=entry_id or id,
        venue_id=venue,
        start_time=at(start, day),
        end_time=at(end, day),
        events=events,
    )


def request(
    *screenings: Screening,
    entries: tuple[ProgrammeEntry, ...] | None = None,
    routes: tuple[Route, ...] = (),
    preferences: Preferences | None = None,
    **kwargs,
) -> SolveRequest:
    """A SolveRequest whose entries default to one per distinct entry id."""
    if entries is None:
        entry_ids = dict.fromkeys(s.programme_entry_id for s in screenings)
        entries = tuple(entry(entry_id) for entry_id in entry_ids)
    venue_ids = dict.fromkeys(s.venue_id for s in screenings)
    return SolveRequest(
        venues=tuple(Venue(id=v, name=v) for v in venue_ids),
        programme_entries=entries,
        screenings=screenings,
        routes=RouteTable(routes=routes),
        preferences=preferences or Preferences(buffer_minutes=0),
        **kwargs,
    )
```

Create `src/festival_planner/domain/tests/test_weights.py` (ported from the legacy `tests/test_weight_calculations.py`, which Task 8 deletes):

```python
from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event
from festival_planner.domain.solving import DEFAULT_WEIGHT, screening_weight
from festival_planner.domain.tests.builders import at, entry, screening


def test_default_weight():
    assert (
        screening_weight(screening("s", "14:00", "16:00"), entry("s"), Preferences())
        == DEFAULT_WEIGHT
    )


def test_programme_entry_weight_replaces_default():
    preferences = Preferences(programme_entry_weights={"s": 0.5})
    assert (
        screening_weight(screening("s", "14:00", "16:00"), entry("s"), preferences)
        == 0.5
    )


def test_screening_weight_beats_programme_entry_weight():
    preferences = Preferences(
        programme_entry_weights={"s": 0.5}, screening_weights={"s": 2.0}
    )
    assert (
        screening_weight(screening("s", "14:00", "16:00"), entry("s"), preferences)
        == 2.0
    )


def test_year_weight_is_added():
    preferences = Preferences(year_weights={1960: 0.3})
    assert (
        screening_weight(
            screening("s", "14:00", "16:00"), entry("s", year=1960), preferences
        )
        == DEFAULT_WEIGHT + 0.3
    )


def test_no_year_means_no_year_weight():
    preferences = Preferences(year_weights={1960: 0.3})
    assert (
        screening_weight(screening("s", "14:00", "16:00"), entry("s"), preferences)
        == DEFAULT_WEIGHT
    )


def test_event_weight_applies_to_screenings_with_events():
    preferences = Preferences(event_weight=0.5)
    talk = Event("Director Q&A")
    assert (
        screening_weight(
            screening("s", "14:00", "16:00", events=(talk,)), entry("s"), preferences
        )
        == DEFAULT_WEIGHT + 0.5
    )
    assert (
        screening_weight(screening("t", "14:00", "16:00"), entry("t"), preferences)
        == DEFAULT_WEIGHT
    )


def test_separately_timed_event_also_counts():
    preferences = Preferences(event_weight=0.5)
    panel = Event("Panel", at("16:15"), at("17:00"))
    assert (
        screening_weight(
            screening("s", "14:00", "16:00", events=(panel,)), entry("s"), preferences
        )
        == DEFAULT_WEIGHT + 0.5
    )


def test_weights_combine_and_may_be_negative():
    preferences = Preferences(
        programme_entry_weights={"s": -1.0}, year_weights={2025: -0.2}, event_weight=0.5
    )
    weight = screening_weight(
        screening("s", "14:00", "16:00", events=(Event("Q&A"),)),
        entry("s", year=2025),
        preferences,
    )
    assert weight == -1.0 - 0.2 + 0.5
```

- [ ] **Step 2: Run them to verify they fail**

Run: `mise exec -- uv run pytest src/festival_planner/domain/tests/test_weights.py -q`
Expected: collection error, `ModuleNotFoundError: No module named 'festival_planner.domain.solving'`.

- [ ] **Step 3: Implement `solving.py` (first part)**

Create `src/festival_planner/domain/solving.py`:

```python
"""Solving: turning a self-contained solve request into a Schedule.

`formulate` holds all scheduling rules as pure Python. A `ScheduleSolver`
adapter only has to optimise the resulting `Formulation`.
"""

import datetime
import enum
from dataclasses import dataclass, field
from typing import Protocol

from .planning import Preferences
from .programme import (
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
)
from .travel import RouteTable

DEFAULT_WEIGHT = 1.0
"""Weight of a Screening without any weight preference."""


@dataclass(frozen=True)
class SolveRequest:
    """Everything needed to solve one Schedule, as plain values."""

    venues: tuple[Venue, ...]
    programme_entries: tuple[ProgrammeEntry, ...]
    screenings: tuple[Screening, ...]
    routes: RouteTable = field(default_factory=RouteTable)
    preferences: Preferences = field(default_factory=Preferences)
    screening_commitments: frozenset[ScreeningId] = frozenset()
    film_commitments: frozenset[ProgrammeEntryId] = frozenset()
    excluded_screenings: frozenset[ScreeningId] = frozenset()
    excluded_programme_entries: frozenset[ProgrammeEntryId] = frozenset()
    seen_films: frozenset[FilmId] = frozenset()
    active_schedule: frozenset[ScreeningId] = frozenset()
    now: datetime.datetime | None = None
    time_limit_seconds: float = 60.0


class SolveStatus(enum.StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    """The time limit ran out before any Schedule was found."""


@dataclass(frozen=True, slots=True)
class ScheduledScreening:
    screening_id: ScreeningId
    arrival_time: datetime.datetime
    weight: float


@dataclass(frozen=True)
class SolveResult:
    status: SolveStatus
    scheduled: tuple[ScheduledScreening, ...] = ()
    objective: float = 0.0
    wall_time_seconds: float = 0.0
    reasons: tuple[str, ...] = ()
    """Why the request cannot be satisfied, when known."""

    @property
    def is_solved(self) -> bool:
        return self.status in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)


class ScheduleSolver(Protocol):
    """Port: produces the best Schedule for a solve request."""

    def solve(self, request: SolveRequest) -> SolveResult: ...


def screening_weight(
    screening: Screening, entry: ProgrammeEntry, preferences: Preferences
) -> float:
    """How much attending `screening` is worth.

    A screening weight overrides a programme entry weight, which overrides
    `DEFAULT_WEIGHT`. Year and Event weights are added on top.
    """
    weight = preferences.screening_weights.get(
        screening.id, preferences.programme_entry_weights.get(entry.id, DEFAULT_WEIGHT)
    )
    if entry.year is not None:
        weight += preferences.year_weights.get(entry.year, 0.0)
    if screening.events:
        weight += preferences.event_weight
    return weight
```

- [ ] **Step 4: Run the domain tests**

Run: `mise exec -- uv run pytest src/festival_planner/domain -q`
Expected: `18 passed`

- [ ] **Step 5: Format and commit**

Run: `mise exec -- uv run ruff format src/festival_planner/domain`

```bash
jj commit -m "feat(domain): add solve request/result, solver port and weights"
```

---

### Task 4: Scheduling rules (`formulate`)

All rules live here as pure Python; the solver adapter in Task 5 only optimises the result.

**Files:**
- Modify: `src/festival_planner/domain/solving.py` (imports; append `Formulation`, `formulate`, `_conflicts`, `_reachable`)
- Test: `src/festival_planner/domain/tests/test_formulate.py`

**Interfaces:**
- Consumes: Task 3's `SolveRequest`, `screening_weight`, builders.
- Produces:
  - `Formulation(candidates: tuple[Screening, ...], weights: Mapping[ScreeningId, float], required: frozenset[ScreeningId], exactly_one: tuple[frozenset[ScreeningId], ...], at_most_one: tuple[frozenset[ScreeningId], ...], conflicts: frozenset[tuple[ScreeningId, ScreeningId]], unsatisfiable: tuple[str, ...])`
  - `formulate(request: SolveRequest) -> Formulation`. Rules, in precedence order (also in its docstring):
    1. Screenings that started before `request.now` are fixed: required if in `active_schedule`, otherwise dropped (and reported as unsatisfiable if they were Screening Commitments).
    2. Screening Commitments are required, regardless of exclusions, Seen or the date range.
    3. Excluded Screenings and Programme Entries are dropped.
    4. Screenings of Seen Films are dropped unless their Programme Entry has a Film Commitment.
    5. Screenings outside `preferences.covers(start_time.date())` are dropped.
    6. Each Film Commitment needs exactly one remaining Screening, otherwise it is reported as unsatisfiable.
    7. At most one Screening per Programme Entry (groups only for entries with 2+ candidates).
    8. Two Screenings conflict when neither can be reached from the other: `first.ends_at(include_events=preferences.attend_events) + travel(first.venue → second.venue, preferences.transport_mode) + preferences.buffer_for(second.venue) <= second.start_time` must hold for at least one order.

- [ ] **Step 1: Write the failing tests**

Create `src/festival_planner/domain/tests/test_formulate.py`:

```python
import datetime

from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event
from festival_planner.domain.solving import formulate
from festival_planner.domain.tests.builders import DAY, at, entry, request, screening
from festival_planner.domain.travel import Route


def candidate_ids(req) -> set[str]:
    return {s.id for s in formulate(req).candidates}


class TestCandidates:
    def test_all_screenings_are_candidates_by_default(self):
        req = request(
            screening("a", "14:00", "16:00"), screening("b", "18:00", "20:00")
        )
        assert candidate_ids(req) == {"a", "b"}

    def test_excluded_screening_is_dropped(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening("b", "18:00", "20:00"),
            excluded_screenings=frozenset({"a"}),
        )
        assert candidate_ids(req) == {"b"}

    def test_excluded_programme_entry_drops_all_its_screenings(self):
        req = request(
            screening("a1", "14:00", "16:00", entry_id="a"),
            screening("a2", "18:00", "20:00", entry_id="a"),
            excluded_programme_entries=frozenset({"a"}),
        )
        assert candidate_ids(req) == set()

    def test_seen_film_is_dropped(self):
        req = request(
            screening("a", "14:00", "16:00"), seen_films=frozenset({"film-a"})
        )
        assert candidate_ids(req) == set()

    def test_seen_film_with_film_commitment_is_kept(self):
        req = request(
            screening("a", "14:00", "16:00"),
            seen_films=frozenset({"film-a"}),
            film_commitments=frozenset({"a"}),
        )
        assert candidate_ids(req) == {"a"}

    def test_screenings_outside_date_range_are_dropped(self):
        next_day = DAY + datetime.timedelta(days=1)
        req = request(
            screening("a", "14:00", "16:00"),
            screening("b", "14:00", "16:00", day=next_day),
            preferences=Preferences(start_date=next_day),
        )
        assert candidate_ids(req) == {"b"}

    def test_screening_commitment_overrides_exclusion_seen_and_dates(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening_commitments=frozenset({"a"}),
            excluded_screenings=frozenset({"a"}),
            seen_films=frozenset({"film-a"}),
            preferences=Preferences(end_date=DAY - datetime.timedelta(days=1)),
        )
        formulation = formulate(req)
        assert {s.id for s in formulation.candidates} == {"a"}
        assert formulation.required == {"a"}


class TestStartedScreenings:
    def test_started_screening_in_active_schedule_is_required(self):
        req = request(
            screening("a", "14:00", "16:00"),
            active_schedule=frozenset({"a"}),
            now=at("15:00"),
        )
        formulation = formulate(req)
        assert formulation.required == {"a"}

    def test_started_screening_outside_active_schedule_is_dropped(self):
        req = request(screening("a", "14:00", "16:00"), now=at("15:00"))
        assert candidate_ids(req) == set()

    def test_started_committed_screening_is_unsatisfiable(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening_commitments=frozenset({"a"}),
            now=at("15:00"),
        )
        assert formulate(req).unsatisfiable


class TestGroups:
    def test_film_commitment_requires_exactly_one_of_its_screenings(self):
        req = request(
            screening("a1", "14:00", "16:00", entry_id="a"),
            screening("a2", "18:00", "20:00", entry_id="a"),
            film_commitments=frozenset({"a"}),
        )
        assert formulate(req).exactly_one == (frozenset({"a1", "a2"}),)

    def test_film_commitment_without_screenings_is_unsatisfiable(self):
        req = request(
            screening("a", "14:00", "16:00"),
            entries=(entry("a"), entry("b")),
            film_commitments=frozenset({"b"}),
        )
        assert formulate(req).unsatisfiable

    def test_at_most_one_screening_per_programme_entry(self):
        req = request(
            screening("a1", "14:00", "16:00", entry_id="a"),
            screening("a2", "18:00", "20:00", entry_id="a"),
            screening("b", "21:00", "23:00"),
        )
        assert formulate(req).at_most_one == (frozenset({"a1", "a2"}),)


def conflicts(req) -> set[frozenset[str]]:
    return {frozenset(pair) for pair in formulate(req).conflicts}


class TestConflicts:
    def test_overlapping_screenings_conflict(self):
        req = request(
            screening("a", "14:00", "16:00"), screening("b", "15:00", "17:00")
        )
        assert conflicts(req) == {frozenset({"a", "b"})}

    def test_back_to_back_at_same_venue_without_buffer_is_fine(self):
        req = request(
            screening("a", "14:00", "16:00"), screening("b", "16:00", "18:00")
        )
        assert conflicts(req) == set()

    def test_buffer_of_next_venue_is_needed(self):
        req = request(
            screening("a", "14:00", "16:00"),
            screening("b", "16:10", "18:00"),
            preferences=Preferences(buffer_minutes=15),
        )
        assert conflicts(req) == {frozenset({"a", "b"})}

    def test_per_venue_buffer_overrides_general_buffer(self):
        req = request(
            screening("a", "14:00", "16:00", venue="A"),
            screening("b", "16:10", "18:00", venue="A"),
            preferences=Preferences(buffer_minutes=15, venue_buffer_minutes={"A": 5}),
        )
        assert conflicts(req) == set()

    def test_travel_time_uses_the_direction_travelled(self):
        req = request(
            screening("a", "14:00", "16:00", venue="A"),
            screening("b", "16:10", "18:00", venue="B"),
            routes=(
                Route("A", "B", "walk+e-scooter", 20),
                Route("B", "A", "walk+e-scooter", 5),
            ),
        )
        assert conflicts(req) == {frozenset({"a", "b"})}

    def test_chosen_transport_mode_is_used(self):
        req = request(
            screening("a", "14:00", "16:00", venue="A"),
            screening("b", "16:10", "18:00", venue="B"),
            routes=(
                Route("A", "B", "walk+e-scooter", 20),
                Route("B", "A", "walk+e-scooter", 20),
                Route("A", "B", "bike", 8),
            ),
            preferences=Preferences(buffer_minutes=0, transport_mode="bike"),
        )
        assert conflicts(req) == set()

    def test_separately_timed_event_blocks_time_when_attending_events(self):
        panel = Event("Panel", at("16:00"), at("17:00"))
        a = screening("a", "14:00", "16:00", events=(panel,))
        b = screening("b", "16:30", "18:00")
        assert conflicts(request(a, b)) == set()
        attending = request(
            a, b, preferences=Preferences(buffer_minutes=0, attend_events=True)
        )
        assert conflicts(attending) == {frozenset({"a", "b"})}

    def test_screenings_across_midnight_still_conflict(self):
        next_day = DAY + datetime.timedelta(days=1)
        late = screening("late", "23:00", "23:59")
        after_midnight = screening("early", "00:10", "02:00", day=next_day)
        req = request(late, after_midnight, preferences=Preferences(buffer_minutes=15))
        assert conflicts(req) == {frozenset({"late", "early"})}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `mise exec -- uv run pytest src/festival_planner/domain/tests/test_formulate.py -q`
Expected: collection error, `ImportError: cannot import name 'formulate' from 'festival_planner.domain.solving'`.

- [ ] **Step 3: Implement `formulate`**

In `src/festival_planner/domain/solving.py`, replace the import block:

```python
import datetime
import enum
from dataclasses import dataclass, field
from typing import Protocol

from .planning import Preferences
from .programme import (
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
)
from .travel import RouteTable
```

with:

```python
import datetime
import enum
import itertools
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from .planning import Preferences
from .programme import (
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
)
from .travel import RouteTable
```

Then append to the end of the file:

```python
@dataclass(frozen=True)
class Formulation:
    """The optimisation problem derived from a solve request."""

    candidates: tuple[Screening, ...]
    weights: Mapping[ScreeningId, float]
    required: frozenset[ScreeningId]
    exactly_one: tuple[frozenset[ScreeningId], ...]
    at_most_one: tuple[frozenset[ScreeningId], ...]
    conflicts: frozenset[tuple[ScreeningId, ScreeningId]]
    unsatisfiable: tuple[str, ...]


def formulate(request: SolveRequest) -> Formulation:
    """Apply the scheduling rules to `request`.

    Rules, in order of precedence:
    - Screenings that started before `now` are fixed: kept and required if in
      the Active Schedule, dropped otherwise.
    - Screening Commitments are required, regardless of exclusions, Seen or
      the date range.
    - Excluded Screenings and Programme Entries are dropped.
    - Screenings of Seen Films are dropped unless committed to.
    - Screenings outside the preferred date range are dropped.
    - Each Film Commitment needs exactly one of its remaining Screenings.
    - At most one Screening per Programme Entry.
    - Two Screenings conflict when neither can be reached from the other in
      time, given travel and the arrival buffer.
    """
    preferences = request.preferences
    entries = {e.id: e for e in request.programme_entries}
    unsatisfiable: list[str] = []
    candidates: list[Screening] = []
    required: set[ScreeningId] = set()

    for screening in request.screenings:
        entry = entries[screening.programme_entry_id]
        committed = screening.id in request.screening_commitments
        if request.now is not None and screening.start_time < request.now:
            if screening.id in request.active_schedule:
                candidates.append(screening)
                required.add(screening.id)
            elif committed:
                unsatisfiable.append(
                    f"Committed screening {screening.id!r} has already started"
                )
            continue
        if committed:
            candidates.append(screening)
            required.add(screening.id)
            continue
        if (
            screening.id in request.excluded_screenings
            or entry.id in request.excluded_programme_entries
        ):
            continue
        if (
            entry.film_id in request.seen_films
            and entry.id not in request.film_commitments
        ):
            continue
        if not preferences.covers(screening.start_time.date()):
            continue
        candidates.append(screening)

    by_entry: defaultdict[ProgrammeEntryId, set[ScreeningId]] = defaultdict(set)
    for screening in candidates:
        by_entry[screening.programme_entry_id].add(screening.id)

    exactly_one: list[frozenset[ScreeningId]] = []
    for entry_id in sorted(request.film_commitments):
        options = by_entry.get(entry_id)
        if not options:
            unsatisfiable.append(
                f"Film commitment {entry_id!r} has no schedulable screening"
            )
            continue
        exactly_one.append(frozenset(options))

    return Formulation(
        candidates=tuple(candidates),
        weights={
            s.id: screening_weight(s, entries[s.programme_entry_id], preferences)
            for s in candidates
        },
        required=frozenset(required),
        exactly_one=tuple(exactly_one),
        at_most_one=tuple(frozenset(ids) for ids in by_entry.values() if len(ids) > 1),
        conflicts=_conflicts(candidates, request.routes, preferences),
        unsatisfiable=tuple(unsatisfiable),
    )


def _conflicts(
    screenings: list[Screening], routes: RouteTable, preferences: Preferences
) -> frozenset[tuple[ScreeningId, ScreeningId]]:
    conflicts = set()
    for a, b in itertools.combinations(screenings, 2):
        if not (
            _reachable(a, b, routes, preferences)
            or _reachable(b, a, routes, preferences)
        ):
            conflicts.add((a.id, b.id))
    return frozenset(conflicts)


def _reachable(
    first: Screening, second: Screening, routes: RouteTable, preferences: Preferences
) -> bool:
    """Whether one can attend `first` and still arrive in time for `second`."""
    travel = routes.minutes(first.venue_id, second.venue_id, preferences.transport_mode)
    needed = datetime.timedelta(
        minutes=travel + preferences.buffer_for(second.venue_id)
    )
    leaves = first.ends_at(include_events=preferences.attend_events)
    return leaves + needed <= second.start_time
```

- [ ] **Step 4: Run the domain tests**

Run: `mise exec -- uv run pytest src/festival_planner/domain -q`
Expected: `39 passed`

- [ ] **Step 5: Format and commit**

Run: `mise exec -- uv run ruff format src/festival_planner/domain`

```bash
jj commit -m "feat(domain): formulate scheduling rules from a solve request"
```

---

### Task 5: CP-SAT solver adapter

**Files:**
- Create: `src/festival_planner/adapters/solver/__init__.py`
- Create: `src/festival_planner/adapters/solver/cpsat.py`
- Create: `src/festival_planner/adapters/solver/tests/__init__.py` (empty)
- Test: `src/festival_planner/adapters/solver/tests/test_cpsat.py`

**Interfaces:**
- Consumes: `formulate`, `SolveRequest`, `SolveResult`, `SolveStatus`, `ScheduledScreening`, `ScheduleSolver` (Tasks 3–4); test builders.
- Produces: `CpSatScheduleSolver` with `solve(request: SolveRequest) -> SolveResult`, satisfying the `ScheduleSolver` protocol. Scheduled screenings are sorted by start time; `arrival_time = start_time - buffer_for(venue)`; `objective` is in weight units (unscaled). Unsatisfiable formulations return `INFEASIBLE` with `reasons` without calling CP-SAT. Raises `RuntimeError` on `MODEL_INVALID`.

- [ ] **Step 1: Write the failing tests**

Create `src/festival_planner/adapters/solver/tests/__init__.py` (empty).

Create `src/festival_planner/adapters/solver/tests/test_cpsat.py`:

```python
from festival_planner.adapters.solver.cpsat import CpSatScheduleSolver
from festival_planner.domain.planning import Preferences
from festival_planner.domain.solving import ScheduleSolver, SolveStatus
from festival_planner.domain.tests.builders import at, request, screening

solver: ScheduleSolver = CpSatScheduleSolver()


def scheduled_ids(result) -> list[str]:
    return [s.screening_id for s in result.scheduled]


def test_empty_request_gives_empty_schedule():
    result = solver.solve(request())
    assert result.status == SolveStatus.OPTIMAL
    assert result.scheduled == ()


def test_schedules_everything_that_fits_in_start_order():
    result = solver.solve(
        request(screening("b", "18:00", "20:00"), screening("a", "14:00", "16:00"))
    )
    assert result.is_solved
    assert scheduled_ids(result) == ["a", "b"]


def test_prefers_higher_weight_among_conflicting_screenings():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            preferences=Preferences(
                buffer_minutes=0, programme_entry_weights={"b": 2.0}
            ),
        )
    )
    assert scheduled_ids(result) == ["b"]
    assert result.objective == 2.0


def test_screening_commitment_wins_over_higher_weight():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            preferences=Preferences(
                buffer_minutes=0, programme_entry_weights={"b": 2.0}
            ),
            screening_commitments=frozenset({"a"}),
        )
    )
    assert scheduled_ids(result) == ["a"]


def test_conflicting_commitments_are_infeasible():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            screening_commitments=frozenset({"a", "b"}),
        )
    )
    assert result.status == SolveStatus.INFEASIBLE


def test_unsatisfiable_formulation_reports_reasons():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening_commitments=frozenset({"a"}),
            now=at("15:00"),
        )
    )
    assert result.status == SolveStatus.INFEASIBLE
    assert result.reasons


def test_negative_weight_screenings_are_left_out():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            preferences=Preferences(
                buffer_minutes=0, programme_entry_weights={"a": -1.0}
            ),
        )
    )
    assert result.scheduled == ()


def test_arrival_time_uses_venue_buffer():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00", venue="A"),
            preferences=Preferences(buffer_minutes=15, venue_buffer_minutes={"A": 25}),
        )
    )
    assert result.scheduled[0].arrival_time == at("13:35")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `mise exec -- uv run pytest src/festival_planner/adapters -q`
Expected: collection error, `ModuleNotFoundError: No module named 'festival_planner.adapters.solver'`.

- [ ] **Step 3: Implement the adapter**

Create `src/festival_planner/adapters/solver/__init__.py`:

```python
"""ScheduleSolver adapters."""
```

Create `src/festival_planner/adapters/solver/cpsat.py`:

```python
"""ScheduleSolver adapter using Google OR-Tools CP-SAT."""

import datetime

from ortools.sat.python import cp_model

from ...domain.solving import (
    ScheduledScreening,
    SolveRequest,
    SolveResult,
    SolveStatus,
    formulate,
)

WEIGHT_PRECISION_MULTIPLIER = 1000
"""CP-SAT needs integer coefficients; weights are scaled by this."""

_STATUSES = {
    cp_model.OPTIMAL: SolveStatus.OPTIMAL,
    cp_model.FEASIBLE: SolveStatus.FEASIBLE,
    cp_model.INFEASIBLE: SolveStatus.INFEASIBLE,
    cp_model.UNKNOWN: SolveStatus.UNKNOWN,
}


class CpSatScheduleSolver:
    """Optimises a `Formulation` as a CP-SAT boolean model."""

    def solve(self, request: SolveRequest) -> SolveResult:
        formulation = formulate(request)
        if formulation.unsatisfiable:
            return SolveResult(
                status=SolveStatus.INFEASIBLE, reasons=formulation.unsatisfiable
            )
        if not formulation.candidates:
            return SolveResult(status=SolveStatus.OPTIMAL)

        model = cp_model.CpModel()
        attend = {
            s.id: model.new_bool_var(f"attend[{s.id}]") for s in formulation.candidates
        }
        for screening_id in formulation.required:
            model.add(attend[screening_id] == 1)
        for group in formulation.exactly_one:
            model.add_exactly_one(attend[i] for i in group)
        for group in formulation.at_most_one:
            model.add_at_most_one(attend[i] for i in group)
        for a, b in formulation.conflicts:
            model.add_at_most_one(attend[a], attend[b])
        ids = list(formulation.weights)
        model.maximize(
            cp_model.LinearExpr.weighted_sum(
                [attend[i] for i in ids],
                [
                    round(formulation.weights[i] * WEIGHT_PRECISION_MULTIPLIER)
                    for i in ids
                ],
            )
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = request.time_limit_seconds
        status = _STATUSES.get(solver.solve(model))
        if status is None:
            raise RuntimeError(f"CP-SAT failed: {solver.status_name()}")
        if status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
            return SolveResult(status=status, wall_time_seconds=solver.wall_time)

        preferences = request.preferences
        scheduled = tuple(
            ScheduledScreening(
                screening_id=s.id,
                arrival_time=s.start_time
                - datetime.timedelta(minutes=preferences.buffer_for(s.venue_id)),
                weight=formulation.weights[s.id],
            )
            for s in sorted(formulation.candidates, key=lambda s: s.start_time)
            if solver.boolean_value(attend[s.id])
        )
        return SolveResult(
            status=status,
            scheduled=scheduled,
            objective=solver.objective_value / WEIGHT_PRECISION_MULTIPLIER,
            wall_time_seconds=solver.wall_time,
        )
```

OR-Tools ≥ 9.8 provides the snake_case API used here (`new_bool_var`, `add_exactly_one`, `boolean_value`, `objective_value`, `wall_time`); the lockfile pins 9.15.

- [ ] **Step 4: Run the tests**

Run: `mise exec -- uv run pytest src/festival_planner/adapters -q`
Expected: `8 passed`

- [ ] **Step 5: Format and commit**

Run: `mise exec -- uv run ruff format src/festival_planner/adapters/solver`

```bash
jj commit -m "feat(adapters): add CP-SAT schedule solver adapter"
```

---

### Task 6: Legacy YAML → SolveRequest adapter

Translates the existing `films.yaml`, `config.yaml` and `preferences.yaml` models into a `SolveRequest`, preserving legacy semantics.

**Files:**
- Create: `src/festival_planner/adapters/yaml_files/__init__.py`
- Create: `src/festival_planner/adapters/yaml_files/solve_request.py`
- Create: `src/festival_planner/adapters/yaml_files/tests/__init__.py` (empty)
- Test: `src/festival_planner/adapters/yaml_files/tests/test_solve_request.py`

**Interfaces:**
- Consumes: legacy `festival_planner.models.Film`, `festival_planner.config.Config` (`config.films.seen`, `config.films.weights`, `config.cinemas.travel_times`, `config.schedule`, `config.priority`); domain values from Tasks 2–3.
- Produces: `LEGACY_DEFAULT_TRAVEL_MINUTES = 30`; `screening_id(film: Film) -> str` (format `"{title} @ {start_time.isoformat()} @ {cinema}"`); `build_solve_request(films: list[Film], config: Config) -> SolveRequest`. Mapping:
  - title → Programme Entry id and Film id; cinema → Venue id; `special_notes` → one `Event` within the Screening.
  - `SeenFilm(title, date=None)` → `seen_films`; `SeenFilm(title, date)` → `excluded_screenings` for that title on that date.
  - Weights keep legacy precedence: `FilmWeight` with `start_time` → `screening_weights`; without → `programme_entry_weights`; a scraped `Film.preference_weight != 1.0` → `screening_weights` only if neither override applies.
  - `schedule.buffer_time_minutes/start_date/end_date` → Preferences; `priority.year_weights` → `year_weights`; `priority.special_notes_weight` → `event_weight`.
  - Travel times become default-mode Routes, mirrored unless the reverse is configured; every other pair of Venues gets `LEGACY_DEFAULT_TRAVEL_MINUTES`.

- [ ] **Step 1: Write the failing tests**

Create `src/festival_planner/adapters/yaml_files/tests/__init__.py` (empty).

Create `src/festival_planner/adapters/yaml_files/tests/test_solve_request.py`:

```python
import datetime

from festival_planner.adapters.yaml_files.solve_request import (
    LEGACY_DEFAULT_TRAVEL_MINUTES,
    build_solve_request,
    screening_id,
)
from festival_planner.config import Config, FilmPreferences
from festival_planner.models import (
    CinemaConfig,
    Film,
    FilmWeight,
    PriorityConfig,
    ScheduleConfig,
    SeenFilm,
    TravelTime,
)

DAY = datetime.date(2025, 11, 8)


def film(
    title: str, hour: int, cinema: str = "Vika", day: datetime.date = DAY, **kwargs
) -> Film:
    start = datetime.datetime.combine(day, datetime.time(hour))
    return Film(
        title=title,
        country="Norway",
        start_time=start,
        end_time=start + datetime.timedelta(hours=2),
        cinema=cinema,
        **kwargs,
    )


def test_titles_become_programme_entries_and_films():
    a1, a2 = film("A", 12, year=1960, url="https://a"), film("A", 18)
    request = build_solve_request([a1, a2], Config())

    (entry,) = request.programme_entries
    assert (entry.id, entry.film_id, entry.year, entry.url) == (
        "A",
        "A",
        1960,
        "https://a",
    )
    assert [s.id for s in request.screenings] == [screening_id(a1), screening_id(a2)]
    assert {s.programme_entry_id for s in request.screenings} == {"A"}


def test_special_notes_become_an_event():
    request = build_solve_request([film("A", 12, special_notes="Q&A")], Config())
    assert request.screenings[0].events[0].description == "Q&A"


def test_seen_without_date_marks_film_seen_and_with_date_excludes_screenings():
    next_day = DAY + datetime.timedelta(days=1)
    a, b1, b2 = film("A", 12), film("B", 12), film("B", 12, day=next_day)
    config = Config(
        films=FilmPreferences(seen=[SeenFilm(title="A"), SeenFilm(title="B", date=DAY)])
    )
    request = build_solve_request([a, b1, b2], config)
    assert request.seen_films == {"A"}
    assert request.excluded_screenings == {screening_id(b1)}


def test_weight_precedence_matches_legacy_behaviour():
    a1, a2 = film("A", 12, preference_weight=3.0), film("A", 18)
    b = film("B", 12, preference_weight=3.0)
    config = Config(
        films=FilmPreferences(
            weights=[
                FilmWeight(title="A", weight=0.5),
                FilmWeight(title="A", start_time=a2.start_time, weight=2.0),
            ]
        )
    )
    preferences = build_solve_request([a1, a2, b], config).preferences
    assert preferences.programme_entry_weights == {"A": 0.5}
    assert preferences.screening_weights == {
        screening_id(a2): 2.0,
        screening_id(b): 3.0,
    }


def test_schedule_and_priority_config_become_preferences():
    config = Config(
        schedule=ScheduleConfig(buffer_time_minutes=20, start_date=DAY),
        priority=PriorityConfig(year_weights={1960: 0.3}, special_notes_weight=0.5),
    )
    preferences = build_solve_request([], config).preferences
    assert preferences.buffer_minutes == 20
    assert preferences.start_date == DAY
    assert preferences.year_weights == {1960: 0.3}
    assert preferences.event_weight == 0.5


def test_travel_times_are_symmetric_and_missing_pairs_get_default():
    config = Config(
        cinemas=CinemaConfig(
            travel_times=[TravelTime(from_cinema="Vika", to_cinema="Vega", minutes=15)]
        )
    )
    films = [film("A", 12, "Vika"), film("B", 15, "Vega"), film("C", 18, "Cinemateket")]
    routes = build_solve_request(films, config).routes
    assert routes.minutes("Vika", "Vega", None) == 15
    assert routes.minutes("Vega", "Vika", None) == 15
    assert routes.minutes("Vika", "Cinemateket", None) == LEGACY_DEFAULT_TRAVEL_MINUTES
```

- [ ] **Step 2: Run them to verify they fail**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/yaml_files -q`
Expected: collection error, `ModuleNotFoundError: No module named 'festival_planner.adapters.yaml_files.solve_request'`.

- [ ] **Step 3: Implement the adapter**

Create `src/festival_planner/adapters/yaml_files/__init__.py`:

```python
"""Adapters for the legacy YAML configuration and data files."""
```

Create `src/festival_planner/adapters/yaml_files/solve_request.py`:

```python
"""Build a SolveRequest from the legacy YAML films, config and preferences.

The YAML files identify everything by title, so titles become ids: one
Programme Entry and one Film per title, and one Venue per cinema name.
"""

import itertools

from ...config import Config
from ...domain.planning import Preferences
from ...domain.programme import Event, ProgrammeEntry, Screening, Venue
from ...domain.solving import SolveRequest
from ...domain.travel import Route, RouteTable
from ...models import Film

LEGACY_DEFAULT_TRAVEL_MINUTES = 30
"""Travel time assumed between cinemas without a configured travel time."""


def screening_id(film: Film) -> str:
    return f"{film.title} @ {film.start_time.isoformat()} @ {film.cinema}"


def build_solve_request(films: list[Film], config: Config) -> SolveRequest:
    """Translate legacy YAML inputs into a self-contained SolveRequest."""
    entries: dict[str, ProgrammeEntry] = {}
    for film in films:
        entries.setdefault(
            film.title,
            ProgrammeEntry(
                id=film.title,
                film_id=film.title,
                title=film.title,
                year=film.year,
                country=film.country,
                url=film.url,
            ),
        )
    venue_ids = list(dict.fromkeys(film.cinema for film in films))
    seen = config.films.seen
    excluded_on_date = {(s.title, s.date) for s in seen if s.date is not None}

    return SolveRequest(
        venues=tuple(Venue(id=v, name=v) for v in venue_ids),
        programme_entries=tuple(entries.values()),
        screenings=tuple(_screening(film) for film in films),
        routes=_route_table(config, venue_ids),
        preferences=_preferences(films, config),
        excluded_screenings=frozenset(
            screening_id(film)
            for film in films
            if (film.title, film.date) in excluded_on_date
        ),
        seen_films=frozenset(s.title for s in seen if s.date is None),
    )


def _screening(film: Film) -> Screening:
    return Screening(
        id=screening_id(film),
        programme_entry_id=film.title,
        venue_id=film.cinema,
        start_time=film.start_time,
        end_time=film.end_time,
        auditorium=film.auditorium,
        ticket_url=film.ticket_url,
        events=(Event(film.special_notes),) if film.special_notes else (),
    )


def _route_table(config: Config, venue_ids: list[str]) -> RouteTable:
    """Configured travel times work in both directions unless the reverse is
    configured separately; unconfigured pairs get the legacy default."""
    minutes = {
        (t.from_cinema, t.to_cinema): t.minutes for t in config.cinemas.travel_times
    }
    for (a, b), m in list(minutes.items()):
        minutes.setdefault((b, a), m)
    for a, b in itertools.permutations(venue_ids, 2):
        minutes.setdefault((a, b), LEGACY_DEFAULT_TRAVEL_MINUTES)
    table = RouteTable()
    return RouteTable(
        routes=tuple(
            Route(a, b, table.default_mode, m)
            for (a, b), m in minutes.items()
            if a != b
        )
    )


def _preferences(films: list[Film], config: Config) -> Preferences:
    """Screening overrides beat title overrides, which beat a scraped
    `preference_weight`, matching the legacy precedence."""
    overrides = config.films.weights
    title_weights = {w.title: w.weight for w in overrides if w.start_time is None}
    start_weights = {
        (w.title, w.start_time): w.weight for w in overrides if w.start_time is not None
    }
    screening_weights: dict[str, float] = {}
    for film in films:
        if (film.title, film.start_time) in start_weights:
            screening_weights[screening_id(film)] = start_weights[
                (film.title, film.start_time)
            ]
        elif film.title not in title_weights and film.preference_weight != 1.0:
            screening_weights[screening_id(film)] = film.preference_weight

    return Preferences(
        buffer_minutes=config.schedule.buffer_time_minutes,
        start_date=config.schedule.start_date,
        end_date=config.schedule.end_date,
        programme_entry_weights=title_weights,
        screening_weights=screening_weights,
        year_weights=config.priority.year_weights,
        event_weight=config.priority.special_notes_weight,
    )
```

- [ ] **Step 4: Run the tests**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/yaml_files -q`
Expected: `6 passed`

- [ ] **Step 5: Format and commit**

Run: `mise exec -- uv run ruff format src/festival_planner/adapters/yaml_files`

```bash
jj commit -m "feat(adapters): build solve requests from legacy YAML files"
```

---

### Task 7: JSON solve-request files

Lets the CLI export a solve request and replay it later (e.g. a real User's Draft from the server, once that exists).

**Files:**
- Create: `src/festival_planner/adapters/json_files/__init__.py`
- Create: `src/festival_planner/adapters/json_files/solve_request.py`
- Create: `src/festival_planner/adapters/json_files/tests/__init__.py` (empty)
- Test: `src/festival_planner/adapters/json_files/tests/test_solve_request.py`

**Interfaces:**
- Consumes: `SolveRequest` and nested domain values; test builders.
- Produces: `dump_solve_request(request: SolveRequest, path: Path) -> None`; `load_solve_request(path: Path) -> SolveRequest`. Round-trips losslessly (frozensets, int-keyed mappings, datetimes, Events). Pydantic is used here only, through `TypeAdapter` over the stdlib dataclasses.

- [ ] **Step 1: Write the failing test**

Create `src/festival_planner/adapters/json_files/tests/__init__.py` (empty).

Create `src/festival_planner/adapters/json_files/tests/test_solve_request.py`:

```python
import datetime

from festival_planner.adapters.json_files.solve_request import (
    dump_solve_request,
    load_solve_request,
)
from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event
from festival_planner.domain.tests.builders import DAY, at, entry, request, screening
from festival_planner.domain.travel import Route


def test_round_trips_every_field(tmp_path):
    original = request(
        screening(
            "a", "14:00", "16:00", events=(Event("Panel", at("16:15"), at("17:00")),)
        ),
        screening("b", "18:00", "20:00", venue="B"),
        entries=(entry("a", year=1960), entry("b")),
        routes=(Route("A", "B", "bike", 8),),
        preferences=Preferences(
            buffer_minutes=10,
            venue_buffer_minutes={"A": 20},
            start_date=DAY,
            end_date=DAY + datetime.timedelta(days=2),
            programme_entry_weights={"a": 2.0},
            screening_weights={"b": 0.5},
            year_weights={1960: 0.3},
            event_weight=0.4,
            attend_events=True,
            transport_mode="bike",
        ),
        screening_commitments=frozenset({"a"}),
        film_commitments=frozenset({"b"}),
        excluded_screenings=frozenset({"x"}),
        excluded_programme_entries=frozenset({"y"}),
        seen_films=frozenset({"film-z"}),
        active_schedule=frozenset({"a"}),
        now=at("12:00"),
        time_limit_seconds=5.0,
    )
    path = tmp_path / "request.json"

    dump_solve_request(original, path)

    assert load_solve_request(path) == original
```

- [ ] **Step 2: Run it to verify it fails**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/json_files -q`
Expected: collection error, `ModuleNotFoundError: No module named 'festival_planner.adapters.json_files.solve_request'`.

- [ ] **Step 3: Implement the adapter**

Create `src/festival_planner/adapters/json_files/__init__.py`:

```python
"""Adapters for JSON files."""
```

Create `src/festival_planner/adapters/json_files/solve_request.py`:

```python
"""Save and load SolveRequests as JSON, for replaying solves in the CLI."""

from pathlib import Path

from pydantic import TypeAdapter

from ...domain.solving import SolveRequest

_ADAPTER = TypeAdapter(SolveRequest)


def dump_solve_request(request: SolveRequest, path: Path) -> None:
    path.write_bytes(_ADAPTER.dump_json(request, indent=2))


def load_solve_request(path: Path) -> SolveRequest:
    return _ADAPTER.validate_json(path.read_bytes())
```

- [ ] **Step 4: Run the test**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/json_files -q`
Expected: `1 passed`

- [ ] **Step 5: Format and commit**

Run: `mise exec -- uv run ruff format src/festival_planner/adapters/json_files`

```bash
jj commit -m "feat(adapters): save and load solve requests as JSON"
```

---

### Task 8: CLI `solve` on the solve request; remove the old solver

**Files:**
- Rewrite: `src/festival_planner/cli/solve.py`
- Create: `src/festival_planner/cli/tests/__init__.py` (empty)
- Test: `src/festival_planner/cli/tests/test_solve.py`
- Delete: `src/festival_planner/solver.py`
- Delete: `src/festival_planner/tests/test_weight_calculations.py` (superseded by `domain/tests/test_weights.py`)
- Modify: `src/festival_planner/models.py` (remove `ScheduledFilm`, the last class in the file)
- Modify: `README.md` (`### 2. Solve the Schedule` and `## How It Works`)

**Interfaces:**
- Consumes: `build_solve_request` (Task 6), `dump_solve_request` / `load_solve_request` (Task 7), `CpSatScheduleSolver` (Task 5), domain values.
- Produces: `festival-planner solve` with existing options (`--dates/-d`, `--output/-o`, `--time-limit/-t`, `--buffer/-b`) plus `--request PATH` (solve a JSON request instead of YAML) and `--export-request PATH` (write the request, after CLI overrides, before solving). Exits with code 1 and prints `No schedule found (<STATUS>)` and any reasons when unsolved. The Markdown output uses `- **Venue**:` and one `- **Event**: <description>` line per Event.

- [ ] **Step 1: Write the failing end-to-end tests**

Create `src/festival_planner/cli/tests/__init__.py` (empty).

Create `src/festival_planner/cli/tests/test_solve.py`:

```python
"""End-to-end tests of the `solve` command, from YAML files and JSON requests."""

import json

import pytest
from typer.testing import CliRunner

from festival_planner.cli import app

FILMS_YAML = """\
films:
  - title: "Early"
    country: "Norway"
    year: 1960
    start_time: "2025-11-08T14:00:00"
    end_time: "2025-11-08T16:00:00"
    cinema: "Vika"
  - title: "Clash"
    country: "Norway"
    start_time: "2025-11-08T15:00:00"
    end_time: "2025-11-08T17:00:00"
    cinema: "Vika"
  - title: "Late"
    country: "Sweden"
    start_time: "2025-11-08T19:00:00"
    end_time: "2025-11-08T21:00:00"
    cinema: "Vega"
    special_notes: "Director Q&A"
"""

CONFIG_YAML = """\
cinemas:
  travel_times:
    - from: "Vika"
      to: "Vega"
      minutes: 15
schedule:
  buffer_time_minutes: 15
priority:
  year_weights:
    1960: 0.5
"""


@pytest.fixture
def xdg(tmp_path, monkeypatch):
    """Isolated XDG directories holding the YAML inputs."""
    config_dir = tmp_path / "config" / "festival-planner"
    data_dir = tmp_path / "data" / "festival-planner"
    config_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(CONFIG_YAML)
    (data_dir / "films.yaml").write_text(FILMS_YAML)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_DIRS", str(tmp_path / "none"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "none"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_solves_from_yaml_and_writes_markdown(xdg):
    output = xdg / "schedule.md"

    result = CliRunner().invoke(app, ["solve", "--output", str(output)])

    assert result.exit_code == 0, result.output
    schedule = output.read_text()
    assert "### Early" in schedule
    assert "### Clash" not in schedule
    assert "### Late" in schedule
    assert "- **Event**: Director Q&A" in schedule


def test_exported_request_solves_identically(xdg):
    request_path = xdg / "request.json"
    first, second = xdg / "first.md", xdg / "second.md"

    exported = CliRunner().invoke(
        app, ["solve", "--export-request", str(request_path), "-o", str(first)]
    )
    replayed = CliRunner().invoke(
        app, ["solve", "--request", str(request_path), "-o", str(second)]
    )

    assert exported.exit_code == 0, exported.output
    assert replayed.exit_code == 0, replayed.output
    assert json.loads(request_path.read_text())["preferences"]["buffer_minutes"] == 15
    assert first.read_text() == second.read_text()


def test_infeasible_request_exits_with_error(xdg, tmp_path):
    request_path = xdg / "request.json"
    CliRunner().invoke(app, ["solve", "--export-request", str(request_path)])
    request = json.loads(request_path.read_text())
    request["screening_commitments"] = [s["id"] for s in request["screenings"]]
    request_path.write_text(json.dumps(request))

    result = CliRunner().invoke(app, ["solve", "--request", str(request_path)])

    assert result.exit_code == 1
    assert "No schedule found" in result.output
```

- [ ] **Step 2: Run them to verify they fail**

Run: `mise exec -- uv run pytest src/festival_planner/cli -q`
Expected: 3 failures. `test_solves_from_yaml_and_writes_markdown` exits with code 1: the old solver raises `TypeError: 'CpSolverStatus' object is not callable` under the locked OR-Tools 9.15, so the current `solve` command is already broken and this task fixes it. The other two exit with code 2 (`No such option: --export-request`).

- [ ] **Step 3: Rewrite `cli/solve.py`**

Replace the entire contents of `src/festival_planner/cli/solve.py` with:

```python
"""CLI commands for solving the festival scheduling optimization problem."""

import datetime
from collections import defaultdict
from dataclasses import dataclass, replace
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .._logging import get_logger
from ..adapters.json_files.solve_request import dump_solve_request, load_solve_request
from ..adapters.solver.cpsat import CpSatScheduleSolver
from ..adapters.yaml_files.solve_request import build_solve_request
from ..config import ConfigLoader
from ..domain.programme import ProgrammeEntry, Screening, Venue
from ..domain.solving import SolveRequest, SolveResult

console = Console()
logger = get_logger(__name__)
app = typer.Typer()


@dataclass(frozen=True)
class ScheduledRow:
    """A scheduled Screening with everything needed to display it."""

    screening: Screening
    entry: ProgrammeEntry
    venue: Venue
    arrival_time: datetime.datetime
    weight: float


def _scheduled_rows(request: SolveRequest, result: SolveResult) -> list[ScheduledRow]:
    screenings = {s.id: s for s in request.screenings}
    entries = {e.id: e for e in request.programme_entries}
    venues = {v.id: v for v in request.venues}
    rows = []
    for scheduled in result.scheduled:
        screening = screenings[scheduled.screening_id]
        rows.append(
            ScheduledRow(
                screening=screening,
                entry=entries[screening.programme_entry_id],
                venue=venues[screening.venue_id],
                arrival_time=scheduled.arrival_time,
                weight=scheduled.weight,
            )
        )
    return rows


def _link(text: str, url: str | None) -> Text:
    """Format text as a clickable link if a URL is available."""
    if url:
        return Text(text, style=f"link {url}")
    return Text(text)


def _parse_dates(dates: str) -> tuple[datetime.date, datetime.date]:
    """Parse `YYYY-MM-DD:YYYY-MM-DD` or a single `YYYY-MM-DD`."""
    start, _, end = dates.partition(":")
    return datetime.date.fromisoformat(start), datetime.date.fromisoformat(end or start)


def _apply_overrides(
    request: SolveRequest,
    *,
    dates: str | None,
    buffer_time: int | None,
    time_limit: int,
) -> SolveRequest:
    preferences = request.preferences
    if buffer_time is not None:
        preferences = replace(preferences, buffer_minutes=buffer_time)
    if dates:
        start, end = _parse_dates(dates)
        preferences = replace(preferences, start_date=start, end_date=end)
    return replace(request, preferences=preferences, time_limit_seconds=time_limit)


def _load_request_from_yaml() -> SolveRequest:
    loader = ConfigLoader()
    console.print("[bold blue]Loading configuration...[/bold blue]")
    config = loader.load_config()
    films = loader.load_films().films
    console.print(f"[green]Loaded {len(films)} film screenings[/green]")
    return build_solve_request(films, config)


@app.command()
def solve(
    dates: str | None = typer.Option(
        None,
        "--dates",
        "-d",
        help="Date range filter (format: YYYY-MM-DD:YYYY-MM-DD or single date)",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for schedule",
    ),
    time_limit: int = typer.Option(
        60,
        "--time-limit",
        "-t",
        help="Solver time limit in seconds",
    ),
    buffer_time: int | None = typer.Option(
        None,
        "--buffer",
        "-b",
        help="Buffer time before each film in minutes",
    ),
    request_file: Path | None = typer.Option(
        None,
        "--request",
        help="Solve a JSON solve request instead of the YAML configuration",
    ),
    export_request: Path | None = typer.Option(
        None,
        "--export-request",
        help="Write the solve request as JSON before solving",
    ),
) -> None:
    """Solve the scheduling optimization problem."""
    if request_file:
        request = load_solve_request(request_file)
        console.print(f"[green]Loaded solve request from {request_file}[/green]")
    else:
        request = _load_request_from_yaml()
    request = _apply_overrides(
        request, dates=dates, buffer_time=buffer_time, time_limit=time_limit
    )

    if export_request:
        dump_solve_request(request, export_request)
        console.print(f"[green]Solve request saved to {export_request}[/green]")

    console.print("[bold blue]Solving optimization problem...[/bold blue]")
    result = CpSatScheduleSolver().solve(request)

    if not result.is_solved:
        console.print(f"[bold red]No schedule found ({result.status})[/bold red]")
        for reason in result.reasons:
            console.print(f"  - {reason}")
        raise typer.Exit(code=1)

    rows = _scheduled_rows(request, result)
    console.print("[bold green]Solution found![/bold green]")
    console.print(f"Status: {result.status}")
    console.print(f"Objective value: {result.objective:.2f}")
    console.print(f"Solve time: {result.wall_time_seconds:.2f}s")
    console.print(f"Films scheduled: {len(rows)}")

    display_film_overview(request, rows)
    display_schedule(rows)

    if output:
        save_schedule_to_file(rows, output)
        console.print(f"[green]Schedule saved to {output}[/green]")


def display_film_overview(request: SolveRequest, rows: list[ScheduledRow]) -> None:
    """Display every Programme Entry with whether and when it is scheduled."""
    screenings_by_entry: defaultdict[str, list[Screening]] = defaultdict(list)
    for screening in request.screenings:
        screenings_by_entry[screening.programme_entry_id].append(screening)
    row_by_entry = {row.entry.id: row for row in rows}
    venues = {v.id: v for v in request.venues}

    console.print("\n[bold]Festival Overview[/bold]")
    console.print(f"Unique films: {len(request.programme_entries)}")
    console.print(f"Total screenings: {len(request.screenings)}")
    console.print(f"Films scheduled: [green]{len(rows)}[/green]")
    console.print(
        f"Films missed: [red]{len(request.programme_entries) - len(rows)}[/red]"
    )
    console.print()

    table = Table(title="All Films in Festival", box=box.MINIMAL)
    table.add_column("Status", justify="center", style="bold", width=8, no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Year", justify="center")
    table.add_column("Country", max_width=15, overflow="ellipsis", no_wrap=True)
    table.add_column("Screenings", justify="center")
    table.add_column("Date", style="cyan")
    table.add_column("Time", style="green")
    table.add_column("Venue", style="yellow")
    table.add_column("Events", style="dim")

    entries = sorted(request.programme_entries, key=lambda e: e.title)
    for idx, entry in enumerate(entries):
        row = row_by_entry.get(entry.id)
        screenings = screenings_by_entry[entry.id]
        shown = row.screening if row else screenings[0] if screenings else None
        status = Text.assemble(
            "✅" if row else "❌",
            " ",
            _link("🎬", entry.url),
            " ",
            _link("🎫", shown.ticket_url if shown else None),
        )
        if row:
            screening = row.screening
            date_str = screening.start_time.strftime("%a %d/%m")
            time_str = screening.start_time.strftime("%H:%M")
            venue_str = venues[screening.venue_id].name + (
                f" {screening.auditorium}" if screening.auditorium else ""
            )
            events_str = "; ".join(e.description for e in screening.events)
        else:
            date_str = time_str = venue_str = events_str = ""

        table.add_row(
            status,
            _link(entry.title, entry.url),
            str(entry.year) if entry.year else "",
            entry.country or "",
            str(len(screenings)),
            date_str,
            time_str,
            venue_str,
            events_str,
            style="dim" if idx % 2 == 1 else None,
        )

    console.print(table)
    console.print()


def _rows_by_date(
    rows: list[ScheduledRow],
) -> dict[datetime.date, list[ScheduledRow]]:
    by_date: defaultdict[datetime.date, list[ScheduledRow]] = defaultdict(list)
    for row in rows:
        by_date[row.screening.start_time.date()].append(row)
    return dict(sorted(by_date.items()))


def display_schedule(rows: list[ScheduledRow]) -> None:
    """Display the schedule as one table per day."""
    if not rows:
        console.print("[yellow]No films in schedule[/yellow]")
        return

    max_title_length = max(len(row.entry.title) for row in rows)

    for day, day_rows in _rows_by_date(rows).items():
        table = Table(title=f"Schedule for {day}", box=box.MINIMAL)
        table.add_column("Arrive", style="cyan")
        table.add_column("Start", style="green")
        table.add_column("End", style="red")
        table.add_column("Film", style="bold", min_width=max_title_length)
        table.add_column("Year", max_width=4, overflow="crop", no_wrap=True)
        table.add_column("Venue", style="yellow")
        table.add_column("Auditorium", style="magenta", no_wrap=True)
        table.add_column("Country", max_width=10, overflow="ellipsis", no_wrap=True)
        table.add_column("Weight", justify="right")

        for row in day_rows:
            screening = row.screening
            year_str = f"{row.entry.year:4d}" if row.entry.year else "    "
            table.add_row(
                row.arrival_time.strftime("%H:%M"),
                _link(screening.start_time.strftime("%H:%M"), screening.ticket_url),
                screening.end_time.strftime("%H:%M"),
                row.entry.title,
                _link(year_str, row.entry.url),
                row.venue.name,
                screening.auditorium or "",
                row.entry.country or "",
                f"{row.weight:+.1f}",
            )

        console.print(table)
        console.print()


def save_schedule_to_file(rows: list[ScheduledRow], filepath: Path) -> None:
    """Save the schedule as Markdown."""
    with open(filepath, "w") as f:
        f.write("# Festival Schedule\n\n")

        for day, day_rows in _rows_by_date(rows).items():
            f.write(f"## {day}\n\n")

            for row in day_rows:
                screening = row.screening
                title_md = (
                    f"[{row.entry.title}]({row.entry.url})"
                    if row.entry.url
                    else row.entry.title
                )
                f.write(f"### {title_md}\n")
                f.write(f"- **Arrive**: {row.arrival_time.strftime('%H:%M')}\n")
                f.write(f"- **Start**: {screening.start_time.strftime('%H:%M')}\n")
                f.write(f"- **End**: {screening.end_time.strftime('%H:%M')}\n")
                f.write(f"- **Venue**: {row.venue.name}\n")
                if screening.auditorium:
                    f.write(f"- **Auditorium**: {screening.auditorium}\n")
                if row.entry.country:
                    f.write(f"- **Country**: {row.entry.country}\n")
                for event in screening.events:
                    f.write(f"- **Event**: {event.description}\n")
                f.write(f"- **Weight**: {row.weight:+.1f}\n")
                f.write("\n")

            f.write("\n")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Remove the old solver and its leftovers**

```bash
rm src/festival_planner/solver.py src/festival_planner/tests/test_weight_calculations.py
```

In `src/festival_planner/models.py`, delete the whole `ScheduledFilm` class at the end of the file (from `class ScheduledFilm(BaseModel):` through its `calculated_weight` field), leaving a single trailing newline after `CinemaConfig.get_valid_cinemas`.

Then confirm nothing references them:

Run: `grep -rn "festival_planner.solver\|from \.\.solver\|from \.solver\|ScheduledFilm\|FestivalScheduleSolver" src`
Expected: no output.

- [ ] **Step 5: Run the whole suite**

Run: `mise exec -- uv run pytest -q`
Expected: `101 passed`

- [ ] **Step 6: Update the README**

In `README.md`, under `### 2. Solve the Schedule`, replace the `Options:` list with:

```markdown
Options:
- `--dates`, `-d`: Filter by date range (`YYYY-MM-DD:YYYY-MM-DD` or single date)
- `--output`, `-o`: Save schedule to file
- `--time-limit`, `-t`: Solver time limit in seconds (default: 60)
- `--buffer`, `-b`: Override buffer time in minutes
- `--export-request`: Save the solve request as JSON (after the overrides above)
- `--request`: Solve a saved JSON solve request instead of the YAML configuration
```

and add to the end of that section's `Examples:` code block:

```bash
# Capture a solve request and replay it while experimenting with the solver
mise exec -- festival-planner solve --export-request request.json
mise exec -- festival-planner solve --request request.json --buffer 10
```

Replace the body of `## How It Works` (up to `## Extending for Other Festivals`) with:

```markdown
The planner is built as ports and adapters (see `docs/adr/0001-hexagonal-architecture.md`).
The CLI turns the YAML files (or a saved JSON file) into a self-contained *solve request*;
the domain core applies the scheduling rules (`festival_planner.domain.solving.formulate`)
and a CP-SAT adapter optimises the result:

1. **Decision variables**: one boolean per candidate screening (attend or not)
2. **Objective**: maximise the sum of screening weights (default `1.0`, overridden per
   film or screening, plus year and event adjustments)
3. **Constraints**:
   - At most one screening per film
   - No two screenings unless the earlier one's end + travel time + buffer ≤ the later one's start
   - Seen films are excluded; committed screenings are required
```

- [ ] **Step 7: Smoke-test the CLI help**

Run: `mise exec -- uv run festival-planner solve --help`
Expected: the help lists `--request` and `--export-request`.

- [ ] **Step 8: Format and commit**

Run: `mise exec -- uv run ruff format src/festival_planner/cli`

```bash
jj commit -m "feat(cli): solve via the domain solve request; drop the old solver"
```

