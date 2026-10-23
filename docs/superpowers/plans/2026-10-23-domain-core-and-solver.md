# Domain Core and Solver Boundary Implementation Plan

> Trimmed after implementation to its header, decisions and deferred items. The full task text is in the change history, commit `6850c537a414`.

**Goal:** Introduce a framework-free domain core (programme, travel, preferences, scheduling rules) behind a `ScheduleSolver` port, re-implement the CP-SAT solver as an adapter, and run the CLI's `solve` on a self-contained, JSON-exportable solve request.

**Architecture:** Hexagonal (ports and adapters). `festival_planner.domain` holds frozen dataclasses and pure functions; `formulate()` turns a `SolveRequest` into a `Formulation` (candidates, weights, required screenings, groups, conflicts) so all scheduling rules are testable without OR-Tools. Adapters under `festival_planner.adapters` implement the solver port (CP-SAT) and translate inputs (legacy YAML files, JSON solve requests). The Typer CLI is a driving adapter that renders domain values.

**Tech Stack:** Python 3.13, stdlib dataclasses, OR-Tools CP-SAT 9.15, Pydantic 2 (only in the JSON adapter, via `TypeAdapter`), Typer + Rich, pytest. Tooling via `mise` + `uv`; version control is **jj** (not git).

**Spec:** `docs/superpowers/specs/2026-10-23-graphql-backend-design.md` (roadmap step 1). Vocabulary: `GLOSSARY.md`. Decisions: `docs/adr/0001-hexagonal-architecture.md`.

## Decisions

- Nothing in `src/festival_planner/domain/` may import Strawberry, SQLAlchemy, OR-Tools, Pydantic, httpx or any other third-party library; stdlib only. (Step 2 allowed Pydantic in the domain, per ADR-0001.)
- Use glossary terms in code: Venue (not cinema), Screening, Programme Entry, Event, Route, Transport Mode, Preferences, Screening Commitment, Film Commitment, Excluded, Seen. The legacy `models.py` / YAML files keep their old names; only adapters translate.
- Default Transport Mode is `"walk+e-scooter"`.
- Routes are one-directional; a missing Route raises `MissingRouteError` in the domain. The legacy YAML adapter keeps the old behaviour (configured travel times work both ways; unconfigured pairs get 30 minutes).
- Domain value objects are immutable; collections in them are tuples / frozensets / mappings, never mutated. (Frozen dataclasses here; step 2 made them frozen Pydantic models, `values.Value`.)
- Intentional behaviour changes vs. the old solver (call them out in review, don't "fix" them): screenings on different calendar days *can* conflict (e.g. 23:00 and 00:10); "at most one screening per film" is now per Programme Entry (legacy: per title, which the YAML adapter maps 1:1).
