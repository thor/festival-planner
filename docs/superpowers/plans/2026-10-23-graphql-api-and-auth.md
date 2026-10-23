# GraphQL API and Auth Implementation Plan

> Trimmed after implementation to its header, decisions and deferred items. The full task text is in the change history, commit `8fadcc4224d0`.

**Goal:** Serve the planning use-cases and the read-only festival data over a code-first Strawberry GraphQL API, signed in with bearer JWTs from configured issuers, plus a CLI-based local token issuer and a committed SDL.

**Architecture:** Hexagonal, as in steps 1 to 3. The domain gains distinct id types (`NewType`), a `ProgrammeQueries` read service, lazy Draft diffs and a `TokenVerifier` port with an `Identity` value. Driven adapters: a PyJWT verifier (`adapters/jwt/`) and a local Ed25519 issuer (`adapters/local_issuer/`). A new driving adapter, `api/`, maps domain values to Strawberry types (hand-written, not derived from Pydantic), runs every domain call off the event loop and is served by Starlette and uvicorn. The CLI gains `serve`, `token` and `export-schema`.

**Tech Stack:** Python 3.13, Pydantic 2, SQLAlchemy 2, Strawberry GraphQL (0.336+), Starlette, uvicorn, anyio, PyJWT with `cryptography`, Typer, pytest. Tooling via `mise` + `uv`; version control is **jj**.

**Spec:** `docs/superpowers/specs/2026-10-23-graphql-backend-design.md`, sections *Architecture*, *GraphQL conventions*, *Planning* and roadmap step 4. Vocabulary: `GLOSSARY.md`. Decisions: `docs/adr/0001` (hexagonal), `0003` (backend only verifies tokens), `0004` (Drafts are change sets).

## Decisions

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

Changed during execution:

- PyJWT 2.15 refuses non-http(s) key URLs, so `jwks_uri` must be http(s) and the floor is `pyjwt[crypto]>=2.15` (older versions can leak a `TypeError` on an algorithm mismatch).
- The plan let an id inside a Change Set that does not decode pass through to the domain. That accepted raw domain ids, so such ids are `UNKNOWN_ID` problems instead.
- GraphQL enums are API-side copies of the domain enums, mapped by value, rather than `strawberry.enum` applied to the domain classes (ADR-0001).
- After the final review: remote keys are not cached past the key-set cache, unexpected error messages are masked, and Flag lookups are batched.

## Deferred to later steps

- A sign-in path for the frontend (a broker or an HTTP issuer with a URL `iss`).
- A subscription-backed `DraftSolvedNotifier` with the `loop.call_soon_threadsafe` hand-off (subscriptions are out of scope).
- `ProgrammeEntry.festival` (needs `festival_id` on the domain value).
- Curation types and mutations (step 5); watch history and Enrichment (step 6).
- From the final review: rate-limit key refetches on an unknown `kid` before any `jwks_uri` issuer goes live; masking hides Strawberry's own paging errors (`first` above 100, a bad cursor).
