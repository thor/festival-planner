"""Ingest festival data into the database."""

import datetime
from collections.abc import Callable

import typer
from rich.console import Console

from ..adapters.filmfrasor.programme_source import FilmfrasorProgrammeSource
from ..adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from ..adapters.yaml_files.venues import CinemaConfigVenues
from ..config import ConfigLoader
from ..domain.ingestion import (
    IngestionError,
    ProgrammeSource,
    ingest_programme,
    ingest_venues,
)
from .db import DATABASE_OPTION, open_database

app = typer.Typer(name="ingest", help="Ingest festival data into the database.")
console = Console()

PROGRAMME_SOURCES: dict[str, Callable[..., ProgrammeSource]] = {
    "filmfrasor": FilmfrasorProgrammeSource,
}


def _count(n: int, noun: str, plural: str | None = None) -> str:
    return f"{n} {noun if n == 1 else plural or noun + 's'}"


def _abort(error: IngestionError) -> typer.Exit:
    console.print(f"[bold red]Ingestion aborted:[/bold red] {error}", soft_wrap=True)
    return typer.Exit(code=1)


@app.command()
def venues(database: str | None = DATABASE_OPTION) -> None:
    """Ingest Venues and Routes from the cinema configuration."""
    source = CinemaConfigVenues(ConfigLoader().load_config().cinemas)
    engine = open_database(database)
    try:
        report = ingest_venues(SqlAlchemyUnitOfWork(engine), source, source)
    except IngestionError as e:
        raise _abort(e) from e
    finally:
        engine.dispose()
    console.print(
        f"[green]{_count(report.venues_created, 'venue')} created, "
        f"{report.venues_updated} updated, {_count(report.routes, 'route')}[/green]",
        soft_wrap=True,
    )


@app.command()
def programme(
    source: str = typer.Argument(..., help=f"One of: {', '.join(PROGRAMME_SOURCES)}"),
    year: int | None = typer.Option(
        None, "--year", "-y", help="Festival year (default: this year)"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", "-r", help="Bypass the HTTP cache"
    ),
    database: str | None = DATABASE_OPTION,
) -> None:
    """Ingest a Festival's programme."""
    if source not in PROGRAMME_SOURCES:
        console.print(
            f"[bold red]Unknown programme source {source!r}.[/bold red] "
            f"Choose one of: {', '.join(PROGRAMME_SOURCES)}",
            soft_wrap=True,
        )
        raise typer.Exit(code=2)
    engine = open_database(database)
    try:
        uow = SqlAlchemyUnitOfWork(engine)
        with uow:
            names = [n for v in uow.venues.all() for n in (v.name, *v.aliases)]
        programme_source = PROGRAMME_SOURCES[source](
            year or datetime.date.today().year,
            known_venue_names=names,
            cache_dir=ConfigLoader().path_provider.get_cache_home(),
            force_refresh=refresh,
        )
        try:
            report = ingest_programme(uow, programme_source)
        except IngestionError as e:
            raise _abort(e) from e
        with uow:
            festival = uow.festivals.by_slug(report.festival_slug)
    finally:
        engine.dispose()
    console.print(
        f"[green]{festival.name if festival else report.festival_slug}: "
        f"{_count(report.films_created, 'film')} created, "
        f"{_count(report.entries_created, 'entry', 'entries')} created, "
        f"{report.entries_updated} updated, "
        f"{_count(report.screenings_created, 'screening')} created, "
        f"{report.screenings_updated} updated, "
        f"{report.screenings_withdrawn} withdrawn[/green]",
        soft_wrap=True,
    )
