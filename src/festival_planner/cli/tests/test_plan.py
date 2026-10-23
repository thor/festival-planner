"""End-to-end tests of the `plan` commands against a SQLite file."""

import datetime
import json
import re
import zoneinfo

import pytest
from typer.testing import CliRunner

from festival_planner.adapters.sqlalchemy.database import (
    create_engine_for,
    resolve_database_url,
)
from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
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


class FakeSource:
    """Stands in for the Filmfrasor scraper; takes the same arguments."""

    def __init__(self, year, *, known_venue_names, cache_dir, force_refresh):
        pass

    def fetch(self) -> SourceProgramme:
        def at(hour: int) -> datetime.datetime:
            return datetime.datetime(2030, 11, 8, hour, tzinfo=OSLO)

        return SourceProgramme(
            festival=SourceFestival(
                slug="fest-2030", name="Fest", time_zone="Europe/Oslo"
            ),
            entries=tuple(
                SourceEntry(
                    source_key=key,
                    title=key.title(),
                    year=2030,
                    screenings=(
                        SourceScreening(
                            venue_name=venue, start_time=at(h), end_time=at(h + 2)
                        ),
                    ),
                )
                for key, venue, h in (("alpha", "Vika Kino", 14), ("beta", "Vega", 15))
            ),
        )


@pytest.fixture
def db(tmp_path) -> str:
    return str(tmp_path / "db.sqlite")


@pytest.fixture
def cli(config_dir, db, monkeypatch):
    monkeypatch.setenv("LOGNAME", "tester")
    monkeypatch.setitem(PROGRAMME_SOURCES, "filmfrasor", FakeSource)
    runner = CliRunner()

    def invoke(*args: str):
        return runner.invoke(app, [*args, "--database", db])

    assert invoke("ingest", "venues").exit_code == 0
    assert invoke("ingest", "programme", "filmfrasor", "--year", "2030").exit_code == 0
    return invoke


def first_screening_id(db: str) -> str:
    engine = create_engine_for(resolve_database_url(db))
    try:
        with SqlAlchemyUnitOfWork(engine) as uow:
            festival = uow.festivals.by_slug("fest-2030")
            assert festival is not None
            return uow.programme.screenings(festival.id)[0].id
    finally:
        engine.dispose()


def test_draft_accept_and_schedule(cli, tmp_path):
    result = cli("plan", "draft", "fest-2030")
    assert result.exit_code == 0, result.output
    match = re.search(r"Draft (\S+): READY", result.output)
    assert match, result.output
    draft_id = match.group(1)
    assert draft_id in cli("plan", "drafts", "fest-2030").output
    exported = tmp_path / "request.json"
    assert (
        cli("plan", "show", draft_id, "--export-request", str(exported)).exit_code == 0
    )
    assert json.loads(exported.read_text())["format_version"] == 1
    assert cli("plan", "accept", draft_id).exit_code == 0
    assert "Schedule 1" in cli("plan", "schedule", "fest-2030").output


def test_an_invalid_change_set_is_reported(cli, tmp_path):
    change_set = tmp_path / "changes.yaml"
    change_set.write_text("- kind: add_screening_commitment\n  screening_id: nope\n")
    result = cli("plan", "draft", "fest-2030", "--change-set", str(change_set))
    assert result.exit_code == 1
    assert "unknown screening 'nope'" in result.output


def test_unknown_drafts_are_reported(cli):
    result = cli("plan", "accept", "nope")
    assert result.exit_code == 1
    assert "No draft 'nope'" in result.output


def test_tickets_and_seen_commands(cli, db):
    screening_id = first_screening_id(db)
    assert cli("plan", "ticket", "add", screening_id, "--refundable").exit_code == 0
    assert "not in the Active Schedule" in cli("plan", "schedule", "fest-2030").output
    assert cli("plan", "ticket", "remove", screening_id).exit_code == 0
    assert cli("plan", "seen", "add", "nope").exit_code == 1
