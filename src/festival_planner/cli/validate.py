"""CLI commands for validating configuration and data files."""

import typer
from rich.console import Console

from ..config import ConfigLoader
from .._logging import get_logger


console = Console()
logger = get_logger(__name__)
app = typer.Typer()


@app.command()
def validate(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed validation info"
    ),
) -> None:
    """Validate all configuration and data files."""
    loader = ConfigLoader()

    errors = []

    # Validate configuration
    console.print("[bold blue]Validating configuration...[/bold blue]")
    try:
        config = loader.load_config()
        console.print(f"[green]✓ Seen films: {len(config.films.seen)} loaded[/green]")
        console.print(
            f"[green]✓ Film weights: {len(config.films.weights)} loaded[/green]"
        )
        console.print(
            f"[green]✓ Cinema config: {len(config.cinemas.travel_times)} travel times loaded[/green]"
        )
        console.print(
            f"[green]✓ Schedule config: {config.schedule.buffer_time_minutes} buffer time loaded[/green]"
        )
        console.print(
            f"[green]✓ Priority config: {config.priority.year_weights} year weights loaded[/green]"
        )
        console.print("[green]✓ Configuration loaded[/green]")
    except Exception as e:
        errors.append(f"Configuration validation failed: {e}")
        console.print(f"[red]✗ Configuration: {e}[/red]")

    # Validate films
    console.print("[bold blue]Validating scraped films...[/bold blue]")
    try:
        film_list = loader.load_films()
        console.print(f"[green]✓ Films: {len(film_list.films)} loaded[/green]")
        if verbose:
            for film in film_list.films:
                console.print(f"  - {film.title} at {film.cinema}")
    except Exception as e:
        errors.append(f"Films validation failed: {e}")
        console.print(f"[red]✗ Films: {e}[/red]")

    # Report final status
    if errors:
        console.print(f"\n[bold red]Validation failed with {len(errors)} error(s)![/bold red]")
        raise typer.Exit(code=1)
    else:
        console.print("\n[bold green]All validations passed![/bold green]")
