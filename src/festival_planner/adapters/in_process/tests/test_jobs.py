import threading

from festival_planner.adapters.in_process.jobs import (
    ImmediateJobRunner,
    ThreadPoolJobRunner,
)
from festival_planner.domain.jobs import JobRunner


def test_immediate_runner_finishes_work_before_returning():
    done: list[int] = []
    runner: JobRunner = ImmediateJobRunner()
    job = runner.submit(lambda: done.append(1))
    assert done == [1]
    assert job.wait(0) is True


def test_thread_pool_runs_work_in_the_background():
    release = threading.Event()
    done = threading.Event()

    def work() -> None:
        release.wait(5)
        done.set()

    runner = ThreadPoolJobRunner()
    try:
        job = runner.submit(work)
        assert job.wait(0.01) is False
        release.set()
        assert job.wait(5) is True
        assert done.is_set()
    finally:
        runner.shutdown()


def test_thread_pool_survives_failing_work(caplog):
    def failing() -> None:
        _ = 1 / 0

    runner = ThreadPoolJobRunner()
    try:
        job = runner.submit(failing)
        assert job.wait(5) is True
        assert runner.submit(lambda: None).wait(5) is True
    finally:
        runner.shutdown()
    assert "ZeroDivisionError" in caplog.text
