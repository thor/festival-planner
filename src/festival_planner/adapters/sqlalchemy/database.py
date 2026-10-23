"""Locating, connecting to and migrating the database."""

import logging
import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, event

from ...path_providers import PathProvider, create_default_path_provider

DATABASE_URL_ENV = "FESTIVAL_PLANNER_DATABASE_URL"
MIGRATIONS = Path(__file__).parent / "migrations"
SQLITE_BUSY_TIMEOUT_MS = 5000


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
        event.listen(engine, "connect", _configure_sqlite)
    return engine


def _configure_sqlite(dbapi_connection, _record) -> None:
    """Enforce foreign keys; let readers and one writer work concurrently."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def migrate(engine: Engine, revision: str = "head") -> None:
    """Bring the schema up to `revision`, without Alembic's INFO messages."""
    alembic_logger = logging.getLogger("alembic")
    level = alembic_logger.level
    alembic_logger.setLevel(max(level, logging.WARNING))
    try:
        with engine.begin() as connection:
            command.upgrade(alembic_config(connection), revision)
    finally:
        alembic_logger.setLevel(level)


def open_database(database: str | None) -> Engine:
    """An engine on the resolved database, migrated to the latest schema."""
    engine = create_engine_for(resolve_database_url(database))
    migrate(engine)
    return engine
