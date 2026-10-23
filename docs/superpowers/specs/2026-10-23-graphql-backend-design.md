# GraphQL backend design

Settled in a design session on 2026-10-22/23. Vocabulary is defined in
[`GLOSSARY.md`](../../../GLOSSARY.md); architectural decisions are in
[`docs/adr/`](../../adr/). This document records *what* the backend does;
the plans in `docs/superpowers/plans/` record how it gets built.

## Architecture

- Hexagonal ([ADR-0001](../../adr/0001-hexagonal-architecture.md)): a domain
  core of plain Python entities and use-cases with no Strawberry, SQLAlchemy,
  OR-Tools or httpx imports. Pydantic is allowed in the domain if need be.
- Driving adapters: Strawberry GraphQL and the Typer CLI.
- Driven ports: `ProgrammeSource` (festival scrapers), `EnrichmentProvider`,
  `WatchHistoryProvider` (Letterboxd RSS/CSV, Manual), `RouteProvider`,
  `ScheduleSolver` (OR-Tools CP-SAT), `TokenVerifier`, repositories, `JobRunner`.
- Lives in this repo as sibling packages of the existing code.
- The `ScheduleSolver` port takes a self-contained **solve request** (plain
  values). The CLI builds it from local files, the server from the database.
  `--export-request` / `--request` let a real Draft be replayed in the CLI, so
  solver experiments never need the server.
- Persistence: SQLAlchemy 2 + Alembic on SQLite, kept portable to Postgres
  ([ADR-0002](../../adr/0002-sqlite-first-portable-to-postgres.md)).
- Auth: the backend only verifies OIDC/JWT bearer tokens from configured
  issuers; a separate minimal local token issuer lives in the same repo; a User
  is keyed on (issuer, subject)
  ([ADR-0003](../../adr/0003-backend-only-verifies-tokens.md)).

## Festival data

Read-only in the API; filled by adapters (scrapers, route and enrichment
providers).

- **Festival** is one edition; an optional **Festival Series** groups editions.
- **Film** is the cross-festival work, with external ids (e.g. Letterboxd).
  Seen and Enrichment attach to Films.
- **Programme Entry** is a Film as presented by one Festival; its
  festival-supplied information is primary for display. Screenings and
  Curations point at Programme Entries.
- **Screening**: one showing of a Programme Entry at a Venue (optional
  Auditorium), with optional ticket URL.
- **Event**: belongs to one Screening (e.g. director talk, debate, award
  ceremony); free-form description; either within the Screening (no own times)
  or separately timed. Standalone Events are out of scope for now.
- **Venue** and **Route** are global. A Route is (from Venue → to Venue,
  Transport Mode, minutes): one-directional, fixed duration, precomputed. One
  global default Transport Mode (walk + e-scooter) must cover every Venue pair
  (validated at ingestion). A User picks one Transport Mode per Festival; pairs
  without a Route in that mode fall back to the default mode.
- **Enrichment**: source-tagged extra data on a Film, shown alongside but never
  replacing festival information; fetched as a job after ingestion.

## Persistence and ingestion

- Times are timezone-aware, stored as UTC; a Festival has an IANA time zone
  and its dates are local dates
  ([ADR-0005](../../adr/0005-aware-datetimes-with-festival-time-zone.md)).
- A Festival has a unique human-readable slug (e.g.
  `films-from-the-south-2026`), name, local start and end dates, time zone and
  an optional Festival Series (slug, name). The `ProgrammeSource` describes the
  Festival it scrapes; ingestion creates or updates it.
- Ids are opaque strings, random UUIDs assigned on first sight and found again
  by natural keys:
  - Programme Entry: (Festival, source key). The source key is supplied by the
    `ProgrammeSource` (for Filmfrasor, the film page's URL path); re-ingestion
    updates title, year etc. in place.
  - Screening: (Programme Entry, Venue, start time). Screenings missing from a
    re-scrape become **Withdrawn**, never deleted; Withdrawn Screenings are
    not offered to the solver. Auditorium, ticket URL and Events update in
    place.
- Film resolution: reuse a Film with the same normalised title and year,
  else create one; an unknown year always creates a new Film. No fuzzy
  matching or merging yet: duplicates are the safe failure.
- Venues are global and carry aliases; ingestion resolves a source's raw venue
  names through them. An unknown venue name aborts the whole ingestion (one
  transaction) and reports every unknown name. This retires the legacy
  class-level cinema validation.
- A `RouteProvider` (first adapter: the existing YAML travel times) replaces
  the global Route set; the default Transport Mode must cover every ordered
  pair of Venues.
- Ingestion runs synchronously from the CLI, idempotently, one transaction per
  run. Repositories and SQLAlchemy are synchronous.
- The adapter has its own SQLAlchemy declarative models and explicit mappers
  to and from domain models.
- The database defaults to `$XDG_DATA_HOME/festival-planner/festival-planner.db`,
  overridable by `FESTIVAL_PLANNER_DATABASE_URL` or `--database`. Tests run
  the Alembic migrations, not `create_all`.

## Planning

- One **Active Schedule** per (User, Festival); previously accepted Schedules
  form the history. A User may have several **Drafts** at once.
- A Draft is a change set plus the Schedule solved from it
  ([ADR-0004](../../adr/0004-drafts-are-change-sets.md)). Change-set items:
  add/release Screening Commitment, add/release Film Commitment,
  add/remove Excluded, set or reset one Preference setting, record a
  Comparison, adopt a Curation (step 5). Accepting applies the change set and
  makes the Schedule Active atomically. A Draft is **Stale** once the Active
  Schedule it was based on is replaced; it cannot be accepted, and re-solving
  re-validates its change set against the new base and solves it again.
  Re-ingestion, Seen and Ticket edits do not make Drafts Stale.
- The accepted inputs are a snapshot per (User, Festival) (commitments,
  Excluded, a Preferences document); each Schedule in the history keeps the
  change set that produced it.
- Tickets and Seen are edited directly, never through change sets.
- Change sets are validated on Draft creation against the current inputs
  and the Festival's programme. Rejected: unknown ids; the same target added
  and released, or committed and Excluded, in one set; two items for one
  Preference setting key; "A over B" with "B over A"; two Screening
  Commitments for one Programme Entry; releasing or un-Excluding what is not
  there; adding what is already there; committing to something Excluded in
  the base unless the set also removes that Excluded. Re-solving a Stale
  Draft drops items that became no-ops (with a note) and fails, leaving the
  Draft unchanged, on contradictions.
- Draft statuses: `SOLVING`, `READY`, `INFEASIBLE`, `FAILED` (solver error,
  or no Schedule within the time limit); Stale is derived. Only a `READY`,
  non-Stale Draft can be accepted; accepting records a Schedule in the
  history (Screenings, change set, score, accepted-at) and removes the
  Draft. Discarding deletes a Draft. Empty change sets are allowed. Screenings
  that started between solving and accepting are accepted as they are.
- Solving is deterministic (fixed seed, interleaved search, deterministic time
  limit). Ties between equally good Schedules break towards the Active
  Schedule, then lower Screening ids, via a second lexicographic pass
  ([ADR-0004](../../adr/0004-drafts-are-change-sets.md)).
- Solve jobs read in one short unit of work, solve outside any transaction
  and write in another; SQLite runs in WAL mode with a busy timeout. Drafts
  left `SOLVING` at startup are resubmitted.
- **Screening Commitment**: hard constraint, that exact Screening.
  **Film Commitment**: hard constraint, exactly one Screening of that Programme
  Entry. Releasing one is a change-set item.
- **Ticket**: data type for "I hold a ticket", with an exchangeable/refundable
  flag. Informational only for now (no automatic commitment).
- **Excluded**: a Programme Entry or Screening the User does not want.
- **Seen** Films are not scheduled unless committed to.
- Screenings that have started are fixed: kept if in the Active Schedule,
  dropped otherwise. Only the remaining Screenings are solved.
- No stability bonus towards the Active Schedule: reshuffling uncommitted
  Screenings is fine; heavy reshuffling signals too few preferences.
- Draft status: `SOLVING` → `READY` | `INFEASIBLE` (Stale as above). The
  creating mutation waits briefly (configurable, ~2 s) and returns the solved
  Draft if done; otherwise the frontend polls. "Draft solved" goes through a
  port so a subscription can replace polling later.
- Every Draft exposes its changes against the Active Schedule (added, removed,
  score delta). The delta compares the Draft with the Active Schedule
  re-scored under the Draft's Preferences; it warns when a ticketed Screening
  is dropped.
- Flags per (User, Festival): Commitments or Tickets on Withdrawn Screenings,
  Tickets outside the Active Schedule, Withdrawn Screenings in the Active
  Schedule.
- Exported solve requests carry a format version.
- **Preferences** (first version): per-Programme-Entry and per-Screening
  weights, year weights, Event weight (for Screenings with Events), attend
  Events (separately timed Events block time), general buffer and per-Venue
  buffer, date range, Transport Mode, Comparisons; curation weight arrives
  with Curations (step 5). Preferences stay a frozen Pydantic value. Likely
  next: actors, genres, daily time window.
- **Comparison**: "A over B", a change-set item and Preference; one per
  unordered pair, the latest replacing the earlier. `formulate` fits
  Bradley–Terry strengths (deterministic MM iteration, weak prior) over the
  compared Programme Entries and adds `comparison_weight` (default 0.5, never
  negative) times the centred log-strength to their weights. A query
  suggests up to N pairs that conflicted in the latest `READY` Draft (else
  the Active Schedule) where exactly one was scheduled, not yet compared,
  closest weights first; conflicts are recomputed with `formulate`, not
  stored.
- **Ticket**: one per (User, Screening) with `exchangeable` and `refundable`
  flags; never commits; kept and flagged when its Screening is Withdrawn.

## Seen and watch history

- Seen is per Film; sources: manual, provider sync, or a Screening in the
  Active Schedule that has ended. The latter is derived, not stored;
  dismissing it ("I didn't go") is stored. Manual Seen is stored per (User, Film);
  unmarking deletes it.
- Letterboxd sync is import-only and on demand (a mutation that runs a job);
  CSV upload is its own mutation. Imports that match no Film are dropped.

## Curation

- **Organizations** may be linked to Venues ("operates/programmes";
  informational only).
- **Membership** gives a User the curator role in an Organization or in a
  Festival. An **Admin** (User flag, granted via CLI) creates Organizations and
  grants Memberships through admin-only mutations.
- A **Curation** is published by an Organization or by a Festival, authored by
  Curators, and may carry **Curator Notes**. Order is for display only.
- A **Suggested Schedule** is generated from a Curation's Programme Entries over
  a date window, with a heavy User-tunable curation weight. Signed in, it is a
  Draft; accepting it creates Film Commitments for the included entries.
  Signed out, it uses default Preferences, is cached per (Curation, date), and
  becomes a Draft on sign-in.
- Curations are public; Schedules, Drafts and Seen are private.

## GraphQL conventions

- Code-first Strawberry schema, exported to SDL and committed; the frontend
  generates types from it.
- `Node` interface with global ids; cursor connections only for long lists
  (Screenings, Programme Entries, schedule history); plain lists otherwise.
- Mutations take a single `input` and return a union of success and typed
  errors.
- DataLoaders on every relation.

## Out of scope for now

Account deletion and data export; standalone Events; curator priority tiers;
per-Venue-pair Route choice; WebSocket subscriptions; scheduled watch-history
sync; pushing Seen to Letterboxd.

## Roadmap

Each step is its own plan and leaves working, tested software:

1. **Domain core and solver boundary**: domain values, scheduling rules,
   CP-SAT adapter, CLI on the solve request (JSON export/replay).
2. **Persistence**: Festival, Festival Series, Film, Programme Entry,
   Screening, Event, Venue and Route; SQLAlchemy repositories; Alembic;
   ingesting a `ProgrammeSource` (the Filmfrasor scraper) and Routes into the
   database. Decided 2026-10-23 (see *Persistence and ingestion* above and
   [ADR-0005](../../adr/0005-aware-datetimes-with-festival-time-zone.md)).
   Organization moves to step 5 and Film external ids to step 6.
3. **Planning use-cases** (done 2026-10-23, plan `2026-10-23-planning-use-cases.md`): Drafts as change sets, accept, Stale, diff,
   Comparisons, Tickets, Seen-from-schedule; in-process `JobRunner`.
   Also: deterministic solving (CP-SAT seed and tie-break, so Draft diffs
   don't show noise), change-set validation for contradictory inputs, a
   format version in exported solve requests, Comparisons in Preferences,
   a bare User keyed on (issuer, subject) with the CLI acting as a local
   User, and a minimal `plan` CLI. Preferences stay Pydantic. Decided
   2026-10-23.
4. **GraphQL API and auth**: distinct id types (`NewType`) before the
   global-id mapping; Strawberry schema over the use-cases,
   `TokenVerifier` adapters, local token issuer, SDL export. Evaluate
   Strawberry's Pydantic integration
   (<https://strawberry.rocks/docs/integrations/pydantic>) for deriving
   GraphQL types and inputs. Pydantic is approved in the domain if need be
   (ADR-0001), so domain models may become Pydantic models where that lets
   Strawberry derive types directly.
   From step 3: the server calls `Planner.resume_solving()` once at startup
   (the CLI currently does it on every command) and shuts the
   `ThreadPoolJobRunner` down in its lifespan; `create_draft`/`resolve` block
   up to `wait_seconds`, so run them off the event loop; a subscription-backed
   `DraftSolvedNotifier` is called on a worker thread and must hand off with
   `loop.call_soon_threadsafe`; Draft diffs are computed eagerly in
   `DraftView` and should become a lazy field.
5. **Curation**: Organizations, Memberships, Admin, Curations, Curator Notes,
   Suggested Schedules (signed in and anonymous), curation weight in
   Preferences and the adopt-a-Curation change-set item.
6. **Watch history and Enrichment**: Letterboxd RSS/CSV import, enrichment
   fetch job.
