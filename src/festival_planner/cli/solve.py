"""Command-line interface for the festival planner."""

from pathlib import Path
from datetime import date
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..config import ConfigLoader, get_default_paths
from ..models import ScheduledFilm, Film
from ..solver import FestivalScheduleSolver
from .._logging import get_logger

console = Console()
logger = get_logger(__name__)
app = typer.Typer()


def _format_clickable_title(title: str, url: Optional[str]) -> Text:
    """Format a film title as a clickable link if URL is available.

    Args:
        title: Film title to display
        url: Optional URL to link to

    Returns:
        Rich Text object with hyperlink if URL provided, plain text otherwise
    """
    if url:
        return Text(title, style=f"link {url}")
    return Text(title)


def _group_films_by_date(
    scheduled_films: list[ScheduledFilm],
) -> dict[date, list[ScheduledFilm]]:
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
    config = loader.load_config()
    preferences = config.schedule

    # Override buffer time if specified
    if buffer_time is not None:
        preferences.buffer_time_minutes = buffer_time

    # Parse date range if specified
    if dates:
        if ":" in dates:
            start_str, end_str = dates.split(":", 1)
            preferences.start_date = date.fromisoformat(start_str)
            preferences.end_date = date.fromisoformat(end_str)
        else:
            preferences.start_date = date.fromisoformat(dates)
            preferences.end_date = date.fromisoformat(dates)

    # Load films
    film_list = loader.load_films()
    console.print(f"[green]Loaded {len(film_list.films)} film screenings[/green]")

    # Load seen films and filter
    seen_list = config.films.seen
    relevant_films = loader.filter_relevant_films(film_list.films, seen_list)
    console.print(
        f"[yellow]{len(film_list.films) - len(relevant_films)} films not relevant (seen or ignored)[/yellow]"
    )
    console.print(
        f"[green]{len(relevant_films)} film screenings available to schedule[/green]"
    )

    # Load and apply weight overrides
    weights = config.films.weights
    if weights:
        relevant_films = loader.apply_weight_overrides(
            relevant_films, weights
        )
        console.print(
            f"[blue]Applied {len(weights)} custom weight override(s)[/blue]"
        )

    # Solve
    console.print("[bold blue]Solving optimization problem...[/bold blue]")
    solver = FestivalScheduleSolver(relevant_films, config)
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
        title_link = _format_clickable_title(title, film.url)

        table.add_row(
            status,
            title_link,
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


def display_film_overview(
    all_films: list[Film], scheduled_films: list[ScheduledFilm]
) -> None:
    """Display overview of all unique films with scheduled status.

    Args:
        all_films: All available film screenings
        scheduled_films: Films that have been scheduled
    """
    # Get unique films by title
    films_by_title = _group_films_by_title(all_films)

    # Track which films are scheduled
    scheduled_titles = {sf.film.title for sf in scheduled_films}
    scheduled_by_title: dict[str, ScheduledFilm] = {
        sf.film.title: sf for sf in scheduled_films
    }

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
            title_link = _format_clickable_title(sf.film.title, sf.film.url)
            table.add_row(
                sf.arrival_time.strftime("%H:%M"),
                sf.film.start_time.strftime("%H:%M"),
                sf.film.end_time.strftime("%H:%M"),
                title_link,
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
                # Format title with markdown link if URL available
                if sf.film.url:
                    title_md = f"[{sf.film.title}]({sf.film.url})"
                else:
                    title_md = sf.film.title
                
                f.write(f"### {title_md}\n")
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
