"""Tests for the local Ed25519 token issuer."""

import datetime
import json
import stat
from pathlib import Path

import pytest

from festival_planner.adapters.jwt.verifier import JwtTokenVerifier
from festival_planner.adapters.local_issuer.issuer import LocalIssuer
from festival_planner.domain.identity import Identity, InvalidTokenError
from festival_planner.domain.users import LOCAL_ISSUER


@pytest.fixture
def issuer(tmp_path: Path) -> LocalIssuer:
    issuer = LocalIssuer(tmp_path / "local-issuer")
    issuer.init()
    return issuer


def test_init_writes_a_private_key_only_the_owner_can_read(issuer: LocalIssuer):
    mode = (issuer.directory / "private-key.pem").stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_the_jwks_holds_one_public_key(issuer: LocalIssuer):
    jwks = (issuer.directory / "jwks.json").read_text()
    keys = json.loads(jwks)["keys"]
    assert len(keys) == 1
    key = keys[0]
    assert "d" not in key
    assert key["kid"]
    assert key["crv"] == "Ed25519"


def test_init_does_not_overwrite_keys_unless_forced(issuer: LocalIssuer):
    original = (issuer.directory / "private-key.pem").read_bytes()
    with pytest.raises(FileExistsError):
        issuer.init()
    assert (issuer.directory / "private-key.pem").read_bytes() == original

    issuer.init(force=True)
    assert (issuer.directory / "private-key.pem").read_bytes() != original


def test_forced_init_restores_the_private_key_mode(issuer: LocalIssuer):
    private_key_path = issuer.directory / "private-key.pem"
    private_key_path.chmod(0o644)

    issuer.init(force=True)

    mode = private_key_path.stat().st_mode
    assert stat.S_IMODE(mode) == 0o600


def test_init_creates_the_directory_with_owner_only_access(issuer: LocalIssuer):
    mode = issuer.directory.stat().st_mode
    assert stat.S_IMODE(mode) == 0o700


def test_an_issued_token_verifies_as_the_local_issuer(issuer: LocalIssuer):
    verifier = JwtTokenVerifier([issuer.trusted_issuer()])
    assert verifier.verify(issuer.issue("alice")) == Identity(
        issuer=LOCAL_ISSUER, subject="alice"
    )


def test_an_issued_token_expires_after_its_lifetime(issuer: LocalIssuer):
    verifier = JwtTokenVerifier([issuer.trusted_issuer()])
    expired = issuer.issue(
        "alice", now=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=31)
    )
    with pytest.raises(InvalidTokenError):
        verifier.verify(expired)


def test_issuing_without_keys_fails(tmp_path: Path):
    issuer = LocalIssuer(tmp_path / "no-keys-here")
    with pytest.raises(FileNotFoundError):
        issuer.issue("alice")
