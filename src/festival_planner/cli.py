"""Command-line interface for the festival planner."""

from pathlib import Path
from datetime import date
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from .config import ConfigLoader
from .models import SeenFilm
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
    
    console.print("[bold blue]Scraping Filmfrasor.no...[/bold blue]")
    
    scraper = FilmfrasorScraper(cache_dir=data_dir, year=year, force_refresh=refresh)
    film_list = scraper.scrape()
    
    console.print(f"[green]Scraped {len(film_list.films)} films[/green]")
    
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
    console.print(f"[green]Loaded {len(film_list.films)} films[/green]")

    # Load seen films and filter
    seen_list = loader.load_seen_films()
    unseen_films = loader.filter_unseen_films(film_list.films, seen_list.seen)
    console.print(
        f"[yellow]{len(film_list.films) - len(unseen_films)} films already seen[/yellow]"
    )
    console.print(f"[green]{len(unseen_films)} films available to schedule[/green]")

    # Load cinema configuration
    cinema_config = loader.load_cinema_config()
    travel_matrix = loader.build_travel_time_matrix(cinema_config)

    # Solve
    console.print("[bold blue]Solving optimization problem...[/bold blue]")
    solver = FestivalScheduleSolver(unseen_films, travel_matrix, schedule_config)
    scheduled_films = solver.solve(time_limit_seconds=time_limit)

    # Display results
    stats = solver.get_solution_stats()
    console.print("[bold green]Solution found![/bold green]")
    console.print(f"Status: {stats['status']}")
    console.print(f"Objective value: {stats['objective_value']:.2f}")
    console.print(f"Solve time: {stats['wall_time']:.2f}s")
    console.print(f"Films scheduled: {len(scheduled_films)}")

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


def display_schedule(scheduled_films: list):
    """Display the schedule in a nice table format."""
    if not scheduled_films:
        console.print("[yellow]No films in schedule[/yellow]")
        return

    # Group by date
    by_date = {}
    for sf in scheduled_films:
        film_date = sf.film.date
        if film_date not in by_date:
            by_date[film_date] = []
        by_date[film_date].append(sf)

    # Display each day
    for film_date in sorted(by_date.keys()):
        table = Table(title=f"Schedule for {film_date}")
        table.add_column("Arrival", style="cyan")
        table.add_column("Start", style="green")
        table.add_column("End", style="red")
        table.add_column("Film", style="bold")
        table.add_column("Cinema", style="yellow")
        table.add_column("Country")
        table.add_column("Weight", justify="right")

        for sf in by_date[film_date]:
            table.add_row(
                sf.arrival_time.strftime("%H:%M"),
                sf.film.start_time.strftime("%H:%M"),
                sf.film.end_time.strftime("%H:%M"),
                sf.film.title,
                sf.film.cinema,
                sf.film.country,
                f"{sf.film.preference_weight:+.1f}",
            )

        console.print(table)
        console.print()


def save_schedule_to_file(scheduled_films: list, filepath: Path):
    """Save the schedule to a file."""
    with open(filepath, "w") as f:
        f.write("# Festival Schedule\n\n")

        # Group by date
        by_date = {}
        for sf in scheduled_films:
            film_date = sf.film.date
            if film_date not in by_date:
                by_date[film_date] = []
            by_date[film_date].append(sf)

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
                f.write(f"- **Weight**: {sf.film.preference_weight:+.1f}\n")
                f.write("\n")

            f.write("\n")


if __name__ == "__main__":
    app()
