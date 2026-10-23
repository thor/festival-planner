# Web

Concepts for the Festival Planner frontend. React 19, shadcn on Base UI,
Tailwind 4, urql core with gql.tada types from `../schema.graphql`.

Design and layering: [DESIGN.md](DESIGN.md).

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
pnpm build       # types and bundle
pnpm lint
pnpm schema      # regenerate GraphQL types after schema.graphql changes
```

## Pages

- `/:slug` programme, filter by day
- `/:slug/film/:id` one film, its screenings, tickets
- `/:slug/week` the Active Schedule as day tracks
- `/:slug/drafts` and `/:slug/drafts/:id` diff, accept, discard, solve again
- `/:slug/compare` which would you rather see

Edits collect in the tray as a Change Set. Solve makes a Draft.
