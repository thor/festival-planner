"""Base class and shared types for the domain's immutable, validated values."""

import zoneinfo
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


class Value(BaseModel):
    """An immutable domain value, validated on construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")


def _known_time_zone(key: str) -> str:
    try:
        zoneinfo.ZoneInfo(key)
    except (zoneinfo.ZoneInfoNotFoundError, ValueError) as e:
        raise ValueError(f"Unknown time zone {key!r}") from e
    return key


TimeZone = Annotated[str, AfterValidator(_known_time_zone)]
"""An IANA time zone key, e.g. "Europe/Oslo"."""

Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")]
"""A stable, human-readable handle such as "films-from-the-south-2025"."""
