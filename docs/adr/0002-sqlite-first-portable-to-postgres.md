# SQLite first, kept portable to Postgres

Persistence uses SQLAlchemy 2 with Alembic migrations against SQLite for development and early use, keeping the option to move to Postgres later. To keep that move cheap, schema and queries avoid dialect-specific features (no Postgres arrays/JSONB operators, no SQLite-only behaviours), and persistence sits behind repository ports per ADR-0001.

## Consequences

Some conveniences (JSONB querying, `LISTEN/NOTIFY` for job wake-ups, concurrent writers) are unavailable until the move; the in-process `JobRunner` must tolerate SQLite's single-writer model.
