"""Global ids: base64 of "<TypeName>:<domain id>", as Strawberry's relay uses.

Inputs take a plain `ID` and decode it here, so a garbage or wrong-type id
becomes `None` (and then `null` or a typed error), never a GraphQL error.
"""

import base64
import binascii

from strawberry import relay


def encode(type_name: str, domain_id: str) -> str:
    """The global id of the `type_name` node with `domain_id`."""
    return relay.to_base64(type_name, domain_id)


def decode_any(global_id: str) -> tuple[str, str] | None:
    """`(type name, domain id)`, or `None` if `global_id` is malformed."""
    try:
        raw = base64.b64decode(global_id.encode(), validate=True).decode()
    except (binascii.Error, UnicodeError):
        return None
    type_name, colon, domain_id = raw.partition(":")
    if not colon or not type_name or not domain_id:
        return None
    return type_name, domain_id


def decode(global_id: str, type_name: str) -> str | None:
    """The domain id, or `None` unless `global_id` is a valid `type_name` id."""
    decoded = decode_any(global_id)
    if decoded is None or decoded[0] != type_name:
        return None
    return decoded[1]
