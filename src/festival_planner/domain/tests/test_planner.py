import datetime

import pytest

from festival_planner.domain.change_sets import (
    AddExcludedScreening,
    AddScreeningCommitment,
    ChangeSet,
    InvalidChangeSetError,
    SetProgrammeEntryWeight,
)
from festival_planner.domain.drafts import Draft, DraftStatus, Schedule, ScheduleId
from festival_planner.domain.festival import Festival, FestivalId
from festival_planner.domain.planner import (
    DraftNotAcceptableError,
    DraftStillSolvingError,
    NotFoundError,
    Planner,
    PlanningError,
)
from festival_planner.domain.planning import PlanningInputs, Ticket
from festival_planner.domain.programme import (
    Film,
    FilmId,
    ProgrammeEntryId,
    ScreeningId,
    Venue,
    VenueId,
)
from festival_planner.domain.users import UserId

from .builders import DAY, ZONE, at, entry, screening
from .fakes import (
    DeferredJobRunner,
    FailingSolver,
    GreedySolver,
    InlineJobRunner,
    InMemoryUnitOfWork,
    RecordingNotifier,
    TickingClock,
    concurrently,
    sequential_ids,
)

SLUG = "fest-2025"
U = UserId("u")
F = FestivalId("f")


@pytest.fixture
def uow() -> InMemoryUnitOfWork:
    """A Festival with a, b (conflicting) and c, d (later, conflicting)."""
    uow = InMemoryUnitOfWork()
    with uow:
        uow.festivals.save(
            Festival(
                id=F,
                slug=SLUG,
                name="Fest",
                start_date=DAY,
                end_date=DAY,
                time_zone=ZONE,
            )
        )
        uow.venues.save(Venue(id=VenueId("A"), name="A"))
        for e in ("a", "b", "c", "d"):
            uow.films.save(Film(id=FilmId(f"film-{e}"), title=e))
            uow.programme.save_entry(F, e, entry(e))
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
            SetProgrammeEntryWeight(programme_entry_id=ProgrammeEntryId(e), weight=v)
            for e, v in w.items()
        )
    )


def test_a_new_draft_is_solved_and_diffed_against_nothing(uow):
    notifier = RecordingNotifier()
    view = planner(uow, notifier=notifier).create_draft(U, SLUG, weights(b=2.0))
    assert view.draft.status is DraftStatus.READY
    assert view.draft.screening_ids == frozenset({"b", "c"})
    assert not view.stale
    assert view.diff is not None and view.diff.added == frozenset({"b", "c"})
    assert [d.id for d in notifier.solved] == [view.draft.id]


def test_an_invalid_change_set_creates_no_draft(uow):
    p = planner(uow)
    with pytest.raises(InvalidChangeSetError):
        p.create_draft(
            U,
            SLUG,
            ChangeSet(
                items=(AddScreeningCommitment(screening_id=ScreeningId("nope")),)
            ),
        )
    assert p.drafts(U, SLUG) == ()


def test_unknown_festivals_are_not_found(uow):
    with pytest.raises(NotFoundError):
        planner(uow).create_draft(U, "nope")


def test_a_slow_solve_returns_the_draft_while_solving(uow):
    jobs = DeferredJobRunner()
    p = planner(uow, jobs=jobs)
    view = p.create_draft(U, SLUG)
    assert view.draft.status is DraftStatus.SOLVING
    jobs.run_all()
    assert p.draft(U, view.draft.id).draft.status is DraftStatus.READY


def test_accepting_applies_the_change_set_and_makes_the_schedule_active(uow):
    p = planner(uow)
    view = p.create_draft(U, SLUG, weights(b=2.0))
    schedule = p.accept(U, view.draft.id)
    assert schedule.number == 1
    assert p.active_schedule(U, SLUG) == schedule
    assert schedule.screening_ids == frozenset({"b", "c"})
    assert p.drafts(U, SLUG) == ()
    with uow:
        assert uow.planning.inputs(U, F).preferences.programme_entry_weights == {
            ProgrammeEntryId("b"): 2.0
        }


def test_accepting_makes_other_drafts_stale_and_unacceptable(uow):
    p = planner(uow)
    first = p.create_draft(U, SLUG, weights(b=2.0))
    second = p.create_draft(U, SLUG, weights(d=2.0))
    p.accept(U, first.draft.id)
    assert p.draft(U, second.draft.id).stale
    with pytest.raises(DraftNotAcceptableError):
        p.accept(U, second.draft.id)


def test_resolving_a_stale_draft_rebases_it(uow):
    p = planner(uow)
    first = p.create_draft(U, SLUG, weights(b=2.0))
    second = p.create_draft(
        U, SLUG, ChangeSet(items=(*weights(b=2.0).items, *weights(d=2.0).items))
    )
    p.accept(U, first.draft.id)
    resolved = p.resolve(U, second.draft.id)
    assert not resolved.stale
    assert resolved.draft.attempt == 2
    assert resolved.draft.change_set == weights(d=2.0)
    assert len(resolved.draft.notes) == 1
    assert resolved.draft.screening_ids == frozenset({"b", "d"})
    assert resolved.diff is not None and resolved.diff.added == frozenset({"d"})
    assert p.accept(U, second.draft.id).number == 2


def test_a_resolve_that_now_contradicts_leaves_the_draft_alone(uow):
    p = planner(uow)
    exclude = p.create_draft(
        U, SLUG, ChangeSet(items=(AddExcludedScreening(screening_id=ScreeningId("a")),))
    )
    commit = p.create_draft(
        U,
        SLUG,
        ChangeSet(items=(AddScreeningCommitment(screening_id=ScreeningId("a")),)),
    )
    p.accept(U, exclude.draft.id)
    with pytest.raises(InvalidChangeSetError):
        p.resolve(U, commit.draft.id)
    assert p.draft(U, commit.draft.id).draft == commit.draft


def test_results_of_a_superseded_solve_are_ignored(uow):
    jobs = DeferredJobRunner()
    p = planner(uow, jobs=jobs)
    view = p.create_draft(U, SLUG)
    jobs.run_all()
    p.resolve(U, view.draft.id)  # attempt 2 pending
    p._solve(view.draft.id, 1)
    assert p.draft(U, view.draft.id).draft.status is DraftStatus.SOLVING
    jobs.run_all()
    assert p.draft(U, view.draft.id).draft.status is DraftStatus.READY


def test_infeasible_and_failed_drafts(uow):
    with uow:
        uow.programme.save_screening(
            screening("a", "14:00", "16:00").model_copy(update={"withdrawn": True})
        )
        uow.commit()
    view = planner(uow).create_draft(
        U,
        SLUG,
        ChangeSet(items=(AddScreeningCommitment(screening_id=ScreeningId("a")),)),
    )
    assert view.draft.status is DraftStatus.INFEASIBLE
    assert "withdrawn" in view.draft.reasons[0]
    failed = planner(uow, solver=FailingSolver()).create_draft(U, SLUG)
    assert failed.draft.status is DraftStatus.FAILED
    assert "solver exploded" in failed.draft.reasons[0]
    with pytest.raises(DraftNotAcceptableError):
        planner(uow).accept(U, failed.draft.id)


def test_other_users_drafts_are_not_found(uow):
    p = planner(uow)
    view = p.create_draft(U, SLUG)
    for action in (p.draft, p.accept, p.discard, p.resolve, p.solve_request):
        with pytest.raises(NotFoundError):
            action(UserId("someone-else"), view.draft.id)


def test_discarding_deletes_the_draft(uow):
    p = planner(uow)
    view = p.create_draft(U, SLUG)
    p.discard(U, view.draft.id)
    assert p.drafts(U, SLUG) == ()


def test_resolving_while_solving_is_refused(uow):
    p = planner(uow, jobs=DeferredJobRunner())
    view = p.create_draft(U, SLUG)
    with pytest.raises(DraftStillSolvingError):
        p.resolve(U, view.draft.id)
    assert issubclass(DraftStillSolvingError, PlanningError)


def test_resume_solving_resubmits_solving_drafts(uow):
    jobs = DeferredJobRunner()
    planner(uow, jobs=jobs).create_draft(U, SLUG)  # never run: as if the process died
    fresh = planner(uow)
    assert fresh.resume_solving() == 1
    assert fresh.drafts(U, SLUG)[0].draft.status is DraftStatus.READY


def test_ended_active_screenings_are_seen_unless_dismissed(uow):
    p = planner(uow)
    p.accept(U, p.create_draft(U, SLUG, weights(b=2.0)).draft.id)
    later = planner(uow, start=at("17:30"))
    assert later.seen_films(U) == frozenset({"film-b"})
    later.dismiss_inferred_seen(U, ScreeningId("b"))
    assert later.seen_films(U) == frozenset()
    later.restore_inferred_seen(U, ScreeningId("b"))
    later.mark_seen(U, FilmId("film-d"))
    assert later.seen_films(U) == frozenset({"film-b", "film-d"})


def test_manual_seen_films_are_not_scheduled(uow):
    p = planner(uow)
    p.mark_seen(U, FilmId("film-b"))
    view = p.create_draft(U, SLUG, weights(b=2.0))
    assert "b" not in view.draft.screening_ids


def test_unknown_films_and_screenings_are_not_found(uow):
    p = planner(uow)
    with pytest.raises(NotFoundError):
        p.mark_seen(U, FilmId("film-nope"))
    with pytest.raises(NotFoundError):
        p.record_ticket(U, Ticket(screening_id=ScreeningId("nope")))


def test_tickets_flags_and_dropped_ticket_warnings(uow):
    p = planner(uow)
    p.accept(U, p.create_draft(U, SLUG, weights(b=2.0)).draft.id)
    p.record_ticket(U, Ticket(screening_id=ScreeningId("b"), refundable=True))
    p.record_ticket(U, Ticket(screening_id=ScreeningId("a")))
    assert [(f.kind.value, f.target_id) for f in p.flags(U, SLUG)] == [
        ("UNSCHEDULED_TICKET", "a")
    ]
    view = p.create_draft(U, SLUG, weights(a=3.0))
    assert view.diff is not None and view.diff.dropped_tickets == frozenset({"b"})
    p.remove_ticket(U, ScreeningId("a"))
    assert p.tickets(U) == (Ticket(screening_id=ScreeningId("b"), refundable=True),)


def test_suggestions_come_from_the_latest_ready_draft(uow):
    p = planner(uow)
    assert p.suggest_comparisons(U, SLUG) == ()
    p.create_draft(U, SLUG, weights(b=2.0))
    suggestions = p.suggest_comparisons(U, SLUG)
    assert {(s.scheduled, s.other) for s in suggestions} == {("b", "a"), ("c", "d")}


def test_the_solve_request_reflects_the_change_set(uow):
    p = planner(uow)
    view = p.create_draft(
        U,
        SLUG,
        ChangeSet(items=(AddScreeningCommitment(screening_id=ScreeningId("a")),)),
    )
    request = p.solve_request(U, view.draft.id)
    assert request.screening_commitments == frozenset({"a"})
    assert request.time_zone == ZONE
    assert request.now is not None and request.now.tzinfo is not None


def test_a_draft_discarded_before_its_solve_runs_stays_gone(uow):
    jobs = DeferredJobRunner()
    notifier = RecordingNotifier()
    p = planner(uow, jobs=jobs, notifier=notifier)
    view = p.create_draft(U, SLUG)
    p.discard(U, view.draft.id)
    jobs.run_all()
    assert p.drafts(U, SLUG) == ()
    assert notifier.solved == []


def test_a_job_that_breaks_outside_the_solver_fails_the_draft(uow):
    jobs = DeferredJobRunner()
    notifier = RecordingNotifier()
    p = planner(uow, jobs=jobs, notifier=notifier)
    view = p.create_draft(U, SLUG)
    uow.stored.festivals.clear()  # the request can no longer be built
    jobs.run_all()
    failed = p.draft(U, view.draft.id).draft
    assert failed.status is DraftStatus.FAILED
    assert "failed" in failed.reasons[0]
    assert [d.id for d in notifier.solved] == [view.draft.id]


def _accept_sibling(state) -> None:
    """Another process accepts a sibling Draft: Schedule 1, excluding "a"."""
    state.schedules[ScheduleId("sibling")] = Schedule(
        id=ScheduleId("sibling"),
        user_id=U,
        festival_id=F,
        number=1,
        screening_ids=frozenset({ScreeningId("b")}),
        score=1.0,
        change_set=ChangeSet(
            items=(AddExcludedScreening(screening_id=ScreeningId("a")),)
        ),
        accepted_at=at("09:00"),
    )
    state.inputs[U, F] = state.inputs.get((U, F), PlanningInputs()).model_copy(
        update={"excluded_screenings": frozenset({ScreeningId("a")})}
    )


def test_a_sibling_accepted_while_creating_a_draft_makes_it_stale(uow):
    uow.hooks["planning.inputs"] = concurrently(uow, _accept_sibling)
    view = planner(uow).create_draft(U, SLUG, weights(b=2.0))
    assert view.stale


def test_a_sibling_accepted_while_resolving_a_draft_makes_it_stale(uow):
    p = planner(uow)
    view = p.create_draft(U, SLUG)
    uow.hooks["planning.inputs"] = concurrently(uow, _accept_sibling)
    assert p.resolve(U, view.draft.id).stale


def test_a_sibling_accepted_while_accepting_wins(uow):
    p = planner(uow)
    view = p.create_draft(U, SLUG, weights(b=2.0))
    uow.hooks["planning.inputs"] = concurrently(uow, _accept_sibling)
    with pytest.raises(DraftNotAcceptableError, match="meanwhile"):
        p.accept(U, view.draft.id)
    assert [s.id for s in p.schedules(U, SLUG)] == ["sibling"]
    assert p.draft(U, view.draft.id).stale


class RaisingNotifier:
    def draft_solved(self, draft: Draft) -> None:
        raise RuntimeError("notifier exploded")


def test_a_failing_notifier_does_not_fail_the_solved_draft(uow):
    view = planner(uow, notifier=RaisingNotifier()).create_draft(U, SLUG)
    assert view.draft.status is DraftStatus.READY
