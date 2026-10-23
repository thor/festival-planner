# Planning Use-Cases Implementation Plan

> Trimmed after implementation to its header, decisions and deferred items. The full task text is in the change history, commit `6850c537a414`.

**Goal:** Let a User plan a Festival through Drafts that are Change Sets: create, solve (deterministically, through a `JobRunner`), diff against the Active Schedule, accept, go Stale, re-solve and discard; plus Comparisons, Tickets, Seen (manual and inferred from the Active Schedule), flags, and a minimal `plan` CLI acting as a local User.

**Architecture:** Hexagonal, as in steps 1 and 2. The domain gains planning values (`Comparison`, `PlanningInputs`, `Ticket`, change-set items), change-set rules (`check`, `apply`, `rebase`), Bradley–Terry comparison bonuses in `formulate`, planning entities (`User`, `Draft`, `Schedule`), ports (`UserRepository`, `PlanningRepository`, `TicketRepository`, `SeenRepository`, `PlanningUnitOfWork`, `JobRunner`, `DraftSolvedNotifier`), pure read-side functions (diff, flags, comparison suggestions, inferred Seen) and a `Planner` holding the use-cases. Driven adapters: the CP-SAT solver becomes deterministic with a lexicographic tie-break; SQLAlchemy gets the planning tables (migration `0002`), repositories and WAL mode; `adapters/in_process/` holds the thread-pool and immediate job runners and a null notifier. The Typer CLI composes them as `festival-planner plan …`.

**Tech Stack:** Python 3.13, Pydantic 2, SQLAlchemy 2, Alembic, SQLite, OR-Tools CP-SAT, Typer, pytest. Tooling via `mise` + `uv`; version control is **jj**.

**Spec:** `docs/superpowers/specs/2026-10-23-graphql-backend-design.md`, sections *Planning*, *Seen and watch history* and roadmap step 3. Vocabulary: `GLOSSARY.md` (note **Change Set**, **Stale**, **Seen**, **Withdrawn**). Decisions: `docs/adr/0001` (hexagonal), `0002` (SQLite first, portable), `0003` (User keyed on issuer and subject), `0004` (Drafts are change sets; tie-break), `0005` (aware datetimes).

## Decisions

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

## Deferred to later steps

- GraphQL types, global ids and `NewType` ids over `Planner` (step 4); the server calls `resume_solving()` at startup and uses `ThreadPoolJobRunner`. Done in step 4.
- A subscription-backed `DraftSolvedNotifier` (WebSockets are out of scope).
- Curation weight in Preferences and the adopt-a-Curation item (step 5).
- Provider-synchronised Seen (step 6); `SeenRow.source` is ready for it.
