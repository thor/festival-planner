"""OR-Tools based schedule optimizer for film festivals."""

from datetime import timedelta
from typing import Optional
from ortools.sat.python import cp_model

from .models import Film, ScheduledFilm, ScheduleConfig


class FestivalScheduleSolver:
    """Solves the festival scheduling optimization problem using OR-Tools CP-SAT."""

    def __init__(
        self,
        films: list[Film],
        travel_time_matrix: dict[tuple[str, str], int],
        config: ScheduleConfig,
    ):
        """Initialize the solver.

        Args:
            films: List of films to schedule
            travel_time_matrix: Dictionary mapping (from_cinema, to_cinema) to travel time in minutes
            config: Schedule configuration with buffer time and date filters
        """
        self.films = films
        self.travel_time_matrix = travel_time_matrix
        self.config = config
        self.model = cp_model.CpModel()
        self.attend_vars = {}
        self.solver = cp_model.CpSolver()

    def solve(self, time_limit_seconds: Optional[int] = 60) -> list[ScheduledFilm]:
        """Solve the scheduling optimization problem.

        Args:
            time_limit_seconds: Maximum time to spend solving (default: 60 seconds)

        Returns:
            List of ScheduledFilm objects representing the optimal schedule
        """
        if not self.films:
            return []

        # Filter films by date range if specified
        filtered_films = self._filter_films_by_date()

        if not filtered_films:
            return []

        # Build the optimization model
        self._build_model(filtered_films)

        # Configure solver
        self.solver.parameters.max_time_in_seconds = time_limit_seconds

        # Solve
        status = self.solver.Solve(self.model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._extract_schedule(filtered_films)
        else:
            print(f"No solution found. Status: {status}")
            return []

    def _filter_films_by_date(self) -> list[Film]:
        """Filter films based on date range in config.

        Returns:
            List of films within the specified date range
        """
        if not self.config.start_date and not self.config.end_date:
            return self.films

        filtered = []
        for film in self.films:
            film_date = film.date

            if self.config.start_date and film_date < self.config.start_date:
                continue
            if self.config.end_date and film_date > self.config.end_date:
                continue

            filtered.append(film)

        return filtered

    def _build_model(self, films: list[Film]) -> None:
        """Build the CP-SAT optimization model.

        Args:
            films: List of films to include in the model
        """
        # Create decision variables: attend[i] = 1 if we attend film i, 0 otherwise
        for i, film in enumerate(films):
            self.attend_vars[i] = self.model.NewBoolVar(f"attend_film_{i}")

        # Add constraints for overlapping films
        for i, film_i in enumerate(films):
            for j, film_j in enumerate(films):
                if i >= j:  # Only consider each pair once
                    continue

                # Check if films conflict (considering buffer and travel time)
                if self._films_conflict(film_i, film_j):
                    # Constraint: cannot attend both films if they conflict
                    self.model.Add(self.attend_vars[i] + self.attend_vars[j] <= 1)

        # Objective: maximize total value of attended films
        # Value = 1.0 (base weight) + preference_weight + dynamic adjustments
        objective_terms = []
        for i, film in enumerate(films):
            # Calculate dynamic weight adjustments
            dynamic_weight = self._calculate_film_weight(film)

            # Scale to integer (OR-Tools works with integers)
            # Multiply by 1000 to preserve precision
            weight = int(dynamic_weight * 1000)
            objective_terms.append(self.attend_vars[i] * weight)

        self.model.Maximize(sum(objective_terms))

    def _calculate_film_weight(self, film: Film) -> float:
        """Calculate the total weight for a film including dynamic adjustments.

        Args:
            film: Film to calculate weight for

        Returns:
            Total weight (base + preference + year adjustment + special notes adjustment)
        """
        # Start with base weight and preference weight
        weight = 1.0 + film.preference_weight

        # Add year-based weight adjustment
        if film.year and film.year in self.config.year_weights:
            year_adjustment = self.config.year_weights[film.year]
            weight += year_adjustment

        # Add special notes weight adjustment
        if film.special_notes:
            weight += self.config.special_notes_weight

        return weight

    def _films_conflict(self, film1: Film, film2: Film) -> bool:
        """Check if two films conflict (overlap with buffer and travel time).

        Args:
            film1: First film
            film2: Second film

        Returns:
            True if films conflict, False otherwise
        """
        # Films on different days never conflict
        if film1.date != film2.date:
            return False

        # Get travel time between cinemas
        travel_time = self._get_travel_time(film1.cinema, film2.cinema)

        # Calculate required time between films (buffer + travel)
        required_gap_minutes = self.config.buffer_time_minutes + travel_time

        # Check if film1 ends in time to attend film2
        gap1_to_2 = (film2.start_time - film1.end_time).total_seconds() / 60
        can_do_1_then_2 = gap1_to_2 >= required_gap_minutes

        # Check if film2 ends in time to attend film1
        gap2_to_1 = (film1.start_time - film2.end_time).total_seconds() / 60
        can_do_2_then_1 = gap2_to_1 >= required_gap_minutes

        # Films conflict if neither order works
        return not (can_do_1_then_2 or can_do_2_then_1)

    def _get_travel_time(self, from_cinema: str, to_cinema: str) -> int:
        """Get travel time between two cinemas.

        Args:
            from_cinema: Origin cinema
            to_cinema: Destination cinema

        Returns:
            Travel time in minutes (0 if not specified or same cinema)
        """
        if from_cinema == to_cinema:
            return 0

        # Check both directions (use symmetric travel time if only one is defined)
        if (from_cinema, to_cinema) in self.travel_time_matrix:
            return self.travel_time_matrix[(from_cinema, to_cinema)]
        elif (to_cinema, from_cinema) in self.travel_time_matrix:
            return self.travel_time_matrix[(to_cinema, from_cinema)]
        else:
            # If no travel time is specified, assume a default (30 minutes)
            return 30

    def _extract_schedule(self, films: list[Film]) -> list[ScheduledFilm]:
        """Extract the schedule from the solved model.

        Args:
            films: List of films that were included in the model

        Returns:
            List of ScheduledFilm objects for attended films, sorted by start time
        """
        scheduled_films = []

        for i, film in enumerate(films):
            if self.solver.Value(self.attend_vars[i]) == 1:
                # Calculate arrival time (start time - buffer)
                arrival_time = film.start_time - timedelta(
                    minutes=self.config.buffer_time_minutes
                )

                scheduled_films.append(
                    ScheduledFilm(
                        film=film,
                        arrival_time=arrival_time,
                    )
                )

        # Sort by start time
        scheduled_films.sort(key=lambda sf: sf.film.start_time)

        return scheduled_films

    def get_solution_stats(self) -> dict:
        """Get statistics about the solution.

        Returns:
            Dictionary with solver statistics
        """
        return {
            "status": self.solver.StatusName(),
            "objective_value": self.solver.ObjectiveValue() / 1000.0
            if self.solver.ObjectiveValue()
            else 0,
            "wall_time": self.solver.WallTime(),
            "branches": self.solver.NumBranches(),
            "conflicts": self.solver.NumConflicts(),
        }
