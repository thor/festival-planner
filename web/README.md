# Entr’acte web

The web app for Entr’acte, the festival planner. React 19, shadcn on Base
UI, Tailwind 4, urql core with gql.tada types from `../schema.graphql`.

Design: [DESIGN.md](DESIGN.md). Words: [CONTEXT.md](CONTEXT.md).

## Architecture

Ports and adapters, like the backend.

- `domain/`: types and pure functions (time in the Festival's zone, the
  Change Set rules, tickets to let go, timeline layout). No React.
- `domain/ports.ts`: interfaces the app needs: programme, planning, session.
- `adapters/graphql`: urql core with gql.tada types from `../schema.graphql`.
- `adapters/memory`: seeded sample data and a greedy fake solver, so the
  app runs without a server.
- `adapters/browser`: the token in localStorage.
- `app/`: hooks that turn ports into view models and actions.
- `views/`: props in, JSX out. No hooks, no fetching.
- `routes/`: call one app hook, render one view.

Pick the adapter with `VITE_ADAPTER=memory|graphql` (default `memory`).

## Run

```bash
pnpm install
pnpm dev                     # sample data in memory, signed in
```

Against the API:

```bash
# In the repo root, with FESTIVAL_PLANNER_ISSUERS set (see ../README.md)
mise exec -- festival-planner serve

# Here. Vite proxies /graphql to http://127.0.0.1:8000
# (FESTIVAL_PLANNER_API overrides it).
VITE_ADAPTER=graphql pnpm dev
```

Sign in with the account icon. Paste a token from
`festival-planner token issue`.

## Check

```bash
pnpm test        # domain rules
pnpm check       # tsc, oxlint, oxfmt --check; writes nothing
pnpm format      # oxfmt
pnpm lint:fix    # oxlint --fix
pnpm build       # types and bundle
pnpm schema      # regenerate GraphQL types after schema.graphql changes
```

From the repo root: `mise run web:check`, or `mise run web:fix` to
format and fix. `mise run fix` covers the Python side too.

## Pages

- `/` Home: every festival, on now first, then ahead, then over
- `/:slug` programme, filter by day
- `/:slug/film/:id` one film, its screenings, tickets
- `/:slug/schedule` the Active Schedule as day tracks
- `/:slug/tickets` tickets to let go, then the ones held
- `/:slug/drafts` and `/:slug/drafts/:id` diff, accept, discard, solve again
- `/:slug/compare` which would you rather see
- `/:slug/preferences` days, arriving early, events, years, comparisons

Edits collect in the tray as a Change Set. Solve makes a Draft.
