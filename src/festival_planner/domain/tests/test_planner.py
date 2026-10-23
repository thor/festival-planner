import datetime

import pytest

from festival_planner.domain.change_sets import (
    AddExcludedScreening,
    AddScreeningCommitment,
    ChangeSet,
    InvalidChangeSetError,
    SetProgrammeEntryWeight,
)
from festival_planner.domain.drafts import DraftStatus
from festival_planner.domain.festival import Festival
from festival_planner.domain.planner import (
    DraftNotAcceptableError,
    NotFoundError,
    Planner,
    PlanningError,
)
from festival_planner.domain.planning import Ticket
from festival_planner.domain.programme import Film, Venue

from .builders import DAY, ZONE, at, entry, screening
from .fakes import (
    DeferredJobRunner,
    FailingSolver,
    GreedySolver,
    InlineJobRunner,
    InMemoryUnitOfWork,
    RecordingNotifier,
    TickingClock,
    sequential_ids,
)

SLUG = "fest-2025"


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    """A Festival with a, b (conflicting) and c, d (later, conflicting)."""
    uow = InMemoryUnitOfWork()
    with uow:
        uow.festivals.save(
            Festival(
                id="f",
                slug=SLUG,
                name="Fest",
                start_date=DAY,
                end_date=DAY,
                time_zone=ZONE,
            )
        )
        uow.venues.save(Venue(id="A", name="A"))
        for e in ("a", "b", "c", "d"):
            uow.films.save(Film(id=f"film-{e}", title=e))
            uow.programme.save_entry("f", e, entry(e))
        for s in (
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            screening("c", "18:00", "20:00"),
            screening("d", "19:00", "21:00"),
        ):
            uow.programme.save_screening(s)
        uow.commit()
    return uow


def planner(
    uow,
    *,
    solver=None,
    jobs=None,
    notifier=None,
    start: datetime.datetime | None = None,
) -> Planner:
    return Planner(
        lambda: uow,
        solver or GreedySolver(),
        jobs or InlineJobRunner(),
        notifier or RecordingNotifier(),
        clock=TickingClock(start or at("09:00")),
        new_id=sequential_ids(),
    )


def weights(**w: float) -> ChangeSet:
    return ChangeSet(
        items=tuple(
            SetProgrammeEntryWeight(programme_entry_id=e, weight=v)
            for e, v in w.items()
        )
    )


def test_a_new_draft_is_solved_and_diffed_against_nothing(uow):
    notifier = RecordingNotifier()
    view = planner(uow, notifier=notifier).create_draft("u", SLUG, weights(b=2.0))
    assert view.draft.status is DraftStatus.READY
    assert view.draft.screening_ids == frozenset({"b", "c"})
    assert not view.stale
    assert view.diff is not None and view.diff.added == frozenset({"b", "c"})
    assert [d.id for d in notifier.solved] == [view.draft.id]


def test_an_invalid_change_set_creates_no_draft(uow):
    p = planner(uow)
    with pytest.raises(InvalidChangeSetError):
        p.create_draft(
            "u", SLUG, ChangeSet(items=(AddScreeningCommitment(screening_id="nope"),))
        )
    assert p.drafts("u", SLUG) == ()


def test_unknown_festivals_are_not_found(uow):
    with pytest.raises(NotFoundError):
        planner(uow).create_draft("u", "nope")


def test_a_slow_solve_returns_the_draft_while_solving(uow):
    jobs = DeferredJobRunner()
    p = planner(uow, jobs=jobs)
    view = p.create_draft("u", SLUG)
    assert view.draft.status is DraftStatus.SOLVING
    jobs.run_all()
    assert p.draft("u", view.draft.id).draft.status is DraftStatus.READY


def test_accepting_applies_the_change_set_and_makes_the_schedule_active(uow):
    p = planner(uow)
    view = p.create_draft("u", SLUG, weights(b=2.0))
    schedule = p.accept("u", view.draft.id)
    assert schedule.number == 1
    assert p.active_schedule("u", SLUG) == schedule
    assert schedule.screening_ids == frozenset({"b", "c"})
    assert p.drafts("u", SLUG) == ()
    with uow:
        assert uow.planning.inputs("u", "f").preferences.programme_entry_weights == {
            "b": 2.0
        }


def test_accepting_makes_other_drafts_stale_and_unacceptable(uow):
    p = planner(uow)
    first = p.create_draft("u", SLUG, weights(b=2.0))
    second = p.create_draft("u", SLUG, weights(d=2.0))
    p.accept("u", first.draft.id)
    assert p.draft("u", second.draft.id).stale
    with pytest.raises(DraftNotAcceptableError):
        p.accept("u", second.draft.id)


def test_resolving_a_stale_draft_rebases_it(uow):
    p = planner(uow)
    first = p.create_draft("u", SLUG, weights(b=2.0))
    second = p.create_draft(
        "u", SLUG, ChangeSet(items=(*weights(b=2.0).items, *weights(d=2.0).items))
    )
    p.accept("u", first.draft.id)
    resolved = p.resolve("u", second.draft.id)
    assert not resolved.stale
    assert resolved.draft.attempt == 2
    assert resolved.draft.change_set == weights(d=2.0)
    assert len(resolved.draft.notes) == 1
    assert resolved.draft.screening_ids == frozenset({"b", "d"})
    assert resolved.diff is not None and resolved.diff.added == frozenset({"d"})
    assert p.accept("u", second.draft.id).number == 2


def test_a_resolve_that_now_contradicts_leaves_the_draft_alone(uow):
    p = planner(uow)
    exclude = p.create_draft(
        "u", SLUG, ChangeSet(items=(AddExcludedScreening(screening_id="a"),))
    )
    commit = p.create_draft(
        "u", SLUG, ChangeSet(items=(AddScreeningCommitment(screening_id="a"),))
    )
    p.accept("u", exclude.draft.id)
    with pytest.raises(InvalidChangeSetError):
        p.resolve("u", commit.draft.id)
    assert p.draft("u", commit.draft.id).draft == commit.draft


def test_results_of_a_superseded_solve_are_ignored(uow):
    jobs = DeferredJobRunner()
    p = planner(uow, jobs=jobs)
    view = p.create_draft("u", SLUG)
    jobs.run_all()
    p.resolve("u", view.draft.id)  # attempt 2 pending
    p._solve(view.draft.id, 1)
    assert p.draft("u", view.draft.id).draft.status is DraftStatus.SOLVING
    jobs.run_all()
    assert p.draft("u", view.draft.id).draft.status is DraftStatus.READY


def test_infeasible_and_failed_drafts(uow):
    with uow:
        uow.programme.save_screening(
            screening("a", "14:00", "16:00").model_copy(update={"withdrawn": True})
        )
        uow.commit()
    view = planner(uow).create_draft(
        "u", SLUG, ChangeSet(items=(AddScreeningCommitment(screening_id="a"),))
    )
    assert view.draft.status is DraftStatus.INFEASIBLE
    assert "withdrawn" in view.draft.reasons[0]
    failed = planner(uow, solver=FailingSolver()).create_draft("u", SLUG)
    assert failed.draft.status is DraftStatus.FAILED
    assert "solver exploded" in failed.draft.reasons[0]
    with pytest.raises(DraftNotAcceptableError):
        planner(uow).accept("u", failed.draft.id)


def test_other_users_drafts_are_not_found(uow):
    p = planner(uow)
    view = p.create_draft("u", SLUG)
    for action in (p.draft, p.accept, p.discard, p.resolve, p.solve_request):
        with pytest.raises(NotFoundError):
            action("someone-else", view.draft.id)


def test_discarding_deletes_the_draft(uow):
    p = planner(uow)
    view = p.create_draft("u", SLUG)
    p.discard("u", view.draft.id)
    assert p.drafts("u", SLUG) == ()


def test_resolving_while_solving_is_refused(uow):
    p = planner(uow, jobs=DeferredJobRunner())
    view = p.create_draft("u", SLUG)
    with pytest.raises(PlanningError):
        p.resolve("u", view.draft.id)


def test_resume_solving_resubmits_solving_drafts(uow):
    jobs = DeferredJobRunner()
    planner(uow, jobs=jobs).create_draft("u", SLUG)  # never run: as if the process died
    fresh = planner(uow)
    assert fresh.resume_solving() == 1
    assert fresh.drafts("u", SLUG)[0].draft.status is DraftStatus.READY


def test_ended_active_screenings_are_seen_unless_dismissed(uow):
    p = planner(uow)
    p.accept("u", p.create_draft("u", SLUG, weights(b=2.0)).draft.id)
    later = planner(uow, start=at("17:30"))
    assert later.seen_films("u") == frozenset({"film-b"})
    later.dismiss_inferred_seen("u", "b")
    assert later.seen_films("u") == frozenset()
    later.restore_inferred_seen("u", "b")
    later.mark_seen("u", "film-d")
    assert later.seen_films("u") == frozenset({"film-b", "film-d"})


def test_manual_seen_films_are_not_scheduled(uow):
    p = planner(uow)
    p.mark_seen("u", "film-b")
    view = p.create_draft("u", SLUG, weights(b=2.0))
    assert "b" not in view.draft.screening_ids


def test_unknown_films_and_screenings_are_not_found(uow):
    p = planner(uow)
    with pytest.raises(NotFoundError):
        p.mark_seen("u", "film-nope")
    with pytest.raises(NotFoundError):
        p.record_ticket("u", Ticket(screening_id="nope"))


def test_tickets_flags_and_dropped_ticket_warnings(uow):
    p = planner(uow)
    p.accept("u", p.create_draft("u", SLUG, weights(b=2.0)).draft.id)
    p.record_ticket("u", Ticket(screening_id="b", refundable=True))
    p.record_ticket("u", Ticket(screening_id="a"))
    assert [(f.kind.value, f.target_id) for f in p.flags("u", SLUG)] == [
        ("UNSCHEDULED_TICKET", "a")
    ]
    view = p.create_draft("u", SLUG, weights(a=3.0))
    assert view.diff is not None and view.diff.dropped_tickets == frozenset({"b"})
    p.remove_ticket("u", "a")
    assert p.tickets("u") == (Ticket(screening_id="b", refundable=True),)


def test_suggestions_come_from_the_latest_ready_draft(uow):
    p = planner(uow)
    assert p.suggest_comparisons("u", SLUG) == ()
    p.create_draft("u", SLUG, weights(b=2.0))
    suggestions = p.suggest_comparisons("u", SLUG)
    assert {(s.scheduled, s.other) for s in suggestions} == {("b", "a"), ("c", "d")}


def test_the_solve_request_reflects_the_change_set(uow):
    p = planner(uow)
    view = p.create_draft(
        "u", SLUG, ChangeSet(items=(AddScreeningCommitment(screening_id="a"),))
    )
    request = p.solve_request("u", view.draft.id)
    assert request.screening_commitments == frozenset({"a"})
    assert request.time_zone == ZONE
    assert request.now is not None and request.now.tzinfo is not None


def test_a_draft_discarded_before_its_solve_runs_stays_gone(uow):
    jobs = DeferredJobRunner()
    notifier = RecordingNotifier()
    p = planner(uow, jobs=jobs, notifier=notifier)
    view = p.create_draft("u", SLUG)
    p.discard("u", view.draft.id)
    jobs.run_all()
    assert p.drafts("u", SLUG) == ()
    assert notifier.solved == []


def test_a_job_that_breaks_outside_the_solver_fails_the_draft(uow):
    jobs = DeferredJobRunner()
    notifier = RecordingNotifier()
    p = planner(uow, jobs=jobs, notifier=notifier)
    view = p.create_draft("u", SLUG)
    uow.stored.festivals.clear()  # the request can no longer be built
    jobs.run_all()
    failed = p.draft("u", view.draft.id).draft
    assert failed.status is DraftStatus.FAILED
    assert "failed" in failed.reasons[0]
    assert [d.id for d in notifier.solved] == [view.draft.id]
