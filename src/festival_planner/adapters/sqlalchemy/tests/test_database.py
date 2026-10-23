import logging

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from festival_planner.adapters.sqlalchemy.database import (
    DATABASE_URL_ENV,
    alembic_config,
    create_engine_for,
    migrate,
    resolve_database_url,
)

TABLES = {
    "festival_series",
    "festival",
    "film",
    "venue",
    "venue_alias",
    "route",
    "programme_entry",
    "screening",
    "screening_event",
    "alembic_version",
    "app_user",
    "planning_inputs",
    "planning_target",
    "schedule",
    "schedule_screening",
    "draft",
    "draft_screening",
    "ticket",
    "seen",
    "seen_dismissal",
}


def test_migrate_creates_every_table(engine):
    assert set(inspect(engine).get_table_names()) == TABLES


def test_sqlite_runs_in_wal_mode_with_a_busy_timeout(engine):
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000


def test_migrations_match_the_table_definitions(engine):
    with engine.connect() as connection:
        command.check(alembic_config(connection))  # raises if autogenerate finds a diff


def test_migrate_is_idempotent(engine):
    migrate(engine)


def test_migrate_logs_nothing_below_warning(tmp_path, caplog):
    engine = create_engine_for(f"sqlite:///{tmp_path / 'quiet.db'}")
    try:
        with caplog.at_level(logging.INFO):
            migrate(engine)
    finally:
        engine.dispose()
    assert not [r for r in caplog.records if r.name.startswith("alembic")]
    assert logging.getLogger("alembic").level == logging.NOTSET


def test_sqlite_enforces_foreign_keys(engine):
    with engine.begin() as c, pytest.raises(IntegrityError):
        c.execute(
            text("INSERT INTO venue_alias (venue_id, alias) VALUES ('nope', 'x')")
        )


def test_explicit_url_wins(monkeypatch):
    monkeypatch.setenv(DATABASE_URL_ENV, "sqlite:///env.db")
    assert resolve_database_url("postgresql://h/db") == "postgresql://h/db"


def test_explicit_path_becomes_a_sqlite_url(tmp_path):
    assert (
        resolve_database_url(str(tmp_path / "x.db")) == f"sqlite:///{tmp_path / 'x.db'}"
    )


def test_environment_beats_the_default(monkeypatch):
    monkeypatch.setenv(DATABASE_URL_ENV, "sqlite:///env.db")
    assert resolve_database_url() == "sqlite:///env.db"


def test_default_is_in_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.delenv(DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    expected = tmp_path / "festival-planner" / "festival-planner.db"
    assert resolve_database_url() == f"sqlite:///{expected}"
    assert expected.parent.is_dir()
