"""Command-line interface for the festival planner."""

import typer
from rich.console import Console

from .._logging import configure_logging, get_logger
from .add_seen import app as add_seen
from .db import app as db_app
from .ingest import app as ingest_app
from .plan import app as plan_app
from .scrape import app as scrape
from .serve import app as serve_app
from .set_weight import app as set_weight
from .solve import app as solve
from .token import app as token_app
from .validate import app as validate

app = typer.Typer(help="Festival Planner - Optimize your film festival schedule")
app.add_typer(scrape)
app.add_typer(solve)
app.add_typer(add_seen)
app.add_typer(set_weight)
app.add_typer(validate)
app.add_typer(db_app, name="db")
app.add_typer(ingest_app, name="ingest")
app.add_typer(plan_app, name="plan")
app.add_typer(token_app, name="token")
app.add_typer(serve_app)

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
