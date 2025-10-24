"""Command-line interface for the festival planner."""

from pathlib import Path
from datetime import date
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from iterfzf import iterfzf

from .config import ConfigLoader
from .models import SeenFilm, ScheduledFilm, Film, FilmWeight
from .solver import FestivalScheduleSolver
from .scrapers import FilmfrasorScraper
from ._logging import configure_logging, get_logger

app = typer.Typer(help="Festival Planner - Optimize your film festival schedule")
console = Console()
logger = get_logger(__name__)


@app.callback()
def main(
    log_level: str = typer.Option(
        "INFO",
        "--log-level",
        "-l",
        help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
        case_sensitive=False,
    ),
):
    """Configure global settings for the festival planner."""
    configure_logging(log_level)


def get_default_paths():
    """Get default paths for config and data directories."""
    cwd = Path.cwd()
    return cwd / "config", cwd / "data"


def _group_films_by_date(scheduled_films: list[ScheduledFilm]) -> dict[date, list[ScheduledFilm]]:
    """Group scheduled films by date.
    
    Args:
        scheduled_films: List of scheduled films
        
    Returns:
        Dictionary mapping dates to lists of scheduled films
    """
    by_date: dict[date, list[ScheduledFilm]] = {}
    for sf in scheduled_films:
        film_date = sf.film.date
        if film_date not in by_date:
            by_date[film_date] = []
        by_date[film_date].append(sf)
    return by_date


@app.command()
def scrape(
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: data/films.yaml)",
    ),
    year: Optional[int] = typer.Option(
        None,
        "--year",
        "-y",
        help="Festival year (default: current year)",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        "-r",
        help="Force refresh: bypass HTTP cache and fetch fresh data from server",
    ),
):
    """Scrape the Filmfrasor.no programme and cache the results."""
    config_dir, data_dir = get_default_paths()

    console.print("[bold blue]Scraping filmfrasor.no...[/bold blue]")

    scraper = FilmfrasorScraper(
        cache_dir=data_dir, year=year, force_refresh=refresh, config_dir=config_dir
    )
    film_list = scraper.scrape()

    console.print(f"[green]Scraped {len(film_list.films)} film screenings[/green]")

    # Save to file
    loader = ConfigLoader(config_dir, data_dir)
    output_path = output or (data_dir / "films.yaml")
    loader.save_films(film_list, output_path)

    console.print(f"[green]Saved to {output_path}[/green]")


@app.command()
def solve(
    dates: Optional[str] = typer.Option(
        None,
        "--dates",
        "-d",
        help="Date range filter (format: YYYY-MM-DD:YYYY-MM-DD or single date)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for schedule",
    ),
    time_limit: int = typer.Option(
        60,
        "--time-limit",
        "-t",
        help="Solver time limit in seconds",
    ),
    buffer_time: Optional[int] = typer.Option(
        None,
        "--buffer",
        "-b",
        help="Buffer time before each film in minutes",
    ),
):
    """Solve the scheduling optimization problem."""
    config_dir, data_dir = get_default_paths()
    loader = ConfigLoader(config_dir, data_dir)

    # Load configuration
    console.print("[bold blue]Loading configuration...[/bold blue]")
    schedule_config = loader.load_schedule_config()

    # Override buffer time if specified
    if buffer_time is not None:
        schedule_config.buffer_time_minutes = buffer_time

    # Parse date range if specified
    if dates:
        if ":" in dates:
            start_str, end_str = dates.split(":", 1)
            schedule_config.start_date = date.fromisoformat(start_str)
            schedule_config.end_date = date.fromisoformat(end_str)
        else:
            schedule_config.start_date = date.fromisoformat(dates)
            schedule_config.end_date = date.fromisoformat(dates)

    # Load films
    film_list = loader.load_films()
    console.print(f"[green]Loaded {len(film_list.films)} film screenings[/green]")

    # Load seen films and filter
    seen_list = loader.load_seen_films()
    relevant_films = loader.filter_relevant_films(film_list.films, seen_list.seen)
    console.print(
        f"[yellow]{len(film_list.films) - len(relevant_films)} films not relevant (seen or ignored)[/yellow]"
    )
    console.print(
        f"[green]{len(relevant_films)} film screenings available to schedule[/green]"
    )

    # Load and apply weight overrides
    weight_list = loader.load_film_weights()
    if weight_list.weights:
        relevant_films = loader.apply_weight_overrides(relevant_films, weight_list.weights)
        console.print(
            f"[blue]Applied {len(weight_list.weights)} custom weight override(s)[/blue]"
        )

    # Load cinema configuration
    cinema_config = loader.load_cinema_config()
    travel_matrix = loader.build_travel_time_matrix(cinema_config)

    # Solve
    console.print("[bold blue]Solving optimization problem...[/bold blue]")
    solver = FestivalScheduleSolver(relevant_films, travel_matrix, schedule_config)
    scheduled_films = solver.solve(time_limit_seconds=time_limit)

    # Display results
    stats = solver.get_solution_stats()
    console.print("[bold green]Solution found![/bold green]")
    console.print(f"Status: {stats['status']}")
    console.print(f"Objective value: {stats['objective_value']:.2f}")
    console.print(f"Solve time: {stats['wall_time']:.2f}s")
    console.print(f"Films scheduled: {len(scheduled_films)}")

    # Display comprehensive film overview
    display_film_overview(relevant_films, scheduled_films)

    # Display schedule
    display_schedule(scheduled_films)

    # Save to file if requested
    if output:
        save_schedule_to_file(scheduled_films, output)
        console.print(f"[green]Schedule saved to {output}[/green]")


@app.command()
def add_seen(
    title: str = typer.Argument(..., help="Film title"),
    date_str: Optional[str] = typer.Option(
        None,
        "--date",
        "-d",
        help="Specific screening date (YYYY-MM-DD) - omit to ignore all screenings",
    ),
):
    """Mark a film as seen or to be ignored."""
    config_dir, data_dir = get_default_paths()
    loader = ConfigLoader(config_dir, data_dir)

    # Load existing seen films
    seen_list = loader.load_seen_films()

    # Add new seen film
    film_date = date.fromisoformat(date_str) if date_str else None
    seen_film = SeenFilm(title=title, date=film_date)
    seen_list.seen.append(seen_film)

    # Save
    loader.save_seen_films(seen_list)

    if film_date:
        console.print(f"[green]Marked '{title}' on {film_date} as seen[/green]")
    else:
        console.print(f"[green]Marked all screenings of '{title}' as seen[/green]")


@app.command()
def set_weight(
    search: Optional[str] = typer.Option(
        None,
        "--search",
        "-s",
        help="Initial search term to filter films (you can further filter in fzf)",
    ),
):
    """Set a custom weight for a specific film screening using interactive fuzzy finder."""
    config_dir, data_dir = get_default_paths()
    loader = ConfigLoader(config_dir, data_dir)

    # Load all films
    film_list = loader.load_films()
    
    # Load existing custom weight overrides
    weight_list = loader.load_film_weights()
    
    # Build lookup map for existing overrides: (title, start_time) -> weight
    override_map = {
        (w.title, w.start_time): w.weight for w in weight_list.weights
    }
    
    # Filter by search term if provided
    films = film_list.films
    if search:
        search_lower = search.lower()
        films = [f for f in films if search_lower in f.title.lower()]
        
    if not films:
        console.print("[yellow]No films found matching your search.[/yellow]")
        return
    
    # Sort by date and time
    films.sort(key=lambda f: (f.date, f.start_time))
    
    # Create formatted strings and mapping
    film_strings = []
    film_map = {}
    
    for film in films:
        date_str = film.start_time.strftime("%a %d/%m")
        time_str = film.start_time.strftime("%H:%M")
        cinema_str = film.cinema
        if film.auditorium:
            cinema_str += f" {film.auditorium}"
        
        # Check if this film has a custom weight override
        key = (film.title, film.start_time)
        if key in override_map:
            weight_display = f"{override_map[key]:+.1f} [custom]"
        else:
            weight_display = f"{film.preference_weight:+.1f}"
        
        # Create a formatted string for fzf display
        formatted = f"{film.title:<60} │ {date_str} {time_str} │ {cinema_str:<25} │ Weight: {weight_display}"
        film_strings.append(formatted)
        film_map[formatted] = film
    
    # Use iterfzf for interactive selection
    try:
        selected = iterfzf(
            film_strings,
            prompt="Select a film screening > ",
            query=search or "",
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Selection cancelled.[/yellow]")
        return
    
    if not selected:
        console.print("[yellow]No film selected.[/yellow]")
        return
    
    selected_film = film_map[selected]
    
    # Get current weight (custom override or preference weight)
    key = (selected_film.title, selected_film.start_time)
    current_weight = override_map.get(key, selected_film.preference_weight)
    weight_type = "custom" if key in override_map else "scraped"
    
    # Ask for weight
    weight = typer.prompt(
        f"\nEnter custom weight for '{selected_film.title}' (current: {current_weight:+.1f} [{weight_type}])",
        type=float,
    )
    
    # Check if this screening already has an override
    existing_idx = None
    for i, w in enumerate(weight_list.weights):
        if w.title == selected_film.title and w.start_time == selected_film.start_time:
            existing_idx = i
            break
    
    # Add or update weight
    film_weight = FilmWeight(
        title=selected_film.title,
        start_time=selected_film.start_time,
        weight=weight,
    )
    
    if existing_idx is not None:
        weight_list.weights[existing_idx] = film_weight
        console.print(f"[green]Updated weight for '{selected_film.title}' to {weight:+.1f}[/green]")
    else:
        weight_list.weights.append(film_weight)
        console.print(f"[green]Set weight for '{selected_film.title}' to {weight:+.1f}[/green]")
    
    # Save
    loader.save_film_weights(weight_list)
    
    date_str = selected_film.start_time.strftime("%a %d/%m at %H:%M")
    console.print(f"[dim]({date_str} at {selected_film.cinema})[/dim]")


@app.command()
def validate(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed validation info"
    ),
):
    """Validate all configuration and data files."""
    config_dir, data_dir = get_default_paths()
    loader = ConfigLoader(config_dir, data_dir)

    errors = []

    # Validate films
    console.print("[bold blue]Validating films...[/bold blue]")
    try:
        film_list = loader.load_films()
        console.print(f"[green]✓ Films: {len(film_list.films)} loaded[/green]")
        if verbose:
            for film in film_list.films:
                console.print(f"  - {film.title} at {film.cinema}")
    except Exception as e:
        errors.append(f"Films validation failed: {e}")
        console.print(f"[red]✗ Films: {e}[/red]")

    # Validate seen films
    console.print("[bold blue]Validating seen films...[/bold blue]")
    try:
        seen_list = loader.load_seen_films()
        console.print(f"[green]✓ Seen films: {len(seen_list.seen)} loaded[/green]")
    except Exception as e:
        errors.append(f"Seen films validation failed: {e}")
        console.print(f"[red]✗ Seen films: {e}[/red]")

    # Validate cinema config
    console.print("[bold blue]Validating cinema configuration...[/bold blue]")
    try:
        cinema_config = loader.load_cinema_config()
        console.print(
            f"[green]✓ Cinema config: {len(cinema_config.travel_times)} travel times loaded[/green]"
        )
        if verbose:
            for tt in cinema_config.travel_times:
                console.print(
                    f"  - {tt.from_cinema} → {tt.to_cinema}: {tt.minutes} min"
                )
    except Exception as e:
        errors.append(f"Cinema config validation failed: {e}")
        console.print(f"[red]✗ Cinema config: {e}[/red]")

    # Validate schedule config
    console.print("[bold blue]Validating schedule configuration...[/bold blue]")
    try:
        schedule_config = loader.load_schedule_config()
        console.print(
            f"[green]✓ Schedule config: buffer time = {schedule_config.buffer_time_minutes} min[/green]"
        )
    except Exception as e:
        errors.append(f"Schedule config validation failed: {e}")
        console.print(f"[red]✗ Schedule config: {e}[/red]")

    # Summary
    if errors:
        console.print(f"\n[bold red]{len(errors)} validation error(s) found[/bold red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)
    else:
        console.print("\n[bold green]All validations passed![/bold green]")


def _group_films_by_title(films: list[Film]) -> dict[str, list[Film]]:
    """Group films by title.
    
    Args:
        films: List of films to group
        
    Returns:
        Dictionary mapping film titles to lists of screenings
    """
    films_by_title: dict[str, list[Film]] = {}
    for film in films:
        if film.title not in films_by_title:
            films_by_title[film.title] = []
        films_by_title[film.title].append(film)
    return films_by_title


def _print_festival_statistics(
    total_unique: int,
    total_screenings: int,
    scheduled_count: int,
    missed_count: int,
) -> None:
    """Print festival overview statistics.
    
    Args:
        total_unique: Total number of unique films
        total_screenings: Total number of screenings
        scheduled_count: Number of films scheduled
        missed_count: Number of films missed
    """
    console.print("\n[bold]Festival Overview[/bold]")
    console.print(f"Unique films: {total_unique}")
    console.print(f"Total screenings: {total_screenings}")
    console.print(f"Films scheduled: [green]{scheduled_count}[/green]")
    console.print(f"Films missed: [red]{missed_count}[/red]")
    console.print()


def _build_film_overview_table(
    films_by_title: dict[str, list[Film]],
    scheduled_titles: set[str],
    scheduled_by_title: dict[str, ScheduledFilm],
) -> Table:
    """Build the film overview table with scheduling details.
    
    Args:
        films_by_title: Films grouped by title
        scheduled_titles: Set of scheduled film titles
        scheduled_by_title: Mapping of titles to scheduled films
        
    Returns:
        Formatted Rich Table
    """
    table = Table(title="All Films in Festival")
    table.add_column("Status", justify="center", style="bold", width=6)
    table.add_column("Title", style="bold")
    table.add_column("Year", justify="center")
    table.add_column("Country", max_width=15, overflow="ellipsis", no_wrap=True)
    table.add_column("Screenings", justify="center")
    table.add_column("Date", style="cyan")
    table.add_column("Time", style="green")
    table.add_column("Cinema", style="yellow")
    table.add_column("Special Notes", style="magenta")

    # Sort by title and add rows with alternating styles
    sorted_titles = sorted(films_by_title.keys())
    for idx, title in enumerate(sorted_titles):
        screenings = films_by_title[title]
        num_screenings = len(screenings)

        # Determine row style (every other row dimmed)
        style = "dim" if idx % 2 == 1 else None

        if title in scheduled_titles:
            # Film is scheduled - show details
            sf = scheduled_by_title[title]
            film = sf.film
            status = "✅"
            date_str = film.start_time.strftime("%a %d/%m")
            time_str = film.start_time.strftime("%H:%M")
            cinema_str = f"{film.cinema}"
            if film.auditorium:
                cinema_str += f" {film.auditorium}"
            special_str = film.special_notes if film.special_notes else ""
        else:
            # Film not scheduled - show minimal info
            film = screenings[0]  # Use first screening for basic info
            status = "❌"
            date_str = ""
            time_str = ""
            cinema_str = ""
            special_str = ""

        year_str = str(film.year) if film.year else ""

        table.add_row(
            status,
            title,
            year_str,
            film.country,
            str(num_screenings),
            date_str,
            time_str,
            cinema_str,
            special_str,
            style=style,
        )

    return table


def display_film_overview(all_films: list[Film], scheduled_films: list[ScheduledFilm]) -> None:
    """Display overview of all unique films with scheduled status.
    
    Args:
        all_films: All available film screenings
        scheduled_films: Films that have been scheduled
    """
    # Get unique films by title
    films_by_title = _group_films_by_title(all_films)

    # Track which films are scheduled
    scheduled_titles = {sf.film.title for sf in scheduled_films}
    scheduled_by_title: dict[str, ScheduledFilm] = {sf.film.title: sf for sf in scheduled_films}

    # Calculate and print statistics
    total_unique = len(films_by_title)
    total_screenings = len(all_films)
    scheduled_count = len(scheduled_titles)
    missed_count = total_unique - scheduled_count

    _print_festival_statistics(
        total_unique, total_screenings, scheduled_count, missed_count
    )

    # Build and display table
    table = _build_film_overview_table(
        films_by_title, scheduled_titles, scheduled_by_title
    )
    console.print(table)
    console.print()


def display_schedule(scheduled_films: list[ScheduledFilm]) -> None:
    """Display the schedule in a nice table format.
    
    Args:
        scheduled_films: List of scheduled films to display
    """
    if not scheduled_films:
        console.print("[yellow]No films in schedule[/yellow]")
        return

    # Group by date
    by_date = _group_films_by_date(scheduled_films)

    # Display each day
    for film_date in sorted(by_date.keys()):
        table = Table(title=f"Schedule for {film_date}")
        table.add_column("Arrival", style="cyan")
        table.add_column("Start", style="green")
        table.add_column("End", style="red")
        table.add_column("Film", style="bold")
        table.add_column("Year", max_width=4, overflow="crop", no_wrap=True)
        table.add_column("Cinema", style="yellow")
        table.add_column("Country", max_width=10, overflow="ellipsis", no_wrap=True)
        table.add_column("Weight", justify="right")

        for sf in by_date[film_date]:
            year_str = f"{sf.film.year:4d}" if sf.film.year else "    "
            table.add_row(
                sf.arrival_time.strftime("%H:%M"),
                sf.film.start_time.strftime("%H:%M"),
                sf.film.end_time.strftime("%H:%M"),
                sf.film.title,
                year_str,
                sf.film.cinema,
                sf.film.country,
                f"{sf.calculated_weight:+.1f}",
            )

        console.print(table)
        console.print()


def save_schedule_to_file(scheduled_films: list[ScheduledFilm], filepath: Path) -> None:
    """Save the schedule to a file.
    
    Args:
        scheduled_films: List of scheduled films to save
        filepath: Path to output file
    """
    with open(filepath, "w") as f:
        f.write("# Festival Schedule\n\n")

        # Group by date
        by_date = _group_films_by_date(scheduled_films)

        # Write each day
        for film_date in sorted(by_date.keys()):
            f.write(f"## {film_date}\n\n")

            for sf in by_date[film_date]:
                f.write(f"### {sf.film.title}\n")
                f.write(f"- **Arrival**: {sf.arrival_time.strftime('%H:%M')}\n")
                f.write(f"- **Start**: {sf.film.start_time.strftime('%H:%M')}\n")
                f.write(f"- **End**: {sf.film.end_time.strftime('%H:%M')}\n")
                f.write(f"- **Cinema**: {sf.film.cinema}\n")
                f.write(f"- **Country**: {sf.film.country}\n")
                if sf.film.special_notes:
                    f.write(f"- **Notes**: {sf.film.special_notes}\n")
                f.write(f"- **Weight**: {sf.calculated_weight:+.1f}\n")
                f.write("\n")

            f.write("\n")


if __name__ == "__main__":
    app()
