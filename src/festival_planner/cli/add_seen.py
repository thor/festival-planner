"""Command-line interface for the festival planner."""

from datetime import date
from typing import Optional
import typer
from rich.console import Console

from ..config import ConfigLoader
from ..models import SeenFilm
from .._logging import get_logger


console = Console()
logger = get_logger(__name__)
app = typer.Typer()


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

    # Load existing seen films
    loader = ConfigLoader()
    config = loader.load_config()
    film_preferences = config.films

    # Add new seen film
    film_date = date.fromisoformat(date_str) if date_str else None
    seen_film = SeenFilm(title=title, date=film_date)
    film_preferences.seen.append(seen_film)

    # Save
    loader.save_preferences(film_preferences)

    if film_date:
        console.print(f"[green]Marked '{title}' on {film_date} as seen[/green]")
    else:
        console.print(f"[green]Marked all screenings of '{title}' as seen[/green]")
