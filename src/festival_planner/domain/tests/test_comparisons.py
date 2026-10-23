import pytest

from festival_planner.domain.comparisons import comparison_bonuses
from festival_planner.domain.planning import Comparison
from festival_planner.domain.programme import ProgrammeEntryId

A, B, C = ProgrammeEntryId("a"), ProgrammeEntryId("b"), ProgrammeEntryId("c")


def over(a: str, b: str) -> Comparison:
    return Comparison(preferred=ProgrammeEntryId(a), other=ProgrammeEntryId(b))


def test_no_comparisons_no_bonuses():
    assert comparison_bonuses((), 0.5) == {}


def test_the_preferred_entry_gains_what_the_other_loses():
    bonuses = comparison_bonuses([over("a", "b")], 0.5)
    assert bonuses[A] > 0 > bonuses[B]
    assert bonuses[A] == pytest.approx(-bonuses[B])


def test_a_chain_orders_the_bonuses():
    bonuses = comparison_bonuses([over("a", "b"), over("b", "c")], 1.0)
    assert bonuses[A] > bonuses[B] > bonuses[C]


def test_a_cycle_cancels_out():
    bonuses = comparison_bonuses([over("a", "b"), over("b", "c"), over("c", "a")], 1.0)
    assert bonuses == pytest.approx({A: 0.0, B: 0.0, C: 0.0})


def test_bonuses_scale_with_the_comparison_weight():
    assert comparison_bonuses([over("a", "b")], 0.0) == {A: 0.0, B: 0.0}
    one = comparison_bonuses([over("a", "b")], 1.0)
    two = comparison_bonuses([over("a", "b")], 2.0)
    assert two[A] == pytest.approx(2 * one[A])


def test_bonuses_do_not_depend_on_input_order():
    comparisons = [over("a", "b"), over("c", "b"), over("a", "c")]
    assert comparison_bonuses(comparisons, 1.0) == comparison_bonuses(
        reversed(comparisons), 1.0
    )
