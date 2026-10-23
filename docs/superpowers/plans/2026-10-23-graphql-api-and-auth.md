# GraphQL API and Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve the planning use-cases and the read-only festival data over a code-first Strawberry GraphQL API, signed in with bearer JWTs from configured issuers, plus a CLI-based local token issuer and a committed SDL.

**Architecture:** Hexagonal, as in steps 1 to 3. The domain gains distinct id types (`NewType`), a `ProgrammeQueries` read service, lazy Draft diffs and a `TokenVerifier` port with an `Identity` value. Driven adapters: a PyJWT verifier (`adapters/jwt/`) and a local Ed25519 issuer (`adapters/local_issuer/`). A new driving adapter, `api/`, maps domain values to Strawberry types (hand-written, not derived from Pydantic), runs every domain call off the event loop and is served by Starlette and uvicorn. The CLI gains `serve`, `token` and `export-schema`.

**Tech Stack:** Python 3.13, Pydantic 2, SQLAlchemy 2, Strawberry GraphQL (0.336+), Starlette, uvicorn, anyio, PyJWT with `cryptography`, Typer, pytest. Tooling via `mise` + `uv`; version control is **jj**.

**Spec:** `docs/superpowers/specs/2026-10-23-graphql-backend-design.md`, sections *Architecture*, *GraphQL conventions*, *Planning* and roadmap step 4. Vocabulary: `GLOSSARY.md`. Decisions: `docs/adr/0001` (hexagonal), `0003` (backend only verifies tokens), `0004` (Drafts are change sets).

## Decisions taken for this step

Settled with the user on 2026-10-23:

- **Local token issuer:** a CLI (`festival-planner token init|issue`) that mints JWTs from a local Ed25519 keypair. No HTTP issuer now. A frontend will need a sign-in path later; that is a separate decision.
- **`iss` of the local issuer:** `"local"`, the same as `domain.users.LOCAL_ISSUER`, so a token for subject `<os user>` is the same User as the CLI. `"local"` is reserved for this CLI issuer: an HTTP issuer, now or later, must use another `iss` (a URL). The issuer config enforces this: `"local"` may only use `jwks_file`, never `jwks_uri`.
- **Change Set items as input:** one `@oneOf` input, `ChangeSetItemInput`, with one field per item kind.
- **Trusted issuers:** from the environment variable `FESTIVAL_PLANNER_ISSUERS`, a JSON list.
- **Typed ids in tests:** tests wrap literal ids in the id constructors (e.g. `ScreeningId("a")`) or use builders that return typed ids. Pyright checks tests as strictly as code.

Taken here, without needing the user:

- **Strawberry's Pydantic integration: not used.** Probed on 2026-10-23 (Strawberry 0.336.2): flat values (`Event`, `Screening`, `Ticket`) convert, but nested models need manual registration (`Preferences` fails on `Comparison`, `Draft` on `ChangeSet`), `Mapping` fields have no GraphQL form, the discriminated `ChangeSetItem` union cannot be an input, and ids come out as raw strings, not global ids. The module is also still `experimental`. Types are hand-written mappings (ADR-0001 expects that).
- **Server:** Starlette app with a lifespan, Strawberry's ASGI `GraphQL` app mounted at `/graphql`, uvicorn via `festival-planner serve`.
- **Auth outcomes:** no `Authorization` header means signed out (public festival data still works; `viewer` is `null`; mutations return `NotSignedIn`). A header that is not `Bearer <token>`, or a token that fails verification, gets HTTP 401 with `WWW-Authenticate: Bearer error="invalid_token"`.
- **JWT verification:** PyJWT. Pick the trusted issuer by the token's unverified `iss`, then verify with that issuer's keys only, its algorithm allowlist, its audience, `leeway=30` seconds, and required claims `exp`, `iss`, `sub`, `aud`.
- **Global ids:** Strawberry relay `Node` types; global id = base64 `"<TypeName>:<domain id>"`. Inputs take plain `ID` and decode it themselves, so a garbage or wrong-type id gives a typed error or `null`, never a GraphQL error. Mutations take global ids. The `Planner` stays keyed on Festival slugs; the API resolves a Festival id to its slug.
- **Blocking work:** every resolver that touches the domain is `async` and calls the domain through `anyio.to_thread.run_sync`. DataLoaders do the same. That keeps `create_draft`/`resolve` (which wait up to `wait_seconds`) and PyJWKClient's network fetch off the event loop.
- **DataLoaders:** created per request in the context, one per relation.
- **Connections:** `relay.ListConnection` over in-memory lists for Programme Entries, Screenings and schedule history (a Festival has hundreds of entries, not millions).
- **Notifier:** the server keeps `NullDraftSolvedNotifier`; clients poll `node(id:)`. Subscriptions are out of scope (spec), so the `loop.call_soon_threadsafe` hand-off waits for them.
- **SDL:** committed at the repo root as `schema.graphql`; a test compares it with the live schema.

## Global Constraints

- `src/festival_planner/domain/` (tests included) imports only the stdlib, Pydantic and other domain modules. No Strawberry, Starlette, PyJWT, SQLAlchemy, OR-Tools, httpx or Typer. `api/` may import the domain and adapters; the domain never imports `api/`.
- Use glossary terms in code and schema: Festival, Festival Series, Film, Programme Entry, Screening, Withdrawn, Event, Venue, User, Draft, Change Set, Stale, Active Schedule, Schedule, Screening Commitment, Film Commitment, Excluded, Comparison, Ticket, Seen, Preferences. Avoid the glossary's "_Avoid_" words (no "catalogue", "listing", "plan" for a Schedule). "Viewer" is GraphQL convention for the signed-in User and is fine in the schema.
- Ids are `typing.NewType` over `str`: `UserId`, `FestivalId`, `FestivalSeriesId`, `VenueId`, `FilmId`, `ProgrammeEntryId`, `ScreeningId`, `DraftId`, `ScheduleId`. Adapters wrap raw strings at the boundary (row mappers, CLI arguments, decoded global ids).
- Every domain call from `api/` goes through `Context.run(...)` (a thread offload). No sync resolver touches the domain.
- GraphQL: mutations take one `input` argument and return a union of a success type and typed errors. Field names are camelCase (Strawberry's default).
- The issuer `"local"` may only be configured with `jwks_file`.
- Run tests with `env -u FORCE_COLOR mise exec -- uv run pytest -q`. This shell sets `FORCE_COLOR=3`, which makes 6 existing CLI tests fail on ANSI codes; that is the environment, not the code, so do not "fix" those tests.
- Type-check with `mise exec -- uv run --with pyright pyright src`: 0 errors at the end of every task.
- Format only files you touched: `mise exec -- uv run ruff format <paths>` and `mise exec -- uv run ruff check <paths>`.
- Tests live next to code in `tests/` sub-packages, each with an empty `__init__.py`.
- Version control is jj. Each task is its own change, inserted between the previous task's change and the megamerge `rrnvryyy`: start a task with `jj new --insert-after @ --insert-before rrnvryyy`, finish with `jj describe -m "<message>"`. Then check with `jj log -r 'rrnvryyy | rrnvryyy- | main'` that the megamerge's parents are `wsqzprvx` and your change, and `main` has not moved. Never `git commit`, `jj commit`, push, or move bookmarks. Do not touch `wsqzprvx`. Do not use git worktrees.
- Commit messages: Conventional Commits, concise, no em-dashes, no trailers (no `Co-Authored-By`).
- Prose, comments and docs: plain words, short sentences, no em-dashes.

## Review Focus

- **Another User's private data.** `node(id:)` on another User's Draft or Schedule returns `null`; mutations on another User's Draft return `NotFound`. Owned by Tasks 8 and 9.
- **Hostile or broken tokens.** Expired, wrong `aud`, unknown `iss`, `alg: none`, an `iss` of issuer B signed with issuer A's key, unknown `kid`, a garbage string: each is HTTP 401 via `InvalidTokenError`, never a 500. Owned by Tasks 4 and 6.
- **A slow solve.** `createDraft` blocking for `wait_seconds` must not stall other requests. Owned by Task 11.
- **Bad global ids.** A garbage id, or a valid id of the wrong type, gives `null` from `node`/`planning` and `NotFound` from mutations; inside a Change Set it is an `UNKNOWN_ID` problem. Owned by Tasks 7, 8 and 9.
- **Malformed `@oneOf` input.** Zero or two fields set in a `ChangeSetItemInput` is a GraphQL validation error with HTTP 200 and no server exception; an invalid item value (date range ending before it starts) is an `INVALID_ITEM` problem. Owned by Task 9.

---

## File Structure

```
schema.graphql                           # NEW (T6, regenerated T7-T10) committed SDL
pyproject.toml                           # MODIFY (T4, T6) pyjwt[crypto], strawberry-graphql, starlette, uvicorn
src/festival_planner/
├── domain/
│   ├── programme.py festival.py drafts.py users.py   # MODIFY (T1) NewType ids
│   ├── travel.py solving.py planning.py change_sets.py insights.py ingestion.py planner.py
│   │                                    # MODIFY (T1) typed ids through signatures
│   ├── ingestion.py                     # MODIFY (T3) FestivalRepository.all/by_ids/series_by_ids,
│   │                                    #   FilmRepository.by_ids, ProgrammeRepository.screenings_of_entries
│   ├── planning_ports.py                # MODIFY (T2) PlanningRepository.schedule
│   ├── planner.py                       # MODIFY (T2) draft_diff, schedule, inputs; DraftView loses diff
│   ├── programme_queries.py             # NEW (T3) ProgrammeQueries
│   ├── identity.py                      # NEW (T4) Identity, TokenVerifier, InvalidTokenError
│   ├── change_sets.py                   # MODIFY (T9) ProblemCode.INVALID_ITEM
│   └── tests/ fakes.py builders.py test_ids.py test_programme_queries.py ...
├── adapters/
│   ├── sqlalchemy/                      # MODIFY (T1) typed mappers; (T2, T3) new repository methods
│   ├── in_process/jobs.py               # MODIFY (T6) shutdown(cancel_futures=)
│   ├── jwt/verifier.py                  # NEW (T4) TrustedIssuer, JwtTokenVerifier, trusted_issuers_from_env
│   └── local_issuer/issuer.py           # NEW (T5) LocalIssuer
├── api/                                 # NEW driving adapter
│   ├── app.py                           # (T6) ApiDependencies, create_app, bearer auth
│   ├── server.py                        # (T6) build_server: the composition root
│   ├── context.py                       # (T6) Context, Info, run(); (T7) loaders
│   ├── ids.py                           # (T7) encode/decode global ids
│   ├── loaders.py                       # (T7) Loaders
│   ├── programme_types.py               # (T7) Festival, FestivalSeries, Venue, Film, ProgrammeEntry, Screening, Event
│   ├── planning_types.py                # (T8) Viewer, FestivalPlanning, Draft, Schedule, ... ; ChangeSetItem union
│   ├── errors.py                        # (T9) NotSignedIn, NotFound, InvalidChangeSet, ...
│   ├── inputs.py                        # (T9) ChangeSetItemInput (@oneOf) -> domain items
│   ├── mutations.py                     # (T9, T10)
│   ├── schema.py                        # (T6..T10) Query, Mutation, schema
│   └── tests/ support.py test_*.py
└── cli/
    ├── __init__.py                      # MODIFY (T5, T6) register token, serve, export-schema
    ├── plan.py                          # MODIFY (T1) typed ids; (T2) lazy diff
    ├── token.py                         # NEW (T5)
    └── serve.py                         # NEW (T6) serve, export-schema
docs/adr/0006-local-token-issuer-is-a-cli.md   # NEW (T11)
```

## Schema outline

The target SDL, abbreviated. Tasks 7 to 10 build it; exact field lists are in each task. Scalars: Strawberry's `Date`, `DateTime` (ISO 8601 with offset).

```graphql
interface Node { id: ID! }

type Query {
  node(id: ID!): Node                      # null for garbage, wrong-type, unknown or not-yours
  nodes(ids: [ID!]!): [Node]!
  festivals: [Festival!]!                  # by start date, then slug
  festival(slug: String!): Festival
  venues: [Venue!]!                        # by name
  viewer: Viewer                           # null when signed out
}

type Festival implements Node { id slug name startDate endDate timeZone series: FestivalSeries
  programmeEntries(first after last before): ProgrammeEntryConnection!   # by title
  screenings(includeWithdrawn: Boolean! = false, first after last before): ScreeningConnection! }  # by start time
type FestivalSeries { slug name }
type Venue implements Node { id name }
type Film implements Node { id title year }
type ProgrammeEntry implements Node { id title year country url film: Film!
  screenings(includeWithdrawn: Boolean! = false): [Screening!]! }
type Screening implements Node { id programmeEntry: ProgrammeEntry! venue: Venue! startTime endTime
  auditorium ticketUrl events: [Event!]! withdrawn: Boolean! }
type Event { description startTime endTime }

type Viewer { issuer subject tickets: [Ticket!]! seenFilms: [Film!]!
  planning(festivalId: ID!): FestivalPlanning }          # null if not a Festival id
type FestivalPlanning { festival: Festival! activeSchedule: Schedule
  schedules(first after last before): ScheduleConnection!  # oldest first
  drafts: [Draft!]! inputs: PlanningInputs! flags: [Flag!]!
  comparisonSuggestions(limit: Int! = 10): [ComparisonSuggestion!]! }
type Draft implements Node { id festival: Festival! status: DraftStatus! stale: Boolean!
  changeSet: [ChangeSetItem!]! screenings: [ScheduledScreening!]! score: Float!
  reasons: [String!]! notes: [String!]! createdAt solvedAt diff: DraftDiff }   # diff resolved lazily
type Schedule implements Node { id festival: Festival! number: Int! screenings: [Screening!]!
  score: Float! changeSet: [ChangeSetItem!]! acceptedAt: DateTime! }
type ScheduledScreening { screening: Screening! arrivalTime: DateTime! weight: Float! }
type DraftDiff { added: [Screening!]! removed: [Screening!]! scoreDelta: Float! droppedTickets: [Screening!]! }
type PlanningInputs { screeningCommitments: [Screening!]! filmCommitments: [ProgrammeEntry!]!
  excludedScreenings: [Screening!]! excludedProgrammeEntries: [ProgrammeEntry!]! preferences: Preferences! }
type Preferences { bufferMinutes venueBuffers: [VenueBuffer!]! startDate endDate
  programmeEntryWeights: [ProgrammeEntryWeight!]! screeningWeights: [ScreeningWeight!]!
  yearWeights: [YearWeight!]! eventWeight attendEvents transportMode comparisonWeight
  comparisons: [Comparison!]! }
type Flag { kind: FlagKind! message: String! screening: Screening programmeEntry: ProgrammeEntry }
type ComparisonSuggestion { scheduled: ProgrammeEntry! other: ProgrammeEntry! weightGap: Float! }
type Ticket { screening: Screening! exchangeable: Boolean! refundable: Boolean! }
union ChangeSetItem = AddScreeningCommitment | ReleaseScreeningCommitment | ... | RecordComparison  # 18 types

type Mutation {
  createDraft(input: CreateDraftInput!): CreateDraftResult!      # DraftResult | InvalidChangeSet | NotFound | NotSignedIn
  resolveDraft(input: DraftInput!): ResolveDraftResult!          # DraftResult | InvalidChangeSet | DraftStillSolving | NotFound | NotSignedIn
  acceptDraft(input: DraftInput!): AcceptDraftResult!            # ScheduleResult | DraftNotAcceptable | NotFound | NotSignedIn
  discardDraft(input: DraftInput!): DiscardDraftResult!          # Discarded | NotFound | NotSignedIn
  recordTicket(input: RecordTicketInput!): RecordTicketResult!   # TicketResult | NotFound | NotSignedIn
  removeTicket(input: ScreeningInput!): ScreeningMutationResult! # ScreeningResult | NotSignedIn
  markSeen(input: FilmInput!): FilmMutationResult!               # FilmResult | NotFound | NotSignedIn
  unmarkSeen(input: FilmInput!): FilmMutationResult!
  dismissInferredSeen(input: ScreeningInput!): ScreeningMutationResult!  # + NotFound
  restoreInferredSeen(input: ScreeningInput!): ScreeningMutationResult!
}
input CreateDraftInput { festivalId: ID! changeSet: [ChangeSetItemInput!]! = [] }
input ChangeSetItemInput @oneOf { addScreeningCommitment: ScreeningInput  setBuffer: SetBufferInput  ... }
```

---

### Task 1: Distinct id types

**Files:**
- Modify: `domain/programme.py`, `domain/festival.py`, `domain/drafts.py`, `domain/users.py` (the aliases), and every module pyright then flags: `domain/*.py`, `adapters/sqlalchemy/*.py`, `adapters/yaml_files/solve_request.py`, `adapters/json_files/`, `adapters/solver/`, `cli/*.py`, all `tests/`.
- Modify: `domain/tests/builders.py`, `domain/tests/fakes.py`
- Test: `src/festival_planner/domain/tests/test_ids.py`

**Interfaces:**
- Produces: `VenueId`, `FilmId`, `ProgrammeEntryId`, `ScreeningId` (`domain/programme.py`); `FestivalId`, `FestivalSeriesId` (`domain/festival.py`); `DraftId`, `ScheduleId` (`domain/drafts.py`); `UserId` (`domain/users.py`). Each is `NewType("<Name>", str)`. Port and use-case parameters that take an id use its type (e.g. `FilmRepository.by_id(film_id: FilmId)`, `ProgrammeRepository.entries_by_id(ids: Iterable[ProgrammeEntryId])`, `screenings_by_id(ids: Iterable[ScreeningId])`). `ProgrammeRepository.entries` stays `Mapping[str, ProgrammeEntry]` (keys are source keys, not ids). `new_id()` stays `-> str`; callers wrap it (`DraftId(self._new_id())`).

Pyright found 474 errors on a trial switch (81 in code, 393 in tests). Fix them all; no `cast`, no `# pyright: ignore` except in `test_ids.py`. Builders take `str` parameters and wrap them, so most test call sites stay short.

- [ ] **Step 1: Write the failing guard test**

```python
# pyright: reportUnnecessaryTypeIgnoreComment=true
"""Ids of different kinds must not mix. Pyright, not pytest, enforces this:
if the ids were plain `str` aliases, the ignores below would be unnecessary
and pyright would fail."""

from festival_planner.domain.drafts import DraftId
from festival_planner.domain.programme import ProgrammeEntryId, Screening, ScreeningId
from festival_planner.domain.users import UserId

def _takes_screening(screening_id: ScreeningId) -> ScreeningId:
    return screening_id

def test_a_programme_entry_id_is_not_a_screening_id() -> None:
    _takes_screening(ProgrammeEntryId("e"))  # pyright: ignore[reportArgumentType]

def test_a_user_id_is_not_a_draft_id() -> None:
    draft_id: DraftId = UserId("u")  # pyright: ignore[reportAssignmentType]
    assert draft_id == "u"

def test_ids_are_plain_strings_at_runtime() -> None:
    s = Screening.model_validate_json(
        '{"id": "s", "programme_entry_id": "e", "venue_id": "v",'
        ' "start_time": "2030-01-01T10:00:00Z", "end_time": "2030-01-01T12:00:00Z"}'
    )
    assert type(s.id) is str and s.id == "s"
```

- [ ] **Step 2: Run pyright and see it fail**

Run: `mise exec -- uv run --with pyright pyright src/festival_planner/domain/tests/test_ids.py`
Expected: errors "Unnecessary "# pyright: ignore" rule" (the ids are still aliases).

- [ ] **Step 3: Switch the nine aliases to `NewType` and fix every pyright error**

Work outwards: domain modules, then `fakes.py` and `builders.py`, then adapters (wrap row values in mappers, e.g. `ScreeningId(row.id)`), then the CLI (wrap Typer arguments), then tests.

- [ ] **Step 4: Verify**

Run: `mise exec -- uv run --with pyright pyright src` -> `0 errors`.
Run: `env -u FORCE_COLOR mise exec -- uv run pytest -q` -> all pass (342).

- [ ] **Step 5: Commit**

`jj describe -m "refactor(domain): make ids distinct NewTypes"`; check the graph as in Global Constraints.

---

### Task 2: Planner read-side for the API: lazy diffs, one Schedule, the inputs

**Files:**
- Modify: `domain/planner.py`, `domain/planning_ports.py`, `domain/tests/fakes.py`, `adapters/sqlalchemy/planning_repositories.py`, `cli/plan.py`
- Test: `domain/tests/test_planner.py`, `adapters/sqlalchemy/tests/test_planning_repositories.py`, `cli/tests/test_plan.py` (existing tests keep passing)

**Interfaces:**
- Consumes: Task 1 id types.
- Produces:
  - `DraftView` keeps `draft: Draft` and `stale: bool`; the `diff` field is removed.
  - `Planner.draft_diff(user_id: UserId, draft_id: DraftId) -> DraftDiff | None`: `None` unless the Draft is `READY`; `NotFoundError` if not the User's.
  - `Planner.schedule(user_id: UserId, schedule_id: ScheduleId) -> Schedule`: `NotFoundError` if unknown or not the User's.
  - `Planner.inputs(user_id: UserId, festival_slug: str) -> PlanningInputs`: the accepted inputs; `NotFoundError` for an unknown slug.
  - `PlanningRepository.schedule(schedule_id: ScheduleId) -> Schedule | None`, in the fake and SQLAlchemy.

- [ ] **Step 1: Write the failing tests** in `domain/tests/test_planner.py` (reuse its `uow` fixture and planner helper):
  - `test_a_draft_view_has_no_diff_until_asked`: `"diff" not in DraftView.model_fields`.
  - `test_draft_diff_of_a_ready_draft`: create a Draft committing to `c`; `planner.draft_diff(user, view.draft.id).added == frozenset({ScreeningId("b"), ScreeningId("c")})` (adapt the two existing diff assertions at lines 103, 167, 282 to call `draft_diff`).
  - `test_draft_diff_of_a_solving_draft_is_none` (DeferredJobRunner).
  - `test_draft_diff_of_another_users_draft_is_not_found` -> `NotFoundError`.
  - `test_a_schedule_is_found_by_id_for_its_user` and `test_another_users_schedule_is_not_found`.
  - `test_inputs_are_the_accepted_inputs`: after accepting a Draft with `AddScreeningCommitment("a")`, `planner.inputs(user, SLUG).screening_commitments == frozenset({ScreeningId("a")})`; before any accept, `== PlanningInputs()`.
  - `test_planning_repositories.py::test_a_schedule_by_id`: saved Schedule round-trips; unknown id -> `None`.

- [ ] **Step 2: Run them and see them fail** (`AttributeError`/assertion).

- [ ] **Step 3: Implement.** `_view` stops computing the diff; `draft_diff` builds the request and calls `insights.diff` as `_view` did. `cli/plan.py` calls `planner.draft_diff` where it read `view.diff` (lines ~145 and ~194).

- [ ] **Step 4: Verify** pytest and pyright as in Global Constraints.

- [ ] **Step 5: Commit** `feat(planner): compute Draft diffs on demand; find one Schedule; read the inputs`

---

### Task 3: `ProgrammeQueries`, the read side of festival data

**Files:**
- Create: `src/festival_planner/domain/programme_queries.py`
- Modify: `domain/ingestion.py` (port methods), `domain/tests/fakes.py`, `adapters/sqlalchemy/repositories.py`
- Test: `domain/tests/test_programme_queries.py`, `adapters/sqlalchemy/tests/test_repositories.py`

**Interfaces:**
- Consumes: `UnitOfWork` (`domain/ingestion.py`), Task 1 ids.
- Produces, on the ports (fake and SQLAlchemy):
  - `FestivalRepository.all() -> tuple[Festival, ...]`, `by_ids(ids: Iterable[FestivalId]) -> tuple[Festival, ...]`, `series_by_ids(ids: Iterable[FestivalSeriesId]) -> tuple[FestivalSeries, ...]`
  - `FilmRepository.by_ids(ids: Iterable[FilmId]) -> tuple[Film, ...]`
  - `ProgrammeRepository.screenings_of_entries(ids: Iterable[ProgrammeEntryId]) -> tuple[Screening, ...]` (Withdrawn included)
  - Unknown ids are skipped; order is unspecified.
- Produces `class ProgrammeQueries(unit_of_work: Callable[[], UnitOfWork])` with one unit of work per call:
  - `festivals() -> tuple[Festival, ...]` by `(start_date, slug)`
  - `festival(slug: str) -> Festival | None`
  - `festivals_by_id(ids: Iterable[FestivalId]) -> Mapping[FestivalId, Festival]`
  - `series_by_id(ids: Iterable[FestivalSeriesId]) -> Mapping[FestivalSeriesId, FestivalSeries]`
  - `venues() -> tuple[Venue, ...]` by `(name, id)`; `venues_by_id(ids) -> Mapping[VenueId, Venue]`
  - `films_by_id(ids) -> Mapping[FilmId, Film]`
  - `programme_entries(festival_id: FestivalId) -> tuple[ProgrammeEntry, ...]` by `(title_key(title), id)`
  - `programme_entries_by_id(ids) -> Mapping[ProgrammeEntryId, ProgrammeEntry]`
  - `screenings(festival_id: FestivalId, *, include_withdrawn: bool) -> tuple[Screening, ...]` by `(start_time, id)`
  - `screenings_by_id(ids) -> Mapping[ScreeningId, Screening]` (Withdrawn included: Drafts and Tickets may point at them)
  - `screenings_of_entries(ids, *, include_withdrawn: bool) -> Mapping[ProgrammeEntryId, tuple[Screening, ...]]`, each tuple by `(start_time, id)`; every requested id is a key (empty tuple if none)

- [ ] **Step 1: Write failing tests** in `test_programme_queries.py` over `InMemoryUnitOfWork` with two Festivals (`b-fest` starting later than `a-fest`), Programme Entries titled `"Ödipus"`, `"apple"`, `"Banana"`, and one Withdrawn Screening:
  - `test_festivals_are_ordered_by_start_date`
  - `test_an_unknown_festival_slug_is_none`
  - `test_programme_entries_are_ordered_by_title_ignoring_case` -> `["apple", "Banana", "Ödipus"]`
  - `test_withdrawn_screenings_are_left_out_unless_asked`
  - `test_screenings_of_entries_cover_every_requested_entry`: requesting an entry with no Screenings gives `()`
  - `test_lookups_by_id_skip_unknown_ids` (one test per `*_by_id`, or parametrised)
  - SQLAlchemy: `test_festivals_all_and_by_ids`, `test_series_by_ids`, `test_films_by_ids`, `test_screenings_of_entries` in `test_repositories.py`.

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement** the port methods (SQLAlchemy: `select(...).where(Row.id.in_(ids))`; `screenings_of_entries` filters on `programme_entry_id`; load Events the same way `screenings_by_id` does), then `ProgrammeQueries`.

- [ ] **Step 4: Verify** pytest and pyright.

- [ ] **Step 5: Commit** `feat(domain): ProgrammeQueries for reading festival data`

---

### Task 4: `TokenVerifier` port and the JWT adapter

**Files:**
- Create: `src/festival_planner/domain/identity.py`, `src/festival_planner/adapters/jwt/__init__.py`, `src/festival_planner/adapters/jwt/verifier.py`
- Modify: `pyproject.toml` (`pyjwt[crypto]>=2.10`)
- Test: `src/festival_planner/adapters/jwt/tests/test_verifier.py`

**Interfaces:**
- Produces in `domain/identity.py`:
  - `class Identity(Value)`: `issuer: str`, `subject: str`
  - `class InvalidTokenError(Exception)`
  - `class TokenVerifier(Protocol)`: `def verify(self, token: str) -> Identity` (raises `InvalidTokenError`; may block on network)
- Produces in `adapters/jwt/verifier.py`:
  - `ISSUERS_ENV = "FESTIVAL_PLANNER_ISSUERS"`, `DEFAULT_AUDIENCE = "festival-planner"`, `LEEWAY_SECONDS = 30`
  - `class TrustedIssuer(BaseModel, frozen)`: `issuer: str`, `audience: str = DEFAULT_AUDIENCE`, `algorithms: tuple[str, ...] = ("EdDSA", "RS256", "ES256")`, `jwks_uri: str | None = None`, `jwks_file: Path | None = None`. Exactly one of `jwks_uri`/`jwks_file`; `algorithms` may not contain `"none"` or any `HS*`; issuer `LOCAL_ISSUER` (`"local"`) requires `jwks_file`.
  - `trusted_issuers_from_env(environ: Mapping[str, str]) -> tuple[TrustedIssuer, ...]`: unset or empty -> `()`; otherwise a JSON list; malformed JSON or entries -> `ValueError` naming `FESTIVAL_PLANNER_ISSUERS`; duplicate `issuer` -> `ValueError`.
  - `class JwtTokenVerifier`: `__init__(self, issuers: Iterable[TrustedIssuer], *, clock: Callable[[], datetime.datetime] | None = None)`; `verify(token: str) -> Identity`.

Verification order: read the unverified claims (`jwt.decode(token, options={"verify_signature": False})`) only to get `iss`; look up that `TrustedIssuer` (unknown -> `InvalidTokenError`); get the key by the header's `kid` from that issuer only (`PyJWKSet.from_json(file)` loaded once and keyed by `kid`, or `PyJWKClient(jwks_uri, cache_keys=True).get_signing_key_from_jwt`); then `jwt.decode(token, key, algorithms=list(issuer.algorithms), audience=issuer.audience, issuer=issuer.issuer, leeway=LEEWAY_SECONDS, options={"require": ["exp", "iss", "sub", "aud"]})`. Any `jwt.PyJWTError`, `KeyError`, `ValueError` becomes `InvalidTokenError`. A token without `kid` is accepted only if the issuer's key set has exactly one key.

- [ ] **Step 1: Write failing tests.** A fixture makes two Ed25519 keys (`cryptography`), writes each as a one-key JWKS file in `tmp_path` (`jwt.algorithms.OKPAlgorithm.to_jwk(public_key, as_dict=True) | {"kid": ..., "use": "sig", "alg": "EdDSA"}`), and trusts `local` (key A) and `https://other.example` (key B, via `jwks_uri=path.as_uri()`; PyJWKClient reads `file://` URLs through urllib). A helper `token(key, **claims)` signs with defaults `iss="local"`, `sub="alice"`, `aud="festival-planner"`, `exp=now+300`, `kid="a"`.
  - `test_a_valid_token_yields_its_identity` -> `Identity(issuer="local", subject="alice")`
  - `test_a_token_from_a_jwks_uri_issuer_is_verified` (issuer B, key B)
  - `test_an_expired_token_is_rejected` (`exp=now-60`, beyond the 30 s leeway)
  - `test_a_token_for_another_audience_is_rejected`
  - `test_a_token_from_an_unknown_issuer_is_rejected`
  - `test_an_unsigned_token_is_rejected` (`jwt.encode(claims, None, algorithm="none")`)
  - `test_a_token_naming_one_issuer_but_signed_by_another_is_rejected` (`iss="local"`, signed with key B, `kid="a"`)
  - `test_a_token_with_an_unknown_key_id_is_rejected`
  - `test_a_token_without_a_subject_is_rejected`
  - `test_garbage_is_rejected` (`"not-a-jwt"`, `""`, `"a.b.c"`)
  - Each rejection: `pytest.raises(InvalidTokenError)`.
  - Config: `test_no_issuers_variable_means_none_trusted`; `test_issuers_are_read_from_the_environment`; `test_malformed_issuers_are_reported` (`"{"`, `"[{}]"`, `'[{"issuer": "x"}]'`; message contains `FESTIVAL_PLANNER_ISSUERS`); `test_the_local_issuer_may_not_use_a_jwks_uri`; `test_symmetric_and_none_algorithms_are_refused` (`["HS256"]`, `["none"]`); `test_issuers_must_be_unique`.

- [ ] **Step 2: Run them and see them fail** (import errors).

- [ ] **Step 3: Implement** as above; add the dependency with `mise exec -- uv add 'pyjwt[crypto]>=2.10'`.

- [ ] **Step 4: Verify** pytest and pyright.

- [ ] **Step 5: Commit** `feat(auth): verify bearer tokens from trusted issuers`

---

### Task 5: Local token issuer and the `token` CLI

**Files:**
- Create: `src/festival_planner/adapters/local_issuer/__init__.py`, `.../local_issuer/issuer.py`, `src/festival_planner/cli/token.py`
- Modify: `src/festival_planner/cli/__init__.py`
- Test: `adapters/local_issuer/tests/test_issuer.py`, `cli/tests/test_token.py`

**Interfaces:**
- Consumes: `TrustedIssuer`, `JwtTokenVerifier`, `DEFAULT_AUDIENCE` (Task 4); `LOCAL_ISSUER` (`domain/users.py`); `create_default_path_provider().get_data_home()`.
- Produces `class LocalIssuer(directory: Path)`:
  - `default_directory() -> Path` (static): `<XDG data home>/festival-planner/local-issuer`
  - `init(self, *, force: bool = False) -> None`: makes the directory, writes `private-key.pem` (Ed25519, PKCS8, mode `0o600`) and `jwks.json` (one OKP public key, `kid` = RFC 7638 thumbprint, `alg` `EdDSA`, no `d`). Existing keys without `force` -> `FileExistsError`.
  - `issue(self, subject: str, *, audience: str = DEFAULT_AUDIENCE, lifetime: datetime.timedelta = datetime.timedelta(days=30), now: datetime.datetime | None = None) -> str`: claims `iss=LOCAL_ISSUER`, `sub`, `aud`, `iat`, `exp`; header `kid`. No keys yet -> `FileNotFoundError`.
  - `trusted_issuer(self) -> TrustedIssuer`: `issuer="local"`, `jwks_file=<directory>/jwks.json`, `algorithms=("EdDSA",)`.
- CLI (`festival-planner token ...`, `--directory` defaults to `LocalIssuer.default_directory()`):
  - `token init [--force]`: creates the keys, then prints the `FESTIVAL_PLANNER_ISSUERS` value to export, e.g. `export FESTIVAL_PLANNER_ISSUERS='[{"issuer":"local","jwks_file":"...","algorithms":["EdDSA"]}]'`. Existing keys -> red message, exit 1.
  - `token issue [--subject S] [--days N]`: prints only the token. `--subject` defaults to `getpass.getuser()`, so the token's User is the CLI's User. No keys -> red message suggesting `token init`, exit 1.

- [ ] **Step 1: Write failing tests:**
  - `test_init_writes_a_private_key_only_the_owner_can_read` (`stat.S_IMODE(...) == 0o600`)
  - `test_the_jwks_holds_one_public_key` (`"d" not in key`, `key["kid"]`, `key["crv"] == "Ed25519"`)
  - `test_init_does_not_overwrite_keys_unless_forced`
  - `test_an_issued_token_verifies_as_the_local_issuer`: `JwtTokenVerifier([issuer.trusted_issuer()]).verify(issuer.issue("alice")) == Identity(issuer="local", subject="alice")`
  - `test_an_issued_token_expires_after_its_lifetime`: issued with `now` 31 days ago and default lifetime -> `InvalidTokenError`
  - `test_issuing_without_keys_fails` (`FileNotFoundError`)
  - CLI with `typer.testing.CliRunner`: `test_token_init_prints_the_issuers_variable` (output parses as the env value and `trusted_issuers_from_env` accepts it); `test_token_issue_prints_a_token_for_the_os_user` (monkeypatch `getpass.getuser` -> `"thor"`; verified subject `"thor"`); `test_token_issue_without_keys_exits_1`.

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement.** Write the private key with `os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)`.

- [ ] **Step 4: Verify** pytest and pyright.

- [ ] **Step 5: Commit** `feat(auth): local token issuer and the token CLI`

---

### Task 6: API skeleton: app, sign-in, lifespan, `serve`, SDL

**Files:**
- Create: `src/festival_planner/api/__init__.py`, `api/app.py`, `api/context.py`, `api/schema.py`, `api/server.py`, `api/tests/__init__.py`, `api/tests/support.py`, `src/festival_planner/cli/serve.py`, `schema.graphql`
- Modify: `pyproject.toml` (`strawberry-graphql>=0.336`, `starlette>=0.40`, `uvicorn>=0.30`), `cli/__init__.py`, `adapters/in_process/jobs.py`
- Test: `api/tests/test_app.py`, `api/tests/test_schema_file.py`, `adapters/in_process/tests/test_jobs.py`

**Interfaces:**
- Consumes: `Planner` (Task 2), `ProgrammeQueries` (Task 3), `TokenVerifier`, `Identity`, `InvalidTokenError` (Task 4), `user_for`, `User`.
- Produces in `api/app.py`:
  - `@dataclass(frozen=True) class ApiDependencies`: `planner: Planner`, `programme: ProgrammeQueries`, `verifier: TokenVerifier`, `users: Callable[[Identity], User]` (signs in, creating the User on first sight).
  - `create_app(deps: ApiDependencies, *, on_startup: Callable[[], None] = _nothing, on_shutdown: Callable[[], None] = _nothing) -> Starlette`. Route `/graphql` (GET serves GraphiQL, POST runs queries). The lifespan runs `on_startup` then, on exit, `on_shutdown`, both through `anyio.to_thread.run_sync`.
  - Bearer auth happens in `get_context`, before any resolver: no header -> signed out; `Bearer <token>` -> `verifier.verify` then `deps.users`, both offloaded; anything else, or `InvalidTokenError` -> respond 401 with JSON `{"error": "invalid_token"}` and header `WWW-Authenticate: Bearer error="invalid_token"`. (Implementation choice: a small Starlette middleware on the `/graphql` route, or a `GraphQL` subclass overriding `handle_request`; either works if the tests pass.)
- Produces in `api/context.py`:
  - `@dataclass class Context`: `deps: ApiDependencies`, `viewer: User | None`, `loaders` (Task 7 fills it), `async def run(self, fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T` (via `anyio.to_thread.run_sync(functools.partial(...))`).
  - `Info = strawberry.Info[Context, None]`
- Produces in `api/schema.py`: `schema: strawberry.Schema`; `Query.viewer -> Viewer | None` with `Viewer.issuer: str`, `Viewer.subject: str` (Task 8 adds fields).
- Produces in `api/server.py`: `build_server(database: str | None, environ: Mapping[str, str], *, draft_wait_seconds: float = 2.0, solver: ScheduleSolver | None = None) -> Starlette`. It opens and migrates the database (`cli.db.open_database`'s logic; move it to `adapters/sqlalchemy/database.py` as `open_database` if importing from `cli` would invert layers), builds `Planner(ThreadPoolJobRunner(), solver or CpSatScheduleSolver(), NullDraftSolvedNotifier(), clock=UTC now, wait_seconds=draft_wait_seconds)`, `ProgrammeQueries`, `JwtTokenVerifier(trusted_issuers_from_env(environ))` and `users=lambda i: user_for(SqlAlchemyUnitOfWork(engine), i.issuer, i.subject)`. `on_startup` = `planner.resume_solving` (log how many); `on_shutdown` = `jobs.shutdown(wait=True, cancel_futures=True)` then `engine.dispose()`. Logs a warning when no issuers are trusted.
- `ThreadPoolJobRunner.shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None`.
- CLI: `festival-planner serve [--database] [--host 127.0.0.1] [--port 8000] [--draft-wait 2.0]` runs `uvicorn.run(build_server(...), host=, port=)`. `festival-planner export-schema [PATH]` writes `schema.as_str() + "\n"` to PATH or stdout.
- `api/tests/support.py`: `api_client(uow: InMemoryUnitOfWork, *, tokens: Mapping[str, Identity] = {"alice-token": Identity(issuer="local", subject="alice")}, job_runner=None, solver=None) -> TestClient` (a `Planner` over the fake with `InlineJobRunner`, `GreedySolver`, a `TickingClock`; a dict-backed `FakeVerifier`); `gql(client, query, variables=None, *, token=None) -> dict` asserting status 200 and no `errors`, returning `data`. `ALICE = "alice-token"`, `BOB = "bob-token"`.

- [ ] **Step 1: Write failing tests** in `api/tests/test_app.py`:
  - `test_signed_out_viewer_is_null`: `gql(c, "{ viewer { subject } }") == {"viewer": None}`
  - `test_a_valid_token_signs_in_and_creates_the_user`: `{"viewer": {"issuer": "local", "subject": "alice"}}`; the fake has a User for `("local", "alice")`
  - `test_an_invalid_token_is_401`: status 401, `WWW-Authenticate` header as above, no User created
  - `test_a_non_bearer_authorization_is_401` (`Basic abc`)
  - `test_startup_and_shutdown_hooks_run`: `with TestClient(create_app(deps, on_startup=..., on_shutdown=...))` records `["startup"]` inside and `["startup", "shutdown"]` after
  - `test_jobs.py::test_shutdown_can_cancel_queued_work`: one worker blocked on an `Event`, a second job queued; `shutdown(wait=False, cancel_futures=True)`; release; the second never ran
  - `test_schema_file.py::test_the_committed_schema_is_current`: `(repo_root / "schema.graphql").read_text() == schema.as_str() + "\n"`, failing with the hint `run: festival-planner export-schema schema.graphql`
  - `test_build_server_on_a_fresh_database`: `build_server(str(tmp_path / "db.sqlite"), {})` under `with TestClient(app)` answers `{ viewer { subject } }` with `null`

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement**; add dependencies with `uv add`; write `schema.graphql` with `festival-planner export-schema schema.graphql`.

- [ ] **Step 4: Verify** pytest and pyright. Smoke test by hand: `festival-planner token init`, export the printed variable, `festival-planner serve`, then `curl -s localhost:8000/graphql -H "Authorization: Bearer $(festival-planner token issue)" -H 'content-type: application/json' -d '{"query":"{ viewer { subject } }"}'` prints your OS user.

- [ ] **Step 5: Commit** `feat(api): Starlette GraphQL app with bearer sign-in and the serve command`

---

### Task 7: Festival data in the schema

**Files:**
- Create: `api/ids.py`, `api/loaders.py`, `api/programme_types.py`
- Modify: `api/context.py` (loaders), `api/schema.py`, `schema.graphql`
- Test: `api/tests/test_programme_api.py`, `api/tests/test_ids.py`

**Interfaces:**
- Consumes: `ProgrammeQueries` (Task 3), `Context`, `Info` (Task 6).
- Produces in `api/ids.py`:
  - `encode(type_name: str, domain_id: str) -> str` (same encoding as `relay.GlobalID(type_name, domain_id)`)
  - `decode(global_id: str, type_name: str) -> str | None`: the domain id if `global_id` is well-formed and of `type_name`, else `None`. Never raises.
  - `decode_any(global_id: str) -> tuple[str, str] | None`: `(type_name, domain_id)`.
- Produces in `api/loaders.py`: `class Loaders` built per request from `ProgrammeQueries` and `Context.run`, with Strawberry `DataLoader`s: `festival`, `festival_series`, `venue`, `film`, `programme_entry`, `screening` (key: id, value: domain value or `None`), and `screenings_of_entry` (key: `(ProgrammeEntryId, include_withdrawn)`, value: tuple). Each batch is one `ProgrammeQueries` call made through `Context.run`.
- Produces in `api/programme_types.py`: Strawberry types `Festival`, `FestivalSeries`, `Venue`, `Film`, `ProgrammeEntry`, `Screening`, `Event` as in the schema outline. Node types subclass `strawberry.relay.Node` with `id: relay.NodeID[str]` and a `@classmethod from_domain(cls, value) -> Self`. Relations resolve through the loaders. `Festival.programmeEntries` and `Festival.screenings` are `relay.ListConnection` fields.
- `Query`: `node(id: ID!) -> Node | None` and `nodes(ids: [ID!]!) -> [Node | None]` dispatch on `decode_any` to a per-type resolver (Draft and Schedule join in Task 8); `festivals`, `festival(slug)`, `venues`.

- [ ] **Step 1: Write failing tests.** Fixture: the fake with Festival `fest-2030` (series `fest`), Venues A and B, three Programme Entries (`"Banana"`, `"apple"`, `"Cherry"`), Screenings across both Venues, one with an Event, one Withdrawn.
  - `test_ids.py`: `test_decode_round_trips`; `test_decode_rejects_the_wrong_type`; `test_decode_rejects_garbage` (`"!!"`, `""`, base64 of `"nocolon"`).
  - `test_festivals_are_listed` (slug, name, startDate `"2030-11-08"`, timeZone, `series { slug }`)
  - `test_an_unknown_festival_is_null`
  - `test_programme_entries_page_by_title`: `first: 2` gives `apple`, `Banana` with `hasNextPage: true`; `after: endCursor` gives `Cherry`
  - `test_withdrawn_screenings_are_hidden_unless_asked` (on `Festival.screenings` and `ProgrammeEntry.screenings`)
  - `test_a_screening_shows_its_entry_venue_and_events`
  - `test_node_finds_each_type` (parametrised over Festival, Venue, Film, ProgrammeEntry, Screening: `node(id) { id __typename }` returns the same id)
  - `test_node_of_garbage_or_the_wrong_type_is_null` (`"!!"`, `encode("Venue", <screening id>)`, `encode("Nope", "x")`)
  - `test_films_of_many_entries_load_in_one_batch`: wrap `ProgrammeQueries.films_by_id` in a counting spy; `festival { programmeEntries { edges { node { film { title } } } } }` calls it once

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement**; regenerate `schema.graphql`.

- [ ] **Step 4: Verify** pytest and pyright.

- [ ] **Step 5: Commit** `feat(api): festival data with global ids, connections and DataLoaders`

---

### Task 8: Planning queries

**Files:**
- Create: `api/planning_types.py`
- Modify: `api/schema.py`, `api/loaders.py` (if a per-request cache of Planner reads helps), `schema.graphql`
- Test: `api/tests/test_planning_queries.py`

**Interfaces:**
- Consumes: `Planner.draft`, `drafts`, `draft_diff`, `active_schedule`, `schedules`, `schedule`, `inputs`, `flags`, `suggest_comparisons`, `tickets`, `seen_films` (Task 2 and step 3); Task 7 types and loaders; `ids.decode`.
- Produces in `api/planning_types.py`: `Viewer` (adds `tickets`, `seenFilms`, `planning(festivalId: ID!)`), `FestivalPlanning`, `Draft`, `Schedule` (both `relay.Node`), `DraftStatus` (enum from the domain's), `ScheduledScreening`, `DraftDiff`, `PlanningInputs`, `Preferences` and its entry types (`VenueBuffer {venue minutes}`, `ProgrammeEntryWeight {programmeEntry weight}`, `ScreeningWeight {screening weight}`, `YearWeight {year weight}`, `Comparison {preferred other}`), `Flag`, `FlagKind`, `ComparisonSuggestion`, `Ticket`, and the `ChangeSetItem` union: one output type per domain item, named after it, with ids resolved to objects (`AddScreeningCommitment { screening: Screening! }`, `SetBuffer { venue: Venue  minutes: Int }`, `RecordComparison { preferred: ProgrammeEntry!  other: ProgrammeEntry! }`, ...). `null` weight or minutes means "reset to default".
  - `Draft.diff` is its own async resolver calling `planner.draft_diff`; it does not run unless the field is selected.
  - `Viewer.planning` decodes a Festival id, loads the Festival (`null` if unknown) and carries its slug for the Planner calls.
  - `Flag.screening` is set when `target_id` is a Screening of that Festival, otherwise `Flag.programmeEntry`.
- `Query.node`/`nodes` resolve `Draft` and `Schedule` ids only for the signed-in owner (`NotFoundError` -> `null`; signed out -> `null`).

- [ ] **Step 1: Write failing tests** (fixture as in `domain/tests/test_planner.py`: Screenings a, b conflicting, c, d; seed through `deps.planner` for user alice):
  - `test_planning_without_any_activity`: `activeSchedule: null`, `drafts: []`, `inputs.preferences.bufferMinutes == 15`, `comparisonWeight == 0.5`
  - `test_a_draft_shows_status_change_set_screenings_and_diff`: after `create_draft` with `AddScreeningCommitment(b)`: `status "READY"`, `stale false`, `changeSet [{__typename: "AddScreeningCommitment", screening {id}}]`, `diff.added` ids
  - `test_the_diff_is_only_computed_when_asked`: spy on `Planner.draft_diff`; a query without `diff` never calls it
  - `test_accepting_makes_the_active_schedule_and_history`: after `accept`, `activeSchedule.number == 1`, `schedules.edges` length 1
  - `test_another_users_draft_and_schedule_are_null` (Bob queries `node` on Alice's ids; signed out also `null`)
  - `test_planning_of_a_garbage_festival_id_is_null`
  - `test_inputs_show_commitments_and_preferences` (after accepting a Draft with a Screening Commitment, a programme-entry weight and a Comparison)
  - `test_flags_and_comparison_suggestions` (a Ticket outside the Active Schedule gives `UNSCHEDULED_TICKET` with `screening` set)
  - `test_viewer_tickets_and_seen_films`

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement**; regenerate `schema.graphql`.

- [ ] **Step 4: Verify** pytest and pyright.

- [ ] **Step 5: Commit** `feat(api): planning queries: Drafts, Schedules, inputs, flags`

---

### Task 9: Draft mutations and the `@oneOf` Change Set input

**Files:**
- Create: `api/errors.py`, `api/inputs.py`, `api/mutations.py`
- Modify: `domain/change_sets.py` (`ProblemCode.INVALID_ITEM`), `api/schema.py`, `schema.graphql`
- Test: `api/tests/test_draft_mutations.py`, `api/tests/test_inputs.py`

**Interfaces:**
- Consumes: `Planner.create_draft`, `resolve`, `accept`, `discard`; `InvalidChangeSetError`, `ChangeSetProblem`, `ProblemCode`; `NotFoundError`, `DraftNotAcceptableError`, `DraftStillSolvingError`; Task 8 `Draft`, `Schedule`.
- Produces in `api/errors.py`: `NotSignedIn {message}`, `NotFound {message}`, `InvalidChangeSet {problems: [ChangeSetProblem!]!}` with `ChangeSetProblem {code: ChangeSetProblemCode!, items: [Int!]!, message}`, `DraftNotAcceptable {message}`, `DraftStillSolving {message}`.
- Produces in `api/inputs.py`:
  - `@strawberry.input(one_of=True) class ChangeSetItemInput` with one optional field per domain item kind, camelCase of the `kind` (`addScreeningCommitment: ScreeningInput`, `releaseFilmCommitment: ProgrammeEntryInput`, `setProgrammeEntryWeight: SetProgrammeEntryWeightInput {programmeEntryId: ID!, weight: Float}`, `setBuffer: SetBufferInput {venueId: ID, minutes: Int}`, `setDateRange: SetDateRangeInput {startDate: Date, endDate: Date}`, `setAttendEvents: SetAttendEventsInput {attend: Boolean}`, `setTransportMode: SetTransportModeInput {mode: String}`, `recordComparison: RecordComparisonInput {preferredId: ID!, otherId: ID!}`, ...). Shared refs: `ScreeningInput {screeningId: ID!}`, `ProgrammeEntryInput {programmeEntryId: ID!}`, `FilmInput {filmId: ID!}`, `DraftInput {draftId: ID!}`.
  - `to_change_set(items: list[ChangeSetItemInput]) -> ChangeSet`, raising `InvalidChangeSetError` with one `INVALID_ITEM` problem per item that fails Pydantic validation (items index set, message from the validation error). Ids decode with `ids.decode(..., expected type)`; an id that does not decode is passed through as-is so `check` reports it as `UNKNOWN_ID`.
- Produces in `api/mutations.py`: the four Draft mutations of the schema outline. Unions: `CreateDraftResult = DraftResult | InvalidChangeSet | NotFound | NotSignedIn`, `ResolveDraftResult = DraftResult | InvalidChangeSet | DraftStillSolving | NotFound | NotSignedIn`, `AcceptDraftResult = ScheduleResult | DraftNotAcceptable | NotFound | NotSignedIn`, `DiscardDraftResult = Discarded | NotFound | NotSignedIn`, with `DraftResult {draft: Draft!}`, `ScheduleResult {schedule: Schedule!}`, `Discarded {draftId: ID!}`. A Festival or Draft id that does not decode is `NotFound`.

- [ ] **Step 1: Write failing tests:**
  - `test_inputs.py`: `test_each_input_field_maps_to_its_domain_item` (parametrised over all 18 kinds: the input, decoded, equals the expected domain item; also catches a missing field); `test_a_null_weight_resets` -> `SetProgrammeEntryWeight(weight=None)`; `test_an_invalid_item_is_an_invalid_item_problem` (date range ending before it starts at index 1 -> `problems == (ChangeSetProblem(code=INVALID_ITEM, items=(1,), ...),)`); `test_an_undecodable_id_passes_through`.
  - `test_draft_mutations.py`:
    - `test_creating_a_draft_signed_out_is_not_signed_in`
    - `test_creating_a_draft_returns_it_solved` (`InlineJobRunner`: `status "READY"`)
    - `test_creating_a_draft_with_an_unknown_screening_is_invalid` (`code "UNKNOWN_ID"`, `items [0]`)
    - `test_an_item_with_two_fields_or_none_is_a_validation_error`: raw POST, status 200, `errors` present, `data` null, no exception logged
    - `test_creating_a_draft_for_an_unknown_festival_is_not_found` (garbage id and a Venue id)
    - `test_a_still_solving_draft_cannot_be_resolved` (`DeferredJobRunner`)
    - `test_accepting_returns_the_schedule_and_removes_the_draft`
    - `test_accepting_a_stale_draft_is_not_acceptable`
    - `test_discarding_removes_the_draft`
    - `test_another_users_draft_is_not_found` (resolve, accept, discard as Bob)

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement.** Each resolver: no viewer -> `NotSignedIn`; decode ids; `await info.context.run(planner.<use-case>, ...)`; map the domain exceptions to the typed errors. Add `INVALID_ITEM = "INVALID_ITEM"` to `ProblemCode`. Regenerate `schema.graphql`.

- [ ] **Step 4: Verify** pytest and pyright.

- [ ] **Step 5: Commit** `feat(api): Draft mutations with @oneOf Change Set items and typed errors`

---

### Task 10: Ticket and Seen mutations

**Files:**
- Modify: `api/mutations.py`, `api/schema.py`, `schema.graphql`
- Test: `api/tests/test_ticket_and_seen_mutations.py`

**Interfaces:**
- Consumes: `Planner.record_ticket`, `remove_ticket`, `mark_seen`, `unmark_seen`, `dismiss_inferred_seen`, `restore_inferred_seen`; Task 9 errors and input refs.
- Produces: `recordTicket(input: RecordTicketInput {screeningId: ID!, exchangeable: Boolean! = false, refundable: Boolean! = false})` -> `TicketResult {ticket: Ticket!} | NotFound | NotSignedIn`; `removeTicket(input: ScreeningInput)` -> `ScreeningResult {screening: Screening!} | NotFound | NotSignedIn`; `markSeen`/`unmarkSeen(input: FilmInput)` -> `FilmResult {film: Film!} | NotFound | NotSignedIn`; `dismissInferredSeen`/`restoreInferredSeen(input: ScreeningInput)` -> `ScreeningResult | NotFound | NotSignedIn`. Ids that do not decode, or that name nothing, are `NotFound` (the domain already raises for unknown Screenings and Films where it matters; `removeTicket`, `unmarkSeen` and `restoreInferredSeen` check existence through the loaders before calling the Planner).

- [ ] **Step 1: Write failing tests:** `test_recording_a_ticket_shows_on_the_viewer`, `test_recording_a_ticket_twice_updates_its_flags`, `test_removing_a_ticket`, `test_marking_and_unmarking_seen`, `test_dismissing_and_restoring_inferred_seen` (Active Schedule with an ended Screening; `seenFilms` loses then regains the Film), `test_unknown_ids_are_not_found` (parametrised over the six mutations), `test_signed_out_is_not_signed_in` (parametrised).

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement**; regenerate `schema.graphql`.

- [ ] **Step 4: Verify** pytest and pyright.

- [ ] **Step 5: Commit** `feat(api): Ticket and Seen mutations`

---

### Task 11: End to end on SQLite, and the docs

**Files:**
- Create: `api/tests/test_server_on_sqlite.py`, `docs/adr/0006-local-token-issuer-is-a-cli.md`
- Modify: `docs/superpowers/specs/2026-10-23-graphql-backend-design.md` (roadmap step 4 status and outcomes; *GraphQL conventions*: `@oneOf` Change Set items, typed errors, 401 vs signed out), `docs/adr/0003-backend-only-verifies-tokens.md` (link to 0006), `README.md` (API server and tokens section)
- Test: `api/tests/test_server_on_sqlite.py`

**Interfaces:**
- Consumes: `build_server` (Task 6), `LocalIssuer` (Task 5), the ingestion use-cases (as in `adapters/sqlalchemy/tests/test_planner_on_sqlite.py`).

- [ ] **Step 1: Write failing (or at least new) tests**, over a file-backed SQLite database in `tmp_path` (not in-memory: solves run on other threads), the Festival and Venues ingested as in `test_planner_on_sqlite.py`, a `LocalIssuer` in `tmp_path` and `environ={"FESTIVAL_PLANNER_ISSUERS": json.dumps([issuer.trusted_issuer().model_dump(mode="json")])}`:
  - `test_a_draft_is_created_polled_and_accepted`: `build_server(..., draft_wait_seconds=0)`; `createDraft` returns `SOLVING` or `READY`; poll `node(id)` (every 50 ms, at most 10 s) until `READY`; `acceptDraft`; `viewer.planning.activeSchedule.number == 1`
  - `test_a_slow_solve_does_not_block_other_requests`: a solver that blocks on a `threading.Event`; `draft_wait_seconds=5`; one thread sends `createDraft`; the main thread's `{ festivals { slug } }` returns within 1 s while the first request is still waiting; then set the event. Two threads share one `TestClient` (its portal runs both requests on one event loop).
  - `test_drafts_left_solving_are_resumed_at_startup`: save a `SOLVING` Draft through `SqlAlchemyUnitOfWork` before `build_server`; inside `with TestClient(app)`, polling shows it `READY`
  - `test_the_cli_user_and_a_local_token_are_one_user`: a Draft created through `Planner` for `user_for(..., LOCAL_ISSUER, "thor")` is listed by `viewer.planning.drafts` with a token issued for subject `"thor"`

- [ ] **Step 2: Run them.** They should pass if Tasks 6 to 10 are right; a failure here is a bug in those tasks. Fix it in a new change, not by weakening the test.

- [ ] **Step 3: Write the docs.**
  - ADR-0006, three short paragraphs: the local issuer is a CLI minting Ed25519 JWTs from a keypair in the XDG data directory; its `iss` is `"local"`, shared with the CLI's User, and reserved: any HTTP issuer uses a URL `iss`, and config rejects `"local"` with a `jwks_uri`; consequence: a frontend needs a sign-in path later (a broker or an HTTP issuer with its own `iss`).
  - Spec roadmap step 4: "done 2026-10-23, plan `2026-10-23-graphql-api-and-auth.md`", the decisions list from this plan in two or three sentences, and notes for step 5 (Curation types and mutations follow the same patterns; `ProgrammeEntry.festival` is missing because the domain value has no `festival_id`; subscriptions and the `call_soon_threadsafe` hand-off are still open).
  - README: `token init`, exporting `FESTIVAL_PLANNER_ISSUERS`, `serve`, `token issue`, the curl example, `export-schema`.

- [ ] **Step 4: Verify** pytest, pyright, `ruff check` on touched files, and `grep -rn $'\u2014' docs/adr/0006* README.md` finds no em-dash.

- [ ] **Step 5: Commit** `test(api): end to end on SQLite; docs: step 4 outcomes and ADR-0006`

---

## Deferred to later steps

- A sign-in path for the frontend (a broker or an HTTP issuer with a URL `iss`).
- A subscription-backed `DraftSolvedNotifier` with the `loop.call_soon_threadsafe` hand-off (subscriptions are out of scope).
- `ProgrammeEntry.festival` (needs `festival_id` on the domain value).
- Curation types and mutations (step 5); watch history and Enrichment (step 6).
