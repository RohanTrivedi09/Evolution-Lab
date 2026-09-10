"""Optimization package: one representation, one evaluator, four search strategies."""
from __future__ import annotations

from typing import Callable

from ..models import Weights
from .base import HISTORY_POINTS, TRAJECTORY_POINTS, Optimizer, OptimizationResult
from .evaluator import HARD_CATEGORIES, SOFT_CATEGORIES, Score, evaluate
from .genetic import GeneticAlgorithm
from .local_search import HillClimbing, SimulatedAnnealing
from .neighborhood import OPERATORS, random_neighbor
from .representation import Assignment, Candidate, Problem, Session
from .swarm import ParticleSwarm

STRATEGIES: dict[str, type[Optimizer]] = {
    "hill_climbing": HillClimbing,
    "simulated_annealing": SimulatedAnnealing,
    "genetic_algorithm": GeneticAlgorithm,
    "particle_swarm": ParticleSwarm,
}

DEFAULT_BUDGET = 2000


def resolve_budget(algorithm: str, params: dict, explicit: int | None = None) -> int:
    """Decide how many fitness evaluations a run may spend.

    An explicit budget always wins - that is how comparisons stay fair. Otherwise the
    legacy iteration/generation parameters are translated into their evaluation cost so
    older requests keep behaving as before.
    """
    if explicit:
        return max(1, int(explicit))
    if "max_evaluations" in params:
        return max(1, int(params["max_evaluations"]))
    if algorithm == "genetic_algorithm" and "generations" in params:
        return max(1, int(params["generations"]) * int(params.get("population_size", 30)))
    if algorithm == "particle_swarm" and "iterations" in params:
        return max(1, int(params["iterations"]) * int(params.get("swarm_size", 20)))
    for legacy in ("iterations", "generations"):
        if legacy in params:
            return max(1, int(params[legacy]) + 1)
    return DEFAULT_BUDGET


def optimizer_for(name: str, problem: Problem, weights: Weights, seed: int, params: dict,
                  progress_callback: Callable | None = None, max_evaluations: int | None = None,
                  initial_schedule: dict | None = None) -> Optimizer:
    strategy = STRATEGIES.get(name)
    if strategy is None:
        raise ValueError(f"Unknown algorithm: {name}")
    return strategy(problem, weights, seed, params, progress_callback,
                    resolve_budget(name, params, max_evaluations), initial_schedule)


__all__ = [
    "Assignment", "Candidate", "DEFAULT_BUDGET", "GeneticAlgorithm", "HARD_CATEGORIES",
    "HISTORY_POINTS", "HillClimbing", "OPERATORS", "OptimizationResult", "Optimizer",
    "ParticleSwarm", "Problem", "SOFT_CATEGORIES", "STRATEGIES", "Score", "Session",
    "SimulatedAnnealing", "TRAJECTORY_POINTS", "evaluate", "optimizer_for",
    "random_neighbor", "resolve_budget",
]
