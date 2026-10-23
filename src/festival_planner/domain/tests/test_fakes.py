import datetime

from festival_planner.domain.change_sets import ChangeSet
from festival_planner.domain.drafts import (
    Draft,
    DraftId,
    DraftStatus,
    Schedule,
    ScheduleId,
)
from festival_planner.domain.festival import FestivalId
from festival_planner.domain.planning import PlanningInputs, Ticket
from festival_planner.domain.programme import FilmId, ScreeningId
from festival_planner.domain.users import UserId

from .fakes import InMemoryUnitOfWork

NOW = datetime.datetime(2025, 11, 1, 12, tzinfo=datetime.UTC)


def schedule(id: str, number: int, festival: str = "f") -> Schedule:
    return Schedule(
        id=ScheduleId(id),
        user_id=UserId("u"),
        festival_id=FestivalId(festival),
        number=number,
        screening_ids=frozenset(),
        score=0.0,
        change_set=ChangeSet(),
        accepted_at=NOW,
    )


def test_inputs_default_to_empty():
    with InMemoryUnitOfWork() as uow:
        assert uow.planning.inputs(UserId("u"), FestivalId("f")) == PlanningInputs()


def test_the_active_schedule_has_the_highest_number():
    uow = InMemoryUnitOfWork()
    with uow:
        uow.planning.save_schedule(schedule("one", 1))
        uow.planning.save_schedule(schedule("two", 2))
        uow.planning.save_schedule(schedule("other", 1, festival="g"))
        uow.commit()
    with uow:
        active = uow.planning.active_schedule(UserId("u"), FestivalId("f"))
        assert active is not None
        assert active.id == "two"
        assert [s.id for s in uow.planning.schedules(UserId("u"), FestivalId("f"))] == [
            "one",
            "two",
        ]
        assert {s.id for s in uow.planning.active_schedules(UserId("u"))} == {
            "two",
            "other",
        }


def test_drafts_can_be_listed_found_and_deleted():
    uow = InMemoryUnitOfWork()
    draft = Draft(
        id=DraftId("d"),
        user_id=UserId("u"),
        festival_id=FestivalId("f"),
        change_set=ChangeSet(),
        base_schedule_id=None,
        created_at=NOW,
    )
    with uow:
        uow.planning.save_draft(draft)
        uow.commit()
    with uow:
        assert uow.planning.draft(DraftId("d")) == draft
        assert uow.planning.drafts(UserId("u"), FestivalId("f")) == (draft,)
        assert uow.planning.solving_drafts() == (draft,)
        uow.planning.save_draft(draft.model_copy(update={"status": DraftStatus.READY}))
        assert uow.planning.solving_drafts() == ()
        uow.planning.delete_draft(DraftId("d"))
        assert uow.planning.draft(DraftId("d")) is None


def test_tickets_and_seen():
    uow = InMemoryUnitOfWork()
    with uow:
        uow.tickets.save(
            UserId("u"), Ticket(screening_id=ScreeningId("s"), refundable=True)
        )
        uow.seen.mark(UserId("u"), FilmId("film"))
        uow.seen.dismiss(UserId("u"), ScreeningId("s"))
        uow.commit()
    with uow:
        assert uow.tickets.tickets(UserId("u")) == (
            Ticket(screening_id=ScreeningId("s"), refundable=True),
        )
        assert uow.seen.films(UserId("u")) == frozenset({"film"})
        assert uow.seen.dismissals(UserId("u")) == frozenset({"s"})
        uow.tickets.delete(UserId("u"), ScreeningId("s"))
        uow.seen.unmark(UserId("u"), FilmId("film"))
        uow.seen.restore(UserId("u"), ScreeningId("s"))
        assert uow.tickets.tickets(UserId("u")) == ()
        assert uow.seen.films(UserId("u")) == frozenset()
        assert uow.seen.dismissals(UserId("u")) == frozenset()
