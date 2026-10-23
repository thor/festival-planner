from pathlib import Path

from typer.testing import CliRunner

from festival_planner.api.schema import schema
from festival_planner.cli import app

REPO_ROOT = Path(__file__).parents[4]


def test_the_committed_schema_is_current():
    committed = (REPO_ROOT / "schema.graphql").read_text()
    assert committed == schema.as_str() + "\n", (
        "schema.graphql is out of date; run: festival-planner export-schema schema.graphql"
    )


def test_export_schema_writes_the_sdl(tmp_path):
    path = tmp_path / "schema.graphql"
    result = CliRunner().invoke(app, ["export-schema", str(path)])
    assert result.exit_code == 0, result.output
    assert path.read_text() == schema.as_str() + "\n"
