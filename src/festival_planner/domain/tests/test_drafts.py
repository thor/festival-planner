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
from festival_planner.domain.programme import ScreeningId
from festival_planner.domain.solving import ScheduledScreening
from festival_planner.domain.users import UserId

NOW = datetime.datetime(2025, 11, 1, 12, tzinfo=datetime.UTC)


def schedule(id: str) -> Schedule:
    return Schedule(
        id=ScheduleId(id),
        user_id=UserId("u"),
        festival_id=FestivalId("f"),
        number=1,
        screening_ids=frozenset({ScreeningId("s1")}),
        score=1.0,
        change_set=ChangeSet(),
        accepted_at=NOW,
    )


def draft(base: str | None) -> Draft:
    return Draft(
        id=DraftId("d"),
        user_id=UserId("u"),
        festival_id=FestivalId("f"),
        change_set=ChangeSet(),
        base_schedule_id=ScheduleId(base) if base is not None else None,
        created_at=NOW,
    )


def test_a_new_draft_is_solving():
    assert draft(None).status is DraftStatus.SOLVING
    assert draft(None).attempt == 1


def test_a_draft_is_stale_once_its_base_is_no_longer_active():
    assert not draft(None).is_stale(None)
    assert draft(None).is_stale(schedule("s"))
    assert not draft("s").is_stale(schedule("s"))
    assert draft("s").is_stale(schedule("t"))


def test_a_draft_lists_its_scheduled_screening_ids():
    solved = draft(None).model_copy(
        update={
            "status": DraftStatus.READY,
            "scheduled": (
                ScheduledScreening(
                    screening_id=ScreeningId("s1"), arrival_time=NOW, weight=1.0
                ),
            ),
        }
    )
    assert solved.screening_ids == frozenset({ScreeningId("s1")})


def test_drafts_round_trip_through_json():
    assert Draft.model_validate_json(draft("s").model_dump_json()) == draft("s")
