"""Save and load SolveRequests as JSON, for replaying solves in the CLI."""

from pathlib import Path

from pydantic import TypeAdapter

from ...domain.solving import SolveRequest

_ADAPTER = TypeAdapter(SolveRequest)


def dump_solve_request(request: SolveRequest, path: Path) -> None:
    path.write_bytes(_ADAPTER.dump_json(request, indent=2))


def load_solve_request(path: Path) -> SolveRequest:
    return _ADAPTER.validate_json(path.read_bytes())
