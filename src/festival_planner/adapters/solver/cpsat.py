"""ScheduleSolver adapter using Google OR-Tools CP-SAT."""

import datetime
import logging

from ortools.sat.python import cp_model

from ...domain.solving import (
    ScheduledScreening,
    SolveRequest,
    SolveResult,
    SolveStatus,
    formulate,
)

logger = logging.getLogger(__name__)

WEIGHT_PRECISION_MULTIPLIER = 1000
"""CP-SAT needs integer coefficients; weights are scaled by this."""

_STATUSES = {
    cp_model.OPTIMAL: SolveStatus.OPTIMAL,
    cp_model.FEASIBLE: SolveStatus.FEASIBLE,
    cp_model.INFEASIBLE: SolveStatus.INFEASIBLE,
    cp_model.UNKNOWN: SolveStatus.UNKNOWN,
}


RANDOM_SEED = 0
NUM_WORKERS = 8


def _solver(time_limit_seconds: float) -> cp_model.CpSolver:
    """A CP-SAT solver whose result depends only on the model.

    The limit is deterministic time, with no wall-clock backstop."""
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = RANDOM_SEED
    solver.parameters.num_workers = NUM_WORKERS
    solver.parameters.interleave_search = True
    solver.parameters.max_deterministic_time = time_limit_seconds
    return solver


class CpSatScheduleSolver:
    """Optimises a `Formulation` as a CP-SAT boolean model."""

    def solve(self, request: SolveRequest) -> SolveResult:
        formulation = formulate(request)
        if formulation.unsatisfiable:
            return SolveResult(
                status=SolveStatus.INFEASIBLE, reasons=formulation.unsatisfiable
            )
        if not formulation.candidates:
            return SolveResult(status=SolveStatus.OPTIMAL)

        model = cp_model.CpModel()
        attend = {
            s.id: model.new_bool_var(f"attend[{s.id}]") for s in formulation.candidates
        }
        for screening_id in formulation.required:
            model.add(attend[screening_id] == 1)
        for group in formulation.exactly_one:
            model.add_exactly_one(attend[i] for i in group)
        for group in formulation.at_most_one:
            model.add_at_most_one(attend[i] for i in group)
        for a, b in formulation.conflicts:
            model.add_at_most_one(attend[a], attend[b])
        ids = sorted(formulation.weights)
        objective = cp_model.LinearExpr.weighted_sum(
            [attend[i] for i in ids],
            [round(formulation.weights[i] * WEIGHT_PRECISION_MULTIPLIER) for i in ids],
        )
        model.maximize(objective)

        solver = _solver(request.time_limit_seconds)
        status = _STATUSES.get(solver.solve(model))
        if status is None:
            raise RuntimeError(f"CP-SAT failed: {solver.status_name()}")
        if status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
            return SolveResult(status=status, wall_time_seconds=solver.wall_time)
        wall_time = solver.wall_time

        # Among Schedules at least as good, prefer Active Screenings (each
        # outweighs everything else), then fewer extra Screenings (each costs),
        # then lower Screening ids (cheaper, or worth more if Active); this
        # never lowers the score.
        model.add(objective >= round(solver.objective_value))
        for i in ids:
            model.add_hint(attend[i], solver.boolean_value(attend[i]))
        n = len(ids)
        model.maximize(
            cp_model.LinearExpr.weighted_sum(
                [attend[i] for i in ids],
                [
                    n * n + (n - rank) if i in request.active_schedule else -(rank + 1)
                    for rank, i in enumerate(ids)
                ],
            )
        )
        tie_break = _solver(request.time_limit_seconds)
        if _STATUSES.get(tie_break.solve(model)) in (
            SolveStatus.OPTIMAL,
            SolveStatus.FEASIBLE,
        ):
            solver, wall_time = tie_break, wall_time + tie_break.wall_time
        else:
            logger.warning(
                "CP-SAT tie-break failed (%s); using the first solution",
                tie_break.status_name(),
            )

        preferences = request.preferences
        chosen = [
            s for s in formulation.candidates if solver.boolean_value(attend[s.id])
        ]
        scheduled = tuple(
            ScheduledScreening(
                screening_id=s.id,
                arrival_time=s.starts_at(include_events=preferences.attend_events)
                - datetime.timedelta(minutes=preferences.buffer_for(s.venue_id)),
                weight=formulation.weights[s.id],
            )
            for s in sorted(chosen, key=lambda s: (s.start_time, s.id))
        )
        return SolveResult(
            status=status,
            scheduled=scheduled,
            objective=round(sum(formulation.weights[s.id] for s in chosen), 6),
            wall_time_seconds=wall_time,
        )
