"""Genetic Algorithm with real crossover and cached fitness.

Two properties matter here. Crossover is genuinely applied - a chromosome's genes come
from two parents - and every individual carries its own Score, so tournament selection
costs zero extra evaluations. Re-evaluating during selection would both waste the
budget and misreport it.
"""
from __future__ import annotations

import time

from .base import Optimizer, OptimizationResult
from .evaluator import Score
from .neighborhood import uniform_crossover
from .representation import Candidate

Individual = tuple[Candidate, Score]


class GeneticAlgorithm(Optimizer):
    name = "genetic_algorithm"

    def _uniform_crossover(self, left: Candidate, right: Candidate) -> Candidate:
        return uniform_crossover(left, right, self.rng)

    def _one_point_crossover(self, left: Candidate, right: Candidate) -> Candidate:
        if len(left) < 2:
            return [a.copy() for a in left]
        cut = self.rng.randrange(1, len(left))
        return [a.copy() for a in left[:cut]] + [b.copy() for b in right[cut:]]

    def _tournament(self, population: list[Individual], size: int) -> Candidate:
        """Selection reads cached fitness only - it must not call the evaluator."""
        contenders = self.rng.sample(population, min(size, len(population)))
        return min(contenders, key=lambda individual: individual[1].total_cost)[0]

    def run(self) -> OptimizationResult:
        started = time.perf_counter()
        size = max(2, int(self.params.get("population_size", 30)))
        mutation_rate = float(self.params.get("mutation_rate", 0.12))
        crossover_rate = float(self.params.get("crossover_rate", 0.8))
        elite_count = max(1, min(int(self.params.get("elite_count", 2)), size - 1))
        tournament_size = max(2, int(self.params.get("tournament_size", 3)))
        style = str(self.params.get("crossover", "uniform"))
        crossover = self._one_point_crossover if style == "one_point" else self._uniform_crossover

        seed_candidate = self.initial_candidate()
        population: list[Individual] = [(seed_candidate, self.score(seed_candidate))]
        while len(population) < size and not self.budget_exhausted():
            candidate = self.problem.random_candidate(self.rng)
            population.append((candidate, self.score(candidate)))

        population.sort(key=lambda individual: individual[1].total_cost)
        best: Individual = ([a.copy() for a in population[0][0]], population[0][1])

        generation = 0
        while not self.budget_exhausted():
            elites = [([a.copy() for a in c], s) for c, s in population[:elite_count]]
            offspring: list[Individual] = []
            while len(elites) + len(offspring) < size and not self.budget_exhausted():
                parent = self._tournament(population, tournament_size)
                if self.rng.random() < crossover_rate:
                    partner = self._tournament(population, tournament_size)
                    child = crossover(parent, partner)
                else:
                    child = [a.copy() for a in parent]
                if self.rng.random() < mutation_rate:
                    child = self.mutate(child)
                offspring.append((child, self.score(child)))

            population = sorted(elites + offspring,
                                key=lambda individual: individual[1].total_cost)
            if population[0][1].total_cost < best[1].total_cost:
                best = ([a.copy() for a in population[0][0]], population[0][1])

            generation += 1
            average = sum(s.total_cost for _, s in population) / len(population)
            diversity = len({self.problem.fingerprint(c) for c, _ in population})
            self.record(generation, best[1], best[0], average=average, force=True,
                        event="Population bred through selection, crossover and mutation",
                        generation=generation,
                        population_size=len(population),
                        population_diversity=diversity,
                        mutation_rate=mutation_rate,
                        crossover_rate=crossover_rate,
                        elite_count=elite_count,
                        best_individual_fitness=best[1].normalized_fitness)

        return self.finish(best[0], best[1], started)
