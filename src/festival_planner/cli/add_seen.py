"""Command-line interface for the festival planner."""

import datetime
from typing import Optional
from iterfzf import iterfzf
import typer
from rich.console import Console

from ..config import Config, ConfigLoader
from ..models import SeenFilm
from .._logging import get_logger


console = Console()
logger = get_logger(__name__)
app = typer.Typer()


@app.command()
def add_seen(
    title: Optional[str] = typer.Option(
        None,
        "--title",
        "-t",
        help="Film title",
    ),
    search: Optional[str] = typer.Option(
        None,
        "--search",
        "-s",
        help="Initial search term to filter films",
    ),
    date: Optional[str] = typer.Option(
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

    # Add new seen film entered by user
    if title:
        _save_seen_film(loader, config, title, date)
        return

    films = loader.load_films()
    unique_film_titles = sorted({f.title for f in films.films})
    try:
        selected = iterfzf(
            unique_film_titles,
            prompt="Film already seen: ",
            query=search or "",
        )
    except KeyboardInterrupt:
        console.print("[yellow]Selection cancelled.[/yellow]")
        return

    if not selected or not isinstance(selected, str):
        console.print("[yellow]No film selected.[/yellow]")
        return

    _save_seen_film(loader, config, selected, date)


def _save_seen_film(
    loader: ConfigLoader, config: Config, title: str, date: str | None = None
) -> None:
    # Convert date string to datetime.date for proper comparison
    film_date = datetime.date.fromisoformat(date) if date else None
    
    seen_map = {(f.title, f.date): f for f in config.films.seen}
    if (title, film_date) in seen_map:
        console.print(
            f"[yellow]Film '{title}' ({f'on {date}' if date else 'all screenings'}) already marked as seen.[/yellow]"
        )
        return

    seen_film = SeenFilm(title=title, date=film_date)
    config.films.seen.append(seen_film)
    loader.save_preferences(config.films)

    if date:
        console.print(f"[green]Marked '{title}' on {date} as seen[/green]")
    else:
        console.print(f"[green]Marked all screenings of '{title}' as seen[/green]")
