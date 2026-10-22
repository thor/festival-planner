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

## Planning

- One **Active Schedule** per (User, Festival); previously accepted Schedules
  form the history. A User may have several **Drafts** at once.
- A Draft is a change set plus the Schedule solved from it
  ([ADR-0004](../../adr/0004-drafts-are-change-sets.md)). Change-set items:
  add/release Screening Commitment, add/release Film Commitment,
  add/remove Excluded, change a Preference, record a Comparison, adopt a
  Curation. Accepting applies the change set and makes the Schedule Active
  atomically. Other Drafts become Stale and can be re-solved (nice-to-have).
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
  score delta).
- **Preferences** (first version): per-Programme-Entry and per-Screening
  weights, year weights, Event weight (for Screenings with Events), attend
  Events (separately timed Events block time), general buffer and per-Venue
  buffer, date range, curation weight, Transport Mode, Comparisons. Likely
  next: actors, genres, daily time window.
- **Comparison**: "A over B", a change-set item and Preference. A query
  suggests pairs that conflicted in the latest Draft. Turning Comparisons into
  solver weights is an implementation detail (e.g. Bradley–Terry-style).

## Seen and watch history

- Seen is per Film; sources: manual, provider sync, or a past committed
  Screening (automatic, undoable).
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
2. **Persistence**: Festival, Film, Venue, Organization entities; SQLAlchemy
   repositories; Alembic; ingesting a `ProgrammeSource` (the Filmfrasor
   scraper) and Routes into the database.
3. **Planning use-cases**: Drafts as change sets, accept, Stale, diff,
   Comparisons, Tickets, Seen-from-schedule; in-process `JobRunner`.
4. **GraphQL API and auth**: Strawberry schema over the use-cases,
   `TokenVerifier` adapters, local token issuer, SDL export. Evaluate
   Strawberry's Pydantic integration
   (<https://strawberry.rocks/docs/integrations/pydantic>) for deriving
   GraphQL types and inputs. Pydantic is approved in the domain if need be
   (ADR-0001), so domain models may become Pydantic models where that lets
   Strawberry derive types directly.
5. **Curation**: Organizations, Memberships, Admin, Curations, Curator Notes,
   Suggested Schedules (signed in and anonymous).
6. **Watch history and Enrichment**: Letterboxd RSS/CSV import, enrichment
   fetch job.
