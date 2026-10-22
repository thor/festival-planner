# Aware datetimes, with a time zone per Festival

Screening and Event times are timezone-aware datetimes in the domain and are stored as UTC; each Festival carries an IANA time zone, and anything phrased in festival days (a Festival's dates, a Preferences date range) is a local date interpreted through that zone. We chose this over keeping naive festival-local datetimes because "has this Screening started?" must be correct across DST changes and for Users outside the festival's zone, and because GraphQL `DateTime` values carry offsets anyway. `ProgrammeSource` adapters attach the Festival's zone at the boundary, and the domain rejects naive Screening and Event times.

## Consequences

SQLite has no timezone-aware column type, so the persistence adapter normalises to UTC on write and re-attaches UTC on read; converting to festival-local time for display or day boundaries is always explicit. Legacy YAML inputs, which are naive, are interpreted in a configured festival zone when building a solve request.
