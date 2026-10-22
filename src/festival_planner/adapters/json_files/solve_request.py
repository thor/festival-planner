"""Save and load SolveRequests as JSON, for replaying solves in the CLI."""

from pathlib import Path

from ...domain.solving import SolveRequest


def dump_solve_request(request: SolveRequest, path: Path) -> None:
    path.write_text(request.model_dump_json(indent=2))


def load_solve_request(path: Path) -> SolveRequest:
    return SolveRequest.model_validate_json(path.read_bytes())
