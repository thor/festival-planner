"""End-to-end tests of the `solve` command, from YAML files and JSON requests."""

import datetime
import json

import pytest
from typer.testing import CliRunner

from festival_planner.cli import app

FILMS_YAML = """\
films:
  - title: "Early"
    country: "Norway"
    year: 1960
    start_time: "2025-11-08T14:00:00"
    end_time: "2025-11-08T16:00:00"
    cinema: "Vika"
  - title: "Clash"
    country: "Norway"
    start_time: "2025-11-08T15:00:00"
    end_time: "2025-11-08T17:00:00"
    cinema: "Vika"
  - title: "Late"
    country: "Sweden"
    start_time: "2025-11-08T19:00:00"
    end_time: "2025-11-08T21:00:00"
    cinema: "Vega"
    special_notes: "Director Q&A"
"""

CONFIG_YAML = """\
cinemas:
  travel_times:
    - from: "Vika"
      to: "Vega"
      minutes: 15
schedule:
  buffer_time_minutes: 15
priority:
  year_weights:
    1960: 0.5
"""


@pytest.fixture
def xdg(tmp_path, monkeypatch):
    """Isolated XDG directories holding the YAML inputs."""
    config_dir = tmp_path / "config" / "festival-planner"
    data_dir = tmp_path / "data" / "festival-planner"
    config_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(CONFIG_YAML)
    (data_dir / "films.yaml").write_text(FILMS_YAML)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_DIRS", str(tmp_path / "none"))
    monkeypatch.setenv("XDG_DATA_DIRS", str(tmp_path / "none"))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_solves_from_yaml_and_writes_markdown(xdg):
    output = xdg / "schedule.md"

    result = CliRunner().invoke(app, ["solve", "--output", str(output)])

    assert result.exit_code == 0, result.output
    schedule = output.read_text()
    assert "### Early" in schedule
    assert "### Clash" not in schedule
    assert "### Late" in schedule
    assert "- **Event**: Director Q&A" in schedule


def test_exported_request_solves_identically(xdg):
    request_path = xdg / "request.json"
    first, second = xdg / "first.md", xdg / "second.md"

    exported = CliRunner().invoke(
        app, ["solve", "--export-request", str(request_path), "-o", str(first)]
    )
    replayed = CliRunner().invoke(
        app, ["solve", "--request", str(request_path), "-o", str(second)]
    )

    assert exported.exit_code == 0, exported.output
    assert replayed.exit_code == 0, replayed.output
    assert json.loads(request_path.read_text())["preferences"]["buffer_minutes"] == 15
    assert first.read_text() == second.read_text()


def test_infeasible_request_exits_with_error(xdg, tmp_path):
    request_path = xdg / "request.json"
    CliRunner().invoke(app, ["solve", "--export-request", str(request_path)])
    request = json.loads(request_path.read_text())
    request["screening_commitments"] = [s["id"] for s in request["screenings"]]
    request_path.write_text(json.dumps(request))

    result = CliRunner().invoke(app, ["solve", "--request", str(request_path)])

    assert result.exit_code == 1
    assert "No schedule found" in result.output


def test_overview_separates_seen_films_from_missed_ones(xdg):
    (xdg / "config" / "festival-planner" / "preferences.yaml").write_text(
        'seen:\n  - title: "Late"\n'
    )

    result = CliRunner().invoke(app, ["solve"])

    assert result.exit_code == 0, result.output
    assert "Films not relevant (seen or excluded): 1" in result.output
    assert "Films missed: 1" in result.output
    assert "Films scheduled: 1" in result.output


def test_time_limit_of_a_loaded_request_is_kept_unless_given(xdg):
    first, second = xdg / "first.json", xdg / "second.json"
    CliRunner().invoke(app, ["solve", "--export-request", str(first)])
    request = json.loads(first.read_text())
    request["time_limit_seconds"] = 5
    first.write_text(json.dumps(request))

    result = CliRunner().invoke(
        app, ["solve", "--request", str(first), "--export-request", str(second)]
    )

    assert result.exit_code == 0, result.output
    assert json.loads(second.read_text())["time_limit_seconds"] == 5


def test_times_are_shown_in_the_festival_time_zone(xdg):
    request_path, output = xdg / "request.json", xdg / "schedule.md"
    CliRunner().invoke(app, ["solve", "--export-request", str(request_path)])
    request = json.loads(request_path.read_text())
    for screening in request["screenings"]:
        for key in ("start_time", "end_time"):
            local = datetime.datetime.fromisoformat(screening[key])
            screening[key] = local.astimezone(datetime.UTC).isoformat()
    request_path.write_text(json.dumps(request))

    result = CliRunner().invoke(
        app, ["solve", "--request", str(request_path), "-o", str(output)]
    )

    assert result.exit_code == 0, result.output
    schedule = output.read_text()
    assert "## 2025-11-08" in schedule
    assert "- **Start**: 14:00" in schedule
    assert "- **Arrive**: 13:45" in schedule
