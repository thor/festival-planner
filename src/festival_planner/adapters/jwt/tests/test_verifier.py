"""Tests for JWT verification against trusted issuers.

Deviation from the brief: the brief's fixture trusts the `https://other.example`
issuer via a `file://` `jwks_uri` (`PyJWKClient` reading it through urllib). The
installed PyJWT (2.15.1) rejects any `PyJWKClient` URI whose scheme isn't
`http`/`https` (a hardening fix against SSRF through an attacker-controlled
`jku`/`jwks_uri`). This fixture instead serves that issuer's JWKS from a local
HTTP server, which is both compatible with the installed library and closer to
how a real `jwks_uri` issuer works.
"""

import json
import re
import threading
import time
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt.algorithms import OKPAlgorithm
from jwt.api_jws import PyJWS
from jwt.utils import base64url_decode, base64url_encode

from festival_planner.adapters.jwt.verifier import (
    DEFAULT_AUDIENCE,
    ISSUERS_ENV,
    JwtTokenVerifier,
    TrustedIssuer,
    trusted_issuers_from_env,
)
from festival_planner.domain.identity import Identity, InvalidTokenError
from festival_planner.domain.users import LOCAL_ISSUER

OTHER_ISSUER = "https://other.example"


def _jwk(key: Ed25519PrivateKey, kid: str) -> dict:
    public = key.public_key()
    jwk = OKPAlgorithm.to_jwk(public, as_dict=True)
    return jwk | {"kid": kid, "use": "sig", "alg": "EdDSA"}


def _jwks_handler(content: bytes) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args: object) -> None:
            pass

    return Handler


@pytest.fixture
def jwks_server() -> Iterator[Callable[[bytes], str]]:
    started: list[ThreadingHTTPServer] = []

    def start(content: bytes) -> str:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _jwks_handler(content))
        started.append(server)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_address[1]
        return f"http://127.0.0.1:{port}/jwks.json"

    yield start
    for server in started:
        server.shutdown()
        server.server_close()


@pytest.fixture
def keys() -> tuple[Ed25519PrivateKey, Ed25519PrivateKey]:
    return Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()


@pytest.fixture
def issuers(
    tmp_path: Path,
    keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey],
    jwks_server,
) -> tuple[TrustedIssuer, TrustedIssuer]:
    key_a, key_b = keys
    jwks_file = tmp_path / "local.json"
    jwks_file.write_text(json.dumps({"keys": [_jwk(key_a, "a")]}))
    jwks_uri = jwks_server(json.dumps({"keys": [_jwk(key_b, "b")]}).encode())
    return (
        TrustedIssuer(issuer=LOCAL_ISSUER, jwks_file=jwks_file),
        TrustedIssuer(issuer=OTHER_ISSUER, jwks_uri=jwks_uri),
    )


@pytest.fixture
def verifier(issuers: tuple[TrustedIssuer, TrustedIssuer]) -> JwtTokenVerifier:
    return JwtTokenVerifier(issuers)


def token(key: Ed25519PrivateKey, *, kid: str | None = "a", **claims: object) -> str:
    payload = {
        "iss": LOCAL_ISSUER,
        "sub": "alice",
        "aud": DEFAULT_AUDIENCE,
        "exp": int(time.time()) + 300,
    }
    payload.update(claims)
    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(payload, key, algorithm="EdDSA", headers=headers)


def test_a_valid_token_yields_its_identity(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    assert verifier.verify(token(key_a)) == Identity(
        issuer=LOCAL_ISSUER, subject="alice"
    )


def test_a_token_from_a_jwks_uri_issuer_is_verified(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    _, key_b = keys
    identity = verifier.verify(token(key_b, iss=OTHER_ISSUER, kid="b"))
    assert identity == Identity(issuer=OTHER_ISSUER, subject="alice")


def test_an_expired_token_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    bad = token(key_a, exp=int(time.time()) - 60)
    with pytest.raises(InvalidTokenError):
        verifier.verify(bad)


def test_a_token_for_another_audience_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    with pytest.raises(InvalidTokenError):
        verifier.verify(token(key_a, aud="someone-else"))


def test_a_token_from_an_unknown_issuer_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    with pytest.raises(InvalidTokenError):
        verifier.verify(token(key_a, iss="https://unknown.example"))


def test_an_unsigned_token_is_rejected(verifier: JwtTokenVerifier):
    claims = {
        "iss": LOCAL_ISSUER,
        "sub": "alice",
        "aud": DEFAULT_AUDIENCE,
        "exp": int(time.time()) + 300,
    }
    bad = jwt.encode(claims, None, algorithm="none")  # type: ignore[arg-type]
    with pytest.raises(InvalidTokenError):
        verifier.verify(bad)


def test_a_token_naming_one_issuer_but_signed_by_another_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    _, key_b = keys
    bad = token(key_b, iss=LOCAL_ISSUER, kid="a")
    with pytest.raises(InvalidTokenError):
        verifier.verify(bad)


def test_a_token_whose_header_algorithm_does_not_match_its_keys_algorithm_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    """A PyJWK's algorithm is fixed by its own `alg` (here "EdDSA", from the
    JWKS entry), not by whatever the token header claims. Verifying this
    requires PyJWT 2.15+: before that fix, a header naming an algorithm the
    key was never meant for could reach that algorithm's verify() with the
    wrong key type and raise an uncaught error instead of InvalidTokenError.
    Tampering only the header (not the payload or signature) is enough to
    trigger the check, since it runs before the signature itself is checked.
    """
    key_a, _ = keys
    good = token(key_a)
    header_b64, payload_b64, signature_b64 = good.split(".")
    header = json.loads(base64url_decode(header_b64))
    header["alg"] = "RS256"
    tampered_header_b64 = base64url_encode(json.dumps(header).encode()).decode()
    bad = f"{tampered_header_b64}.{payload_b64}.{signature_b64}"
    with pytest.raises(InvalidTokenError):
        verifier.verify(bad)


def test_a_token_with_an_unknown_key_id_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    with pytest.raises(InvalidTokenError):
        verifier.verify(token(key_a, kid="unknown"))


def test_a_token_without_a_subject_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    claims = {
        "iss": LOCAL_ISSUER,
        "aud": DEFAULT_AUDIENCE,
        "exp": int(time.time()) + 300,
    }
    bad = jwt.encode(claims, key_a, algorithm="EdDSA", headers={"kid": "a"})
    with pytest.raises(InvalidTokenError):
        verifier.verify(bad)


def test_a_token_without_an_expiry_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    claims = {"iss": LOCAL_ISSUER, "sub": "alice", "aud": DEFAULT_AUDIENCE}
    bad = jwt.encode(claims, key_a, algorithm="EdDSA", headers={"kid": "a"})
    with pytest.raises(InvalidTokenError):
        verifier.verify(bad)


def test_a_token_without_an_audience_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    claims = {
        "iss": LOCAL_ISSUER,
        "sub": "alice",
        "exp": int(time.time()) + 300,
    }
    bad = jwt.encode(claims, key_a, algorithm="EdDSA", headers={"kid": "a"})
    with pytest.raises(InvalidTokenError):
        verifier.verify(bad)


def test_a_token_without_a_kid_is_accepted_when_its_issuer_has_exactly_one_key(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    identity = verifier.verify(token(key_a, kid=None))
    assert identity == Identity(issuer=LOCAL_ISSUER, subject="alice")


def test_a_token_without_a_kid_is_rejected_when_its_issuer_has_two_keys(
    tmp_path: Path, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, key_b = keys
    jwks_file = tmp_path / "local.json"
    jwks_file.write_text(json.dumps({"keys": [_jwk(key_a, "a"), _jwk(key_b, "b")]}))
    verifier = JwtTokenVerifier(
        [TrustedIssuer(issuer=LOCAL_ISSUER, jwks_file=jwks_file)]
    )
    with pytest.raises(InvalidTokenError):
        verifier.verify(token(key_a, kid=None))


def test_a_token_with_a_non_string_issuer_is_rejected(
    verifier: JwtTokenVerifier, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    """A non-string `iss` must not reach the trusted-issuer lookup as a dict
    key (a list there would raise an unhandled TypeError, not InvalidTokenError).
    `jwt.encode` refuses a non-string `iss` itself, so this is built at the
    JWS level, which doesn't know about claim semantics."""
    key_a, _ = keys
    payload = json.dumps(
        {
            "iss": ["local"],
            "sub": "alice",
            "aud": DEFAULT_AUDIENCE,
            "exp": int(time.time()) + 300,
        }
    ).encode()
    bad = PyJWS().encode(payload, key_a, algorithm="EdDSA", headers={"kid": "a"})
    with pytest.raises(InvalidTokenError):
        verifier.verify(bad)


@pytest.mark.parametrize("garbage", ["not-a-jwt", "", "a.b.c"])
def test_garbage_is_rejected(verifier: JwtTokenVerifier, garbage: str):
    with pytest.raises(InvalidTokenError):
        verifier.verify(garbage)


def test_no_issuers_variable_means_none_trusted():
    assert trusted_issuers_from_env({}) == ()
    assert trusted_issuers_from_env({ISSUERS_ENV: ""}) == ()


def test_issuers_are_read_from_the_environment(tmp_path: Path):
    jwks_file = tmp_path / "local.json"
    jwks_file.write_text("{}")
    environ = {
        ISSUERS_ENV: json.dumps([{"issuer": LOCAL_ISSUER, "jwks_file": str(jwks_file)}])
    }
    assert trusted_issuers_from_env(environ) == (
        TrustedIssuer(issuer=LOCAL_ISSUER, jwks_file=jwks_file),
    )


@pytest.mark.parametrize("raw", ["{", "[{}]", '[{"issuer": "x"}]'])
def test_malformed_issuers_are_reported(raw: str):
    with pytest.raises(ValueError, match=ISSUERS_ENV):
        trusted_issuers_from_env({ISSUERS_ENV: raw})


def test_the_local_issuer_may_not_use_a_jwks_uri():
    with pytest.raises(ValueError, match="jwks_file"):
        TrustedIssuer(issuer=LOCAL_ISSUER, jwks_uri="https://example.com/jwks.json")


@pytest.mark.parametrize("algorithms", [("HS256",), ("none",)])
def test_symmetric_and_none_algorithms_are_refused(
    tmp_path: Path, algorithms: tuple[str, ...]
):
    jwks_file = tmp_path / "x.json"
    jwks_file.write_text("{}")
    with pytest.raises(ValueError, match=re.escape(algorithms[0])):
        TrustedIssuer(issuer=OTHER_ISSUER, jwks_file=jwks_file, algorithms=algorithms)


def test_issuers_must_be_unique(tmp_path: Path):
    jwks_file = tmp_path / "local.json"
    jwks_file.write_text("{}")
    entry = {"issuer": LOCAL_ISSUER, "jwks_file": str(jwks_file)}
    environ = {ISSUERS_ENV: json.dumps([entry, entry])}
    with pytest.raises(ValueError, match=ISSUERS_ENV):
        trusted_issuers_from_env(environ)


def test_a_missing_jwks_file_is_reported(tmp_path: Path):
    missing = tmp_path / "missing.json"
    issuer = TrustedIssuer(issuer=LOCAL_ISSUER, jwks_file=missing)
    with pytest.raises(ValueError, match=re.escape(str(missing))):
        JwtTokenVerifier([issuer])


def test_an_invalid_jwks_file_is_reported(tmp_path: Path):
    jwks_file = tmp_path / "bad.json"
    jwks_file.write_text("not json")
    issuer = TrustedIssuer(issuer=LOCAL_ISSUER, jwks_file=jwks_file)
    with pytest.raises(ValueError, match=re.escape(str(jwks_file))):
        JwtTokenVerifier([issuer])


def test_duplicate_issuers_are_rejected_by_the_verifier(
    tmp_path: Path, keys: tuple[Ed25519PrivateKey, Ed25519PrivateKey]
):
    key_a, _ = keys
    jwks_file = tmp_path / "local.json"
    jwks_file.write_text(json.dumps({"keys": [_jwk(key_a, "a")]}))
    issuer = TrustedIssuer(issuer=LOCAL_ISSUER, jwks_file=jwks_file)
    with pytest.raises(ValueError, match=re.escape(LOCAL_ISSUER)):
        JwtTokenVerifier([issuer, issuer])
