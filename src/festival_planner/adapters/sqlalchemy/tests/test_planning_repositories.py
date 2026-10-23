import datetime

import pytest

from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.domain.change_sets import AddScreeningCommitment, ChangeSet
from festival_planner.domain.drafts import Draft, DraftStatus, Schedule
from festival_planner.domain.festival import Festival
from festival_planner.domain.planning import (
    Comparison,
    PlanningInputs,
    Preferences,
    Ticket,
)
from festival_planner.domain.planning_ports import ConflictError, PlanningUnitOfWork
from festival_planner.domain.programme import Film, ProgrammeEntry, Screening, Venue
from festival_planner.domain.solving import ScheduledScreening
from festival_planner.domain.users import User

T0 = datetime.datetime(2025, 11, 8, 12, tzinfo=datetime.UTC)


@pytest.fixture
def stored(engine) -> SqlAlchemyUnitOfWork:
    """A User and a Festival with Screenings s1 and s2 of entry e."""
    uow = SqlAlchemyUnitOfWork(engine)
    with uow:
        uow.users.save(User(id="u", issuer="local", subject="thor"))
        uow.festivals.save(
            Festival(
                id="f",
                slug="f",
                name="F",
                start_date=T0.date(),
                end_date=T0.date(),
                time_zone="Europe/Oslo",
            )
        )
        uow.venues.save(Venue(id="v", name="V"))
        uow.films.save(Film(id="film", title="Film"))
        uow.programme.save_entry(
            "f", "e", ProgrammeEntry(id="e", film_id="film", title="Film")
        )
        for i, hour in (("s1", 12), ("s2", 18)):
            uow.programme.save_screening(
                Screening(
                    id=i,
                    programme_entry_id="e",
                    venue_id="v",
                    start_time=T0.replace(hour=hour),
                    end_time=T0.replace(hour=hour + 2),
                )
            )
        uow.commit()
    return uow


def schedule(id: str, number: int) -> Schedule:
    return Schedule(
        id=id,
        user_id="u",
        festival_id="f",
        number=number,
        screening_ids=frozenset({"s1"}),
        score=1.5,
        change_set=ChangeSet(items=(AddScreeningCommitment(screening_id="s1"),)),
        accepted_at=T0,
    )


def test_satisfies_the_planning_unit_of_work_port(stored):
    uow: PlanningUnitOfWork = stored
    assert uow is stored


def test_users_are_found_by_identity(stored):
    with stored as uow:
        assert uow.users.by_identity("local", "thor") == User(
            id="u", issuer="local", subject="thor"
        )
        assert uow.users.by_identity("other", "thor") is None


def test_inputs_round_trip(stored):
    inputs = PlanningInputs(
        screening_commitments=frozenset({"s1"}),
        film_commitments=frozenset({"e"}),
        excluded_screenings=frozenset({"s2"}),
        preferences=Preferences(
            buffer_minutes=10,
            year_weights={2025: 0.2},
            comparisons=(Comparison(preferred="e", other="x"),),
        ),
    )
    with stored as uow:
        assert uow.planning.inputs("u", "f") == PlanningInputs()
        uow.planning.save_inputs("u", "f", inputs)
        uow.commit()
    with stored as uow:
        assert uow.planning.inputs("u", "f") == inputs
        uow.planning.save_inputs("u", "f", PlanningInputs())
        uow.commit()
    with stored as uow:
        assert uow.planning.inputs("u", "f") == PlanningInputs()


def test_schedules_and_the_active_one(stored):
    with stored as uow:
        assert uow.planning.active_schedule("u", "f") is None
        uow.planning.save_schedule(schedule("one", 1))
        uow.planning.save_schedule(schedule("two", 2))
        uow.commit()
    with stored as uow:
        assert uow.planning.active_schedule("u", "f") == schedule("two", 2)
        assert [s.id for s in uow.planning.schedules("u", "f")] == ["one", "two"]
        assert uow.planning.active_schedules("u") == (schedule("two", 2),)


def test_drafts_round_trip_and_are_deleted(stored):
    draft = Draft(
        id="d",
        user_id="u",
        festival_id="f",
        change_set=ChangeSet(items=(AddScreeningCommitment(screening_id="s1"),)),
        base_schedule_id=None,
        created_at=T0,
    )
    solved = draft.model_copy(
        update={
            "status": DraftStatus.READY,
            "score": 1.0,
            "reasons": ("r",),
            "notes": ("n",),
            "scheduled": (
                ScheduledScreening(screening_id="s1", arrival_time=T0, weight=1.0),
            ),
            "solved_at": T0,
        }
    )
    with stored as uow:
        uow.planning.save_draft(draft)
        uow.commit()
    with stored as uow:
        assert uow.planning.draft("d") == draft
        assert uow.planning.solving_drafts() == (draft,)
        uow.planning.save_draft(solved)
        uow.commit()
    with stored as uow:
        assert uow.planning.draft("d") == solved
        assert uow.planning.drafts("u", "f") == (solved,)
        assert uow.planning.solving_drafts() == ()
        uow.planning.delete_draft("d")
        uow.commit()
    with stored as uow:
        assert uow.planning.draft("d") is None


def test_tickets_and_seen(stored):
    with stored as uow:
        uow.tickets.save("u", Ticket(screening_id="s1", exchangeable=True))
        uow.tickets.save("u", Ticket(screening_id="s1", refundable=True))
        uow.seen.mark("u", "film")
        uow.seen.mark("u", "film")
        uow.seen.dismiss("u", "s2")
        uow.commit()
    with stored as uow:
        assert uow.tickets.tickets("u") == (Ticket(screening_id="s1", refundable=True),)
        assert uow.seen.films("u") == frozenset({"film"})
        assert uow.seen.dismissals("u") == frozenset({"s2"})
        uow.tickets.delete("u", "s1")
        uow.seen.unmark("u", "film")
        uow.seen.restore("u", "s2")
        uow.commit()
    with stored as uow:
        assert uow.tickets.tickets("u") == ()
        assert uow.seen.films("u") == frozenset()
        assert uow.seen.dismissals("u") == frozenset()


def test_lookups_by_id(stored):
    with stored as uow:
        assert uow.festivals.by_id("f").slug == "f"
        assert uow.festivals.by_id("nope") is None
        assert uow.films.by_id("film").title == "Film"
        assert [s.id for s in uow.programme.screenings_by_id(["s2", "nope", "s1"])] == [
            "s1",
            "s2",
        ]
        assert [e.id for e in uow.programme.entries_by_id(["e", "nope"])] == ["e"]


def test_a_schedule_number_taken_by_another_unit_of_work_conflicts(stored):
    with stored as uow:
        uow.planning.save_schedule(schedule("first", 1))
        uow.commit()
    with stored as uow, pytest.raises(ConflictError):
        uow.planning.save_schedule(schedule("second", 1))


def test_an_identity_taken_by_another_unit_of_work_conflicts(stored):
    with stored as uow, pytest.raises(ConflictError):
        uow.users.save(User(id="other", issuer="local", subject="thor"))
