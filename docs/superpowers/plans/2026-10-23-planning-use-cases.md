# Planning Use-Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a User plan a Festival through Drafts that are Change Sets: create, solve (deterministically, through a `JobRunner`), diff against the Active Schedule, accept, go Stale, re-solve and discard; plus Comparisons, Tickets, Seen (manual and inferred from the Active Schedule), flags, and a minimal `plan` CLI acting as a local User.

**Architecture:** Hexagonal, as in steps 1 and 2. The domain gains planning values (`Comparison`, `PlanningInputs`, `Ticket`, change-set items), change-set rules (`check`, `apply`, `rebase`), Bradley–Terry comparison bonuses in `formulate`, planning entities (`User`, `Draft`, `Schedule`), ports (`UserRepository`, `PlanningRepository`, `TicketRepository`, `SeenRepository`, `PlanningUnitOfWork`, `JobRunner`, `DraftSolvedNotifier`), pure read-side functions (diff, flags, comparison suggestions, inferred Seen) and a `Planner` holding the use-cases. Driven adapters: the CP-SAT solver becomes deterministic with a lexicographic tie-break; SQLAlchemy gets the planning tables (migration `0002`), repositories and WAL mode; `adapters/in_process/` holds the thread-pool and immediate job runners and a null notifier. The Typer CLI composes them as `festival-planner plan …`.

**Tech Stack:** Python 3.13, Pydantic 2, SQLAlchemy 2, Alembic, SQLite, OR-Tools CP-SAT, Typer, pytest. Tooling via `mise` + `uv`; version control is **jj**.

**Spec:** `docs/superpowers/specs/2026-10-23-graphql-backend-design.md`, sections *Planning*, *Seen and watch history* and roadmap step 3. Vocabulary: `GLOSSARY.md` (note **Change Set**, **Stale**, **Seen**, **Withdrawn**). Decisions: `docs/adr/0001` (hexagonal), `0002` (SQLite first, portable), `0003` (User keyed on issuer and subject), `0004` (Drafts are change sets; tie-break), `0005` (aware datetimes).

## Global Constraints

- `src/festival_planner/domain/` (tests included) imports only the stdlib, Pydantic and other domain modules. No SQLAlchemy, Alembic, OR-Tools, httpx, structlog or Typer. Use stdlib `logging` in the domain.
- Use glossary terms in code: User, Draft, Change Set, Stale, Active Schedule, Schedule, Screening Commitment, Film Commitment, Excluded, Comparison, Ticket, Seen, Withdrawn, Preferences. "Flag" is presentation language, not a glossary term.
- Domain values subclass `values.Value` (frozen Pydantic, `extra="forbid"`). Times are `pydantic.AwareDatetime`; stored as UTC via `UTCDateTime`.
- Ids are opaque strings, new ones from an injectable `new_id: Callable[[], str]` (default `domain.ingestion.new_id`, a UUID4). Time comes from an injectable `clock: Callable[[], datetime.datetime]` returning aware datetimes.
- A User is keyed on `(issuer, subject)`. The CLI acts as the User `("local", getpass.getuser())`, created on first use.
- Accepted inputs are a snapshot per (User, Festival); commitments, Preferences and Excluded change **only** by accepting a Draft. Tickets and Seen are edited directly, never through Change Sets.
- The Active Schedule is the (User, Festival) Schedule with the highest `number` (1, 2, … in acceptance order).
- Stale is derived (`draft.base_schedule_id != active schedule id`), never stored.
- Solving is deterministic: same request, same result. Ties break towards the Active Schedule, then lower Screening ids, without ever lowering the score.
- Schema stays dialect-neutral (ADR-0002): no `JSON`/array column types. Documents (Preferences, Change Sets, reasons) are Pydantic/`json` text in `Text` columns. Table names avoid reserved words (`app_user`, not `user`).
- Tests apply migrations with Alembic (`migrate(engine)`), never `metadata.create_all`. `test_migrations_match_the_table_definitions` must stay green.
- Tests live next to code in `tests/` sub-packages, each with an empty `__init__.py`.
- Run tests with `mise exec -- uv run pytest -q`; type-check with `mise exec -- uv run --with pyright pyright src` (0 errors at the end of every wave; between tasks of one wave, errors caused only by a sibling task's missing half are acceptable). Format only files you touched: `mise exec -- uv run ruff format <paths>`; don't fix unrelated pre-existing ruff findings.
- In isolated workspaces the shell refuses `cd x && …`: use absolute paths, `jj -R <ws> …` and `mise exec -C <ws> -- uv run --directory <ws> …`.
- Commit with `jj commit -m "<message>"` (Conventional Commits). Never `git commit`. Do not push. No commit trailers (no `Co-Authored-By`).

## Execution Waves

Tasks within a wave touch disjoint files, so each wave runs in parallel in isolated jj workspaces (`jj workspace add --name <n> -r <rev> /home/thor/dev/thor/festival-planner-ws/<n>`); results are rebased into one linear history on top of `main` between waves.

| Wave | In parallel | Depends on |
|------|-------------|------------|
| 1 | Task 1 (deterministic CP-SAT, tie-break) · Task 2 (planning values, comparison bonuses, request format version) · Task 3 (planning tables, migration 0002, WAL) · Task 4 (`JobRunner` port, in-process runners) | — |
| 2 | Task 5 (change-set rules) · Task 6 (User, Draft, Schedule, planning ports, fakes) · Task 7 (diff, flags, suggestions, inferred Seen) | Task 2 |
| 3 | Task 8 (`Planner` use-cases) · Task 9 (SQLAlchemy planning repositories) | waves 1–2 |
| 4 | Task 10 (`plan` CLI, null notifier, SQLite end-to-end) | wave 3 |

File ownership: Task 2 owns `domain/planning.py`, `domain/solving.py`, `domain/change_sets.py` (item values), `domain/comparisons.py`, `adapters/json_files/`, `cli/solve.py`; Task 5 appends the rules to `domain/change_sets.py` afterwards. Task 6 owns `domain/ingestion.py` port additions and `domain/tests/fakes.py` in wave 2; Task 8 appends to `fakes.py` in wave 3. Task 3 owns `tables.py`, `database.py`, migrations; Task 9 owns `repositories.py`, `planning_repositories.py`, `unit_of_work.py`.

## File Structure

```
src/festival_planner/
├── domain/
│   ├── planning.py                # MODIFY (T2) Comparison, Preferences.comparisons/comparison_weight, PlanningInputs, Ticket
│   ├── comparisons.py             # NEW (T2) comparison_bonuses (Bradley–Terry)
│   ├── solving.py                 # MODIFY (T2) format_version, bonuses in weights, score()
│   ├── change_sets.py             # NEW (T2) item values, ChangeSet; (T5) ProgrammeIndex, check/apply/rebase, problems
│   ├── jobs.py                    # NEW (T4) Job, JobRunner ports
│   ├── users.py                   # NEW (T6) User, UserRepository, user_for
│   ├── drafts.py                  # NEW (T6) DraftStatus, Draft, Schedule
│   ├── planning_ports.py          # NEW (T6) PlanningRepository, TicketRepository, SeenRepository, DraftSolvedNotifier, PlanningUnitOfWork
│   ├── ingestion.py               # MODIFY (T6) FestivalRepository.by_id, FilmRepository.by_id, ProgrammeRepository.screenings_by_id/entries_by_id
│   ├── insights.py                # NEW (T7) DraftDiff/diff, Flag/flags, ComparisonSuggestion/suggest_comparisons, inferred_seen
│   ├── planner.py                 # NEW (T8) Planner, DraftView, errors
│   └── tests/ fakes.py (T6, T8), test_*.py
├── adapters/
│   ├── solver/cpsat.py            # MODIFY (T1)
│   ├── json_files/solve_request.py  # MODIFY (T2) version check
│   ├── in_process/                # NEW (T4) jobs.py; (T10) notifications.py
│   └── sqlalchemy/
│       ├── database.py            # MODIFY (T3) WAL, busy timeout
│       ├── tables.py              # MODIFY (T3) planning tables
│       ├── migrations/versions/0002_planning.py   # NEW (T3)
│       ├── repositories.py        # MODIFY (T9) by_id, screenings_by_id, entries_by_id
│       ├── planning_repositories.py  # NEW (T9)
│       └── unit_of_work.py        # MODIFY (T9) users, planning, tickets, seen
└── cli/
    ├── __init__.py                # MODIFY (T10) register plan
    ├── solve.py                   # MODIFY (T2) unsupported format message
    ├── plan.py                    # NEW (T10)
    └── tests/test_plan.py         # NEW (T10)
```

---

### Task 1: Deterministic CP-SAT solving with a lexicographic tie-break

**Files:**
- Modify: `src/festival_planner/adapters/solver/cpsat.py`
- Test: `src/festival_planner/adapters/solver/tests/test_cpsat.py`

**Interfaces:**
- Consumes: `formulate`, `SolveRequest` (`active_schedule`, `time_limit_seconds`), as today.
- Produces: `CpSatScheduleSolver.solve` is deterministic. `time_limit_seconds` is applied as CP-SAT's `max_deterministic_time`. Module constants `RANDOM_SEED = 0`, `NUM_WORKERS = 8`.

CP-SAT is deterministic with a fixed `random_seed` and `interleave_search = True` (“the search is deterministic, independently of num_workers”), provided the limit is deterministic time rather than wall time. The tie-break is a second solve: keep the primary objective at least at the first pass's value, then maximise `n² · [in Active Schedule] + (n − rank(id))`, where `rank` orders candidate ids ascending and `n` is the number of candidates. Since `Σ(n − rank) < n²`, one more Active Screening always beats any id preference, and neither ever costs score.

- [ ] **Step 1: Write the failing tests** (append to `test_cpsat.py`)

```python
def test_identical_requests_give_identical_schedules():
    screenings = [
        screening(f"s{i:02}", f"{10 + i % 8}:00", f"{11 + i % 8}:30", venue="AB"[i % 2])
        for i in range(24)
    ]
    routes = (
        Route(from_venue_id="A", to_venue_id="B", mode=DEFAULT_TRANSPORT_MODE, minutes=10),
        Route(from_venue_id="B", to_venue_id="A", mode=DEFAULT_TRANSPORT_MODE, minutes=10),
    )
    first = solver.solve(request(*screenings, routes=routes))
    for _ in range(3):
        assert solver.solve(request(*screenings, routes=routes)).scheduled == first.scheduled


def test_ties_break_towards_lower_screening_ids():
    result = solver.solve(
        request(screening("b", "14:00", "16:00"), screening("a", "14:00", "16:00"))
    )
    assert scheduled_ids(result) == ["a"]


def test_ties_break_towards_the_active_schedule_before_ids():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening("b", "14:00", "16:00"),
            active_schedule=frozenset({"b"}),
        )
    )
    assert scheduled_ids(result) == ["b"]


def test_tie_break_never_costs_score():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            preferences=Preferences(buffer_minutes=0, programme_entry_weights={"a": 2.0}),
            active_schedule=frozenset({"b"}),
        )
    )
    assert scheduled_ids(result) == ["a"]
    assert result.objective == 2.0
```

Add imports: `from festival_planner.domain.travel import DEFAULT_TRANSPORT_MODE, Route`.

- [ ] **Step 2: Run them to verify the tie-break tests fail**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/solver/tests/test_cpsat.py -q`
Expected: at least `test_ties_break_towards_the_active_schedule_before_ids` FAILS (no tie-break yet); the others may pass by chance.

- [ ] **Step 3: Implement** (replace the body of `solve` after the model is built)

```python
RANDOM_SEED = 0
NUM_WORKERS = 8


def _solver(time_limit_seconds: float) -> cp_model.CpSolver:
    """A CP-SAT solver whose result depends only on the model."""
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = RANDOM_SEED
    solver.parameters.num_workers = NUM_WORKERS
    solver.parameters.interleave_search = True
    solver.parameters.max_deterministic_time = time_limit_seconds
    return solver
```

In `CpSatScheduleSolver.solve`, keep the formulation and constraints, then:

```python
        ids = sorted(formulation.weights)
        objective = cp_model.LinearExpr.weighted_sum(
            [attend[i] for i in ids],
            [round(formulation.weights[i] * WEIGHT_PRECISION_MULTIPLIER) for i in ids],
        )
        model.maximize(objective)

        solver = _solver(request.time_limit_seconds)
        status = _STATUSES.get(solver.solve(model))
        if status is None:
            raise RuntimeError(f"CP-SAT failed: {solver.status_name()}")
        if status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
            return SolveResult(status=status, wall_time_seconds=solver.wall_time)
        wall_time = solver.wall_time

        # Among Schedules at least as good, prefer the Active Schedule, then
        # lower Screening ids; this never lowers the score.
        model.add(objective >= round(solver.objective_value))
        for i in ids:
            model.add_hint(attend[i], solver.boolean_value(attend[i]))
        n = len(ids)
        model.maximize(
            cp_model.LinearExpr.weighted_sum(
                [attend[i] for i in ids],
                [
                    (n * n if i in request.active_schedule else 0) + (n - rank)
                    for rank, i in enumerate(ids)
                ],
            )
        )
        tie_break = _solver(request.time_limit_seconds)
        if _STATUSES.get(tie_break.solve(model)) in (
            SolveStatus.OPTIMAL,
            SolveStatus.FEASIBLE,
        ):
            solver, wall_time = tie_break, wall_time + tie_break.wall_time
```

and build the result from `solver` as before, except the objective is recomputed from the chosen Screenings (the second solver's objective is the tie-break):

```python
        chosen = [s for s in formulation.candidates if solver.boolean_value(attend[s.id])]
        scheduled = tuple(
            ScheduledScreening(
                screening_id=s.id,
                arrival_time=s.starts_at(include_events=preferences.attend_events)
                - datetime.timedelta(minutes=preferences.buffer_for(s.venue_id)),
                weight=formulation.weights[s.id],
            )
            for s in sorted(chosen, key=lambda s: (s.start_time, s.id))
        )
        return SolveResult(
            status=status,
            scheduled=scheduled,
            objective=sum(formulation.weights[s.id] for s in chosen),
            wall_time_seconds=wall_time,
        )
```

- [ ] **Step 4: Run the solver tests**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/solver -q`
Expected: all PASS. If `objective` comparisons fail by float error in existing tests, round with `round(..., 6)` in the result.

- [ ] **Step 5: Full suite, pyright, format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src
mise exec -- uv run ruff format src/festival_planner/adapters/solver
jj commit -m "feat(solver): deterministic CP-SAT with a tie-break towards the Active Schedule"
```

---

### Task 2: Planning values, comparison bonuses and the solve-request format version

**Files:**
- Modify: `src/festival_planner/domain/planning.py`, `domain/solving.py`, `adapters/json_files/solve_request.py`, `cli/solve.py`
- Create: `src/festival_planner/domain/comparisons.py`, `src/festival_planner/domain/change_sets.py`
- Test: `domain/tests/test_planning.py`, `domain/tests/test_comparisons.py` (new), `domain/tests/test_weights.py`, `domain/tests/test_change_set_items.py` (new), `adapters/json_files/tests/test_solve_request.py`

**Interfaces:**
- Produces (`domain/planning.py`):
  - `Comparison(preferred: ProgrammeEntryId, other: ProgrammeEntryId)`, rejects `preferred == other`; property `pair -> frozenset[ProgrammeEntryId]`.
  - `Preferences.comparison_weight: float = 0.5`; `Preferences.comparisons: tuple[Comparison, ...] = ()`, at most one per pair, normalised to sorted `(preferred, other)` order.
  - `PlanningInputs(screening_commitments, film_commitments, excluded_screenings, excluded_programme_entries: frozenset[...] = frozenset(), preferences: Preferences = Preferences())`.
  - `Ticket(screening_id: ScreeningId, exchangeable: bool = False, refundable: bool = False)`.
- Produces (`domain/comparisons.py`): `comparison_bonuses(comparisons: Iterable[Comparison], weight: float) -> dict[ProgrammeEntryId, float]`.
- Produces (`domain/solving.py`): `SOLVE_REQUEST_FORMAT_VERSION = 1`; `SolveRequest.format_version: Literal[1] = 1`; `screening_weight(screening, entry, preferences, bonuses: Mapping[ProgrammeEntryId, float] | None = None)`; `score(request: SolveRequest, screening_ids: Iterable[ScreeningId]) -> float`.
- Produces (`adapters/json_files/solve_request.py`): `UnsupportedFormatError(ValueError)` raised by `load_solve_request` for another version.
- Produces (`domain/change_sets.py`): the item values below, `ChangeSetItem` (discriminated union on `kind`), `ChangeSet(items: tuple[ChangeSetItem, ...] = ())`.

- [ ] **Step 1: Write the failing tests**

`domain/tests/test_planning.py` (add):

```python
import pytest
from pydantic import ValidationError

from festival_planner.domain.planning import Comparison, PlanningInputs, Preferences, Ticket


def test_a_comparison_needs_two_entries():
    with pytest.raises(ValidationError):
        Comparison(preferred="a", other="a")


def test_one_comparison_per_pair():
    with pytest.raises(ValidationError):
        Preferences(
            comparisons=(Comparison(preferred="a", other="b"), Comparison(preferred="b", other="a"))
        )


def test_comparisons_are_kept_in_a_stable_order():
    one = Preferences(comparisons=(Comparison(preferred="c", other="d"), Comparison(preferred="a", other="b")))
    other = Preferences(comparisons=(Comparison(preferred="a", other="b"), Comparison(preferred="c", other="d")))
    assert one == other


def test_preferences_round_trip_through_json():
    preferences = Preferences(
        year_weights={2025: 0.2},
        venue_buffer_minutes={"v": 5},
        comparisons=(Comparison(preferred="a", other="b"),),
    )
    assert Preferences.model_validate_json(preferences.model_dump_json()) == preferences


def test_empty_planning_inputs_have_default_preferences():
    assert PlanningInputs().preferences == Preferences()
    assert PlanningInputs().screening_commitments == frozenset()


def test_tickets_are_neither_exchangeable_nor_refundable_by_default():
    ticket = Ticket(screening_id="s")
    assert (ticket.exchangeable, ticket.refundable) == (False, False)
```

`domain/tests/test_comparisons.py`:

```python
import pytest

from festival_planner.domain.comparisons import comparison_bonuses
from festival_planner.domain.planning import Comparison


def over(a: str, b: str) -> Comparison:
    return Comparison(preferred=a, other=b)


def test_no_comparisons_no_bonuses():
    assert comparison_bonuses((), 0.5) == {}


def test_the_preferred_entry_gains_what_the_other_loses():
    bonuses = comparison_bonuses([over("a", "b")], 0.5)
    assert bonuses["a"] > 0 > bonuses["b"]
    assert bonuses["a"] == pytest.approx(-bonuses["b"])


def test_a_chain_orders_the_bonuses():
    bonuses = comparison_bonuses([over("a", "b"), over("b", "c")], 1.0)
    assert bonuses["a"] > bonuses["b"] > bonuses["c"]


def test_a_cycle_cancels_out():
    bonuses = comparison_bonuses([over("a", "b"), over("b", "c"), over("c", "a")], 1.0)
    assert bonuses == pytest.approx({"a": 0.0, "b": 0.0, "c": 0.0})


def test_bonuses_scale_with_the_comparison_weight():
    assert comparison_bonuses([over("a", "b")], 0.0) == {"a": 0.0, "b": 0.0}
    one = comparison_bonuses([over("a", "b")], 1.0)
    two = comparison_bonuses([over("a", "b")], 2.0)
    assert two["a"] == pytest.approx(2 * one["a"])


def test_bonuses_do_not_depend_on_input_order():
    comparisons = [over("a", "b"), over("c", "b"), over("a", "c")]
    assert comparison_bonuses(comparisons, 1.0) == comparison_bonuses(reversed(comparisons), 1.0)
```

`domain/tests/test_weights.py` (add):

```python
from festival_planner.domain.planning import Comparison
from festival_planner.domain.solving import formulate, score


def test_comparisons_shift_programme_entry_weights():
    req = request(
        screening("a", "14:00", "16:00"),
        screening("b", "18:00", "20:00"),
        preferences=Preferences(
            buffer_minutes=0, comparisons=(Comparison(preferred="b", other="a"),)
        ),
    )
    weights = formulate(req).weights
    assert weights["b"] > 1.0 > weights["a"]


def test_score_sums_the_weights_of_known_screenings():
    req = request(
        screening("a", "14:00", "16:00"),
        screening("b", "18:00", "20:00"),
        preferences=Preferences(buffer_minutes=0, programme_entry_weights={"b": 3.0}),
    )
    assert score(req, {"a", "b", "unknown"}) == 4.0
```

`domain/tests/test_change_set_items.py`:

```python
import datetime

import pytest
from pydantic import ValidationError

from festival_planner.domain.change_sets import (
    AddScreeningCommitment,
    ChangeSet,
    RecordComparison,
    SetBuffer,
    SetDateRange,
    SetYearWeight,
)


def test_change_sets_round_trip_through_json_by_kind():
    change_set = ChangeSet(
        items=(
            AddScreeningCommitment(screening_id="s"),
            SetYearWeight(year=2025, weight=0.2),
            SetBuffer(venue_id="v", minutes=5),
            RecordComparison(preferred="a", other="b"),
        )
    )
    dumped = change_set.model_dump_json()
    assert '"kind":"add_screening_commitment"' in dumped
    assert ChangeSet.model_validate_json(dumped) == change_set


def test_items_are_validated_from_plain_data():
    change_set = ChangeSet.model_validate(
        {"items": [{"kind": "add_film_commitment", "programme_entry_id": "e"}]}
    )
    assert change_set.items[0].kind == "add_film_commitment"


def test_unknown_kinds_are_rejected():
    with pytest.raises(ValidationError):
        ChangeSet.model_validate({"items": [{"kind": "teleport"}]})


def test_a_date_range_cannot_end_before_it_starts():
    with pytest.raises(ValidationError):
        SetDateRange(start_date=datetime.date(2025, 11, 9), end_date=datetime.date(2025, 11, 8))


def test_negative_buffers_are_rejected():
    with pytest.raises(ValidationError):
        SetBuffer(minutes=-1)
```

`adapters/json_files/tests/test_solve_request.py` (add):

```python
from festival_planner.adapters.json_files.solve_request import UnsupportedFormatError


def test_exported_requests_carry_their_format_version(tmp_path):
    path = tmp_path / "request.json"
    dump_solve_request(request(screening("a", "14:00", "16:00")), path)
    assert json.loads(path.read_text())["format_version"] == 1


def test_requests_without_a_version_are_version_one(tmp_path):
    path = tmp_path / "request.json"
    dump_solve_request(request(screening("a", "14:00", "16:00")), path)
    data = json.loads(path.read_text())
    del data["format_version"]
    path.write_text(json.dumps(data))
    assert load_solve_request(path).format_version == 1


def test_other_versions_are_refused_clearly(tmp_path):
    path = tmp_path / "request.json"
    dump_solve_request(request(screening("a", "14:00", "16:00")), path)
    data = json.loads(path.read_text())
    data["format_version"] = 2
    path.write_text(json.dumps(data))
    with pytest.raises(UnsupportedFormatError, match="version 2"):
        load_solve_request(path)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `mise exec -- uv run pytest src/festival_planner/domain src/festival_planner/adapters/json_files -q`
Expected: FAIL on imports (`Comparison`, `comparison_bonuses`, `change_sets`, `score`, `UnsupportedFormatError`).

- [ ] **Step 3: Implement `domain/planning.py`**

Add before `Preferences`:

```python
class Comparison(Value):
    """A User's statement that they would rather watch `preferred` than `other`."""

    preferred: ProgrammeEntryId
    other: ProgrammeEntryId

    @model_validator(mode="after")
    def _compares_two_entries(self) -> Self:
        if self.preferred == self.other:
            raise ValueError(f"Cannot compare {self.preferred!r} with itself")
        return self

    @property
    def pair(self) -> frozenset[ProgrammeEntryId]:
        return frozenset((self.preferred, self.other))
```

Add to `Preferences` (after `transport_mode`):

```python
    comparison_weight: float = 0.5
    """How strongly Comparisons shift Programme Entry weights."""
    comparisons: tuple[Comparison, ...] = ()

    @field_validator("comparisons")
    @classmethod
    def _one_comparison_per_pair(
        cls, comparisons: tuple[Comparison, ...]
    ) -> tuple[Comparison, ...]:
        pairs: set[frozenset[str]] = set()
        for comparison in comparisons:
            if comparison.pair in pairs:
                raise ValueError(
                    f"Several comparisons of {sorted(comparison.pair)}"
                )
            pairs.add(comparison.pair)
        return tuple(sorted(comparisons, key=lambda c: (c.preferred, c.other)))
```

Add after `Preferences`:

```python
class PlanningInputs(Value):
    """A User's accepted commitments, Excluded and Preferences for one Festival."""

    screening_commitments: frozenset[ScreeningId] = frozenset()
    film_commitments: frozenset[ProgrammeEntryId] = frozenset()
    excluded_screenings: frozenset[ScreeningId] = frozenset()
    excluded_programme_entries: frozenset[ProgrammeEntryId] = frozenset()
    preferences: Preferences = Field(default_factory=Preferences)


class Ticket(Value):
    """A User's record that they hold a ticket for a Screening."""

    screening_id: ScreeningId
    exchangeable: bool = False
    refundable: bool = False
```

Update the module docstring to `"""A User's planning inputs: Preferences, Comparisons, commitments and Tickets."""` and imports (`Self`, `field_validator`, `model_validator`).

- [ ] **Step 4: Implement `domain/comparisons.py`**

```python
"""Turning Comparisons into weights with a Bradley–Terry model."""

import math
from collections import Counter, defaultdict
from collections.abc import Iterable

from .planning import Comparison
from .programme import ProgrammeEntryId

ITERATIONS = 1000
TOLERANCE = 1e-12


def comparison_bonuses(
    comparisons: Iterable[Comparison], weight: float
) -> dict[ProgrammeEntryId, float]:
    """Weight bonuses for the compared Programme Entries.

    Fits Bradley–Terry strengths by minorisation–maximisation. A weak prior,
    one win and one loss against a virtual entry of strength 1, keeps the
    strengths finite for unbeaten entries. The bonus is `weight` times the
    log-strength, centred so the bonuses sum to zero. Entries are processed in
    sorted order, so the result does not depend on input order.
    """
    comparisons = tuple(comparisons)
    games: defaultdict[str, Counter[str]] = defaultdict(Counter)
    wins: Counter[str] = Counter()
    for c in comparisons:
        games[c.preferred][c.other] += 1
        games[c.other][c.preferred] += 1
        wins[c.preferred] += 1
    entries = sorted(games)
    if not entries:
        return {}
    strength = dict.fromkeys(entries, 1.0)
    for _ in range(ITERATIONS):
        updated = {
            i: (wins[i] + 1)
            / (
                2 / (strength[i] + 1.0)
                + sum(
                    n / (strength[i] + strength[j])
                    for j, n in sorted(games[i].items())
                )
            )
            for i in entries
        }
        change = max(abs(updated[i] - strength[i]) for i in entries)
        strength = updated
        if change < TOLERANCE:
            break
    logs = {i: math.log(strength[i]) for i in entries}
    mean = sum(logs.values()) / len(logs)
    return {i: weight * (logs[i] - mean) for i in entries}
```

- [ ] **Step 5: Implement `domain/solving.py` changes**

```python
SOLVE_REQUEST_FORMAT_VERSION = 1
"""Bumped whenever an exported SolveRequest would no longer load."""
```

In `SolveRequest`, first field:

```python
    format_version: Literal[1] = SOLVE_REQUEST_FORMAT_VERSION
    """Exported requests carry this so replays fail clearly after changes."""
```

and change the `time_limit_seconds` docstring to: `"""CP-SAT deterministic time limit (roughly seconds)."""`.

`screening_weight` gains `bonuses: Mapping[ProgrammeEntryId, float] | None = None` and adds `weight += (bonuses or {}).get(entry.id, 0.0)` after the year weight; docstring: "Year, Event and Comparison weights are added on top." In `formulate`, compute once:

```python
    bonuses = comparison_bonuses(preferences.comparisons, preferences.comparison_weight)
```

and pass `bonuses` to every `screening_weight` call. Add:

```python
def score(request: SolveRequest, screening_ids: Iterable[ScreeningId]) -> float:
    """What attending `screening_ids` is worth under the request's Preferences.

    Ids the request does not know count for nothing.
    """
    preferences = request.preferences
    entries = {e.id: e for e in request.programme_entries}
    screenings = {s.id: s for s in request.screenings}
    bonuses = comparison_bonuses(preferences.comparisons, preferences.comparison_weight)
    return sum(
        screening_weight(
            screenings[i], entries[screenings[i].programme_entry_id], preferences, bonuses
        )
        for i in sorted(set(screening_ids))
        if i in screenings
    )
```

- [ ] **Step 6: Implement `domain/change_sets.py` (item values only)**

```python
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
```

- [ ] **Step 7: Implement the version check**

`adapters/json_files/solve_request.py`:

```python
"""Save and load SolveRequests as JSON, for replaying solves in the CLI."""

import json
from pathlib import Path

from ...domain.solving import SOLVE_REQUEST_FORMAT_VERSION, SolveRequest


class UnsupportedFormatError(ValueError):
    """The file is a solve request in a format this version cannot read."""


def dump_solve_request(request: SolveRequest, path: Path) -> None:
    path.write_text(request.model_dump_json(indent=2))


def load_solve_request(path: Path) -> SolveRequest:
    """Requests exported before versioning count as version 1."""
    raw = path.read_bytes()
    data = json.loads(raw)
    version = (
        data.get("format_version", SOLVE_REQUEST_FORMAT_VERSION)
        if isinstance(data, dict)
        else None
    )
    if version != SOLVE_REQUEST_FORMAT_VERSION:
        raise UnsupportedFormatError(
            f"{path} is solve request format version {version!r}; "
            f"this version reads {SOLVE_REQUEST_FORMAT_VERSION}"
        )
    return SolveRequest.model_validate_json(raw)
```

In `cli/solve.py`, wrap `load_solve_request(request_file)`:

```python
        try:
            request = load_solve_request(request_file)
        except UnsupportedFormatError as e:
            console.print(f"[bold red]{e}[/bold red]", soft_wrap=True)
            raise typer.Exit(code=2) from e
```

- [ ] **Step 8: Run tests, pyright, format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src
mise exec -- uv run ruff format src/festival_planner/domain/planning.py src/festival_planner/domain/comparisons.py src/festival_planner/domain/solving.py src/festival_planner/domain/change_sets.py src/festival_planner/adapters/json_files src/festival_planner/cli/solve.py src/festival_planner/domain/tests
jj commit -m "feat(domain): Comparisons, planning inputs, Tickets, change-set items and a solve request format version"
```

---

### Task 3: Planning tables, migration 0002 and SQLite WAL mode

**Files:**
- Modify: `src/festival_planner/adapters/sqlalchemy/tables.py`, `adapters/sqlalchemy/database.py`
- Create: `src/festival_planner/adapters/sqlalchemy/migrations/versions/0002_planning.py` (autogenerated)
- Test: `adapters/sqlalchemy/tests/test_database.py`, `adapters/sqlalchemy/tests/test_tables.py`

**Interfaces:**
- Produces rows (all in `tables.py`): `UserRow` (`app_user`), `PlanningInputsRow` (`planning_inputs`), `PlanningTargetRow` (`planning_target`), `ScheduleRow` (`schedule`) with `screenings: list[ScheduleScreeningRow]`, `ScheduleScreeningRow` (`schedule_screening`), `DraftRow` (`draft`) with `scheduled: list[DraftScreeningRow]`, `DraftScreeningRow` (`draft_screening`), `TicketRow` (`ticket`), `SeenRow` (`seen`), `SeenDismissalRow` (`seen_dismissal`). Constants `PLANNING_TARGET_KINDS` = the four `PlanningInputs` set field names.
- Produces: `create_engine_for` sets, for SQLite, `PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`, `PRAGMA journal_mode=WAL`.

- [ ] **Step 1: Write the failing tests**

`test_database.py`: extend the expected table set in `test_migrate_creates_every_table` with `"app_user", "planning_inputs", "planning_target", "schedule", "schedule_screening", "draft", "draft_screening", "ticket", "seen", "seen_dismissal"`, and add:

```python
def test_sqlite_runs_in_wal_mode_with_a_busy_timeout(engine):
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
```

`test_tables.py` (add):

```python
def test_a_user_is_unique_per_issuer_and_subject(engine):
    with Session(engine) as session:
        session.add_all(
            [
                UserRow(id="u1", issuer="local", subject="thor"),
                UserRow(id="u2", issuer="local", subject="thor"),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_a_schedule_number_is_unique_per_user_and_festival(engine):
    with Session(engine) as session:
        session.add(UserRow(id="u", issuer="local", subject="thor"))
        session.add(
            FestivalRow(
                id="f", slug="f", name="F", time_zone="Europe/Oslo",
                start_date=datetime.date(2025, 11, 1), end_date=datetime.date(2025, 11, 9),
            )
        )
        session.flush()
        now = datetime.datetime(2025, 11, 1, tzinfo=datetime.UTC)
        for schedule_id in ("s1", "s2"):
            session.add(
                ScheduleRow(
                    id=schedule_id, user_id="u", festival_id="f", number=1,
                    score=0.0, change_set="{}", accepted_at=now,
                )
            )
        with pytest.raises(IntegrityError):
            session.commit()
```

(add `UserRow`, `ScheduleRow`, `FestivalRow`, `Session`, `IntegrityError` imports as needed.)

- [ ] **Step 2: Run them to verify they fail**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/sqlalchemy -q`
Expected: FAIL (missing rows, journal mode `delete`).

- [ ] **Step 3: WAL and busy timeout in `database.py`**

```python
SQLITE_BUSY_TIMEOUT_MS = 5000


def create_engine_for(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _configure_sqlite)
    return engine


def _configure_sqlite(dbapi_connection, _record) -> None:
    """Enforce foreign keys; let readers and one writer work concurrently."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()
```

- [ ] **Step 4: Planning rows in `tables.py`** (append; add `Boolean`, `Float`, `Text` imports)

```python
PLANNING_TARGET_KINDS = (
    "screening_commitments",
    "film_commitments",
    "excluded_screenings",
    "excluded_programme_entries",
)
"""`PlanningTargetRow.kind` values: the set fields of `PlanningInputs`."""


class UserRow(Base):
    __tablename__ = "app_user"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    issuer: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    __table_args__ = (UniqueConstraint("issuer", "subject"),)


class PlanningInputsRow(Base):
    __tablename__ = "planning_inputs"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    festival_id: Mapped[str] = mapped_column(ForeignKey("festival.id"), primary_key=True)
    preferences: Mapped[str] = mapped_column(Text)
    """`Preferences` as JSON."""


class PlanningTargetRow(Base):
    """One commitment or Excluded id of a User's accepted inputs."""

    __tablename__ = "planning_target"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    festival_id: Mapped[str] = mapped_column(ForeignKey("festival.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String, primary_key=True)
    target_id: Mapped[str] = mapped_column(ID, primary_key=True)


class ScheduleRow(Base):
    __tablename__ = "schedule"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    festival_id: Mapped[str] = mapped_column(ForeignKey("festival.id"))
    number: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    change_set: Mapped[str] = mapped_column(Text)
    """`ChangeSet` as JSON."""
    accepted_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    screenings: Mapped[list["ScheduleScreeningRow"]] = relationship(
        cascade="all, delete-orphan", order_by="ScheduleScreeningRow.screening_id"
    )
    __table_args__ = (UniqueConstraint("user_id", "festival_id", "number"),)


class ScheduleScreeningRow(Base):
    __tablename__ = "schedule_screening"
    schedule_id: Mapped[str] = mapped_column(
        ForeignKey("schedule.id", ondelete="CASCADE"), primary_key=True
    )
    screening_id: Mapped[str] = mapped_column(ForeignKey("screening.id"), primary_key=True)


class DraftRow(Base):
    __tablename__ = "draft"
    id: Mapped[str] = mapped_column(ID, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    festival_id: Mapped[str] = mapped_column(ForeignKey("festival.id"))
    base_schedule_id: Mapped[str | None] = mapped_column(ForeignKey("schedule.id"))
    status: Mapped[str] = mapped_column(String)
    attempt: Mapped[int] = mapped_column(Integer)
    change_set: Mapped[str] = mapped_column(Text)
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[str] = mapped_column(Text)
    """JSON list of strings."""
    notes: Mapped[str] = mapped_column(Text)
    """JSON list of strings."""
    created_at: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    solved_at: Mapped[datetime.datetime | None] = mapped_column(UTCDateTime)
    scheduled: Mapped[list["DraftScreeningRow"]] = relationship(
        cascade="all, delete-orphan", order_by="DraftScreeningRow.position"
    )
    __table_args__ = (Index("ix_draft_user_id_festival_id", "user_id", "festival_id"),)


class DraftScreeningRow(Base):
    __tablename__ = "draft_screening"
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("draft.id", ondelete="CASCADE"), primary_key=True
    )
    screening_id: Mapped[str] = mapped_column(ForeignKey("screening.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    arrival_time: Mapped[datetime.datetime] = mapped_column(UTCDateTime)
    weight: Mapped[float] = mapped_column(Float)


class TicketRow(Base):
    __tablename__ = "ticket"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    screening_id: Mapped[str] = mapped_column(ForeignKey("screening.id"), primary_key=True)
    exchangeable: Mapped[bool] = mapped_column(Boolean)
    refundable: Mapped[bool] = mapped_column(Boolean)


class SeenRow(Base):
    """A Film a User marked Seen by hand (or, later, by provider sync)."""

    __tablename__ = "seen"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    film_id: Mapped[str] = mapped_column(ForeignKey("film.id"), primary_key=True)
    source: Mapped[str] = mapped_column(String)


class SeenDismissalRow(Base):
    """A Screening the User did not attend, though it was in their Active Schedule."""

    __tablename__ = "seen_dismissal"
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), primary_key=True)
    screening_id: Mapped[str] = mapped_column(ForeignKey("screening.id"), primary_key=True)
```

- [ ] **Step 5: Generate the migration**

```bash
rm -f /tmp/fp-autogen.db  # use the workspace's own scratch path if /tmp is shared
FESTIVAL_PLANNER_DATABASE_URL=sqlite:////home/thor/dev/thor/festival-planner-ws/<ws>/autogen.db mise exec -- uv run alembic upgrade head
FESTIVAL_PLANNER_DATABASE_URL=sqlite:////home/thor/dev/thor/festival-planner-ws/<ws>/autogen.db mise exec -- uv run alembic revision --autogenerate --rev-id 0002 -m "planning"
```

Rename the generated file to `0002_planning.py` if needed, check it creates exactly the ten tables (with `op.f(...)` constraint names, `sa.DateTime()` for `UTCDateTime`), delete `autogen.db`.

- [ ] **Step 6: Run tests, pyright, format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src
mise exec -- uv run ruff format src/festival_planner/adapters/sqlalchemy
jj commit -m "feat(persistence): planning tables, migration 0002 and SQLite WAL mode"
```

---

### Task 4: The `JobRunner` port and in-process runners

**Files:**
- Create: `src/festival_planner/domain/jobs.py`, `src/festival_planner/adapters/in_process/__init__.py`, `adapters/in_process/jobs.py`
- Test: `src/festival_planner/adapters/in_process/tests/__init__.py`, `adapters/in_process/tests/test_jobs.py`

**Interfaces:**
- Produces (`domain/jobs.py`): `Job` protocol with `wait(self, timeout: float | None = None) -> bool` (True once finished); `JobRunner` protocol with `submit(self, work: Callable[[], None]) -> Job`.
- Produces (`adapters/in_process/jobs.py`): `ThreadPoolJobRunner(max_workers: int = 2)` with `submit` and `shutdown(wait: bool = True)`, logging (not raising) exceptions from work; `ImmediateJobRunner` running work inside `submit` (exceptions propagate), returning a finished `Job`.

- [ ] **Step 1: Write the failing tests** (`adapters/in_process/tests/test_jobs.py`)

```python
import threading

from festival_planner.adapters.in_process.jobs import ImmediateJobRunner, ThreadPoolJobRunner
from festival_planner.domain.jobs import JobRunner


def test_immediate_runner_finishes_work_before_returning():
    done: list[int] = []
    runner: JobRunner = ImmediateJobRunner()
    job = runner.submit(lambda: done.append(1))
    assert done == [1]
    assert job.wait(0) is True


def test_thread_pool_runs_work_in_the_background():
    release = threading.Event()
    done = threading.Event()

    def work() -> None:
        release.wait(5)
        done.set()

    runner = ThreadPoolJobRunner()
    try:
        job = runner.submit(work)
        assert job.wait(0.01) is False
        release.set()
        assert job.wait(5) is True
        assert done.is_set()
    finally:
        runner.shutdown()


def test_thread_pool_survives_failing_work(caplog):
    runner = ThreadPoolJobRunner()
    try:
        job = runner.submit(lambda: 1 / 0)
        assert job.wait(5) is True
        assert runner.submit(lambda: None).wait(5) is True
    finally:
        runner.shutdown()
    assert "ZeroDivisionError" in caplog.text
```

- [ ] **Step 2: Run to verify failure**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/in_process -q`
Expected: FAIL on imports.

- [ ] **Step 3: Implement**

`domain/jobs.py`:

```python
"""Running work outside the request that asked for it."""

from collections.abc import Callable
from typing import Protocol


class Job(Protocol):
    def wait(self, timeout: float | None = None) -> bool:
        """Wait up to `timeout` seconds; whether the work has finished."""
        ...


class JobRunner(Protocol):
    """Port: runs work, possibly in the background."""

    def submit(self, work: Callable[[], None]) -> Job: ...
```

`adapters/in_process/jobs.py`:

```python
"""JobRunner adapters that run work in this process."""

import concurrent.futures
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class _FutureJob:
    def __init__(self, future: concurrent.futures.Future[None]):
        self._future = future

    def wait(self, timeout: float | None = None) -> bool:
        concurrent.futures.wait([self._future], timeout=timeout)
        return self._future.done()


class ThreadPoolJobRunner:
    """Runs work on a small thread pool. Failures are logged, not raised."""

    def __init__(self, max_workers: int = 2):
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="job"
        )

    def submit(self, work: Callable[[], None]) -> _FutureJob:
        return _FutureJob(self._pool.submit(_logging_failures, work))

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)


def _logging_failures(work: Callable[[], None]) -> None:
    try:
        work()
    except Exception:
        logger.exception("Job failed")


class _FinishedJob:
    def wait(self, timeout: float | None = None) -> bool:
        return True


class ImmediateJobRunner:
    """Runs work inside `submit`, for the CLI and tests."""

    def submit(self, work: Callable[[], None]) -> _FinishedJob:
        work()
        return _FinishedJob()
```

- [ ] **Step 4: Run tests, pyright, format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src
mise exec -- uv run ruff format src/festival_planner/domain/jobs.py src/festival_planner/adapters/in_process
jj commit -m "feat(jobs): JobRunner port with thread-pool and immediate runners"
```

---
### Task 5: Change-set rules: check, apply, rebase

**Files:**
- Modify: `src/festival_planner/domain/change_sets.py` (append below the item values)
- Test: `src/festival_planner/domain/tests/test_change_set_rules.py`

**Interfaces:**
- Consumes (Task 2): the item values, `ChangeSet`, `PlanningInputs`, `Preferences`, `Comparison`.
- Produces:
  - `ProgrammeIndex` (frozen dataclass): `entry_of: Mapping[ScreeningId, ProgrammeEntryId]`, `programme_entries: frozenset[ProgrammeEntryId]`, `venues: frozenset[VenueId]`; `ProgrammeIndex.of(entries: Iterable[ProgrammeEntry], screenings: Iterable[Screening], venues: Iterable[Venue]) -> ProgrammeIndex`.
  - `ProblemCode` (StrEnum): `UNKNOWN_ID`, `CONFLICTING_ITEMS`, `NO_OP`, `COMMITTED_AND_EXCLUDED`, `TWO_SCREENING_COMMITMENTS`.
  - `ChangeSetProblem(code: ProblemCode, items: tuple[int, ...], message: str)`; `items` are indexes into `ChangeSet.items`.
  - `InvalidChangeSetError(Exception)` with `.problems: tuple[ChangeSetProblem, ...]`.
  - `problems(change_set, base: PlanningInputs, programme: ProgrammeIndex) -> tuple[ChangeSetProblem, ...]`
  - `check(change_set, base, programme) -> None`, raising `InvalidChangeSetError` on any problem.
  - `apply(change_set, base: PlanningInputs) -> PlanningInputs` (total: never raises).
  - `rebase(change_set, base, programme) -> tuple[ChangeSet, tuple[str, ...]]`: drops `NO_OP` items and returns a note per dropped item; raises `InvalidChangeSetError` with the other problems.

Rules (spec *Planning*): unknown ids; two items changing the same target in one set (add + release of one commitment, commit + release, two settings of one key, "A over B" with "B over A"); an item that changes nothing against the base (adding what is there, releasing or un-Excluding what is not, setting a value it already has, recording an existing Comparison); a resulting Screening or Film Commitment that is also Excluded (so committing to something Excluded in the base needs the removal in the same set); two Screening Commitments of one Programme Entry in the result. Withdrawn Screenings are **not** a problem here.

- [ ] **Step 1: Write the failing tests** (`domain/tests/test_change_set_rules.py`)

```python
import datetime

import pytest

from festival_planner.domain.change_sets import (
    AddExcludedScreening,
    AddFilmCommitment,
    AddScreeningCommitment,
    ChangeSet,
    InvalidChangeSetError,
    ProblemCode,
    ProgrammeIndex,
    RecordComparison,
    ReleaseFilmCommitment,
    ReleaseScreeningCommitment,
    RemoveExcludedScreening,
    SetBuffer,
    SetDateRange,
    SetProgrammeEntryWeight,
    SetYearWeight,
    apply,
    check,
    problems,
    rebase,
)
from festival_planner.domain.planning import Comparison, PlanningInputs, Preferences
from festival_planner.domain.programme import Venue

from .builders import entry, screening

PROGRAMME = ProgrammeIndex.of(
    entries=[entry("e1"), entry("e2")],
    screenings=[
        screening("s1", "14:00", "16:00", entry_id="e1"),
        screening("s2", "18:00", "20:00", entry_id="e1"),
        screening("s3", "18:00", "20:00", entry_id="e2"),
    ],
    venues=[Venue(id="A", name="A")],
)


def codes(change_set: ChangeSet, base: PlanningInputs = PlanningInputs()) -> list[ProblemCode]:
    return [p.code for p in problems(change_set, base, PROGRAMME)]


def cs(*items) -> ChangeSet:
    return ChangeSet(items=items)


def test_a_sound_change_set_has_no_problems():
    change_set = cs(
        AddScreeningCommitment(screening_id="s1"),
        AddFilmCommitment(programme_entry_id="e2"),
        SetYearWeight(year=2025, weight=0.2),
        SetBuffer(venue_id="A", minutes=5),
        RecordComparison(preferred="e1", other="e2"),
    )
    assert codes(change_set) == []
    check(change_set, PlanningInputs(), PROGRAMME)


def test_unknown_ids_are_problems():
    assert codes(cs(AddScreeningCommitment(screening_id="nope"))) == [ProblemCode.UNKNOWN_ID]
    assert codes(cs(SetBuffer(venue_id="nowhere", minutes=5))) == [ProblemCode.UNKNOWN_ID]
    assert codes(cs(RecordComparison(preferred="e1", other="nope"))) == [ProblemCode.UNKNOWN_ID]


@pytest.mark.parametrize(
    "items",
    [
        (AddScreeningCommitment(screening_id="s1"), AddScreeningCommitment(screening_id="s1")),
        (SetProgrammeEntryWeight(programme_entry_id="e1", weight=2.0),
         SetProgrammeEntryWeight(programme_entry_id="e1", weight=3.0)),
        (RecordComparison(preferred="e1", other="e2"), RecordComparison(preferred="e2", other="e1")),
        (SetBuffer(minutes=5), SetBuffer(minutes=10)),
    ],
)
def test_two_items_for_one_target_conflict(items):
    assert ProblemCode.CONFLICTING_ITEMS in codes(cs(*items))


def test_buffers_of_different_venues_do_not_conflict():
    assert codes(cs(SetBuffer(minutes=5), SetBuffer(venue_id="A", minutes=10))) == []


def test_releasing_what_is_not_committed_is_a_no_op():
    assert codes(cs(ReleaseScreeningCommitment(screening_id="s1"))) == [ProblemCode.NO_OP]


def test_adding_what_is_there_is_a_no_op():
    base = PlanningInputs(film_commitments=frozenset({"e1"}))
    assert codes(cs(AddFilmCommitment(programme_entry_id="e1")), base) == [ProblemCode.NO_OP]


def test_setting_a_preference_to_its_current_value_is_a_no_op():
    assert codes(cs(SetBuffer(minutes=Preferences().buffer_minutes))) == [ProblemCode.NO_OP]
    assert codes(cs(SetProgrammeEntryWeight(programme_entry_id="e1", weight=None))) == [
        ProblemCode.NO_OP
    ]


def test_committing_and_excluding_one_screening_is_a_problem():
    change_set = cs(
        AddScreeningCommitment(screening_id="s1"), AddExcludedScreening(screening_id="s1")
    )
    assert codes(change_set) == [ProblemCode.COMMITTED_AND_EXCLUDED]


def test_committing_to_something_excluded_needs_its_removal():
    base = PlanningInputs(excluded_screenings=frozenset({"s1"}))
    assert codes(cs(AddScreeningCommitment(screening_id="s1")), base) == [
        ProblemCode.COMMITTED_AND_EXCLUDED
    ]
    both = cs(
        AddScreeningCommitment(screening_id="s1"), RemoveExcludedScreening(screening_id="s1")
    )
    assert codes(both, base) == []


def test_two_screening_commitments_of_one_entry_are_a_problem():
    base = PlanningInputs(screening_commitments=frozenset({"s1"}))
    assert codes(cs(AddScreeningCommitment(screening_id="s2")), base) == [
        ProblemCode.TWO_SCREENING_COMMITMENTS
    ]


def test_check_raises_with_every_problem():
    with pytest.raises(InvalidChangeSetError) as raised:
        check(
            cs(ReleaseFilmCommitment(programme_entry_id="e1"), AddScreeningCommitment(screening_id="x")),
            PlanningInputs(),
            PROGRAMME,
        )
    assert [p.items for p in raised.value.problems] == [(0,), (1,)]


def test_apply_changes_commitments_excluded_and_preferences():
    base = PlanningInputs(
        screening_commitments=frozenset({"s1"}),
        preferences=Preferences(comparisons=(Comparison(preferred="e2", other="e1"),)),
    )
    result = apply(
        cs(
            ReleaseScreeningCommitment(screening_id="s1"),
            AddExcludedScreening(screening_id="s2"),
            SetProgrammeEntryWeight(programme_entry_id="e1", weight=2.0),
            SetDateRange(start_date=datetime.date(2025, 11, 8), end_date=None),
            RecordComparison(preferred="e1", other="e2"),
        ),
        base,
    )
    assert result.screening_commitments == frozenset()
    assert result.excluded_screenings == frozenset({"s2"})
    assert result.preferences.programme_entry_weights == {"e1": 2.0}
    assert result.preferences.start_date == datetime.date(2025, 11, 8)
    assert result.preferences.comparisons == (Comparison(preferred="e1", other="e2"),)


def test_resetting_a_setting_restores_its_default():
    base = PlanningInputs(preferences=Preferences(buffer_minutes=30, venue_buffer_minutes={"A": 5}))
    result = apply(cs(SetBuffer(minutes=None), SetBuffer(venue_id="A", minutes=None)), base)
    assert result.preferences == Preferences()


def test_rebase_drops_items_that_became_no_ops():
    base = PlanningInputs(screening_commitments=frozenset({"s1"}))
    change_set = cs(
        AddScreeningCommitment(screening_id="s1"), AddFilmCommitment(programme_entry_id="e2")
    )
    rebased, notes = rebase(change_set, base, PROGRAMME)
    assert rebased == cs(AddFilmCommitment(programme_entry_id="e2"))
    assert len(notes) == 1 and "add_screening_commitment" in notes[0]


def test_rebase_refuses_contradictions_with_the_new_base():
    base = PlanningInputs(excluded_screenings=frozenset({"s1"}))
    with pytest.raises(InvalidChangeSetError):
        rebase(cs(AddScreeningCommitment(screening_id="s1")), base, PROGRAMME)
```

- [ ] **Step 2: Run to verify failure**

Run: `mise exec -- uv run pytest src/festival_planner/domain/tests/test_change_set_rules.py -q`
Expected: FAIL on imports.

- [ ] **Step 3: Implement** (append to `domain/change_sets.py`; add imports `enum`, `dataclass`, `defaultdict`, `Iterable`, `Mapping`, `Comparison`, `PlanningInputs`, `Preferences`, `ProgrammeEntry`, `Screening`, `Venue`)

```python
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
            changes = {"venue_buffer_minutes": _put(p.venue_buffer_minutes, venue_id, m)}
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


def check(change_set: ChangeSet, base: PlanningInputs, programme: ProgrammeIndex) -> None:
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
```

`_target` for `SetDateRange` etc. falls through to `(item.kind,)`; that makes two date-range items conflict, as intended.

- [ ] **Step 4: Run the tests**

Run: `mise exec -- uv run pytest src/festival_planner/domain -q`
Expected: PASS. If pyright objects to `getattr(item, "programme_entry_id")` returning `Any`, keep it: it is deliberate.

- [ ] **Step 5: pyright, format, commit**

```bash
mise exec -- uv run --with pyright pyright src
mise exec -- uv run ruff format src/festival_planner/domain/change_sets.py src/festival_planner/domain/tests/test_change_set_rules.py
jj commit -m "feat(domain): check, apply and rebase change sets"
```

---

### Task 6: User, Draft, Schedule and the planning ports

**Files:**
- Create: `src/festival_planner/domain/users.py`, `domain/drafts.py`, `domain/planning_ports.py`
- Modify: `src/festival_planner/domain/ingestion.py` (port additions only), `domain/tests/fakes.py`
- Test: `domain/tests/test_users.py`, `domain/tests/test_drafts.py`, `domain/tests/test_fakes.py`

**Interfaces:**
- Consumes (Task 2): `ChangeSet`, `PlanningInputs`, `Ticket`; `solving.ScheduledScreening`.
- Produces (`domain/users.py`): `UserId = str`; `LOCAL_ISSUER = "local"`; `User(id, issuer, subject)`; `UserRepository` protocol (`by_identity(issuer: str, subject: str) -> User | None`, `save(user: User) -> None`); `user_for(uow: PlanningUnitOfWork, issuer: str, subject: str, *, new_id=new_id) -> User` (get or create, commits).
- Produces (`domain/drafts.py`): `DraftId = str`, `ScheduleId = str`; `DraftStatus` (`SOLVING`, `READY`, `INFEASIBLE`, `FAILED`); `Schedule(id, user_id, festival_id, number: int, screening_ids: frozenset[ScreeningId], score: float, change_set: ChangeSet, accepted_at: AwareDatetime)`; `Draft(id, user_id, festival_id, change_set, base_schedule_id: ScheduleId | None, created_at: AwareDatetime, status=SOLVING, attempt=1, scheduled: tuple[ScheduledScreening, ...] = (), score=0.0, reasons=(), notes=(), solved_at=None)` with `screening_ids` property and `is_stale(active: Schedule | None) -> bool`.
- Produces (`domain/planning_ports.py`): `PlanningRepository`, `TicketRepository`, `SeenRepository`, `DraftSolvedNotifier`, `PlanningUnitOfWork` (below).
- Produces (`domain/ingestion.py`): `FestivalRepository.by_id(festival_id) -> Festival | None`; `FilmRepository.by_id(film_id) -> Film | None`; `ProgrammeRepository.screenings_by_id(ids: Iterable[ScreeningId]) -> tuple[Screening, ...]` and `entries_by_id(ids: Iterable[ProgrammeEntryId]) -> tuple[ProgrammeEntry, ...]` (unknown ids are skipped; any order).
- Produces (`domain/tests/fakes.py`): `InMemoryUnitOfWork` also implements `PlanningUnitOfWork` (`users`, `planning`, `tickets`, `seen`) and the new programme/festival/film lookups.

- [ ] **Step 1: Write the failing tests**

`domain/tests/test_drafts.py`:

```python
import datetime

from festival_planner.domain.change_sets import ChangeSet
from festival_planner.domain.drafts import Draft, DraftStatus, Schedule
from festival_planner.domain.solving import ScheduledScreening

NOW = datetime.datetime(2025, 11, 1, 12, tzinfo=datetime.UTC)


def schedule(id: str) -> Schedule:
    return Schedule(
        id=id, user_id="u", festival_id="f", number=1, screening_ids=frozenset({"s1"}),
        score=1.0, change_set=ChangeSet(), accepted_at=NOW,
    )


def draft(base: str | None) -> Draft:
    return Draft(
        id="d", user_id="u", festival_id="f", change_set=ChangeSet(),
        base_schedule_id=base, created_at=NOW,
    )


def test_a_new_draft_is_solving():
    assert draft(None).status is DraftStatus.SOLVING
    assert draft(None).attempt == 1


def test_a_draft_is_stale_once_its_base_is_no_longer_active():
    assert not draft(None).is_stale(None)
    assert draft(None).is_stale(schedule("s"))
    assert not draft("s").is_stale(schedule("s"))
    assert draft("s").is_stale(schedule("t"))


def test_a_draft_lists_its_scheduled_screening_ids():
    solved = draft(None).model_copy(
        update={
            "status": DraftStatus.READY,
            "scheduled": (ScheduledScreening(screening_id="s1", arrival_time=NOW, weight=1.0),),
        }
    )
    assert solved.screening_ids == frozenset({"s1"})


def test_drafts_round_trip_through_json():
    assert Draft.model_validate_json(draft("s").model_dump_json()) == draft("s")
```

`domain/tests/test_users.py`:

```python
from festival_planner.domain.users import LOCAL_ISSUER, user_for

from .fakes import InMemoryUnitOfWork, sequential_ids


def test_user_for_creates_a_user_once():
    uow = InMemoryUnitOfWork()
    ids = sequential_ids()
    first = user_for(uow, LOCAL_ISSUER, "thor", new_id=ids)
    again = user_for(uow, LOCAL_ISSUER, "thor", new_id=ids)
    assert first == again
    assert (first.issuer, first.subject) == ("local", "thor")


def test_users_are_keyed_on_issuer_and_subject():
    uow = InMemoryUnitOfWork()
    ids = sequential_ids()
    assert user_for(uow, "local", "thor", new_id=ids) != user_for(
        uow, "https://accounts.example", "thor", new_id=ids
    )
```

`domain/tests/test_fakes.py` (the fakes must keep behaving like the ports promise, since Task 8 tests run on them):

```python
import datetime

from festival_planner.domain.change_sets import ChangeSet
from festival_planner.domain.drafts import Draft, DraftStatus, Schedule
from festival_planner.domain.planning import PlanningInputs, Ticket

from .fakes import InMemoryUnitOfWork

NOW = datetime.datetime(2025, 11, 1, 12, tzinfo=datetime.UTC)


def schedule(id: str, number: int, festival: str = "f") -> Schedule:
    return Schedule(
        id=id, user_id="u", festival_id=festival, number=number,
        screening_ids=frozenset(), score=0.0, change_set=ChangeSet(), accepted_at=NOW,
    )


def test_inputs_default_to_empty():
    with InMemoryUnitOfWork() as uow:
        assert uow.planning.inputs("u", "f") == PlanningInputs()


def test_the_active_schedule_has_the_highest_number():
    uow = InMemoryUnitOfWork()
    with uow:
        uow.planning.save_schedule(schedule("one", 1))
        uow.planning.save_schedule(schedule("two", 2))
        uow.planning.save_schedule(schedule("other", 1, festival="g"))
        uow.commit()
    with uow:
        assert uow.planning.active_schedule("u", "f").id == "two"
        assert [s.id for s in uow.planning.schedules("u", "f")] == ["one", "two"]
        assert {s.id for s in uow.planning.active_schedules("u")} == {"two", "other"}


def test_drafts_can_be_listed_found_and_deleted():
    uow = InMemoryUnitOfWork()
    draft = Draft(
        id="d", user_id="u", festival_id="f", change_set=ChangeSet(),
        base_schedule_id=None, created_at=NOW,
    )
    with uow:
        uow.planning.save_draft(draft)
        uow.commit()
    with uow:
        assert uow.planning.draft("d") == draft
        assert uow.planning.drafts("u", "f") == (draft,)
        assert uow.planning.solving_drafts() == (draft,)
        uow.planning.save_draft(draft.model_copy(update={"status": DraftStatus.READY}))
        assert uow.planning.solving_drafts() == ()
        uow.planning.delete_draft("d")
        assert uow.planning.draft("d") is None


def test_tickets_and_seen():
    uow = InMemoryUnitOfWork()
    with uow:
        uow.tickets.save("u", Ticket(screening_id="s", refundable=True))
        uow.seen.mark("u", "film")
        uow.seen.dismiss("u", "s")
        uow.commit()
    with uow:
        assert uow.tickets.tickets("u") == (Ticket(screening_id="s", refundable=True),)
        assert uow.seen.films("u") == frozenset({"film"})
        assert uow.seen.dismissals("u") == frozenset({"s"})
        uow.tickets.delete("u", "s")
        uow.seen.unmark("u", "film")
        uow.seen.restore("u", "s")
        assert uow.tickets.tickets("u") == ()
        assert uow.seen.films("u") == frozenset()
        assert uow.seen.dismissals("u") == frozenset()
```

- [ ] **Step 2: Run to verify failure**

Run: `mise exec -- uv run pytest src/festival_planner/domain -q`
Expected: FAIL on imports.

- [ ] **Step 3: Implement `domain/drafts.py`**

```python
"""Drafts and accepted Schedules."""

import enum

from pydantic import AwareDatetime

from .change_sets import ChangeSet
from .festival import FestivalId
from .programme import ScreeningId
from .solving import ScheduledScreening
from .users import UserId
from .values import Value

DraftId = str
ScheduleId = str


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
```

- [ ] **Step 4: Implement `domain/users.py`**

```python
"""Users, keyed on the (issuer, subject) of their identity tokens (ADR-0003)."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from .ingestion import new_id as _new_id
from .values import Value

if TYPE_CHECKING:
    from .planning_ports import PlanningUnitOfWork

UserId = str

LOCAL_ISSUER = "local"
"""The issuer the CLI acts as, with the operating-system user as subject."""


class User(Value):
    """A person who plans their attendance at Festivals."""

    id: UserId
    issuer: str
    subject: str


class UserRepository(Protocol):
    def by_identity(self, issuer: str, subject: str) -> User | None: ...
    def save(self, user: User) -> None: ...


def user_for(
    uow: "PlanningUnitOfWork",
    issuer: str,
    subject: str,
    *,
    new_id: Callable[[], str] = _new_id,
) -> User:
    """The User with this identity, created on first sight."""
    with uow:
        if (user := uow.users.by_identity(issuer, subject)) is None:
            user = User(id=new_id(), issuer=issuer, subject=subject)
            uow.users.save(user)
            uow.commit()
    return user
```

- [ ] **Step 5: Implement `domain/planning_ports.py`**

```python
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
```

- [ ] **Step 6: Port additions in `domain/ingestion.py`**

```python
class FestivalRepository(Protocol):
    def by_id(self, festival_id: FestivalId) -> Festival | None: ...
    # by_slug, save, series_by_slug, save_series unchanged


class FilmRepository(Protocol):
    def by_id(self, film_id: str) -> Film | None: ...
    # find, save unchanged


class ProgrammeRepository(Protocol):
    # entries, save_entry, screenings, save_screening unchanged
    def screenings_by_id(self, ids: Iterable[str]) -> tuple[Screening, ...]:
        """The Screenings with these ids, in any Festival; unknown ids are skipped."""
        ...

    def entries_by_id(self, ids: Iterable[str]) -> tuple[ProgrammeEntry, ...]:
        """The Programme Entries with these ids; unknown ids are skipped."""
        ...
```

- [ ] **Step 7: Extend `domain/tests/fakes.py`**

Add to `_State`:

```python
        self.users: dict[str, User] = {}
        self.inputs: dict[tuple[str, str], PlanningInputs] = {}
        self.schedules: dict[str, Schedule] = {}
        self.drafts: dict[str, Draft] = {}
        self.tickets: dict[tuple[str, str], Ticket] = {}
        self.seen: set[tuple[str, str]] = set()
        self.dismissals: set[tuple[str, str]] = set()
```

In `InMemoryUnitOfWork.__enter__` add `self.users = _Users(self._work)`, `self.planning = _Planning(self._work)`, `self.tickets = _Tickets(self._work)`, `self.seen = _Seen(self._work)`. Add `by_id` to `_Festivals` (`return self.s.festivals.get(festival_id)`) and `_Films` (`return self.s.films.get(film_id)`), and to `_Programme`:

```python
    def screenings_by_id(self, ids: Iterable[str]) -> tuple[Screening, ...]:
        return tuple(self.s.screenings[i] for i in sorted(set(ids)) if i in self.s.screenings)

    def entries_by_id(self, ids: Iterable[str]) -> tuple[ProgrammeEntry, ...]:
        return tuple(self.s.entries[i][2] for i in sorted(set(ids)) if i in self.s.entries)
```

New classes:

```python
class _Users:
    def __init__(self, state: _State) -> None:
        self.s = state

    def by_identity(self, issuer: str, subject: str) -> User | None:
        return next(
            (u for u in self.s.users.values() if (u.issuer, u.subject) == (issuer, subject)),
            None,
        )

    def save(self, user: User) -> None:
        self.s.users[user.id] = user


class _Planning:
    def __init__(self, state: _State) -> None:
        self.s = state

    def inputs(self, user_id: str, festival_id: str) -> PlanningInputs:
        return self.s.inputs.get((user_id, festival_id), PlanningInputs())

    def save_inputs(self, user_id: str, festival_id: str, inputs: PlanningInputs) -> None:
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
        festivals = sorted({s.festival_id for s in self.s.schedules.values() if s.user_id == user_id})
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
        return tuple(d for d in self.s.drafts.values() if d.status is DraftStatus.SOLVING)

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
```

- [ ] **Step 8: Run tests, pyright, format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src   # errors limited to SqlAlchemyUnitOfWork lacking the new lookups are expected until Task 9
mise exec -- uv run ruff format src/festival_planner/domain/users.py src/festival_planner/domain/drafts.py src/festival_planner/domain/planning_ports.py src/festival_planner/domain/ingestion.py src/festival_planner/domain/tests
jj commit -m "feat(domain): Users, Drafts, Schedules and the planning ports"
```

---

### Task 7: Read-side planning functions: diff, flags, comparison suggestions, inferred Seen

**Files:**
- Create: `src/festival_planner/domain/insights.py`
- Test: `src/festival_planner/domain/tests/test_insights.py`

**Interfaces:**
- Consumes (Task 2): `PlanningInputs`, `Ticket`, `solving.score`, `solving.formulate`.
- Produces:
  - `DraftDiff(added: frozenset[ScreeningId], removed: frozenset[ScreeningId], score_delta: float, dropped_tickets: frozenset[ScreeningId])`; `diff(request: SolveRequest, scheduled: frozenset[ScreeningId], tickets: Iterable[Ticket]) -> DraftDiff`. The request is the Draft's; its `active_schedule` is the current Active Schedule.
  - `FlagKind` (StrEnum): `WITHDRAWN_COMMITMENT`, `WITHDRAWN_TICKET`, `UNSCHEDULED_TICKET`, `WITHDRAWN_IN_SCHEDULE`; `Flag(kind, target_id: str, message: str)`; `flags(screenings: Iterable[Screening], inputs: PlanningInputs, tickets: Iterable[Ticket], active: frozenset[ScreeningId]) -> tuple[Flag, ...]`, sorted by `(kind, target_id)`; only the Festival's (`screenings`) Tickets count.
  - `ComparisonSuggestion(scheduled: ProgrammeEntryId, other: ProgrammeEntryId, weight_gap: float)`; `suggest_comparisons(request: SolveRequest, scheduled: frozenset[ScreeningId], limit: int = 10) -> tuple[ComparisonSuggestion, ...]`.
  - `inferred_seen(screenings: Iterable[Screening], entries: Mapping[ProgrammeEntryId, ProgrammeEntry], dismissed: frozenset[ScreeningId], now: datetime.datetime) -> frozenset[FilmId]`: Films of non-Withdrawn, non-dismissed Screenings that ended at or before `now`. `screenings` are the User's Active Schedule Screenings.

- [ ] **Step 1: Write the failing tests** (`domain/tests/test_insights.py`)

```python
import pytest

from festival_planner.domain.insights import (
    ComparisonSuggestion,
    FlagKind,
    diff,
    flags,
    inferred_seen,
    suggest_comparisons,
)
from festival_planner.domain.planning import Comparison, PlanningInputs, Preferences, Ticket

from .builders import at, entry, request, screening


def withdrawn(s):
    return s.model_copy(update={"withdrawn": True})


def test_diff_lists_added_and_removed_and_the_score_delta():
    req = request(
        screening("a", "10:00", "12:00"),
        screening("b", "14:00", "16:00"),
        screening("c", "18:00", "20:00"),
        preferences=Preferences(buffer_minutes=0, programme_entry_weights={"c": 3.0}),
        active_schedule=frozenset({"a", "b"}),
    )
    result = diff(req, frozenset({"b", "c"}), [Ticket(screening_id="a")])
    assert result.added == frozenset({"c"})
    assert result.removed == frozenset({"a"})
    assert result.score_delta == pytest.approx(2.0)
    assert result.dropped_tickets == frozenset({"a"})


def test_without_an_active_schedule_everything_is_added():
    req = request(screening("a", "10:00", "12:00"))
    result = diff(req, frozenset({"a"}), [])
    assert (result.added, result.removed, result.score_delta) == (frozenset({"a"}), frozenset(), 1.0)


def test_flags():
    screenings = [
        withdrawn(screening("gone", "10:00", "12:00")),
        screening("here", "14:00", "16:00"),
    ]
    found = flags(
        screenings,
        PlanningInputs(screening_commitments=frozenset({"gone"})),
        [Ticket(screening_id="gone"), Ticket(screening_id="here"), Ticket(screening_id="elsewhere")],
        active=frozenset({"gone"}),
    )
    assert [(f.kind, f.target_id) for f in found] == [
        (FlagKind.WITHDRAWN_COMMITMENT, "gone"),
        (FlagKind.WITHDRAWN_TICKET, "gone"),
        (FlagKind.UNSCHEDULED_TICKET, "here"),
        (FlagKind.WITHDRAWN_IN_SCHEDULE, "gone"),
    ]


def test_a_film_commitment_with_only_withdrawn_screenings_is_flagged():
    found = flags(
        [withdrawn(screening("s", "10:00", "12:00", entry_id="e"))],
        PlanningInputs(film_commitments=frozenset({"e"})),
        [],
        active=frozenset(),
    )
    assert [(f.kind, f.target_id) for f in found] == [(FlagKind.WITHDRAWN_COMMITMENT, "e")]


def test_suggests_conflicting_pairs_closest_weights_first():
    req = request(
        screening("a", "14:00", "16:00"),
        screening("b", "15:00", "17:00"),
        screening("c", "18:00", "20:00"),
        screening("d", "19:00", "21:00"),
        preferences=Preferences(
            buffer_minutes=0,
            programme_entry_weights={"a": 2.0, "b": 1.0, "c": 1.2, "d": 1.1},
        ),
    )
    suggestions = suggest_comparisons(req, frozenset({"a", "c"}))
    assert [(s.scheduled, s.other) for s in suggestions] == [("c", "d"), ("a", "b")]
    assert suggestions[0].weight_gap == pytest.approx(0.1)


def test_pairs_already_compared_are_not_suggested():
    req = request(
        screening("a", "14:00", "16:00"),
        screening("b", "15:00", "17:00"),
        preferences=Preferences(buffer_minutes=0, comparisons=(Comparison(preferred="a", other="b"),)),
    )
    assert suggest_comparisons(req, frozenset({"a"})) == ()


def test_suggestions_are_limited():
    req = request(
        screening("a", "14:00", "16:00"),
        screening("b", "15:00", "17:00"),
        screening("c", "15:30", "17:00"),
    )
    assert len(suggest_comparisons(req, frozenset({"a"}), limit=1)) == 1


def test_ended_screenings_make_their_films_seen_unless_dismissed():
    screenings = [
        screening("past", "10:00", "12:00"),
        screening("dismissed", "10:00", "12:00"),
        screening("future", "18:00", "20:00"),
        withdrawn(screening("gone", "10:00", "12:00")),
    ]
    entries = {s.programme_entry_id: entry(s.programme_entry_id) for s in screenings}
    seen = inferred_seen(screenings, entries, frozenset({"dismissed"}), at("13:00"))
    assert seen == frozenset({"film-past"})
```

- [ ] **Step 2: Run to verify failure**

Run: `mise exec -- uv run pytest src/festival_planner/domain/tests/test_insights.py -q`
Expected: FAIL on import.

- [ ] **Step 3: Implement `domain/insights.py`**

```python
"""Read-side planning: diffs, flags, Comparison suggestions, inferred Seen."""

import datetime
import enum
from collections import defaultdict
from collections.abc import Iterable, Mapping

from .planning import PlanningInputs, Ticket
from .programme import FilmId, ProgrammeEntry, ProgrammeEntryId, Screening, ScreeningId
from .solving import SolveRequest, formulate, score
from .values import Value


class DraftDiff(Value):
    """A Draft's Schedule against the Active Schedule."""

    added: frozenset[ScreeningId]
    removed: frozenset[ScreeningId]
    score_delta: float
    """Draft score minus the Active Schedule's, both under the Draft's Preferences."""
    dropped_tickets: frozenset[ScreeningId]
    """Removed Screenings the User holds a Ticket for."""


def diff(
    request: SolveRequest, scheduled: frozenset[ScreeningId], tickets: Iterable[Ticket]
) -> DraftDiff:
    active = request.active_schedule
    removed = active - scheduled
    return DraftDiff(
        added=scheduled - active,
        removed=removed,
        score_delta=score(request, scheduled) - score(request, active),
        dropped_tickets=frozenset(t.screening_id for t in tickets) & removed,
    )


class FlagKind(enum.StrEnum):
    WITHDRAWN_COMMITMENT = "WITHDRAWN_COMMITMENT"
    WITHDRAWN_TICKET = "WITHDRAWN_TICKET"
    UNSCHEDULED_TICKET = "UNSCHEDULED_TICKET"
    WITHDRAWN_IN_SCHEDULE = "WITHDRAWN_IN_SCHEDULE"


class Flag(Value):
    """Something in a User's planning that needs their attention."""

    kind: FlagKind
    target_id: str
    """The Screening or (for Film Commitments) Programme Entry concerned."""
    message: str


def flags(
    screenings: Iterable[Screening],
    inputs: PlanningInputs,
    tickets: Iterable[Ticket],
    active: frozenset[ScreeningId],
) -> tuple[Flag, ...]:
    """Flags for one Festival, given its Screenings (Withdrawn included)."""
    by_id = {s.id: s for s in screenings}
    gone = {i for i, s in by_id.items() if s.withdrawn}
    by_entry: defaultdict[ProgrammeEntryId, list[Screening]] = defaultdict(list)
    for s in by_id.values():
        by_entry[s.programme_entry_id].append(s)
    found = [
        Flag(kind=FlagKind.WITHDRAWN_COMMITMENT, target_id=i,
             message=f"Committed Screening {i!r} was withdrawn")
        for i in inputs.screening_commitments & gone
    ]
    found += [
        Flag(kind=FlagKind.WITHDRAWN_COMMITMENT, target_id=e,
             message=f"Every Screening of committed programme entry {e!r} was withdrawn")
        for e in inputs.film_commitments
        if by_entry.get(e) and all(s.withdrawn for s in by_entry[e])
    ]
    for ticket in tickets:
        i = ticket.screening_id
        if i not in by_id:
            continue
        if i in gone:
            found.append(Flag(kind=FlagKind.WITHDRAWN_TICKET, target_id=i,
                              message=f"Ticketed Screening {i!r} was withdrawn"))
        elif i not in active:
            found.append(Flag(kind=FlagKind.UNSCHEDULED_TICKET, target_id=i,
                              message=f"Ticketed Screening {i!r} is not in the Active Schedule"))
    found += [
        Flag(kind=FlagKind.WITHDRAWN_IN_SCHEDULE, target_id=i,
             message=f"Scheduled Screening {i!r} was withdrawn")
        for i in active & gone
    ]
    order = list(FlagKind)
    return tuple(sorted(found, key=lambda f: (order.index(f.kind), f.target_id)))


class ComparisonSuggestion(Value):
    """Two Programme Entries whose Screenings competed; one won."""

    scheduled: ProgrammeEntryId
    other: ProgrammeEntryId
    weight_gap: float


def suggest_comparisons(
    request: SolveRequest, scheduled: frozenset[ScreeningId], limit: int = 10
) -> tuple[ComparisonSuggestion, ...]:
    """Pairs that conflicted in a solve of `request` where exactly one was
    scheduled and the User has not compared them, closest calls first."""
    formulation = formulate(request)
    entry_of = {s.id: s.programme_entry_id for s in formulation.candidates}
    compared = {c.pair for c in request.preferences.comparisons}
    best: dict[frozenset[str], ComparisonSuggestion] = {}
    for a, b in formulation.conflicts:
        if (a in scheduled) == (b in scheduled):
            continue
        won, lost = (a, b) if a in scheduled else (b, a)
        pair = frozenset((entry_of[won], entry_of[lost]))
        if len(pair) < 2 or pair in compared:
            continue
        suggestion = ComparisonSuggestion(
            scheduled=entry_of[won],
            other=entry_of[lost],
            weight_gap=abs(formulation.weights[won] - formulation.weights[lost]),
        )
        if pair not in best or suggestion.weight_gap < best[pair].weight_gap:
            best[pair] = suggestion
    ranked = sorted(best.values(), key=lambda s: (s.weight_gap, s.scheduled, s.other))
    return tuple(ranked[:limit])


def inferred_seen(
    screenings: Iterable[Screening],
    entries: Mapping[ProgrammeEntryId, ProgrammeEntry],
    dismissed: frozenset[ScreeningId],
    now: datetime.datetime,
) -> frozenset[FilmId]:
    """Films Seen because a Screening in an Active Schedule has ended."""
    return frozenset(
        entries[s.programme_entry_id].film_id
        for s in screenings
        if not s.withdrawn
        and s.id not in dismissed
        and s.end_time <= now
        and s.programme_entry_id in entries
    )
```

- [ ] **Step 4: Run tests, pyright, format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src
mise exec -- uv run ruff format src/festival_planner/domain/insights.py src/festival_planner/domain/tests/test_insights.py
jj commit -m "feat(domain): Draft diffs, flags, Comparison suggestions and inferred Seen"
```

---
### Task 8: The `Planner` use-cases

**Files:**
- Create: `src/festival_planner/domain/planner.py`
- Modify: `src/festival_planner/domain/tests/fakes.py` (append test doubles)
- Test: `src/festival_planner/domain/tests/test_planner.py`

**Interfaces:**
- Consumes: Task 2 (`ChangeSet`, `PlanningInputs`, `Ticket`, `SolveRequest`, `SolveResult`), Task 4 (`JobRunner`), Task 5 (`ProgrammeIndex`, `check`, `apply`, `rebase`, `InvalidChangeSetError`), Task 6 (`Draft`, `DraftStatus`, `Schedule`, `PlanningUnitOfWork`, `DraftSolvedNotifier`, new repository lookups), Task 7 (`diff`, `flags`, `suggest_comparisons`, `inferred_seen`).
- Produces (`domain/planner.py`):
  - `Clock = Callable[[], datetime.datetime]`
  - `PlanningError(Exception)`, `NotFoundError(PlanningError)`, `DraftNotAcceptableError(PlanningError)`
  - `DraftView(draft: Draft, stale: bool, diff: DraftDiff | None = None)`
  - `Planner(unit_of_work: Callable[[], PlanningUnitOfWork], solver: ScheduleSolver, jobs: JobRunner, notifier: DraftSolvedNotifier, *, clock: Clock, new_id: Callable[[], str] = new_id, wait_seconds: float = 2.0, time_limit_seconds: float = 30.0)` with methods:
    - `create_draft(user_id, festival_slug, change_set: ChangeSet = ChangeSet()) -> DraftView`
    - `resolve(user_id, draft_id) -> DraftView`
    - `accept(user_id, draft_id) -> Schedule`
    - `discard(user_id, draft_id) -> None`
    - `draft(user_id, draft_id) -> DraftView`; `drafts(user_id, festival_slug) -> tuple[DraftView, ...]`
    - `active_schedule(user_id, festival_slug) -> Schedule | None`; `schedules(user_id, festival_slug) -> tuple[Schedule, ...]`
    - `solve_request(user_id, draft_id) -> SolveRequest` (for `--export-request`)
    - `flags(user_id, festival_slug) -> tuple[Flag, ...]`
    - `suggest_comparisons(user_id, festival_slug, limit: int = 10) -> tuple[ComparisonSuggestion, ...]`
    - `record_ticket(user_id, ticket: Ticket) -> None`; `remove_ticket(user_id, screening_id) -> None`; `tickets(user_id) -> tuple[Ticket, ...]`
    - `mark_seen(user_id, film_id) -> None`; `unmark_seen(user_id, film_id) -> None`; `dismiss_inferred_seen(user_id, screening_id) -> None`; `restore_inferred_seen(user_id, screening_id) -> None`; `seen_films(user_id) -> frozenset[FilmId]`
    - `resume_solving() -> int` (resubmits every `SOLVING` Draft; returns how many)
- Produces (`fakes.py`): `GreedySolver`, `FailingSolver`, `InlineJobRunner`, `DeferredJobRunner` (`run_all()`), `RecordingNotifier` (`.solved: list[Draft]`), `TickingClock(start)` (each call one minute later).

Behaviour (spec *Planning*):
- Creating validates the Change Set against the current inputs (`check`), stores a `SOLVING` Draft based on the current Active Schedule, submits the solve job and waits up to `wait_seconds`, then returns the Draft as it is.
- The solve job reads the request in one unit of work, solves outside it, and writes the result in another, ignoring results for a Draft that was discarded or re-solved meanwhile (`attempt` changed). Status: solved → `READY`; `INFEASIBLE` → `INFEASIBLE` with reasons; `UNKNOWN` or a solver exception → `FAILED` with a reason. The notifier is told after the write.
- Accept: only `READY` and not Stale (`DraftNotAcceptableError` otherwise); applies the Change Set to the inputs, records Schedule `number = len(history) + 1`, deletes the Draft, all in one unit of work.
- Re-solve: not while `SOLVING`; `rebase` against the current inputs (on `InvalidChangeSetError` the Draft is left unchanged), new base, `attempt + 1`, results cleared, notes set; submit and wait.
- Drafts of another User are `NotFoundError`.
- Seen for solving = manual Seen ∪ `inferred_seen` over all the User's Active Schedules (dismissals removed).

- [ ] **Step 1: Add the test doubles to `fakes.py`**

```python
class GreedySolver:
    """A deterministic stand-in for CP-SAT: required Screenings first, then by
    weight (highest first) and id, skipping whatever conflicts."""

    def solve(self, request: SolveRequest) -> SolveResult:
        f = formulate(request)
        if f.unsatisfiable:
            return SolveResult(status=SolveStatus.INFEASIBLE, reasons=f.unsatisfiable)
        conflicts = set(f.conflicts) | {(b, a) for a, b in f.conflicts}
        groups = [*f.exactly_one, *f.at_most_one]
        chosen: list[str] = []
        for s in sorted(f.candidates, key=lambda s: (s.id not in f.required, -f.weights[s.id], s.id)):
            fits = all((s.id, c) not in conflicts for c in chosen) and not any(
                s.id in g and any(c in g for c in chosen) for g in groups
            )
            if fits:
                chosen.append(s.id)
            elif s.id in f.required:
                return SolveResult(status=SolveStatus.INFEASIBLE, reasons=(f"{s.id} does not fit",))
        if any(not g & set(chosen) for g in f.exactly_one):
            return SolveResult(status=SolveStatus.INFEASIBLE, reasons=("A Film Commitment does not fit",))
        scheduled = tuple(
            ScheduledScreening(screening_id=s.id, arrival_time=s.start_time, weight=f.weights[s.id])
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
```

- [ ] **Step 2: Write the failing tests** (`domain/tests/test_planner.py`)

```python
import datetime

import pytest

from festival_planner.domain.change_sets import (
    AddExcludedScreening,
    AddScreeningCommitment,
    ChangeSet,
    InvalidChangeSetError,
    SetProgrammeEntryWeight,
)
from festival_planner.domain.drafts import DraftStatus
from festival_planner.domain.festival import Festival
from festival_planner.domain.planner import (
    DraftNotAcceptableError,
    NotFoundError,
    Planner,
    PlanningError,
)
from festival_planner.domain.planning import Ticket
from festival_planner.domain.programme import Film, Venue

from .builders import DAY, ZONE, at, entry, screening
from .fakes import (
    DeferredJobRunner,
    FailingSolver,
    GreedySolver,
    InMemoryUnitOfWork,
    InlineJobRunner,
    RecordingNotifier,
    TickingClock,
    sequential_ids,
)

SLUG = "fest-2025"


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    """A Festival with a, b (conflicting) and c, d (later, conflicting)."""
    uow = InMemoryUnitOfWork()
    with uow:
        uow.festivals.save(
            Festival(id="f", slug=SLUG, name="Fest", start_date=DAY, end_date=DAY, time_zone=ZONE)
        )
        uow.venues.save(Venue(id="A", name="A"))
        for e in ("a", "b", "c", "d"):
            uow.films.save(Film(id=f"film-{e}", title=e))
            uow.programme.save_entry("f", e, entry(e))
        for s in (
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            screening("c", "18:00", "20:00"),
            screening("d", "19:00", "21:00"),
        ):
            uow.programme.save_screening(s)
        uow.commit()
    return uow


def planner(uow, *, solver=None, jobs=None, notifier=None, start=at("09:00")) -> Planner:
    return Planner(
        lambda: uow,
        solver or GreedySolver(),
        jobs or InlineJobRunner(),
        notifier or RecordingNotifier(),
        clock=TickingClock(start),
        new_id=sequential_ids(),
    )


def weights(**w: float) -> ChangeSet:
    return ChangeSet(
        items=tuple(SetProgrammeEntryWeight(programme_entry_id=e, weight=v) for e, v in w.items())
    )


def test_a_new_draft_is_solved_and_diffed_against_nothing(uow):
    notifier = RecordingNotifier()
    view = planner(uow, notifier=notifier).create_draft("u", SLUG, weights(b=2.0))
    assert view.draft.status is DraftStatus.READY
    assert view.draft.screening_ids == frozenset({"b", "c"})
    assert not view.stale
    assert view.diff is not None and view.diff.added == frozenset({"b", "c"})
    assert [d.id for d in notifier.solved] == [view.draft.id]


def test_an_invalid_change_set_creates_no_draft(uow):
    p = planner(uow)
    with pytest.raises(InvalidChangeSetError):
        p.create_draft("u", SLUG, ChangeSet(items=(AddScreeningCommitment(screening_id="nope"),)))
    assert p.drafts("u", SLUG) == ()


def test_unknown_festivals_are_not_found(uow):
    with pytest.raises(NotFoundError):
        planner(uow).create_draft("u", "nope")


def test_a_slow_solve_returns_the_draft_while_solving(uow):
    jobs = DeferredJobRunner()
    p = planner(uow, jobs=jobs)
    view = p.create_draft("u", SLUG)
    assert view.draft.status is DraftStatus.SOLVING
    jobs.run_all()
    assert p.draft("u", view.draft.id).draft.status is DraftStatus.READY


def test_accepting_applies_the_change_set_and_makes_the_schedule_active(uow):
    p = planner(uow)
    view = p.create_draft("u", SLUG, weights(b=2.0))
    schedule = p.accept("u", view.draft.id)
    assert schedule.number == 1
    assert p.active_schedule("u", SLUG) == schedule
    assert schedule.screening_ids == frozenset({"b", "c"})
    assert p.drafts("u", SLUG) == ()
    with uow:
        assert uow.planning.inputs("u", "f").preferences.programme_entry_weights == {"b": 2.0}


def test_accepting_makes_other_drafts_stale_and_unacceptable(uow):
    p = planner(uow)
    first = p.create_draft("u", SLUG, weights(b=2.0))
    second = p.create_draft("u", SLUG, weights(d=2.0))
    p.accept("u", first.draft.id)
    assert p.draft("u", second.draft.id).stale
    with pytest.raises(DraftNotAcceptableError):
        p.accept("u", second.draft.id)


def test_resolving_a_stale_draft_rebases_it(uow):
    p = planner(uow)
    first = p.create_draft("u", SLUG, weights(b=2.0))
    second = p.create_draft("u", SLUG, ChangeSet(items=(*weights(b=2.0).items, *weights(d=2.0).items)))
    p.accept("u", first.draft.id)
    resolved = p.resolve("u", second.draft.id)
    assert not resolved.stale
    assert resolved.draft.attempt == 2
    assert resolved.draft.change_set == weights(d=2.0)
    assert len(resolved.draft.notes) == 1
    assert resolved.draft.screening_ids == frozenset({"b", "d"})
    assert resolved.diff is not None and resolved.diff.added == frozenset({"d"})
    assert p.accept("u", second.draft.id).number == 2


def test_a_resolve_that_now_contradicts_leaves_the_draft_alone(uow):
    p = planner(uow)
    exclude = p.create_draft("u", SLUG, ChangeSet(items=(AddExcludedScreening(screening_id="a"),)))
    commit = p.create_draft("u", SLUG, ChangeSet(items=(AddScreeningCommitment(screening_id="a"),)))
    p.accept("u", exclude.draft.id)
    with pytest.raises(InvalidChangeSetError):
        p.resolve("u", commit.draft.id)
    assert p.draft("u", commit.draft.id).draft == commit.draft


def test_results_of_a_superseded_solve_are_ignored(uow):
    jobs = DeferredJobRunner()
    p = planner(uow, jobs=jobs)
    view = p.create_draft("u", SLUG)
    jobs.run_all()
    p.resolve("u", view.draft.id)  # attempt 2 pending
    first_job_again = lambda: p._solve(view.draft.id, 1)  # noqa: E731
    first_job_again()
    assert p.draft("u", view.draft.id).draft.status is DraftStatus.SOLVING
    jobs.run_all()
    assert p.draft("u", view.draft.id).draft.status is DraftStatus.READY


def test_infeasible_and_failed_drafts(uow):
    with uow:
        uow.programme.save_screening(screening("a", "14:00", "16:00").model_copy(update={"withdrawn": True}))
        uow.commit()
    view = planner(uow).create_draft("u", SLUG, ChangeSet(items=(AddScreeningCommitment(screening_id="a"),)))
    assert view.draft.status is DraftStatus.INFEASIBLE
    assert "withdrawn" in view.draft.reasons[0]
    failed = planner(uow, solver=FailingSolver()).create_draft("u", SLUG)
    assert failed.draft.status is DraftStatus.FAILED
    assert "solver exploded" in failed.draft.reasons[0]
    with pytest.raises(DraftNotAcceptableError):
        planner(uow).accept("u", failed.draft.id)


def test_other_users_drafts_are_not_found(uow):
    p = planner(uow)
    view = p.create_draft("u", SLUG)
    for action in (p.draft, p.accept, p.discard, p.resolve):
        with pytest.raises(NotFoundError):
            action("someone-else", view.draft.id)


def test_discarding_deletes_the_draft(uow):
    p = planner(uow)
    view = p.create_draft("u", SLUG)
    p.discard("u", view.draft.id)
    assert p.drafts("u", SLUG) == ()


def test_resolving_while_solving_is_refused(uow):
    p = planner(uow, jobs=DeferredJobRunner())
    view = p.create_draft("u", SLUG)
    with pytest.raises(PlanningError):
        p.resolve("u", view.draft.id)


def test_resume_solving_resubmits_solving_drafts(uow):
    jobs = DeferredJobRunner()
    planner(uow, jobs=jobs).create_draft("u", SLUG)  # never run: as if the process died
    fresh = planner(uow)
    assert fresh.resume_solving() == 1
    assert fresh.drafts("u", SLUG)[0].draft.status is DraftStatus.READY


def test_ended_active_screenings_are_seen_unless_dismissed(uow):
    p = planner(uow)
    p.accept("u", p.create_draft("u", SLUG, weights(b=2.0)).draft.id)
    later = planner(uow, start=at("17:30"))
    assert later.seen_films("u") == frozenset({"film-b"})
    later.dismiss_inferred_seen("u", "b")
    assert later.seen_films("u") == frozenset()
    later.restore_inferred_seen("u", "b")
    later.mark_seen("u", "film-d")
    assert later.seen_films("u") == frozenset({"film-b", "film-d"})


def test_manual_seen_films_are_not_scheduled(uow):
    p = planner(uow)
    p.mark_seen("u", "film-b")
    view = p.create_draft("u", SLUG, weights(b=2.0))
    assert "b" not in view.draft.screening_ids


def test_unknown_films_and_screenings_are_not_found(uow):
    p = planner(uow)
    with pytest.raises(NotFoundError):
        p.mark_seen("u", "film-nope")
    with pytest.raises(NotFoundError):
        p.record_ticket("u", Ticket(screening_id="nope"))


def test_tickets_flags_and_dropped_ticket_warnings(uow):
    p = planner(uow)
    p.accept("u", p.create_draft("u", SLUG, weights(b=2.0)).draft.id)
    p.record_ticket("u", Ticket(screening_id="b", refundable=True))
    p.record_ticket("u", Ticket(screening_id="a"))
    assert [(f.kind.value, f.target_id) for f in p.flags("u", SLUG)] == [("UNSCHEDULED_TICKET", "a")]
    view = p.create_draft("u", SLUG, weights(a=3.0))
    assert view.diff is not None and view.diff.dropped_tickets == frozenset({"b"})
    p.remove_ticket("u", "a")
    assert p.tickets("u") == (Ticket(screening_id="b", refundable=True),)


def test_suggestions_come_from_the_latest_ready_draft(uow):
    p = planner(uow)
    assert p.suggest_comparisons("u", SLUG) == ()
    p.create_draft("u", SLUG, weights(b=2.0))
    suggestions = p.suggest_comparisons("u", SLUG)
    assert {(s.scheduled, s.other) for s in suggestions} == {("b", "a"), ("c", "d")}


def test_the_solve_request_reflects_the_change_set(uow):
    p = planner(uow)
    view = p.create_draft("u", SLUG, ChangeSet(items=(AddScreeningCommitment(screening_id="a"),)))
    request = p.solve_request("u", view.draft.id)
    assert request.screening_commitments == frozenset({"a"})
    assert request.time_zone == ZONE
    assert request.now is not None and request.now.tzinfo is not None
```

- [ ] **Step 3: Run to verify failure**

Run: `mise exec -- uv run pytest src/festival_planner/domain/tests/test_planner.py -q`
Expected: FAIL on import of `festival_planner.domain.planner`.

- [ ] **Step 4: Implement `domain/planner.py`**

```python
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
from .planning_ports import DraftSolvedNotifier, PlanningUnitOfWork
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
        self, user_id: UserId, festival_slug: str, change_set: ChangeSet = ChangeSet()
    ) -> DraftView:
        with self._uow() as uow:
            festival = _festival(uow, festival_slug)
            check(
                change_set,
                uow.planning.inputs(user_id, festival.id),
                _programme_index(uow, festival.id),
            )
            active = uow.planning.active_schedule(user_id, festival.id)
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
            draft = _owned_draft(uow, user_id, draft_id)
            if draft.status is DraftStatus.SOLVING:
                raise PlanningError(f"Draft {draft_id!r} is still solving")
            change_set, notes = rebase(
                draft.change_set,
                uow.planning.inputs(user_id, draft.festival_id),
                _programme_index(uow, draft.festival_id),
            )
            active = uow.planning.active_schedule(user_id, draft.festival_id)
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
            draft = _owned_draft(uow, user_id, draft_id)
            if draft.status is not DraftStatus.READY:
                raise DraftNotAcceptableError(
                    f"Draft {draft_id!r} is {draft.status}, not READY"
                )
            if draft.is_stale(uow.planning.active_schedule(user_id, draft.festival_id)):
                raise DraftNotAcceptableError(
                    f"Draft {draft_id!r} is Stale; re-solve it first"
                )
            inputs = uow.planning.inputs(user_id, draft.festival_id)
            uow.planning.save_inputs(
                user_id, draft.festival_id, apply(draft.change_set, inputs)
            )
            schedule = Schedule(
                id=self._new_id(),
                user_id=user_id,
                festival_id=draft.festival_id,
                number=len(uow.planning.schedules(user_id, draft.festival_id)) + 1,
                screening_ids=draft.screening_ids,
                score=draft.score,
                change_set=draft.change_set,
                accepted_at=self._clock(),
            )
            uow.planning.save_schedule(schedule)
            uow.planning.delete_draft(draft.id)
            uow.commit()
        return schedule

    def discard(self, user_id: UserId, draft_id: DraftId) -> None:
        with self._uow() as uow:
            _owned_draft(uow, user_id, draft_id)
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
        """"I didn't go": the Screening no longer makes its Film Seen."""
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
        return self._jobs.submit(functools.partial(self._solve, draft.id, draft.attempt))

    def _solve(self, draft_id: DraftId, attempt: int) -> None:
        """The solve job: read, solve outside any transaction, write."""
        with self._uow() as uow:
            draft = uow.planning.draft(draft_id)
            if draft is None or draft.attempt != attempt:
                return
            request = self._request(uow, draft.user_id, draft.festival_id, draft.change_set)
        try:
            result = self._solver.solve(request)
        except Exception as e:
            logger.exception("Solving draft %s failed", draft_id)
            result = SolveResult(status=SolveStatus.UNKNOWN, reasons=(f"The solver failed: {e}",))
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
        with self._uow() as uow:
            current = uow.planning.draft(draft_id)
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
        self._notifier.draft_solved(solved)

    def _view(self, uow: PlanningUnitOfWork, draft: Draft) -> DraftView:
        active = uow.planning.active_schedule(draft.user_id, draft.festival_id)
        draft_diff = None
        if draft.status is DraftStatus.READY:
            request = self._request(uow, draft.user_id, draft.festival_id, draft.change_set)
            draft_diff = diff(request, draft.screening_ids, uow.tickets.tickets(draft.user_id))
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

    def _seen_films(self, uow: PlanningUnitOfWork, user_id: UserId) -> frozenset[FilmId]:
        scheduled = frozenset().union(
            *(s.screening_ids for s in uow.planning.active_schedules(user_id))
        )
        screenings = uow.programme.screenings_by_id(scheduled)
        entries = {
            e.id: e
            for e in uow.programme.entries_by_id({s.programme_entry_id for s in screenings})
        }
        return uow.seen.films(user_id) | inferred_seen(
            screenings, entries, uow.seen.dismissals(user_id), self._clock()
        )


def _festival(uow: PlanningUnitOfWork, slug: str) -> Festival:
    if (festival := uow.festivals.by_slug(slug)) is None:
        raise NotFoundError(f"No festival {slug!r}")
    return festival


def _owned_draft(uow: PlanningUnitOfWork, user_id: UserId, draft_id: DraftId) -> Draft:
    draft = uow.planning.draft(draft_id)
    if draft is None or draft.user_id != user_id:
        raise NotFoundError(f"No draft {draft_id!r}")
    return draft


def _screening_exists(uow: PlanningUnitOfWork, screening_id: ScreeningId) -> None:
    if not uow.programme.screenings_by_id([screening_id]):
        raise NotFoundError(f"No screening {screening_id!r}")


def _programme_index(uow: PlanningUnitOfWork, festival_id: FestivalId) -> ProgrammeIndex:
    return ProgrammeIndex.of(
        uow.programme.entries(festival_id).values(),
        uow.programme.screenings(festival_id),
        uow.venues.all(),
    )
```

Note that the ticking clock means `now` in a request is "after" the fixture's 09:00 start; fixtures pick start times so that nothing has started unless a test means it to.

- [ ] **Step 5: Run the tests**

Run: `mise exec -- uv run pytest src/festival_planner/domain -q`
Expected: PASS. Adjust test expectations only where the GreedySolver's documented order demands it, never the Planner's rules.

- [ ] **Step 6: Full suite, pyright, format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src   # SqlAlchemyUnitOfWork gaps are Task 9's
mise exec -- uv run ruff format src/festival_planner/domain/planner.py src/festival_planner/domain/tests/fakes.py src/festival_planner/domain/tests/test_planner.py
jj commit -m "feat(domain): Planner use-cases for Drafts, accepting, Tickets and Seen"
```

---

### Task 9: SQLAlchemy planning repositories

**Files:**
- Create: `src/festival_planner/adapters/sqlalchemy/planning_repositories.py`
- Modify: `adapters/sqlalchemy/repositories.py` (lookups), `adapters/sqlalchemy/unit_of_work.py`
- Test: `adapters/sqlalchemy/tests/test_planning_repositories.py`, `adapters/sqlalchemy/tests/test_repositories.py` (lookups)

**Interfaces:**
- Consumes: Task 3 rows and `PLANNING_TARGET_KINDS`; Task 6 ports and values; Task 2 `ChangeSet`, `PlanningInputs`, `Preferences`, `Ticket`.
- Produces: `SqlAlchemyUserRepository`, `SqlAlchemyPlanningRepository`, `SqlAlchemyTicketRepository`, `SqlAlchemySeenRepository`; `SqlAlchemyFestivalRepository.by_id`, `SqlAlchemyFilmRepository.by_id`, `SqlAlchemyProgrammeRepository.screenings_by_id`/`entries_by_id`; `SqlAlchemyUnitOfWork` gains `users`, `planning`, `tickets`, `seen` and satisfies `PlanningUnitOfWork` (pyright clean).

Rules: every save flushes (module docstring of `repositories.py`). Documents are stored as JSON text: `Preferences.model_dump_json()`, `ChangeSet.model_dump_json()`, `json.dumps(list(reasons))`. Seen rows store `source="manual"`.

- [ ] **Step 1: Write the failing tests** (`test_planning_repositories.py`)

```python
import datetime

import pytest

from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.domain.change_sets import AddScreeningCommitment, ChangeSet
from festival_planner.domain.drafts import Draft, DraftStatus, Schedule
from festival_planner.domain.festival import Festival
from festival_planner.domain.planning import Comparison, PlanningInputs, Preferences, Ticket
from festival_planner.domain.planning_ports import PlanningUnitOfWork
from festival_planner.domain.programme import Film, ProgrammeEntry, Screening, Venue
from festival_planner.domain.solving import ScheduledScreening
from festival_planner.domain.users import User

T0 = datetime.datetime(2025, 11, 8, 12, tzinfo=datetime.UTC)


@pytest.fixture
def stored(engine) -> SqlAlchemyUnitOfWork:
    """A User and a Festival with Screenings s1 and s2 of entry e."""
    uow = SqlAlchemyUnitOfWork(engine)
    with uow:
        uow.users.save(User(id="u", issuer="local", subject="thor"))
        uow.festivals.save(
            Festival(id="f", slug="f", name="F", start_date=T0.date(), end_date=T0.date(),
                     time_zone="Europe/Oslo")
        )
        uow.venues.save(Venue(id="v", name="V"))
        uow.films.save(Film(id="film", title="Film"))
        uow.programme.save_entry("f", "e", ProgrammeEntry(id="e", film_id="film", title="Film"))
        for i, hour in (("s1", 12), ("s2", 18)):
            uow.programme.save_screening(
                Screening(id=i, programme_entry_id="e", venue_id="v",
                          start_time=T0.replace(hour=hour), end_time=T0.replace(hour=hour + 2))
            )
        uow.commit()
    return uow


def schedule(id: str, number: int) -> Schedule:
    return Schedule(
        id=id, user_id="u", festival_id="f", number=number, screening_ids=frozenset({"s1"}),
        score=1.5, change_set=ChangeSet(items=(AddScreeningCommitment(screening_id="s1"),)),
        accepted_at=T0,
    )


def test_satisfies_the_planning_unit_of_work_port(stored):
    uow: PlanningUnitOfWork = stored
    assert uow is stored


def test_users_are_found_by_identity(stored):
    with stored as uow:
        assert uow.users.by_identity("local", "thor") == User(id="u", issuer="local", subject="thor")
        assert uow.users.by_identity("other", "thor") is None


def test_inputs_round_trip(stored):
    inputs = PlanningInputs(
        screening_commitments=frozenset({"s1"}),
        film_commitments=frozenset({"e"}),
        excluded_screenings=frozenset({"s2"}),
        preferences=Preferences(
            buffer_minutes=10, year_weights={2025: 0.2},
            comparisons=(Comparison(preferred="e", other="x"),),
        ),
    )
    with stored as uow:
        assert uow.planning.inputs("u", "f") == PlanningInputs()
        uow.planning.save_inputs("u", "f", inputs)
        uow.commit()
    with stored as uow:
        assert uow.planning.inputs("u", "f") == inputs
        uow.planning.save_inputs("u", "f", PlanningInputs())
        uow.commit()
    with stored as uow:
        assert uow.planning.inputs("u", "f") == PlanningInputs()


def test_schedules_and_the_active_one(stored):
    with stored as uow:
        assert uow.planning.active_schedule("u", "f") is None
        uow.planning.save_schedule(schedule("one", 1))
        uow.planning.save_schedule(schedule("two", 2))
        uow.commit()
    with stored as uow:
        assert uow.planning.active_schedule("u", "f") == schedule("two", 2)
        assert [s.id for s in uow.planning.schedules("u", "f")] == ["one", "two"]
        assert uow.planning.active_schedules("u") == (schedule("two", 2),)


def test_drafts_round_trip_and_are_deleted(stored):
    draft = Draft(
        id="d", user_id="u", festival_id="f",
        change_set=ChangeSet(items=(AddScreeningCommitment(screening_id="s1"),)),
        base_schedule_id=None, created_at=T0,
    )
    solved = draft.model_copy(
        update={
            "status": DraftStatus.READY, "score": 1.0, "reasons": ("r",), "notes": ("n",),
            "scheduled": (ScheduledScreening(screening_id="s1", arrival_time=T0, weight=1.0),),
            "solved_at": T0,
        }
    )
    with stored as uow:
        uow.planning.save_draft(draft)
        uow.commit()
    with stored as uow:
        assert uow.planning.draft("d") == draft
        assert uow.planning.solving_drafts() == (draft,)
        uow.planning.save_draft(solved)
        uow.commit()
    with stored as uow:
        assert uow.planning.draft("d") == solved
        assert uow.planning.drafts("u", "f") == (solved,)
        assert uow.planning.solving_drafts() == ()
        uow.planning.delete_draft("d")
        uow.commit()
    with stored as uow:
        assert uow.planning.draft("d") is None


def test_tickets_and_seen(stored):
    with stored as uow:
        uow.tickets.save("u", Ticket(screening_id="s1", exchangeable=True))
        uow.tickets.save("u", Ticket(screening_id="s1", refundable=True))
        uow.seen.mark("u", "film")
        uow.seen.mark("u", "film")
        uow.seen.dismiss("u", "s2")
        uow.commit()
    with stored as uow:
        assert uow.tickets.tickets("u") == (Ticket(screening_id="s1", refundable=True),)
        assert uow.seen.films("u") == frozenset({"film"})
        assert uow.seen.dismissals("u") == frozenset({"s2"})
        uow.tickets.delete("u", "s1")
        uow.seen.unmark("u", "film")
        uow.seen.restore("u", "s2")
        uow.commit()
    with stored as uow:
        assert uow.tickets.tickets("u") == ()
        assert uow.seen.films("u") == frozenset()
        assert uow.seen.dismissals("u") == frozenset()


def test_lookups_by_id(stored):
    with stored as uow:
        assert uow.festivals.by_id("f").slug == "f"
        assert uow.festivals.by_id("nope") is None
        assert uow.films.by_id("film").title == "Film"
        assert [s.id for s in uow.programme.screenings_by_id(["s2", "nope", "s1"])] == ["s1", "s2"]
        assert [e.id for e in uow.programme.entries_by_id(["e", "nope"])] == ["e"]
```

(Narrow `Optional` results with `assert x is not None` where pyright needs it.)

- [ ] **Step 2: Run to verify failure**

Run: `mise exec -- uv run pytest src/festival_planner/adapters/sqlalchemy -q`
Expected: FAIL (missing attributes and module).

- [ ] **Step 3: Lookups in `repositories.py`**

```python
    # SqlAlchemyFestivalRepository
    def by_id(self, festival_id: FestivalId) -> Festival | None:
        row = self._session.get(FestivalRow, festival_id)
        return None if row is None else _festival(row)

    # SqlAlchemyFilmRepository
    def by_id(self, film_id: str) -> Film | None:
        row = self._session.get(FilmRow, film_id)
        return None if row is None else Film(id=row.id, title=row.title, year=row.year)

    # SqlAlchemyProgrammeRepository
    def screenings_by_id(self, ids: Iterable[str]) -> tuple[Screening, ...]:
        rows = self._session.scalars(
            select(ScreeningRow)
            .where(ScreeningRow.id.in_(sorted(set(ids))))
            .order_by(ScreeningRow.start_time, ScreeningRow.id)
        )
        return tuple(_screening(row) for row in rows)

    def entries_by_id(self, ids: Iterable[str]) -> tuple[ProgrammeEntry, ...]:
        rows = self._session.scalars(
            select(ProgrammeEntryRow)
            .where(ProgrammeEntryRow.id.in_(sorted(set(ids))))
            .order_by(ProgrammeEntryRow.id)
        )
        return tuple(_entry(row) for row in rows)
```

Extract `_entry(row: ProgrammeEntryRow) -> ProgrammeEntry` from `entries()` and reuse it there.

- [ ] **Step 4: `planning_repositories.py`**

```python
"""The planning repository ports over SQLAlchemy rows. Every write flushes
(see `repositories.py`)."""

import json
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...domain.change_sets import ChangeSet
from ...domain.drafts import Draft, DraftStatus, Schedule
from ...domain.planning import PlanningInputs, Preferences, Ticket
from ...domain.solving import ScheduledScreening
from ...domain.users import User
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
        return None if row is None else User(id=row.id, issuer=row.issuer, subject=row.subject)

    def save(self, user: User) -> None:
        row = self._session.get(UserRow, user.id) or UserRow(id=user.id)
        row.issuer, row.subject = user.issuer, user.subject
        self._session.add(row)
        self._session.flush()


class SqlAlchemyPlanningRepository:
    def __init__(self, session: Session):
        self._session = session

    def inputs(self, user_id: str, festival_id: str) -> PlanningInputs:
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
            **{kind: frozenset(ids) for kind, ids in sets.items()},
            preferences=(
                Preferences.model_validate_json(row.preferences) if row else Preferences()
            ),
        )

    def save_inputs(self, user_id: str, festival_id: str, inputs: PlanningInputs) -> None:
        row = self._session.get(PlanningInputsRow, (user_id, festival_id)) or PlanningInputsRow(
            user_id=user_id, festival_id=festival_id
        )
        row.preferences = inputs.preferences.model_dump_json()
        self._session.add(row)
        self._session.execute(
            delete(PlanningTargetRow).where(
                PlanningTargetRow.user_id == user_id,
                PlanningTargetRow.festival_id == festival_id,
            )
        )
        self._session.add_all(
            PlanningTargetRow(user_id=user_id, festival_id=festival_id, kind=kind, target_id=i)
            for kind in PLANNING_TARGET_KINDS
            for i in sorted(getattr(inputs, kind))
        )
        self._session.flush()

    def schedules(self, user_id: str, festival_id: str) -> tuple[Schedule, ...]:
        rows = self._session.scalars(
            select(ScheduleRow)
            .where(ScheduleRow.user_id == user_id, ScheduleRow.festival_id == festival_id)
            .order_by(ScheduleRow.number)
        )
        return tuple(_schedule(row) for row in rows)

    def active_schedule(self, user_id: str, festival_id: str) -> Schedule | None:
        row = self._session.scalars(
            select(ScheduleRow)
            .where(ScheduleRow.user_id == user_id, ScheduleRow.festival_id == festival_id)
            .order_by(ScheduleRow.number.desc())
            .limit(1)
        ).first()
        return None if row is None else _schedule(row)

    def active_schedules(self, user_id: str) -> tuple[Schedule, ...]:
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
        self._session.flush()

    def draft(self, draft_id: str) -> Draft | None:
        row = self._session.get(DraftRow, draft_id)
        return None if row is None else _draft(row)

    def drafts(self, user_id: str, festival_id: str) -> tuple[Draft, ...]:
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
        row.reasons, row.notes = json.dumps(list(draft.reasons)), json.dumps(list(draft.notes))
        row.created_at, row.solved_at = draft.created_at, draft.solved_at
        # Replace the scheduled rows in two flushes, so primary keys that stay
        # are deleted before they are inserted again.
        row.scheduled = []
        self._session.add(row)
        self._session.flush()
        row.scheduled = [
            DraftScreeningRow(
                screening_id=s.screening_id, position=position,
                arrival_time=s.arrival_time, weight=s.weight,
            )
            for position, s in enumerate(draft.scheduled)
        ]
        self._session.flush()

    def delete_draft(self, draft_id: str) -> None:
        if (row := self._session.get(DraftRow, draft_id)) is not None:
            self._session.delete(row)
            self._session.flush()


def _schedule(row: ScheduleRow) -> Schedule:
    return Schedule(
        id=row.id, user_id=row.user_id, festival_id=row.festival_id, number=row.number,
        screening_ids=frozenset(s.screening_id for s in row.screenings), score=row.score,
        change_set=ChangeSet.model_validate_json(row.change_set), accepted_at=row.accepted_at,
    )


def _draft(row: DraftRow) -> Draft:
    return Draft(
        id=row.id, user_id=row.user_id, festival_id=row.festival_id,
        change_set=ChangeSet.model_validate_json(row.change_set),
        base_schedule_id=row.base_schedule_id, created_at=row.created_at,
        status=DraftStatus(row.status), attempt=row.attempt,
        scheduled=tuple(
            ScheduledScreening(screening_id=s.screening_id, arrival_time=s.arrival_time, weight=s.weight)
            for s in row.scheduled
        ),
        score=row.score, reasons=tuple(json.loads(row.reasons)),
        notes=tuple(json.loads(row.notes)), solved_at=row.solved_at,
    )


class SqlAlchemyTicketRepository:
    def __init__(self, session: Session):
        self._session = session

    def tickets(self, user_id: str) -> tuple[Ticket, ...]:
        rows = self._session.scalars(
            select(TicketRow).where(TicketRow.user_id == user_id).order_by(TicketRow.screening_id)
        )
        return tuple(
            Ticket(screening_id=r.screening_id, exchangeable=r.exchangeable, refundable=r.refundable)
            for r in rows
        )

    def save(self, user_id: str, ticket: Ticket) -> None:
        row = self._session.get(TicketRow, (user_id, ticket.screening_id)) or TicketRow(
            user_id=user_id, screening_id=ticket.screening_id
        )
        row.exchangeable, row.refundable = ticket.exchangeable, ticket.refundable
        self._session.add(row)
        self._session.flush()

    def delete(self, user_id: str, screening_id: str) -> None:
        self._session.execute(
            delete(TicketRow).where(TicketRow.user_id == user_id, TicketRow.screening_id == screening_id)
        )
        self._session.flush()


class SqlAlchemySeenRepository:
    def __init__(self, session: Session):
        self._session = session

    def films(self, user_id: str) -> frozenset[str]:
        return frozenset(
            self._session.scalars(select(SeenRow.film_id).where(SeenRow.user_id == user_id))
        )

    def mark(self, user_id: str, film_id: str) -> None:
        if self._session.get(SeenRow, (user_id, film_id)) is None:
            self._session.add(SeenRow(user_id=user_id, film_id=film_id, source="manual"))
            self._session.flush()

    def unmark(self, user_id: str, film_id: str) -> None:
        self._session.execute(
            delete(SeenRow).where(SeenRow.user_id == user_id, SeenRow.film_id == film_id)
        )
        self._session.flush()

    def dismissals(self, user_id: str) -> frozenset[str]:
        return frozenset(
            self._session.scalars(
                select(SeenDismissalRow.screening_id).where(SeenDismissalRow.user_id == user_id)
            )
        )

    def dismiss(self, user_id: str, screening_id: str) -> None:
        if self._session.get(SeenDismissalRow, (user_id, screening_id)) is None:
            self._session.add(SeenDismissalRow(user_id=user_id, screening_id=screening_id))
            self._session.flush()

    def restore(self, user_id: str, screening_id: str) -> None:
        self._session.execute(
            delete(SeenDismissalRow).where(
                SeenDismissalRow.user_id == user_id,
                SeenDismissalRow.screening_id == screening_id,
            )
        )
        self._session.flush()
```

`Iterable` is only needed if you add helpers; drop unused imports.

- [ ] **Step 5: Unit of work**

Add attributes `users: SqlAlchemyUserRepository`, `planning: SqlAlchemyPlanningRepository`, `tickets: SqlAlchemyTicketRepository`, `seen: SqlAlchemySeenRepository` and construct them in `__enter__` like the others.

- [ ] **Step 6: Run tests, pyright (must be 0 now), format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src
mise exec -- uv run ruff format src/festival_planner/adapters/sqlalchemy
jj commit -m "feat(persistence): SQLAlchemy repositories for Users, planning inputs, Drafts, Schedules, Tickets and Seen"
```

---

### Task 10: The `plan` CLI and a SQLite end-to-end test

**Files:**
- Create: `src/festival_planner/adapters/in_process/notifications.py`, `src/festival_planner/cli/plan.py`, `src/festival_planner/cli/tests/test_plan.py`, `src/festival_planner/adapters/sqlalchemy/tests/test_planner_on_sqlite.py`
- Modify: `src/festival_planner/cli/__init__.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `NullDraftSolvedNotifier` (`draft_solved` does nothing); the `festival-planner plan` command group:
  - `plan draft FESTIVAL [--change-set FILE]`: FILE is YAML or JSON, a list of items (`- kind: add_screening_commitment\n  screening_id: …`) or `{items: [...]}`; prints `Draft <id>: <STATUS>` then the diff, reasons and notes. Invalid change sets print every problem and exit 1.
  - `plan drafts FESTIVAL`: one line per Draft: id, status, `stale` marker, `+added −removed`, score delta.
  - `plan show DRAFT [--export-request FILE]`: the Draft's Schedule (festival-local day, time, title, venue), its diff, and optionally the solve request as JSON (replayable with `festival-planner solve --request FILE`).
  - `plan accept DRAFT`, `plan resolve DRAFT`, `plan discard DRAFT`.
  - `plan schedule FESTIVAL`: the Active Schedule (number, score, Screenings) and flags.
  - `plan compare FESTIVAL [--limit N]`: suggested Comparisons with titles.
  - `plan ticket add SCREENING [--exchangeable] [--refundable]`, `plan ticket remove SCREENING`.
  - `plan seen add FILM`, `plan seen remove FILM`, `plan seen dismiss SCREENING`, `plan seen restore SCREENING`.
  - Every command takes `--database` (`DATABASE_OPTION`), acts as `user_for(uow, LOCAL_ISSUER, getpass.getuser())`, uses `CpSatScheduleSolver`, `ImmediateJobRunner`, `NullDraftSolvedNotifier`, `clock=lambda: datetime.datetime.now(datetime.UTC)`, and calls `planner.resume_solving()` once before acting. `PlanningError` and `InvalidChangeSetError` print in red and exit 1.

- [ ] **Step 1: Write the failing tests**

`adapters/sqlalchemy/tests/test_planner_on_sqlite.py` (the real stack with background jobs):

```python
import datetime
import zoneinfo

from festival_planner.adapters.in_process.jobs import ThreadPoolJobRunner
from festival_planner.adapters.in_process.notifications import NullDraftSolvedNotifier
from festival_planner.adapters.solver.cpsat import CpSatScheduleSolver
from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.domain.change_sets import ChangeSet, SetProgrammeEntryWeight
from festival_planner.domain.drafts import DraftStatus
from festival_planner.domain.ingestion import (
    SourceEntry, SourceFestival, SourceProgramme, SourceRoute, SourceScreening, SourceVenue,
    ingest_programme, ingest_venues,
)
from festival_planner.domain.planner import Planner
from festival_planner.domain.travel import DEFAULT_TRANSPORT_MODE
from festival_planner.domain.users import LOCAL_ISSUER, user_for

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


def at(hour: int) -> datetime.datetime:
    return datetime.datetime(2030, 11, 8, hour, tzinfo=OSLO)


class Venues:
    def venues(self):
        return (SourceVenue(name="Vika"), SourceVenue(name="Vega"))

    def routes(self, venues):
        return tuple(
            SourceRoute(from_venue=a, to_venue=b, mode=DEFAULT_TRANSPORT_MODE, minutes=15)
            for a, b in (("Vika", "Vega"), ("Vega", "Vika"))
        )


class Programme:
    def fetch(self):
        return SourceProgramme(
            festival=SourceFestival(slug="fest-2030", name="Fest", time_zone="Europe/Oslo"),
            entries=tuple(
                SourceEntry(
                    source_key=key, title=key,
                    screenings=(SourceScreening(venue_name=venue, start_time=at(h), end_time=at(h + 2)),),
                )
                for key, venue, h in (("a", "Vika", 14), ("b", "Vega", 15), ("c", "Vika", 18))
            ),
        )


def test_drafts_solve_in_the_background_and_can_be_accepted(engine):
    ingest_venues(SqlAlchemyUnitOfWork(engine), Venues(), Venues())
    ingest_programme(SqlAlchemyUnitOfWork(engine), Programme())
    user = user_for(SqlAlchemyUnitOfWork(engine), LOCAL_ISSUER, "tester")
    jobs = ThreadPoolJobRunner()
    try:
        planner = Planner(
            lambda: SqlAlchemyUnitOfWork(engine), CpSatScheduleSolver(), jobs,
            NullDraftSolvedNotifier(), clock=lambda: datetime.datetime.now(datetime.UTC),
            wait_seconds=30,
        )
        with SqlAlchemyUnitOfWork(engine) as uow:
            festival = uow.festivals.by_slug("fest-2030")
            assert festival is not None
            b_id = uow.programme.entries(festival.id)["b"].id
        views = [
            planner.create_draft(user.id, "fest-2030", ChangeSet(items=(
                SetProgrammeEntryWeight(programme_entry_id=b_id, weight=w),
            )))
            for w in (2.0, 3.0)
        ]
        assert all(v.draft.status is DraftStatus.READY for v in views)
        schedule = planner.accept(user.id, views[0].draft.id)
        assert len(schedule.screening_ids) == 2
        assert planner.draft(user.id, views[1].draft.id).stale
    finally:
        jobs.shutdown()
```

`cli/tests/test_plan.py` (copy the `config_dir` fixture and `CONFIG_YAML` from `test_ingest.py`; dates are in 2030 so nothing has started):

```python
import datetime
import json
import re
import zoneinfo

import pytest
from typer.testing import CliRunner

from festival_planner.adapters.sqlalchemy.database import create_engine_for, resolve_database_url
from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.cli import app
from festival_planner.cli.ingest import PROGRAMME_SOURCES
from festival_planner.domain.ingestion import (
    SourceEntry,
    SourceFestival,
    SourceProgramme,
    SourceScreening,
)

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")


class FakeSource:
    """Stands in for the Filmfrasor scraper; takes the same arguments."""

    def __init__(self, year, *, known_venue_names, cache_dir, force_refresh):
        pass

    def fetch(self) -> SourceProgramme:
        def at(hour: int) -> datetime.datetime:
            return datetime.datetime(2030, 11, 8, hour, tzinfo=OSLO)

        return SourceProgramme(
            festival=SourceFestival(slug="fest-2030", name="Fest", time_zone="Europe/Oslo"),
            entries=tuple(
                SourceEntry(
                    source_key=key,
                    title=key.title(),
                    year=2030,
                    screenings=(
                        SourceScreening(venue_name=venue, start_time=at(h), end_time=at(h + 2)),
                    ),
                )
                for key, venue, h in (("alpha", "Vika Kino", 14), ("beta", "Vega", 15))
            ),
        )


@pytest.fixture
def db(tmp_path) -> str:
    return str(tmp_path / "db.sqlite")


@pytest.fixture
def cli(config_dir, db, monkeypatch):
    monkeypatch.setenv("LOGNAME", "tester")
    monkeypatch.setitem(PROGRAMME_SOURCES, "filmfrasor", FakeSource)
    runner = CliRunner()

    def invoke(*args: str):
        return runner.invoke(app, [*args, "--database", db])

    assert invoke("ingest", "venues").exit_code == 0
    assert invoke("ingest", "programme", "filmfrasor", "--year", "2030").exit_code == 0
    return invoke


def first_screening_id(db: str) -> str:
    engine = create_engine_for(resolve_database_url(db))
    try:
        with SqlAlchemyUnitOfWork(engine) as uow:
            festival = uow.festivals.by_slug("fest-2030")
            assert festival is not None
            return uow.programme.screenings(festival.id)[0].id
    finally:
        engine.dispose()


def test_draft_accept_and_schedule(cli, tmp_path):
    result = cli("plan", "draft", "fest-2030")
    assert result.exit_code == 0, result.output
    match = re.search(r"Draft (\S+): READY", result.output)
    assert match, result.output
    draft_id = match.group(1)
    assert draft_id in cli("plan", "drafts", "fest-2030").output
    exported = tmp_path / "request.json"
    assert cli("plan", "show", draft_id, "--export-request", str(exported)).exit_code == 0
    assert json.loads(exported.read_text())["format_version"] == 1
    assert cli("plan", "accept", draft_id).exit_code == 0
    assert "Schedule 1" in cli("plan", "schedule", "fest-2030").output


def test_an_invalid_change_set_is_reported(cli, tmp_path):
    change_set = tmp_path / "changes.yaml"
    change_set.write_text("- kind: add_screening_commitment\n  screening_id: nope\n")
    result = cli("plan", "draft", "fest-2030", "--change-set", str(change_set))
    assert result.exit_code == 1
    assert "unknown screening 'nope'" in result.output


def test_unknown_drafts_are_reported(cli):
    result = cli("plan", "accept", "nope")
    assert result.exit_code == 1
    assert "No draft 'nope'" in result.output


def test_tickets_and_seen_commands(cli, db):
    screening_id = first_screening_id(db)
    assert cli("plan", "ticket", "add", screening_id, "--refundable").exit_code == 0
    assert "not in the Active Schedule" in cli("plan", "schedule", "fest-2030").output
    assert cli("plan", "ticket", "remove", screening_id).exit_code == 0
    assert cli("plan", "seen", "add", "nope").exit_code == 1
```

`--database` goes last because Typer options belong to the leaf command (`plan ticket add … --database`).

- [ ] **Step 2: Run to verify failure**

Run: `mise exec -- uv run pytest src/festival_planner/cli/tests/test_plan.py src/festival_planner/adapters/sqlalchemy/tests/test_planner_on_sqlite.py -q`
Expected: FAIL on imports.

- [ ] **Step 3: Implement**

`adapters/in_process/notifications.py`:

```python
"""DraftSolvedNotifier adapters for a single process."""

from ...domain.drafts import Draft


class NullDraftSolvedNotifier:
    """Nobody is listening yet; clients poll."""

    def draft_solved(self, draft: Draft) -> None:
        pass
```

`cli/plan.py` skeleton (fill in every command listed under *Produces*, following `cli/ingest.py`'s style: module `app = typer.Typer(name="plan", help=...)`, `console = Console()`, sub-apps `ticket_app`, `seen_app` added with `app.add_typer(ticket_app, name="ticket")`):

```python
"""Plan a Festival as the local User: Drafts, Schedules, Tickets and Seen."""

import contextlib
import datetime
import getpass
import json
import zoneinfo
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import typer
import yaml
from rich.console import Console

from ..adapters.in_process.jobs import ImmediateJobRunner
from ..adapters.in_process.notifications import NullDraftSolvedNotifier
from ..adapters.json_files.solve_request import dump_solve_request
from ..adapters.solver.cpsat import CpSatScheduleSolver
from ..adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from ..domain.change_sets import ChangeSet, InvalidChangeSetError
from ..domain.planner import DraftView, Planner, PlanningError
from ..domain.planning import Ticket
from ..domain.users import LOCAL_ISSUER, user_for
from .db import DATABASE_OPTION, open_database

app = typer.Typer(name="plan", help="Plan a Festival: Drafts, Schedules, Tickets and Seen.")
ticket_app = typer.Typer(name="ticket", help="Record Tickets you hold.")
seen_app = typer.Typer(name="seen", help="Mark Films Seen, or correct inferred Seen.")
app.add_typer(ticket_app, name="ticket")
app.add_typer(seen_app, name="seen")
console = Console()


@dataclass
class _Session:
    planner: Planner
    user_id: str
    unit_of_work: SqlAlchemyUnitOfWork


@contextlib.contextmanager
def _session(database: str | None) -> Iterator[_Session]:
    """The planner acting as the local User; errors become exit code 1."""
    engine = open_database(database)
    try:
        def unit_of_work() -> SqlAlchemyUnitOfWork:
            return SqlAlchemyUnitOfWork(engine)

        planner = Planner(
            unit_of_work,
            CpSatScheduleSolver(),
            ImmediateJobRunner(),
            NullDraftSolvedNotifier(),
            clock=lambda: datetime.datetime.now(datetime.UTC),
        )
        planner.resume_solving()
        user = user_for(unit_of_work(), LOCAL_ISSUER, getpass.getuser())
        yield _Session(planner, user.id, unit_of_work())
    except (PlanningError, InvalidChangeSetError) as e:
        console.print(f"[bold red]{e}[/bold red]", soft_wrap=True)
        raise typer.Exit(code=1) from e
    finally:
        engine.dispose()


def _load_change_set(path: Path | None) -> ChangeSet:
    if path is None:
        return ChangeSet()
    data = yaml.safe_load(path.read_text())  # JSON is YAML too
    return ChangeSet.model_validate(data if isinstance(data, dict) else {"items": data or []})


@app.command()
def draft(
    festival: str = typer.Argument(..., help="Festival slug"),
    change_set: Path | None = typer.Option(None, "--change-set", help="YAML or JSON list of change-set items"),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Create and solve a Draft."""
    with _session(database) as s:
        view = s.planner.create_draft(s.user_id, festival, _load_change_set(change_set))
        _print_view(s, view)
```

`_print_view` prints `Draft {id}: {status}` (plus ` (stale)`), reasons, notes and, for READY Drafts, `+{len(added)} −{len(removed)}  score {delta:+.2f}` and any dropped Tickets as a yellow warning. Resolve Screening ids to titles, venues and festival-local times with `s.unit_of_work` (`programme.screenings_by_id`, `programme.entries_by_id`, `venues.all()`, `festivals.by_id(...).time_zone`). `InvalidChangeSetError` prints one line per problem (`str(e)` joins them with `; `; print `e.problems` one per line instead).

Register in `cli/__init__.py`: `from .plan import app as plan_app` and `app.add_typer(plan_app, name="plan")`.

- [ ] **Step 4: Run tests, pyright, format, commit**

```bash
mise exec -- uv run pytest -q
mise exec -- uv run --with pyright pyright src
mise exec -- uv run ruff format src/festival_planner/cli/plan.py src/festival_planner/cli/__init__.py src/festival_planner/cli/tests/test_plan.py src/festival_planner/adapters/in_process src/festival_planner/adapters/sqlalchemy/tests/test_planner_on_sqlite.py
jj commit -m "feat(cli): plan commands for Drafts, Schedules, Tickets and Seen"
```

- [ ] **Step 5: Smoke test against a scratch copy of the real configuration**

```bash
DB=/home/thor/dev/thor/festival-planner-ws/<ws>/smoke.db
mise exec -- uv run festival-planner db upgrade --database $DB
mise exec -- uv run festival-planner ingest venues --database $DB
mise exec -- uv run festival-planner ingest programme filmfrasor --database $DB
mise exec -- uv run festival-planner plan draft <slug printed above> --database $DB
```

Expected: a READY Draft with a plausible Schedule. Report the output; delete `smoke.db`. (Network access is needed for the scrape; if unavailable, say so and skip.)

---

## Deferred to later steps

- GraphQL types, global ids and `NewType` ids over `Planner` (step 4); the server calls `resume_solving()` at startup and uses `ThreadPoolJobRunner`.
- A subscription-backed `DraftSolvedNotifier` (WebSockets are out of scope).
- Curation weight in Preferences and the adopt-a-Curation item (step 5).
- Provider-synchronised Seen (step 6); `SeenRow.source` is ready for it.
