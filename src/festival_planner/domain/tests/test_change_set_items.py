import datetime

import pytest
from pydantic import ValidationError

from festival_planner.domain.change_sets import (
    AddScreeningCommitment,
    ChangeSet,
    RecordComparison,
    SetBuffer,
    SetComparisonWeight,
    SetDateRange,
    SetYearWeight,
)


def test_change_sets_round_trip_through_json_by_kind():
    change_set = ChangeSet(
        items=(
            AddScreeningCommitment(screening_id="s"),
            SetYearWeight(year=2025, weight=0.2),
            SetBuffer(venue_id="v", minutes=5),
            RecordComparison(preferred="a", other="b"),
        )
    )
    dumped = change_set.model_dump_json()
    assert '"kind":"add_screening_commitment"' in dumped
    assert ChangeSet.model_validate_json(dumped) == change_set


def test_items_are_validated_from_plain_data():
    change_set = ChangeSet.model_validate(
        {"items": [{"kind": "add_film_commitment", "programme_entry_id": "e"}]}
    )
    assert change_set.items[0].kind == "add_film_commitment"


def test_unknown_kinds_are_rejected():
    with pytest.raises(ValidationError):
        ChangeSet.model_validate({"items": [{"kind": "teleport"}]})


def test_a_date_range_cannot_end_before_it_starts():
    with pytest.raises(ValidationError):
        SetDateRange(
            start_date=datetime.date(2025, 11, 9), end_date=datetime.date(2025, 11, 8)
        )


def test_negative_buffers_are_rejected():
    with pytest.raises(ValidationError):
        SetBuffer(minutes=-1)


def test_set_comparison_weight_requires_a_non_negative_weight_or_none():
    assert SetComparisonWeight(weight=None).weight is None
    assert SetComparisonWeight(weight=0.0).weight == 0.0
    with pytest.raises(ValidationError):
        SetComparisonWeight(weight=-1.0)
    with pytest.raises(ValidationError):
        SetComparisonWeight.model_validate({})
