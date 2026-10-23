"""CLI commands for scraping film festival programme data."""

from pathlib import Path

import typer
from rich.console import Console

from .._logging import get_logger
from ..config import ConfigLoader
from ..models import normalise_cinemas
from ..scrapers import FilmfrasorScraper

console = Console()
logger = get_logger(__name__)

app = typer.Typer()


@app.command()
def scrape(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path (default: data/films.yaml)",
    ),
    year: int | None = typer.Option(
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
) -> None:
    """Scrape the Filmfrasor.no programme and cache the results."""
    loader = ConfigLoader()
    cinemas = loader.load_config().cinemas

    console.print("[bold blue]Scraping filmfrasor.no...[/bold blue]")

    scraper = FilmfrasorScraper(
        cache_dir=loader.path_provider.get_cache_home(),
        year=year,
        force_refresh=refresh,
        known_venue_names=[
            *cinemas.cinema_aliases,
            *(
                alias
                for aliases in cinemas.cinema_aliases.values()
                for alias in aliases
            ),
        ],
    )
    film_list = normalise_cinemas(scraper.scrape(), cinemas)

    console.print(f"[green]Scraped {len(film_list.films)} film screenings[/green]")

    # Save to file
    output_path = output or (loader.data_write_dir / "films.yaml")
    loader.save_films(film_list, output_path)

    console.print(f"[green]Saved to {output_path}[/green]")
