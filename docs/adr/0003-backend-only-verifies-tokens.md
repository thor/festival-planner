# The backend only verifies tokens; identity lives elsewhere

The backend is a pure resource server: it verifies bearer tokens (JWT/OIDC) from a configured list of trusted issuers and never handles passwords or login flows. A User is keyed on (issuer, subject). Local, self-hosted authentication is provided by a separate minimal token issuer in the same repo, which is just one more trusted issuer. We chose this over an auth module inside the backend so that adding or swapping identity providers (Google, GitHub via a broker, Keycloak, local) is configuration rather than code, and so the API has no credential-handling surface.

The local token issuer is a CLI with a reserved `iss`; see [ADR-0006](0006-local-token-issuer-is-a-cli.md).
