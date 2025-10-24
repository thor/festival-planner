# Cinema Validation

## Overview

The Festival Planner validates cinema names against `config/cinemas.yaml` to ensure data quality. Cinema aliases are configurable, making it easy to handle name variations without code changes.

## Configuration

Cinema aliases are defined in `config/cinemas.yaml`:

```yaml
cinema_aliases:
  Vika:
    - "Vika Kino"
    - "vika"
    - "vika kino"
  Cinemateket:
    - "cinemateket"
  Vega:
    - "vega"
    - "vega scene"
```

All aliases are case-insensitive and automatically normalized to the canonical name (the key).

## How It Works

1. **Scraping**: When films are scraped, cinema names are validated and normalized
2. **Validation**: Only cinemas listed in the config are accepted
3. **Error Handling**: Invalid cinema names log a warning and the film is skipped
4. **Normalization**: Aliases like "Vika Kino" are automatically normalized to "Vika"

## Auditorium Parsing

The scraper intelligently parses cinema and auditorium information:

- `"Vika Kino 3"` → cinema: `"Vika"`, auditorium: `"3"`
- `"Cinemateket Lillebil"` → cinema: `"Cinemateket"`, auditorium: `"Lillebil"`
- `"Vega"` → cinema: `"Vega"`, auditorium: `None`

## Adding New Cinemas or Aliases

Simply edit `config/cinemas.yaml`:

```yaml
cinema_aliases:
  NewCinema:
    - "New Cinema Name"
    - "new cinema"
  Vika:
    - "Vika Kino"
    - "vika"
    - "Vika Cinema"  # ← Add new alias
```

No code changes needed - aliases are loaded dynamically at runtime.

## Running Tests

```bash
# Run all tests
mise run test

# Or directly with uv
uv run pytest
```

The test suite includes 32 tests covering:
- Cinema name normalization
- Auditorium parsing logic
- Film model validation
- Configuration loading

