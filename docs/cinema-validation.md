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

The scraper uses the cinema aliases from config to intelligently parse cinema and auditorium information:

- `"Vika Kino 3"` → cinema: `"Vika Kino"`, auditorium: `"3"` (model normalizes "Vika Kino" → "Vika")
- `"Cinemateket Lillebil"` → cinema: `"Cinemateket"`, auditorium: `"Lillebil"`
- `"Vega 2"` → cinema: `"Vega"`, auditorium: `"2"`
- `"Vega"` → cinema: `"Vega"`, auditorium: `None`

**Key Design**:
- The scraper extracts cinema + auditorium based on known cinema names from config
- Cinema normalization happens in the Film model's Pydantic validator
- This keeps the scraper simple and makes all normalization config-driven

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

