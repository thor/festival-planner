"""CLI commands for scraping film festival programme data."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console

from ..config import ConfigLoader
from ..scrapers import FilmfrasorScraper
from .._logging import get_logger


console = Console()
logger = get_logger(__name__)

app = typer.Typer()


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
) -> None:
    """Scrape the Filmfrasor.no programme and cache the results."""
    loader = ConfigLoader()
    
    console.print("[bold blue]Scraping filmfrasor.no...[/bold blue]")

    scraper = FilmfrasorScraper(
        cache_dir=loader.path_provider.get_cache_home(),
        year=year,
        force_refresh=refresh,
        config_dir=loader.config_write_dir,
    )
    film_list = scraper.scrape()

    console.print(f"[green]Scraped {len(film_list.films)} film screenings[/green]")

    # Save to file
    output_path = output or (loader.data_write_dir / "films.yaml")
    loader.save_films(film_list, output_path)

    console.print(f"[green]Saved to {output_path}[/green]")
