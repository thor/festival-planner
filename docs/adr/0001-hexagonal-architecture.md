# Hexagonal architecture for the backend

The backend is built as ports and adapters: a domain core of plain Python entities and use-cases with no Strawberry, SQLAlchemy or HTTP-client imports, driven by GraphQL (Strawberry) and the CLI (Typer), and driving ports for every external concern — `ProgrammeSource` (festival scrapers), `EnrichmentProvider` and `WatchHistoryProvider` (e.g. Letterboxd), `RouteProvider`, `ScheduleSolver` (OR-Tools CP-SAT), `TokenVerifier`, repositories and a `JobRunner`. We chose this over the simpler "Strawberry types on top of ORM models" layout because nearly every capability has several interchangeable providers (festivals, metadata sources, identity issuers, storage engines), and the solver must stay usable from the CLI without the server.

## Consequences

GraphQL types are a mapping layer over domain entities, not the entities themselves, so schema changes and domain changes are deliberately decoupled at the cost of some duplication.

The `ScheduleSolver` port takes a self-contained solve request (Screenings, Routes, commitments, exclusions, Seen, Preferences) as plain domain values. The CLI builds it from local files and the server builds it from the database, so solver experimentation never needs the server, database or auth.

Pydantic is allowed in the domain when it earns its place (validation, serialisation); not everything has to be pushed into adapters. The framework ban covers Strawberry, SQLAlchemy, HTTP clients and solver libraries.
