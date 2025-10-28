"""Command-line interface for the festival planner."""

import typer
from rich.console import Console

from .._logging import configure_logging, get_logger

from .scrape import app as scrape
from .solve import app as solve
from .add_seen import app as add_seen
from .set_weight import app as set_weight
from .validate import app as validate

app = typer.Typer(help="Festival Planner - Optimize your film festival schedule")
app.add_typer(scrape)
app.add_typer(solve)
app.add_typer(add_seen)
app.add_typer(set_weight)
app.add_typer(validate)

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
) -> None:
    """Configure global settings for the festival planner."""
    configure_logging(log_level)


if __name__ == "__main__":
    app()
