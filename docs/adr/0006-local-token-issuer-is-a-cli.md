# The local token issuer is a CLI, and its `iss` is reserved

The local token issuer from [ADR-0003](0003-backend-only-verifies-tokens.md) is a CLI, not a server: `festival-planner token init` creates an Ed25519 keypair in the XDG data directory, and `festival-planner token issue` mints JWTs signed with it. The backend trusts it like any other issuer, through `FESTIVAL_PLANNER_ISSUERS`, and reads its public keys from a JWKS file. We chose this over a small HTTP issuer because a single user on one machine needs no login flow, and a CLI that only writes files has no network surface.

Its `iss` is `"local"`, the same issuer the CLI's own User has, so a token for subject `thor` signs in as the same User as the CLI run by `thor`. `"local"` is reserved for this CLI. No HTTP server may ever issue tokens with it: any HTTP issuer, now or later, uses a URL as its `iss`. The issuer config enforces this: `"local"` may only use `jwks_file`, and config with a `jwks_uri` for it is rejected.

## Consequences

A browser frontend cannot get a token from a CLI, so it will need its own sign-in path later: a broker or an HTTP issuer, each with its own URL `iss`. Its Users are then new Users, unless that later decision links them to the local ones.
