import pytest

from festival_planner.domain.comparisons import comparison_bonuses
from festival_planner.domain.planning import Comparison


def over(a: str, b: str) -> Comparison:
    return Comparison(preferred=a, other=b)


def test_no_comparisons_no_bonuses():
    assert comparison_bonuses((), 0.5) == {}


def test_the_preferred_entry_gains_what_the_other_loses():
    bonuses = comparison_bonuses([over("a", "b")], 0.5)
    assert bonuses["a"] > 0 > bonuses["b"]
    assert bonuses["a"] == pytest.approx(-bonuses["b"])


def test_a_chain_orders_the_bonuses():
    bonuses = comparison_bonuses([over("a", "b"), over("b", "c")], 1.0)
    assert bonuses["a"] > bonuses["b"] > bonuses["c"]


def test_a_cycle_cancels_out():
    bonuses = comparison_bonuses([over("a", "b"), over("b", "c"), over("c", "a")], 1.0)
    assert bonuses == pytest.approx({"a": 0.0, "b": 0.0, "c": 0.0})


def test_bonuses_scale_with_the_comparison_weight():
    assert comparison_bonuses([over("a", "b")], 0.0) == {"a": 0.0, "b": 0.0}
    one = comparison_bonuses([over("a", "b")], 1.0)
    two = comparison_bonuses([over("a", "b")], 2.0)
    assert two["a"] == pytest.approx(2 * one["a"])


def test_bonuses_do_not_depend_on_input_order():
    comparisons = [over("a", "b"), over("c", "b"), over("a", "c")]
    assert comparison_bonuses(comparisons, 1.0) == comparison_bonuses(
        reversed(comparisons), 1.0
    )
