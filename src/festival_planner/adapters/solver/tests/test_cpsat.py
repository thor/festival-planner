from festival_planner.adapters.solver.cpsat import CpSatScheduleSolver
from festival_planner.domain.planning import Preferences
from festival_planner.domain.programme import Event
from festival_planner.domain.solving import ScheduleSolver, SolveStatus
from festival_planner.domain.tests.builders import at, request, screening

solver: ScheduleSolver = CpSatScheduleSolver()


def scheduled_ids(result) -> list[str]:
    return [s.screening_id for s in result.scheduled]


def test_empty_request_gives_empty_schedule():
    result = solver.solve(request())
    assert result.status == SolveStatus.OPTIMAL
    assert result.scheduled == ()


def test_schedules_everything_that_fits_in_start_order():
    result = solver.solve(
        request(screening("b", "18:00", "20:00"), screening("a", "14:00", "16:00"))
    )
    assert result.is_solved
    assert scheduled_ids(result) == ["a", "b"]


def test_prefers_higher_weight_among_conflicting_screenings():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            preferences=Preferences(
                buffer_minutes=0, programme_entry_weights={"b": 2.0}
            ),
        )
    )
    assert scheduled_ids(result) == ["b"]
    assert result.objective == 2.0


def test_screening_commitment_wins_over_higher_weight():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            preferences=Preferences(
                buffer_minutes=0, programme_entry_weights={"b": 2.0}
            ),
            screening_commitments=frozenset({"a"}),
        )
    )
    assert scheduled_ids(result) == ["a"]


def test_conflicting_commitments_are_infeasible():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening("b", "15:00", "17:00"),
            screening_commitments=frozenset({"a", "b"}),
        )
    )
    assert result.status == SolveStatus.INFEASIBLE


def test_unsatisfiable_formulation_reports_reasons():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            screening_commitments=frozenset({"a"}),
            now=at("15:00"),
        )
    )
    assert result.status == SolveStatus.INFEASIBLE
    assert result.reasons


def test_negative_weight_screenings_are_left_out():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00"),
            preferences=Preferences(
                buffer_minutes=0, programme_entry_weights={"a": -1.0}
            ),
        )
    )
    assert result.scheduled == ()


def test_arrival_time_uses_venue_buffer():
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00", venue="A"),
            preferences=Preferences(buffer_minutes=15, venue_buffer_minutes={"A": 25}),
        )
    )
    assert result.scheduled[0].arrival_time == at("13:35")


def test_arrival_time_uses_earlier_event_when_attending_events():
    ceremony = Event("Ceremony", at("13:30"), at("13:55"))
    result = solver.solve(
        request(
            screening("a", "14:00", "16:00", events=(ceremony,)),
            preferences=Preferences(buffer_minutes=15, attend_events=True),
        )
    )
    assert result.scheduled[0].arrival_time == at("13:15")
