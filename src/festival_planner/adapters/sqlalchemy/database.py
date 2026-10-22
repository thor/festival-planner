"""Locating, connecting to and migrating the database."""

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, event

from ...path_providers import PathProvider, create_default_path_provider

DATABASE_URL_ENV = "FESTIVAL_PLANNER_DATABASE_URL"
MIGRATIONS = Path(__file__).parent / "migrations"


def resolve_database_url(
    explicit: str | None = None, path_provider: PathProvider | None = None
) -> str:
    """`explicit` (a URL or a file path), else $FESTIVAL_PLANNER_DATABASE_URL,
    else a SQLite file in the XDG data directory."""
    if explicit:
        return (
            explicit if "://" in explicit else f"sqlite:///{Path(explicit).resolve()}"
        )
    if from_env := os.environ.get(DATABASE_URL_ENV):
        return from_env
    data_home = (path_provider or create_default_path_provider()).get_data_home()
    data_home.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_home / 'festival-planner.db'}"


def create_engine_for(url: str) -> Engine:
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def migrate(engine: Engine, revision: str = "head") -> None:
    """Bring the schema up to `revision`."""
    with engine.begin() as connection:
        command.upgrade(alembic_config(connection), revision)
