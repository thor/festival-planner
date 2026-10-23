import datetime

from festival_planner.domain.change_sets import ChangeSet
from festival_planner.domain.drafts import Draft, DraftStatus, Schedule
from festival_planner.domain.planning import PlanningInputs, Ticket

from .fakes import InMemoryUnitOfWork

NOW = datetime.datetime(2025, 11, 1, 12, tzinfo=datetime.UTC)


def schedule(id: str, number: int, festival: str = "f") -> Schedule:
    return Schedule(
        id=id,
        user_id="u",
        festival_id=festival,
        number=number,
        screening_ids=frozenset(),
        score=0.0,
        change_set=ChangeSet(),
        accepted_at=NOW,
    )


def test_inputs_default_to_empty():
    with InMemoryUnitOfWork() as uow:
        assert uow.planning.inputs("u", "f") == PlanningInputs()


def test_the_active_schedule_has_the_highest_number():
    uow = InMemoryUnitOfWork()
    with uow:
        uow.planning.save_schedule(schedule("one", 1))
        uow.planning.save_schedule(schedule("two", 2))
        uow.planning.save_schedule(schedule("other", 1, festival="g"))
        uow.commit()
    with uow:
        active = uow.planning.active_schedule("u", "f")
        assert active is not None
        assert active.id == "two"
        assert [s.id for s in uow.planning.schedules("u", "f")] == ["one", "two"]
        assert {s.id for s in uow.planning.active_schedules("u")} == {"two", "other"}


def test_drafts_can_be_listed_found_and_deleted():
    uow = InMemoryUnitOfWork()
    draft = Draft(
        id="d",
        user_id="u",
        festival_id="f",
        change_set=ChangeSet(),
        base_schedule_id=None,
        created_at=NOW,
    )
    with uow:
        uow.planning.save_draft(draft)
        uow.commit()
    with uow:
        assert uow.planning.draft("d") == draft
        assert uow.planning.drafts("u", "f") == (draft,)
        assert uow.planning.solving_drafts() == (draft,)
        uow.planning.save_draft(draft.model_copy(update={"status": DraftStatus.READY}))
        assert uow.planning.solving_drafts() == ()
        uow.planning.delete_draft("d")
        assert uow.planning.draft("d") is None


def test_tickets_and_seen():
    uow = InMemoryUnitOfWork()
    with uow:
        uow.tickets.save("u", Ticket(screening_id="s", refundable=True))
        uow.seen.mark("u", "film")
        uow.seen.dismiss("u", "s")
        uow.commit()
    with uow:
        assert uow.tickets.tickets("u") == (Ticket(screening_id="s", refundable=True),)
        assert uow.seen.films("u") == frozenset({"film"})
        assert uow.seen.dismissals("u") == frozenset({"s"})
        uow.tickets.delete("u", "s")
        uow.seen.unmark("u", "film")
        uow.seen.restore("u", "s")
        assert uow.tickets.tickets("u") == ()
        assert uow.seen.films("u") == frozenset()
        assert uow.seen.dismissals("u") == frozenset()
