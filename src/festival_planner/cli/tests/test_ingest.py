"""End-to-end tests of the `db` and `ingest` commands against a SQLite file."""

import datetime
import sqlite3
import zoneinfo

import pytest
from typer.testing import CliRunner

from festival_planner.cli import app
from festival_planner.cli.ingest import PROGRAMME_SOURCES
from festival_planner.domain.ingestion import (
    SourceEntry,
    SourceFestival,
    SourceProgramme,
    SourceScreening,
)

OSLO = zoneinfo.ZoneInfo("Europe/Oslo")

CONFIG_YAML = """\
cinemas:
  cinema_aliases:
    Vika: ["Vika Kino"]
    Vega: []
  travel_times:
    - from: "Vika Kino"
      to: "Vega"
      minutes: 15
"""

CONFIG_WITHOUT_ROUTES_YAML = """\
cinemas:
  cinema_aliases:
    Vika: ["Vika Kino"]
    Vega: []
"""


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Isolated XDG directories with a cinema configuration."""
    config_dir = tmp_path / "config" / "festival-planner"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(CONFIG_YAML)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_CONFIG_DIRS", str(tmp_path / "none"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "none"))
    monkeypatch.delenv("FESTIVAL_PLANNER_DATABASE_URL", raising=False)
    return config_dir


@pytest.fixture
def db(tmp_path) -> str:
    return str(tmp_path / "db.sqlite")


@pytest.fixture
def cli(config_dir):
    def invoke(*args: str):
        return CliRunner().invoke(app, list(args))

    return invoke


class StaticSource:
    def __init__(self, programme: SourceProgramme):
        self.programme = programme

    def fetch(self) -> SourceProgramme:
        return self.programme


def show(start: str, venue: str = "Vika Kino") -> SourceScreening:
    hour, minute = map(int, start.split(":"))
    begins = datetime.datetime(2025, 11, 8, hour, minute, tzinfo=OSLO)
    return SourceScreening(
        venue_name=venue,
        start_time=begins,
        end_time=begins + datetime.timedelta(hours=2),
    )


def entry_with(*screenings: SourceScreening) -> SourceProgramme:
    return SourceProgramme(
        festival=SourceFestival(
            slug="films-from-the-south-2025",
            name="Films from the South 2025",
            time_zone="Europe/Oslo",
        ),
        entries=(
            SourceEntry(
                source_key="film/fallen-leaves",
                title="Fallen Leaves",
                year=2023,
                screenings=screenings,
            ),
        ),
    )


def use_source(monkeypatch, programme: SourceProgramme, calls: list | None = None):
    def factory(year, **kwargs):
        if calls is not None:
            calls.append((year, kwargs))
        return StaticSource(programme)

    monkeypatch.setitem(PROGRAMME_SOURCES, "filmfrasor", factory)


def test_db_upgrade_creates_the_schema(cli, db):
    result = cli("db", "upgrade", "--database", db)

    assert result.exit_code == 0, result.output
    with sqlite3.connect(db) as connection:
        tables = {
            name
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "screening" in tables


def test_ingest_venues_reports_counts(cli, db):
    result = cli("ingest", "venues", "--database", db)

    assert result.exit_code == 0, result.output
    assert "2 venues created" in result.output and "2 routes" in result.output


def test_ingest_venues_fails_on_incomplete_routes(cli, db, config_dir):
    (config_dir / "config.yaml").write_text(CONFIG_WITHOUT_ROUTES_YAML)

    result = cli("ingest", "venues", "--database", db)

    assert result.exit_code == 1
    assert "Vika → Vega" in result.output


def test_ingest_programme_and_re_ingest(cli, db, monkeypatch):
    cli("ingest", "venues", "--database", db)
    args = ("ingest", "programme", "filmfrasor", "--year", "2025", "--database", db)

    use_source(monkeypatch, entry_with(show("18:00"), show("21:00")))
    first = cli(*args)
    use_source(monkeypatch, entry_with(show("18:00")))
    second = cli(*args)

    assert first.exit_code == 0, first.output
    assert "Films from the South 2025" in first.output
    assert "1 film created, 1 entry created" in first.output
    assert "2 screenings created" in first.output
    assert second.exit_code == 0, second.output
    assert "0 screenings created, 0 updated, 1 withdrawn" in second.output


def test_unknown_venues_fail_with_every_name(cli, db, monkeypatch):
    cli("ingest", "venues", "--database", db)
    use_source(
        monkeypatch, entry_with(show("18:00", "Nowhere"), show("21:00", "Elsewhere"))
    )

    result = cli("ingest", "programme", "filmfrasor", "--database", db)

    assert result.exit_code == 1
    assert "Nowhere" in result.output and "Elsewhere" in result.output


def test_known_venue_names_are_passed_to_the_source(cli, db, monkeypatch):
    cli("ingest", "venues", "--database", db)
    calls: list = []
    use_source(monkeypatch, entry_with(show("18:00")), calls)

    result = cli(
        "ingest", "programme", "filmfrasor", "--year", "2024", "--database", db
    )

    assert result.exit_code == 0, result.output
    [(year, kwargs)] = calls
    assert year == 2024
    assert {"Vika", "Vika Kino", "Vega"} <= set(kwargs["known_venue_names"])
    assert kwargs["force_refresh"] is False


def test_unknown_programme_sources_are_rejected(cli, db):
    result = cli("ingest", "programme", "nonesuch", "--database", db)

    assert result.exit_code == 2
    assert "filmfrasor" in result.output
