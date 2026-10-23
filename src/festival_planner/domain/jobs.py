"""Running work outside the request that asked for it."""

from collections.abc import Callable
from typing import Protocol


class Job(Protocol):
    def wait(self, timeout: float | None = None) -> bool:
        """Wait up to `timeout` seconds; whether the work has finished."""
        ...


class JobRunner(Protocol):
    """Port: runs work, possibly in the background."""

    def submit(self, work: Callable[[], None]) -> Job: ...
