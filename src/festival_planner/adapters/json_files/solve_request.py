"""Save and load SolveRequests as JSON, for replaying solves in the CLI."""

import json
from pathlib import Path

from ...domain.solving import SOLVE_REQUEST_FORMAT_VERSION, SolveRequest


class UnsupportedFormatError(ValueError):
    """The file is a solve request in a format this version cannot read."""


def dump_solve_request(request: SolveRequest, path: Path) -> None:
    path.write_text(request.model_dump_json(indent=2))


def load_solve_request(path: Path) -> SolveRequest:
    """Requests exported before versioning count as version 1."""
    raw = path.read_bytes()
    data = json.loads(raw)
    version = (
        data.get("format_version", SOLVE_REQUEST_FORMAT_VERSION)
        if isinstance(data, dict)
        else None
    )
    if version != SOLVE_REQUEST_FORMAT_VERSION:
        raise UnsupportedFormatError(
            f"{path} is solve request format version {version!r}; "
            f"this version reads {SOLVE_REQUEST_FORMAT_VERSION}"
        )
    return SolveRequest.model_validate_json(raw)
