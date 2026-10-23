"""The Identity verified from a bearer token (ADR-0003)."""

from typing import Protocol

from .values import Value


class Identity(Value):
    """The (issuer, subject) pair proven by a verified bearer token."""

    issuer: str
    subject: str


class InvalidTokenError(Exception):
    """A bearer token failed verification.

    Every way a token can be wrong (malformed, expired, wrong audience,
    unknown issuer, unknown key, bad signature) becomes this one error.
    Callers never need to distinguish the reason.
    """


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Identity:
        """Returns the Identity proven by `token`.

        Raises `InvalidTokenError` if `token` is not a valid, current token
        from a trusted issuer. May block on network (e.g. fetching a JWKS).
        """
        ...
