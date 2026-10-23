"""Mints and holds the keys for `LOCAL_ISSUER` (ADR-0003).

`LocalIssuer` is the `token` CLI's own token issuer: an Ed25519 keypair kept
on disk, a private key for signing and a public JWKS for `JwtTokenVerifier`
to verify against. It never runs as a server; the CLI is the only thing that
ever holds the private key.
"""

import datetime
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jwt.algorithms import OKPAlgorithm
from jwt.utils import base64url_encode

from ...domain.users import LOCAL_ISSUER
from ...path_providers import create_default_path_provider
from ..jwt.verifier import DEFAULT_AUDIENCE, TrustedIssuer

PRIVATE_KEY_FILE = "private-key.pem"
JWKS_FILE = "jwks.json"


def _thumbprint(x: str) -> str:
    """The RFC 7638 thumbprint of an OKP public key's `x` coordinate."""
    canonical = json.dumps(
        {"crv": "Ed25519", "kty": "OKP", "x": x}, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(canonical.encode()).digest()
    return base64url_encode(digest).decode()


def _public_jwk(key: Ed25519PrivateKey) -> dict[str, str]:
    jwk = OKPAlgorithm.to_jwk(key.public_key(), as_dict=True)
    return {**jwk, "kid": _thumbprint(jwk["x"]), "alg": "EdDSA", "use": "sig"}


@dataclass
class LocalIssuer:
    """The keypair and operations for `LOCAL_ISSUER`, under `directory`."""

    directory: Path

    @staticmethod
    def default_directory() -> Path:
        return create_default_path_provider().get_data_home() / "local-issuer"

    def _private_key_path(self) -> Path:
        return self.directory / PRIVATE_KEY_FILE

    def _jwks_path(self) -> Path:
        return self.directory / JWKS_FILE

    def init(self, *, force: bool = False) -> None:
        """Generates a new keypair and writes it to `directory`.

        Raises `FileExistsError` if a private key is already there, unless
        `force` is set, in which case it is replaced.
        """
        private_key_path = self._private_key_path()
        if not force and private_key_path.exists():
            raise FileExistsError(
                f"local issuer keys already exist in {self.directory}"
            )
        self.directory.mkdir(parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        # Unlink any existing key, then create exclusively at 0o600: a plain
        # O_TRUNC open keeps an existing file's mode (e.g. a key someone
        # chmod'ed to 0o644 would stay 0o644 after `force=True`). O_EXCL
        # after the unlink means there is no window where the new file
        # could exist under the wrong (or a stale) mode: either this
        # process creates it at 0o600, or the open fails outright.
        private_key_path.unlink(missing_ok=True)
        fd = os.open(private_key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, pem)
        finally:
            os.close(fd)
        self._jwks_path().write_text(json.dumps({"keys": [_public_jwk(key)]}))

    def _load_private_key(self) -> Ed25519PrivateKey:
        try:
            pem = self._private_key_path().read_bytes()
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"no local issuer keys in {self.directory}; run 'token init' first"
            ) from e
        key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise TypeError(f"{self._private_key_path()} is not an Ed25519 key")
        return key

    def issue(
        self,
        subject: str,
        *,
        audience: str = DEFAULT_AUDIENCE,
        lifetime: datetime.timedelta = datetime.timedelta(days=30),
        now: datetime.datetime | None = None,
    ) -> str:
        """A JWT for `subject`, signed by the local issuer's private key.

        Raises `FileNotFoundError` if there are no keys yet.
        """
        key = self._load_private_key()
        issued_at = now if now is not None else datetime.datetime.now(datetime.UTC)
        claims = {
            "iss": LOCAL_ISSUER,
            "sub": subject,
            "aud": audience,
            "iat": issued_at,
            "exp": issued_at + lifetime,
        }
        kid = _public_jwk(key)["kid"]
        return jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": kid})

    def trusted_issuer(self) -> TrustedIssuer:
        """How `JwtTokenVerifier` should trust this issuer's tokens."""
        return TrustedIssuer(
            issuer=LOCAL_ISSUER, jwks_file=self._jwks_path(), algorithms=("EdDSA",)
        )
