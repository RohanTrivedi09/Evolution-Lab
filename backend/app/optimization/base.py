"""Shared optimizer scaffolding: evaluation budget, history recording, cancellation.

Every algorithm spends the same currency - fitness evaluations - so runs can be
compared on one axis. All fitness calls must go through `score()`; anything that
calls the evaluator directly makes the reported budget a lie.
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable

from ..models import Weights
from .evaluator import Score, evaluate
from .neighborhood import random_neighbor
from .representation import Candidate, Problem

HISTORY_POINTS = 200
TRAJECTORY_POINTS = 300


@dataclass
class OptimizationResult:
    candidate: Candidate
    score: Score
    history: list[dict]
    evaluations: int
    runtime_ms: float
    trajectory: list[dict]

    def as_dict(self, problem: Problem) -> dict:
        return {
            "schedule": problem.to_schedule(self.candidate),
            "score": self.score.as_dict(),
            "history": self.history,
            "evaluations": self.evaluations,
            "runtime_ms": round(self.runtime_ms, 2),
            "trajectory": self.trajectory,
        }


class Optimizer:
    """Base class. Subclasses implement `run()` and stop when the budget is spent."""

    name = "optimizer"

    def __init__(self, problem: Problem, weights: Weights, seed: int, params: dict,
                 progress_callback: Callable | None = None, max_evaluations: int = 1000,
                 initial_schedule: dict | None = None):
        self.problem = problem
        self.weights = weights
        self.rng = random.Random(seed)
        self.params = params
        self.progress_callback = progress_callback
        self.max_evaluations = max(1, int(max_evaluations))
        self.initial_schedule = initial_schedule

        self.evaluations = 0
        self.history: list[dict] = []
        self.trajectory: list[dict] = []
        self._best_cost = float("inf")
        self._record_stride = max(1, self.max_evaluations // HISTORY_POINTS)
        self._next_record = 0
        self._trajectory_stride = max(1, -(-self.max_evaluations // TRAJECTORY_POINTS))
        self._next_trajectory = 0

    # -- budget ------------------------------------------------------------------------
    def score(self, candidate: Candidate) -> Score:
        self.evaluations += 1
        result = evaluate(self.problem, candidate, self.weights)
        if self.evaluations >= self._next_trajectory:
            self._next_trajectory = self.evaluations + self._trajectory_stride
            self.trajectory.append({
                "evaluations": self.evaluations,
                "cost": result.total_cost,
                "placement": [list(a.key()) for a in candidate],
            })
        return result

    @property
    def budget_left(self) -> int:
        return max(0, self.max_evaluations - self.evaluations)

    def budget_exhausted(self) -> bool:
        return self.evaluations >= self.max_evaluations

    # -- candidates --------------------------------------------------------------------
    def initial_candidate(self) -> Candidate:
        """Start from the caller's schedule when repairing an edit, else at random."""
        if self.initial_schedule:
            return self.problem.from_schedule(self.initial_schedule)
        return self.problem.random_candidate(self.rng)

    def neighbor(self, candidate: Candidate) -> Candidate:
        return random_neighbor(self.problem, candidate, self.rng)[0]

    mutate = neighbor

    # -- observation -------------------------------------------------------------------
    def record(self, iteration: int, best_score: Score, best_candidate: Candidate | None = None,
               average: float | None = None, force: bool = False, **extra) -> None:
        """Append a history point on improvement, on stride, or when forced.

        Striding by evaluations keeps every algorithm's history a comparable size no
        matter how many evaluations one iteration costs it.
        """
        improved = best_score.total_cost < self._best_cost
        if improved:
            self._best_cost = best_score.total_cost
        if not (force or improved or self.evaluations >= self._next_record):
            return
        self._next_record = self.evaluations + self._record_stride

        point = {
            "iteration": iteration,
            "evaluations": self.evaluations,
            "best_cost": best_score.total_cost,
            "best_fitness": best_score.normalized_fitness,
            "hard_violations": best_score.hard_violations,
        }
        if average is not None:
            point["average_cost"] = average
        if best_candidate is not None:
            point["schedule"] = self.problem.to_schedule(best_candidate)
        point.update(extra)
        self.history.append(point)
        if self.progress_callback:
            self.progress_callback(point)

    def finish(self, best: Candidate, best_score: Score, started: float) -> OptimizationResult:
        return OptimizationResult(best, best_score, self.history, self.evaluations,
                                  (time.perf_counter() - started) * 1000, self.trajectory)

    def run(self) -> OptimizationResult:
        raise NotImplementedError
