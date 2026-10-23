# pyright: reportUnnecessaryTypeIgnoreComment=true
"""Ids of different kinds must not mix. Pyright, not pytest, enforces this:
if the ids were plain `str` aliases, the ignores below would be unnecessary
and pyright would fail."""

from festival_planner.domain.drafts import DraftId
from festival_planner.domain.programme import ProgrammeEntryId, Screening, ScreeningId
from festival_planner.domain.users import UserId


def _takes_screening(screening_id: ScreeningId) -> ScreeningId:
    return screening_id


def test_a_programme_entry_id_is_not_a_screening_id() -> None:
    _takes_screening(ProgrammeEntryId("e"))  # pyright: ignore[reportArgumentType]


def test_a_user_id_is_not_a_draft_id() -> None:
    draft_id: DraftId = UserId("u")  # pyright: ignore[reportAssignmentType]
    assert draft_id == "u"


def test_ids_are_plain_strings_at_runtime() -> None:
    s = Screening.model_validate_json(
        '{"id": "s", "programme_entry_id": "e", "venue_id": "v",'
        ' "start_time": "2030-01-01T10:00:00Z", "end_time": "2030-01-01T12:00:00Z"}'
    )
    assert type(s.id) is str and s.id == "s"
