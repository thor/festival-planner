"""Database maintenance commands."""

import typer
from rich.console import Console
from sqlalchemy import Engine

from ..adapters.sqlalchemy.database import (
    create_engine_for,
    migrate,
    resolve_database_url,
)

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


def open_database(database: str | None) -> Engine:
    """An engine on the resolved database, migrated to the latest schema."""
    engine = create_engine_for(resolve_database_url(database))
    migrate(engine)
    return engine


@app.command()
def upgrade(database: str | None = DATABASE_OPTION) -> None:
    """Apply all pending migrations."""
    open_database(database).dispose()
    console.print("[green]Database is up to date[/green]")
