"""NSGA-II: multi-objective search over the timetable objectives.

The other strategies minimise one weighted sum, which forces a choice of priorities
before the search begins. This one keeps the objectives separate and returns a set of
schedules that no other schedule beats on every count - the trade-off is handed back to
the user rather than decided for them.

Selection ranks by non-domination front first and crowding distance second, so the
population converges toward the front while staying spread along it.
"""
from __future__ import annotations

import time

from .base import Optimizer, OptimizationResult
from .evaluator import Score
from .neighborhood import uniform_crossover
from .pareto import OBJECTIVE_KEYS, crowding_distance, non_dominated_sort, vector
from .representation import Candidate

Individual = tuple[Candidate, Score]


class NSGA2(Optimizer):
    name = "nsga2"

    def _tournament(self, population: list[Individual], ranks: dict[int, int],
                    crowding: dict[int, float]) -> Candidate:
        """Binary tournament on (front, then crowding) - the NSGA-II crowded comparison."""
        left, right = self.rng.randrange(len(population)), self.rng.randrange(len(population))
        if ranks[left] != ranks[right]:
            winner = left if ranks[left] < ranks[right] else right
        else:
            winner = left if crowding.get(left, 0) >= crowding.get(right, 0) else right
        return population[winner][0]

    def _rank(self, population: list[Individual]):
        vectors = [vector(score.objectives) for _, score in population]
        # Constrained domination: without it hard violations carry only a quarter of the
        # selection pressure and the search never reaches a feasible timetable.
        violations = [score.hard_violations for _, score in population]
        fronts = non_dominated_sort(vectors, violations)
        ranks = {index: position for position, front in enumerate(fronts) for index in front}
        crowding: dict[int, float] = {}
        for front in fronts:
            crowding.update(crowding_distance(vectors, front))
        return vectors, fronts, ranks, crowding

    def run(self) -> OptimizationResult:
        started = time.perf_counter()
        size = max(4, int(self.params.get("population_size", 40)))
        mutation_rate = float(self.params.get("mutation_rate", 0.2))
        crossover_rate = float(self.params.get("crossover_rate", 0.9))

        seed_candidate = self.initial_candidate()
        population: list[Individual] = [(seed_candidate, self.score(seed_candidate))]
        while len(population) < size and not self.budget_exhausted():
            candidate = self.problem.random_candidate(self.rng)
            population.append((candidate, self.score(candidate)))

        best: Individual = min(population, key=lambda ind: ind[1].total_cost)
        generation = 0

        while not self.budget_exhausted():
            _, _, ranks, crowding = self._rank(population)

            offspring: list[Individual] = []
            while len(offspring) < size and not self.budget_exhausted():
                parent = self._tournament(population, ranks, crowding)
                if self.rng.random() < crossover_rate:
                    partner = self._tournament(population, ranks, crowding)
                    child = uniform_crossover(parent, partner, self.rng)
                else:
                    child = [a.copy() for a in parent]
                if self.rng.random() < mutation_rate:
                    child = self.mutate(child)
                offspring.append((child, self.score(child)))

            # Environmental selection over parents and children together, so a good
            # parent is never lost to a worse child.
            combined = population + offspring
            vectors, fronts, _, _ = self._rank(combined)
            chosen: list[int] = []
            for front in fronts:
                if len(chosen) + len(front) <= size:
                    chosen.extend(front)
                    continue
                spread = crowding_distance(vectors, front)
                ordered = sorted(front, key=lambda i: -spread[i])
                chosen.extend(ordered[: size - len(chosen)])
                break
            population = [combined[index] for index in chosen]

            cheapest = min(population, key=lambda ind: ind[1].total_cost)
            if cheapest[1].total_cost < best[1].total_cost:
                best = ([a.copy() for a in cheapest[0]], cheapest[1])

            generation += 1
            _, fronts, _, _ = self._rank(population)
            self.record(generation, best[1], best[0],
                        average=sum(s.total_cost for _, s in population) / len(population),
                        force=True,
                        event="Population sorted by non-domination and crowding",
                        generation=generation,
                        population_size=len(population),
                        front_size=len(fronts[0]) if fronts else 0,
                        fronts=len(fronts),
                        mutation_rate=mutation_rate,
                        crossover_rate=crossover_rate)

        return self.finish(best[0], best[1], started,
                           pareto_front=self._front_payload(population))

    def _front_payload(self, population: list[Individual]) -> list[dict]:
        """The non-dominated set, each with its objectives and its timetable.

        Restricted to feasible members whenever any exist. Mathematically a schedule
        with two clashes but perfect room balance is non-dominated, but the project
        treats hard constraints as dominant, and offering an unusable timetable as a
        "trade-off" would contradict that. When nothing feasible was found the whole
        front is returned, because an infeasible answer still beats no answer.
        """
        _, fronts, _, _ = self._rank(population)
        if not fronts:
            return []
        members = [population[index] for index in fronts[0]]
        feasible = [m for m in members if m[1].hard_violations == 0]
        if feasible:
            members = feasible
        seen: set[tuple] = set()
        payload = []
        for candidate, score in members:
            key = vector(score.objectives)
            if key in seen:
                continue  # identical trade-offs add nothing to choose between
            seen.add(key)
            payload.append({
                "objectives": {name: score.objectives.get(name, 0.0) for name in OBJECTIVE_KEYS},
                "total_cost": score.total_cost,
                "hard_violations": score.hard_violations,
                "schedule": self.problem.to_schedule(candidate),
            })
        payload.sort(key=lambda row: row["total_cost"])
        return payload
