"""Database maintenance commands."""

import typer
from rich.console import Console

from ..adapters.sqlalchemy.database import open_database

app = typer.Typer(name="db", help="Manage the festival database.")
console = Console()

DATABASE_OPTION = typer.Option(
    None,
    "--database",
    help=(
        "Database URL or SQLite file "
        "(default: $FESTIVAL_PLANNER_DATABASE_URL or the XDG data directory)"
    ),
)


@app.command()
def upgrade(database: str | None = DATABASE_OPTION) -> None:
    """Apply all pending migrations."""
    open_database(database).dispose()
    console.print("[green]Database is up to date[/green]")
