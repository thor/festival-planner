<!-- b0621edc-868a-4f7d-aedb-7c673d5f29ca 4a7acee5-1580-4cba-bd0f-fdda4b18bdf8 -->
# Festival Planner System

## Project Structure

```
festival-planner/
├── pyproject.toml              # uv project config with dependencies
├── README.md                   # Setup and usage instructions
├── config/
│   ├── cinemas.yaml           # Cinema locations and travel times
│   └── preferences.yaml       # Default preferences (buffer time, etc.)
├── data/
│   ├── films.yaml             # Manual film entries or cached scrapes
│   └── seen_films.yaml        # Films already seen or to ignore
├── src/
│   ├── festival_planner/
│   │   ├── __init__.py
│   │   ├── models.py          # Pydantic data models
│   │   ├── config.py          # Configuration loading
│   │   ├── solver.py          # OR-Tools optimization logic
│   │   ├── scrapers/
│   │   │   ├── __init__.py
│   │   │   ├── base.py        # Base scraper interface
│   │   │   └── filmfrasor.py  # Filmfrasor.no scraper
│   │   └── cli.py             # Command-line interface
│   └── scripts/
│       └── scrape_filmfrasor.py  # Standalone scraping script
└── tests/                      # Unit tests
```

## Implementation Steps

### 1. Project Setup with mise and uv

- Initialize mise to manage uv: `mise add uv`
- Create `pyproject.toml` with dependencies:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `ortools` for constraint programming
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `pydantic` v2 for data validation
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `pyyaml` for configuration
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `httpx` for web scraping
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `beautifulsoup4` for HTML parsing
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `typer` for CLI interface

### 2. Define Pydantic Models (`models.py`)

Core models:

- **Film**: title, country, start_time (datetime), end_time (datetime), cinema, special_notes, preference_weight (optional float, default=1.0)
- **Cinema**: name, location identifier
- **TravelTime**: from_cinema, to_cinema, duration_minutes
- **SeenFilm**: title, date (to handle multiple screenings)
- **ScheduleConfig**: buffer_time_minutes (default extra time before films), date_range (optional filter)

### 3. YAML Schemas

**`data/films.yaml`** format:

```yaml
films:
 - title: "Film Title"
    country: "Norway"
    start_time: "2024-09-15T18:00:00"
    end_time: "2024-09-15T20:15:00"
    cinema: "Cinemateket"
    special_notes: "Director Q&A"
    preference_weight: 1.5  # optional
```

**`config/cinemas.yaml`** format:

```yaml
travel_times:
 - from: "Cinemateket"
    to: "Vika"
    minutes: 15
 - from: "Vika"
    to: "Colosseum"
    minutes: 20
```

**`data/seen_films.yaml`** format:

```yaml
seen:
 - title: "Film Title"
    date: "2024-09-15"
 - title: "Another Film"  # All screenings ignored
```

### 4. Configuration Management (`config.py`)

- Load and validate YAML files using Pydantic
- Build travel time matrix from cinema configuration
- Merge seen films list for filtering
- Handle missing or default values

### 5. Filmfrasor.no Scraper (`scrapers/filmfrasor.py`)

Implement as a separate module:

- Scrape programme page structure
- Extract: title, country, start/end times, cinema, special event info
- Cache results to `data/films.yaml` with timestamp
- Handle pagination if needed
- Error handling for network issues and HTML structure changes
- Make scraper reusable via base interface for future festivals

### 6. OR-Tools Solver (`solver.py`)

Constraint programming model:

- **Decision variables**: Binary variable for each film (attend or not)
- **Objective**: Maximize sum of (base_weight + preference_weight) for attended films
- **Constraints**:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - No overlapping films (including buffer time and travel time)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Film end + travel time + buffer ≤ next film start
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Exclude seen/ignored films
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - Respect multi-day boundaries (films on different days don't conflict)

Key functions:

- `build_schedule_model()`: Create OR-Tools CP-SAT model
- `solve()`: Run solver and return optimal schedule
- `export_schedule()`: Format results as readable schedule

### 7. CLI Interface (`cli.py`)

Commands using Typer:

- `scrape filmfrasor`: Run scraper and cache data
- `solve`: Run optimizer with current data
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `--dates`: Filter to specific date range
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - `--output`: Save schedule to file
- `add-seen`: Mark films as seen
- `validate`: Check YAML files for errors

### 8. Standalone Scraper Script (`scripts/scrape_filmfrasor.py`)

- Can be run independently: `mise exec python src/scripts/scrape_filmfrasor.py`
- Includes caching logic with file timestamps
- Outputs to `data/films.yaml`
- Logs scraping progress and errors

## Key Technical Details

### OR-Tools Optimization Strategy

The solver uses CP-SAT (Constraint Programming - Boolean Satisfiability):

1. Create boolean variables `attend[i]` for each film i
2. Objective: `maximize sum(attend[i] * (1.0 + preference_weight[i]))`
3. For each pair of films (i, j) on same day:

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                - If they overlap with buffer/travel: `attend[i] + attend[j] <= 1`

4. For seen films: `attend[i] = 0`

### Modular Design for Multiple Festivals

- Abstract `BaseScraper` interface in `scrapers/base.py`
- Each festival gets its own scraper implementing the interface
- Common data models work across all festivals
- Configuration files can be festival-specific

### Subset Date Solving

When re-solving for specific dates:

1. Filter films by date range
2. Load seen_films.yaml to exclude already attended
3. Run solver on remaining films
4. Append new selections to seen_films.yaml

### To-dos

- [ ] Initialize mise, create pyproject.toml with dependencies (ortools, pydantic, pyyaml, httpx, beautifulsoup4, typer)
- [ ] Define Pydantic models for Film, Cinema, TravelTime, SeenFilm, and ScheduleConfig
- [ ] Implement configuration loader for YAML files with validation
- [ ] Build filmfrasor.no web scraper with caching to extract programme data
- [ ] Implement OR-Tools CP-SAT solver with preference weights, travel times, and multi-day constraints
- [ ] Create Typer-based CLI with commands for scraping, solving, and managing seen films
- [ ] Create example YAML configuration files for cinemas, films, and seen films