"""Verifies bearer JWTs against a configured set of trusted issuers.

Every rejection, whatever its cause, becomes `InvalidTokenError`. A caller
never needs to tell a malformed token apart from an expired one or one from
an untrusted issuer.
"""

from collections.abc import Callable, Iterable, Mapping
from datetime import datetime
from pathlib import Path

import jwt
from pydantic import (
    BaseModel,
    ConfigDict,
    TypeAdapter,
    ValidationError,
    model_validator,
)

from ...domain.identity import Identity, InvalidTokenError
from ...domain.users import LOCAL_ISSUER

ISSUERS_ENV = "FESTIVAL_PLANNER_ISSUERS"
DEFAULT_AUDIENCE = "festival-planner"
LEEWAY_SECONDS = 30


class TrustedIssuer(BaseModel):
    """A token issuer this backend trusts, and how to fetch its keys.

    Exactly one of `jwks_uri` (an http(s) JWKS endpoint) or `jwks_file` (a
    local JWKS file) must be set. `LOCAL_ISSUER` is the CLI's own issuer and
    may only use `jwks_file`: it is never served over HTTP.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    issuer: str
    audience: str = DEFAULT_AUDIENCE
    algorithms: tuple[str, ...] = ("EdDSA", "RS256", "ES256")
    jwks_uri: str | None = None
    jwks_file: Path | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "TrustedIssuer":
        if (self.jwks_uri is None) == (self.jwks_file is None):
            raise ValueError(
                f"issuer {self.issuer!r} must set exactly one of jwks_uri or jwks_file"
            )
        if self.jwks_uri is not None and not self.jwks_uri.startswith(
            ("http://", "https://")
        ):
            raise ValueError(f"issuer {self.issuer!r}: jwks_uri must be an http(s) URL")
        if self.issuer == LOCAL_ISSUER and self.jwks_file is None:
            raise ValueError(
                f"issuer {LOCAL_ISSUER!r} must use jwks_file, not jwks_uri"
            )
        for algorithm in self.algorithms:
            lowered = algorithm.lower()
            if lowered == "none" or lowered.startswith("hs"):
                raise ValueError(
                    f"issuer {self.issuer!r}: algorithm {algorithm!r} is not permitted"
                )
        return self


_ISSUERS_ADAPTER = TypeAdapter(tuple[TrustedIssuer, ...])


def trusted_issuers_from_env(environ: Mapping[str, str]) -> tuple[TrustedIssuer, ...]:
    """The issuers configured in `environ[ISSUERS_ENV]`, a JSON list.

    An unset or empty variable trusts no issuer. Raises `ValueError` naming
    `ISSUERS_ENV` for malformed JSON, a malformed entry, or a duplicate
    issuer.
    """
    raw = environ.get(ISSUERS_ENV)
    if not raw:
        return ()
    try:
        issuers = _ISSUERS_ADAPTER.validate_json(raw)
    except ValidationError as e:
        raise ValueError(f"{ISSUERS_ENV}: {e}") from e
    seen: set[str] = set()
    for issuer in issuers:
        if issuer.issuer in seen:
            raise ValueError(f"{ISSUERS_ENV}: duplicate issuer {issuer.issuer!r}")
        seen.add(issuer.issuer)
    return issuers


class _KeySet:
    """Resolves a signing key by `kid` for one issuer's key set.

    A token with no `kid` is accepted only when the issuer has exactly one
    key, so there is no ambiguity about which key signed it.
    """

    def __init__(
        self, keys: Callable[[], list[jwt.PyJWK]], by_kid: Callable[[str], jwt.PyJWK]
    ):
        self._keys = keys
        self._by_kid = by_kid

    def key_for(self, kid: str | None) -> jwt.PyJWK:
        if kid is not None:
            return self._by_kid(kid)
        keys = self._keys()
        if len(keys) != 1:
            raise InvalidTokenError("token has no kid and its issuer has multiple keys")
        return keys[0]

    @staticmethod
    def from_file(issuer: str, path: Path) -> "_KeySet":
        try:
            jwk_set = jwt.PyJWKSet.from_json(path.read_text())
        except OSError as e:
            raise ValueError(
                f"issuer {issuer!r}: cannot read jwks_file {path}: {e}"
            ) from e
        except (ValueError, jwt.PyJWTError) as e:
            raise ValueError(f"issuer {issuer!r}: invalid jwks_file {path}: {e}") from e
        return _KeySet(lambda: list(jwk_set.keys), lambda kid: jwk_set[kid])

    @staticmethod
    def from_uri(uri: str) -> "_KeySet":
        client = jwt.PyJWKClient(uri, cache_keys=True)
        return _KeySet(client.get_signing_keys, client.get_signing_key)


class JwtTokenVerifier:
    """A `domain.identity.TokenVerifier` backed by PyJWT.

    Each trusted issuer's key set is loaded, or its JWKS client built, once
    at construction. `verify` reads the token's unverified `iss` only to
    pick that issuer's keys and policy, then verifies the signature,
    audience, issuer and expiry (with a 30 second leeway) against them.
    """

    def __init__(
        self,
        issuers: Iterable[TrustedIssuer],
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        # `clock` is accepted for symmetry with the domain's other
        # injectable-clock collaborators. PyJWT has no hook for a custom
        # clock, so it is unused: verification always runs against real
        # wall-clock time.
        self._clock = clock
        self._issuers: dict[str, TrustedIssuer] = {}
        self._keys: dict[str, _KeySet] = {}
        for issuer in issuers:
            if issuer.issuer in self._issuers:
                raise ValueError(f"duplicate issuer {issuer.issuer!r}")
            if issuer.jwks_file is not None:
                key_set = _KeySet.from_file(issuer.issuer, issuer.jwks_file)
            else:
                # TrustedIssuer's validator guarantees exactly one of
                # jwks_file/jwks_uri is set, so this one must be set here.
                assert issuer.jwks_uri is not None
                key_set = _KeySet.from_uri(issuer.jwks_uri)
            self._issuers[issuer.issuer] = issuer
            self._keys[issuer.issuer] = key_set

    def verify(self, token: str) -> Identity:
        try:
            unverified = jwt.decode(token, options={"verify_signature": False})
            claimed_issuer = unverified.get("iss")
            if not isinstance(claimed_issuer, str):
                raise InvalidTokenError("token has no string iss claim")
            issuer = self._issuers[claimed_issuer]
            kid = jwt.get_unverified_header(token).get("kid")
            key = self._keys[claimed_issuer].key_for(kid)
            claims = jwt.decode(
                token,
                key,
                algorithms=list(issuer.algorithms),
                audience=issuer.audience,
                issuer=issuer.issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
            return Identity(issuer=claims["iss"], subject=claims["sub"])
        except InvalidTokenError:
            raise
        except (jwt.PyJWTError, KeyError, ValueError) as e:
            raise InvalidTokenError(str(e)) from e
