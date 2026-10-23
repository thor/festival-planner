"""End-to-end tests of the `token` commands."""

import re
from pathlib import Path

from typer.testing import CliRunner

from festival_planner.adapters.jwt.verifier import (
    ISSUERS_ENV,
    JwtTokenVerifier,
    trusted_issuers_from_env,
)
from festival_planner.adapters.local_issuer.issuer import LocalIssuer
from festival_planner.cli import app
from festival_planner.domain.identity import Identity
from festival_planner.domain.users import LOCAL_ISSUER

runner = CliRunner()


def test_token_init_prints_the_issuers_variable(tmp_path: Path):
    directory = tmp_path / "local-issuer"
    result = runner.invoke(app, ["token", "init", "--directory", str(directory)])

    assert result.exit_code == 0, result.output
    match = re.search(rf"export {ISSUERS_ENV}='(.+)'", result.output)
    assert match is not None, result.output
    issuers = trusted_issuers_from_env({ISSUERS_ENV: match.group(1)})
    assert issuers == (LocalIssuer(directory).trusted_issuer(),)


def test_token_init_refuses_to_overwrite_existing_keys(tmp_path: Path):
    directory = tmp_path / "local-issuer"
    LocalIssuer(directory).init()

    result = runner.invoke(app, ["token", "init", "--directory", str(directory)])

    assert result.exit_code == 1


def test_token_issue_prints_a_token_for_the_os_user(tmp_path, monkeypatch):
    monkeypatch.setattr("getpass.getuser", lambda: "thor")
    directory = tmp_path / "local-issuer"
    issuer = LocalIssuer(directory)
    issuer.init()

    result = runner.invoke(app, ["token", "issue", "--directory", str(directory)])

    assert result.exit_code == 0, result.output
    token = result.output.strip()
    verifier = JwtTokenVerifier([issuer.trusted_issuer()])
    assert verifier.verify(token) == Identity(issuer=LOCAL_ISSUER, subject="thor")


def test_token_issue_without_keys_exits_1(tmp_path: Path):
    directory = tmp_path / "local-issuer"

    result = runner.invoke(app, ["token", "issue", "--directory", str(directory)])

    assert result.exit_code == 1
    assert "token init" in result.output
