import datetime

import pytest

from festival_planner.adapters.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from festival_planner.domain.change_sets import AddScreeningCommitment, ChangeSet
from festival_planner.domain.drafts import (
    Draft,
    DraftId,
    DraftStatus,
    Schedule,
    ScheduleId,
)
from festival_planner.domain.festival import Festival, FestivalId
from festival_planner.domain.planning import (
    Comparison,
    PlanningInputs,
    Preferences,
    Ticket,
)
from festival_planner.domain.planning_ports import ConflictError, PlanningUnitOfWork
from festival_planner.domain.programme import (
    Film,
    FilmId,
    ProgrammeEntry,
    ProgrammeEntryId,
    Screening,
    ScreeningId,
    Venue,
    VenueId,
)
from festival_planner.domain.solving import ScheduledScreening
from festival_planner.domain.users import User, UserId

T0 = datetime.datetime(2025, 11, 8, 12, tzinfo=datetime.UTC)

U = UserId("u")
F = FestivalId("f")
V = VenueId("v")
FILM = FilmId("film")
E = ProgrammeEntryId("e")
S1 = ScreeningId("s1")
S2 = ScreeningId("s2")
D = DraftId("d")


@pytest.fixture
def stored(engine) -> SqlAlchemyUnitOfWork:
    """A User and a Festival with Screenings s1 and s2 of entry e."""
    uow = SqlAlchemyUnitOfWork(engine)
    with uow:
        uow.users.save(User(id=U, issuer="local", subject="thor"))
        uow.festivals.save(
            Festival(
                id=F,
                slug="f",
                name="F",
                start_date=T0.date(),
                end_date=T0.date(),
                time_zone="Europe/Oslo",
            )
        )
        uow.venues.save(Venue(id=V, name="V"))
        uow.films.save(Film(id=FILM, title="Film"))
        uow.programme.save_entry(
            F, "e", ProgrammeEntry(id=E, film_id=FILM, title="Film")
        )
        for i, hour in ((S1, 12), (S2, 18)):
            uow.programme.save_screening(
                Screening(
                    id=i,
                    programme_entry_id=E,
                    venue_id=V,
                    start_time=T0.replace(hour=hour),
                    end_time=T0.replace(hour=hour + 2),
                )
            )
        uow.commit()
    return uow


def schedule(id: str, number: int) -> Schedule:
    return Schedule(
        id=ScheduleId(id),
        user_id=U,
        festival_id=F,
        number=number,
        screening_ids=frozenset({S1}),
        score=1.5,
        change_set=ChangeSet(items=(AddScreeningCommitment(screening_id=S1),)),
        accepted_at=T0,
    )


def test_satisfies_the_planning_unit_of_work_port(stored):
    uow: PlanningUnitOfWork = stored
    assert uow is stored


def test_users_are_found_by_identity(stored):
    with stored as uow:
        assert uow.users.by_identity("local", "thor") == User(
            id=U, issuer="local", subject="thor"
        )
        assert uow.users.by_identity("other", "thor") is None


def test_inputs_round_trip(stored):
    inputs = PlanningInputs(
        screening_commitments=frozenset({S1}),
        film_commitments=frozenset({E}),
        excluded_screenings=frozenset({S2}),
        preferences=Preferences(
            buffer_minutes=10,
            year_weights={2025: 0.2},
            comparisons=(Comparison(preferred=E, other=ProgrammeEntryId("x")),),
        ),
    )
    with stored as uow:
        assert uow.planning.inputs(U, F) == PlanningInputs()
        uow.planning.save_inputs(U, F, inputs)
        uow.commit()
    with stored as uow:
        assert uow.planning.inputs(U, F) == inputs
        uow.planning.save_inputs(U, F, PlanningInputs())
        uow.commit()
    with stored as uow:
        assert uow.planning.inputs(U, F) == PlanningInputs()


def test_schedules_and_the_active_one(stored):
    with stored as uow:
        assert uow.planning.active_schedule(U, F) is None
        uow.planning.save_schedule(schedule("one", 1))
        uow.planning.save_schedule(schedule("two", 2))
        uow.commit()
    with stored as uow:
        assert uow.planning.active_schedule(U, F) == schedule("two", 2)
        assert [s.id for s in uow.planning.schedules(U, F)] == ["one", "two"]
        assert uow.planning.active_schedules(U) == (schedule("two", 2),)


def test_drafts_round_trip_and_are_deleted(stored):
    draft = Draft(
        id=D,
        user_id=U,
        festival_id=F,
        change_set=ChangeSet(items=(AddScreeningCommitment(screening_id=S1),)),
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
                ScheduledScreening(screening_id=S1, arrival_time=T0, weight=1.0),
            ),
            "solved_at": T0,
        }
    )
    with stored as uow:
        uow.planning.save_draft(draft)
        uow.commit()
    with stored as uow:
        assert uow.planning.draft(D) == draft
        assert uow.planning.solving_drafts() == (draft,)
        uow.planning.save_draft(solved)
        uow.commit()
    with stored as uow:
        assert uow.planning.draft(D) == solved
        assert uow.planning.drafts(U, F) == (solved,)
        assert uow.planning.solving_drafts() == ()
        uow.planning.delete_draft(D)
        uow.commit()
    with stored as uow:
        assert uow.planning.draft(D) is None


def test_tickets_and_seen(stored):
    with stored as uow:
        uow.tickets.save(U, Ticket(screening_id=S1, exchangeable=True))
        uow.tickets.save(U, Ticket(screening_id=S1, refundable=True))
        uow.seen.mark(U, FILM)
        uow.seen.mark(U, FILM)
        uow.seen.dismiss(U, S2)
        uow.commit()
    with stored as uow:
        assert uow.tickets.tickets(U) == (Ticket(screening_id=S1, refundable=True),)
        assert uow.seen.films(U) == frozenset({FILM})
        assert uow.seen.dismissals(U) == frozenset({S2})
        uow.tickets.delete(U, S1)
        uow.seen.unmark(U, FILM)
        uow.seen.restore(U, S2)
        uow.commit()
    with stored as uow:
        assert uow.tickets.tickets(U) == ()
        assert uow.seen.films(U) == frozenset()
        assert uow.seen.dismissals(U) == frozenset()


def test_lookups_by_id(stored):
    with stored as uow:
        festival = uow.festivals.by_id(F)
        assert festival is not None and festival.slug == "f"
        assert uow.festivals.by_id(FestivalId("nope")) is None
        film = uow.films.by_id(FILM)
        assert film is not None and film.title == "Film"
        assert [
            s.id for s in uow.programme.screenings_by_id([S2, ScreeningId("nope"), S1])
        ] == ["s1", "s2"]
        assert [
            e.id for e in uow.programme.entries_by_id([E, ProgrammeEntryId("nope")])
        ] == ["e"]


def test_a_schedule_by_id(stored):
    with stored as uow:
        uow.planning.save_schedule(schedule("one", 1))
        uow.commit()
    with stored as uow:
        assert uow.planning.schedule(ScheduleId("one")) == schedule("one", 1)
        assert uow.planning.schedule(ScheduleId("nope")) is None


def test_a_schedule_number_taken_by_another_unit_of_work_conflicts(stored):
    with stored as uow:
        uow.planning.save_schedule(schedule("first", 1))
        uow.commit()
    with stored as uow, pytest.raises(ConflictError):
        uow.planning.save_schedule(schedule("second", 1))


def test_an_identity_taken_by_another_unit_of_work_conflicts(stored):
    with stored as uow, pytest.raises(ConflictError):
        uow.users.save(User(id=UserId("other"), issuer="local", subject="thor"))
