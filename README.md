# Festival Planner

A modular film festival scheduling optimizer that uses constraint programming to maximize your ability to attend films while respecting time constraints, travel times, and personal preferences.

## Features

- **Smart Scheduling**: Uses Google OR-Tools CP-SAT solver to find the optimal schedule
- **Multi-day Support**: Plan across multiple festival days
- **Travel Time Aware**: Considers travel time between different cinemas
- **Preference Weighting**: Assign positive or negative weights to films you particularly want or want to avoid
- **Seen Films Tracking**: Keep track of films you've already seen to avoid double-booking
- **Web Scraping**: Built-in scraper for Filmfrasor.no (extensible for other festivals)
- **HTTP Caching**: Uses [Hishel](https://github.com/karpetrosyan/hishel) to cache HTTP responses locally for faster subsequent scrapes
- **Flexible Configuration**: YAML-based configuration for easy customization

## Installation

This project uses `mise` to manage the `uv` dependency manager.

1. Install dependencies:
```bash
mise exec -- uv sync
```

## Project Structure

```
festival-planner/
├── config/
│   ├── cinemas.yaml          # Cinema locations and travel times
│   └── preferences.yaml       # Optimization preferences
├── data/
│   ├── films.yaml            # Film screenings (manual or scraped)
│   └── seen_films.yaml       # Films already seen or to ignore
└── src/festival_planner/     # Source code
```

## Configuration

### Cinema Configuration (`config/cinemas.yaml`)

Define travel times between cinemas:

```yaml
travel_times:
  - from: "Cinemateket"
    to: "Vika Kino"
    minutes: 15
  - from: "Vika Kino"
    to: "Colosseum"
    minutes: 10
```

### Schedule Preferences (`config/preferences.yaml`)

Set default buffer time and optional date filters:

```yaml
buffer_time_minutes: 15
# start_date: "2024-09-15"  # Optional
# end_date: "2024-09-22"    # Optional
```

### Film Data (`data/films.yaml`)

Film screenings with optional preference weights:

```yaml
films:
  - title: "Film Title"
    country: "Norway"
    start_time: "2024-09-15T18:00:00"
    end_time: "2024-09-15T20:15:00"
    cinema: "Cinemateket"
    special_notes: "Director Q&A"
    preference_weight: 1.5  # Optional, default is 1.0
```

**Preference weights**:
- `1.0` (default): Normal priority
- `> 1.0`: Higher priority (e.g., `2.0` for must-see films)
- `< 1.0`: Lower priority (e.g., `0.5` for backup options)
- Negative values can be used to deprioritize films

### Seen Films (`data/seen_films.yaml`)

Track films you've already seen:

```yaml
seen:
  - title: "Film Title"
    date: "2024-09-15"  # Specific screening
  - title: "Another Film"
    date: null  # All screenings
```

## Usage

### 1. Scrape Film Data (Filmfrasor.no)

```bash
mise festival-planner scrape
```

The scraper uses **HTTP caching** powered by [Hishel](https://github.com/karpetrosyan/hishel) to store responses locally, making subsequent scrapes much faster and more respectful to the server.

Options:
- `--output`, `-o`: Custom output file path
- `--year`, `-y`: Festival year (defaults to current year)
- `--refresh`, `-r`: Force refresh - bypass HTTP cache and fetch fresh data

Examples:
```bash
# First scrape - fetches from server and caches
mise festival-planner scrape

# Second scrape - uses cached data (instant!)
mise festival-planner scrape

# Force refresh when you need the latest data
mise festival-planner scrape --refresh
```

### 2. Solve the Schedule

```bash
mise exec -- festival-planner solve
```

Options:
- `--dates`, `-d`: Filter by date range (`YYYY-MM-DD:YYYY-MM-DD` or single date)
- `--output`, `-o`: Save schedule to file
- `--time-limit`, `-t`: Solver time limit in seconds (default: 60)
- `--buffer`, `-b`: Override buffer time in minutes

Examples:
```bash
# Optimize for entire festival
mise exec -- festival-planner solve

# Optimize for specific dates
mise exec -- festival-planner solve --dates 2024-09-15:2024-09-17

# Use custom buffer time
mise exec -- festival-planner solve --buffer 20

# Save schedule to file
mise exec -- festival-planner solve --output schedule.md
```

### 3. Mark Films as Seen

```bash
# Mark specific screening as seen
mise exec -- festival-planner add-seen "Film Title" --date 2024-09-15

# Mark all screenings as seen/ignored
mise exec -- festival-planner add-seen "Film Title"
```

### 4. Validate Configuration

```bash
mise exec -- festival-planner validate
```

Options:
- `--verbose`, `-v`: Show detailed validation info

## Standalone Scraper Script

You can also run the scraper independently:

```bash
mise exec -- python src/scripts/scrape_filmfrasor.py
```

## How It Works

The planner uses constraint programming (CP-SAT) to solve the scheduling problem:

1. **Decision Variables**: Binary variable for each film (attend or not)
2. **Objective**: Maximize sum of `(1.0 + preference_weight)` for attended films
3. **Constraints**:
   - No overlapping films (including buffer and travel time)
   - Film end + travel time + buffer ≤ next film start
   - Exclude already seen films
   - Films on different days don't conflict

## Extending for Other Festivals

To add support for another festival:

1. Create a new scraper in `src/festival_planner/scrapers/`:

```python
from .base import BaseScraper
from ..models import FilmList

class MyFestivalScraper(BaseScraper):
    def get_festival_name(self) -> str:
        return "My Festival"
    
    def scrape(self) -> FilmList:
        # Implement scraping logic
        pass
```

2. Register it in `src/festival_planner/scrapers/__init__.py`

3. Use it in the CLI or directly in your code

## Development

### Running Tests

```bash
mise exec -- pytest
```

### Code Formatting

```bash
mise exec -- ruff check src/
```

## Requirements

- Python >= 3.11
- Dependencies managed by `uv` (see `pyproject.toml`)

## License

This project is open source and available for personal use.

