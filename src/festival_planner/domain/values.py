"""Base class for the domain's immutable, validated values."""

from pydantic import BaseModel, ConfigDict


class Value(BaseModel):
    """An immutable domain value, validated on construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")
