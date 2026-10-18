"""Single-state searches: Hill Climbing and Simulated Annealing.

Both draw neighbours from the same operator set, so the only thing that differs is
the acceptance rule - which is exactly the comparison the project is about.
"""
from __future__ import annotations

import math
import time

from .base import Optimizer, OptimizationResult


class HillClimbing(Optimizer):
    """Accepts only equal-or-better neighbours, and can restart when it stagnates."""

    name = "hill_climbing"

    def run(self) -> OptimizationResult:
        started = time.perf_counter()
        width = max(1, int(self.params.get("neighborhood_size", 1)))
        patience = max(1, int(self.params.get("patience", 40)))
        allow_restart = bool(int(self.params.get("restarts", 1)))

        current = self.initial_candidate()
        current_score = self.score(current)
        best, best_score = [a.copy() for a in current], current_score

        iteration = stagnation = accepted = rejected = plateaus = restarts = 0
        while not self.budget_exhausted():
            # width == 1 is first-improvement; width > 1 is best-improvement over a sample.
            chosen = None
            for _ in range(min(width, self.budget_left)):
                neighbour = self.neighbor(current)
                neighbour_score = self.score(neighbour)
                if chosen is None or neighbour_score.total_cost < chosen[1].total_cost:
                    chosen = (neighbour, neighbour_score)
            if chosen is None:
                break

            candidate, candidate_score = chosen
            delta = candidate_score.total_cost - current_score.total_cost
            if delta <= 0:
                current, current_score = candidate, candidate_score
                accepted += 1
                if delta == 0:
                    plateaus += 1
                    stagnation += 1
                else:
                    stagnation = 0
            else:
                rejected += 1
                stagnation += 1

            if current_score.total_cost < best_score.total_cost:
                best, best_score = [a.copy() for a in current], current_score

            trapped = stagnation >= patience
            event = ("Improved the current timetable" if delta < 0
                     else "Moved sideways across a plateau" if delta == 0
                     else "Rejected a worse neighbour")
            if trapped and allow_restart and not self.budget_exhausted():
                current = self.problem.random_candidate(self.rng)
                current_score = self.score(current)
                restarts += 1
                stagnation = 0
                event = "Stuck in a local optimum - restarted from a fresh timetable"

            self.record(iteration, best_score, best,
                        event=event,
                        current_cost=current_score.total_cost,
                        neighbor_cost=candidate_score.total_cost,
                        accepted_moves=accepted,
                        rejected_moves=rejected,
                        plateaus=plateaus,
                        restarts=restarts,
                        local_optimum_detected=trapped)
            iteration += 1

        self.record(iteration, best_score, best, force=True, event="Search budget spent",
                    accepted_moves=accepted, rejected_moves=rejected, plateaus=plateaus,
                    restarts=restarts, local_optimum_detected=stagnation >= patience)
        return self.finish(best, best_score, started)


class SimulatedAnnealing(Optimizer):
    """Accepts worse neighbours with probability exp(-delta / temperature)."""

    name = "simulated_annealing"

    def run(self) -> OptimizationResult:
        started = time.perf_counter()
        temperature = float(self.params.get("initial_temperature", 1000))
        cooling = float(self.params.get("cooling_rate", 0.95))
        floor = float(self.params.get("minimum_temperature", 0.0001))

        current = self.initial_candidate()
        current_score = self.score(current)
        best, best_score = [a.copy() for a in current], current_score

        iteration = accepted = accepted_worse = escaped = rejected = 0
        while not self.budget_exhausted():
            candidate = self.neighbor(current)
            candidate_score = self.score(candidate)
            delta = candidate_score.total_cost - current_score.total_cost

            probability = 1.0 if delta <= 0 else math.exp(-delta / max(temperature, floor))
            accept = delta <= 0 or self.rng.random() < probability
            if accept:
                was_worse = delta > 0
                current, current_score = candidate, candidate_score
                accepted += 1
                accepted_worse += int(was_worse)
                escaped += int(was_worse and current_score.total_cost > best_score.total_cost)
            else:
                rejected += 1

            if current_score.total_cost < best_score.total_cost:
                best, best_score = [a.copy() for a in current], current_score

            event = ("Accepted a worse timetable to escape a local optimum" if accept and delta > 0
                     else "Improved the current timetable" if accept
                     else "Rejected a worse neighbour")
            self.record(iteration, best_score, best,
                        event=event,
                        temperature=round(temperature, 4),
                        acceptance_probability=round(probability, 4),
                        accepted_worse_moves=accepted_worse,
                        escaped_local_optima=escaped,
                        accepted_moves=accepted,
                        rejected_moves=rejected,
                        current_cost=current_score.total_cost,
                        neighbor_cost=candidate_score.total_cost)
            temperature = max(floor, temperature * cooling)
            iteration += 1

        self.record(iteration, best_score, best, force=True, event="Cooling schedule complete",
                    temperature=round(temperature, 4), accepted_worse_moves=accepted_worse,
                    escaped_local_optima=escaped, accepted_moves=accepted, rejected_moves=rejected)
        return self.finish(best, best_score, started)
