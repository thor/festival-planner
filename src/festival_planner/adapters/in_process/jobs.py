"""JobRunner adapters that run work in this process."""

import concurrent.futures
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class _FutureJob:
    def __init__(self, future: concurrent.futures.Future[None]):
        self._future = future

    def wait(self, timeout: float | None = None) -> bool:
        concurrent.futures.wait([self._future], timeout=timeout)
        return self._future.done()


class ThreadPoolJobRunner:
    """Runs work on a small thread pool. Failures are logged, not raised."""

    def __init__(self, max_workers: int = 2):
        self._pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="job"
        )

    def submit(self, work: Callable[[], None]) -> _FutureJob:
        return _FutureJob(self._pool.submit(_logging_failures, work))

    def shutdown(self, wait: bool = True, *, cancel_futures: bool = False) -> None:
        """Stop taking work. `cancel_futures` drops work not yet started."""
        self._pool.shutdown(wait=wait, cancel_futures=cancel_futures)


def _logging_failures(work: Callable[[], None]) -> None:
    try:
        work()
    except Exception:
        logger.exception("Job failed")


class _FinishedJob:
    def wait(self, timeout: float | None = None) -> bool:
        return True


class ImmediateJobRunner:
    """Runs work inside `submit`, for the CLI and tests."""

    def submit(self, work: Callable[[], None]) -> _FinishedJob:
        work()
        return _FinishedJob()
