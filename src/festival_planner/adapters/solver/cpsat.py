"""ScheduleSolver adapter using Google OR-Tools CP-SAT."""

import datetime

from ortools.sat.python import cp_model

from ...domain.solving import (
    ScheduledScreening,
    SolveRequest,
    SolveResult,
    SolveStatus,
    formulate,
)

WEIGHT_PRECISION_MULTIPLIER = 1000
"""CP-SAT needs integer coefficients; weights are scaled by this."""

_STATUSES = {
    cp_model.OPTIMAL: SolveStatus.OPTIMAL,
    cp_model.FEASIBLE: SolveStatus.FEASIBLE,
    cp_model.INFEASIBLE: SolveStatus.INFEASIBLE,
    cp_model.UNKNOWN: SolveStatus.UNKNOWN,
}


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
        ids = list(formulation.weights)
        model.maximize(
            cp_model.LinearExpr.weighted_sum(
                [attend[i] for i in ids],
                [
                    round(formulation.weights[i] * WEIGHT_PRECISION_MULTIPLIER)
                    for i in ids
                ],
            )
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = request.time_limit_seconds
        status = _STATUSES.get(solver.solve(model))
        if status is None:
            raise RuntimeError(f"CP-SAT failed: {solver.status_name()}")
        if status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
            return SolveResult(status=status, wall_time_seconds=solver.wall_time)

        preferences = request.preferences
        scheduled = tuple(
            ScheduledScreening(
                screening_id=s.id,
                arrival_time=s.start_time
                - datetime.timedelta(minutes=preferences.buffer_for(s.venue_id)),
                weight=formulation.weights[s.id],
            )
            for s in sorted(formulation.candidates, key=lambda s: s.start_time)
            if solver.boolean_value(attend[s.id])
        )
        return SolveResult(
            status=status,
            scheduled=scheduled,
            objective=solver.objective_value / WEIGHT_PRECISION_MULTIPLIER,
            wall_time_seconds=solver.wall_time,
        )
