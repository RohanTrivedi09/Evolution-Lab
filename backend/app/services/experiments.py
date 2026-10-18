"""Repeated-seed experiments.

A single run tells you what one random seed did. Reporting that as "simulated annealing
beats hill climbing" is an anecdote. This runs every algorithm across several seeds on
one shared evaluation budget and reports the spread, so the claim is about the
strategies rather than about luck.
"""
from __future__ import annotations

import statistics
import threading
import time
import uuid
from dataclasses import asdict, dataclass

from ..data import load_dataset
from ..models import ExperimentRequest
from ..optimization import COMPARISON_STRATEGIES, Problem, optimizer_for


@dataclass
class Trial:
    algorithm: str
    seed: int
    total_cost: float
    hard_violations: int
    soft_violations: int
    group_gaps: int
    evaluations: int
    runtime_ms: float
    feasible: bool
    evaluations_to_feasible: int | None


def _first_feasible(history: list[dict]) -> int | None:
    """Evaluations spent before the first zero-hard-violation schedule appeared."""
    for point in history:
        if point["hard_violations"] == 0:
            return point["evaluations"]
    return None


def summarise(trials: list[Trial]) -> list[dict]:
    """Per-algorithm aggregates, plus how many seeds each one actually won."""
    by_algorithm: dict[str, list[Trial]] = {}
    for trial in trials:
        by_algorithm.setdefault(trial.algorithm, []).append(trial)

    # A "win" is being strictly best on a given seed; ties credit every joint winner.
    wins = {name: 0 for name in by_algorithm}
    seeds = sorted({trial.seed for trial in trials})
    for seed in seeds:
        same_seed = [t for t in trials if t.seed == seed]
        if not same_seed:
            continue
        best = min(t.total_cost for t in same_seed)
        for trial in same_seed:
            if trial.total_cost == best:
                wins[trial.algorithm] += 1

    rows = []
    for name, group in by_algorithm.items():
        costs = [t.total_cost for t in group]
        reached = [t.evaluations_to_feasible for t in group if t.evaluations_to_feasible is not None]
        rows.append({
            "algorithm": name,
            "runs": len(group),
            "mean_cost": round(statistics.fmean(costs), 2),
            "std_cost": round(statistics.pstdev(costs), 2) if len(costs) > 1 else 0.0,
            "best_cost": min(costs),
            "worst_cost": max(costs),
            "median_cost": round(statistics.median(costs), 2),
            "feasible_rate": round(sum(t.feasible for t in group) / len(group), 3),
            "mean_evaluations_to_feasible": round(statistics.fmean(reached), 1) if reached else None,
            "mean_runtime_ms": round(statistics.fmean([t.runtime_ms for t in group]), 1),
            "seed_wins": wins[name],
        })
    # Feasibility dominates: a fast schedule with clashes must not outrank a valid one.
    rows.sort(key=lambda row: (-row["feasible_rate"], row["mean_cost"]))
    return rows


class ExperimentManager:
    def __init__(self, ttl_seconds: float = 7200, max_experiments: int = 50):
        self._store: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._ttl = ttl_seconds
        self._max = max_experiments

    def get(self, experiment_id: str) -> dict:
        with self._lock:
            return self._store[experiment_id]

    def create(self, request: ExperimentRequest) -> dict:
        load_dataset(request.dataset_id)  # raises KeyError for unknown datasets
        algorithms = request.algorithms or list(COMPARISON_STRATEGIES)
        seeds = request.resolved_seeds()
        experiment_id = uuid.uuid4().hex
        record = {
            "experiment_id": experiment_id, "status": "running", "progress": 0,
            "dataset_id": request.dataset_id, "algorithms": algorithms, "seeds": seeds,
            "max_evaluations": request.max_evaluations,
            "total_trials": len(algorithms) * len(seeds),
            "trials": [], "summary": [], "created_at": time.time(),
        }
        with self._lock:
            self._evict()
            self._store[experiment_id] = record
        threading.Thread(target=self._execute, args=(record, request, algorithms, seeds),
                         daemon=True).start()
        return record

    def _evict(self) -> None:
        now = time.time()
        with self._lock:
            for key in [k for k, v in self._store.items()
                        if v["status"] in {"completed", "failed"} and now - v["created_at"] > self._ttl]:
                self._store.pop(key, None)
            while len(self._store) > self._max:
                oldest = min(self._store.items(), key=lambda kv: kv[1]["created_at"])[0]
                self._store.pop(oldest, None)

    def _execute(self, record: dict, request: ExperimentRequest,
                 algorithms: list[str], seeds: list[int]) -> None:
        try:
            problem = Problem(load_dataset(request.dataset_id))
            trials: list[Trial] = []
            # Sequential on purpose: parallel threads would contend on the GIL and
            # distort the runtime figures this experiment is meant to report.
            for seed in seeds:
                for name in algorithms:
                    result = optimizer_for(name, problem, request.weights, seed,
                                           request.parameters,
                                           max_evaluations=request.max_evaluations).run()
                    score = result.score
                    trials.append(Trial(
                        algorithm=name, seed=seed, total_cost=score.total_cost,
                        hard_violations=score.hard_violations,
                        soft_violations=score.soft_violations,
                        group_gaps=score.group_gaps, evaluations=result.evaluations,
                        runtime_ms=round(result.runtime_ms, 2),
                        feasible=score.hard_violations == 0,
                        evaluations_to_feasible=_first_feasible(result.history),
                    ))
                    record["trials"] = [asdict(t) for t in trials]
                    record["progress"] = round(100 * len(trials) / record["total_trials"])
                    record["summary"] = summarise(trials)
            record["status"] = "completed"
        except Exception as exc:
            record.update({"status": "failed", "error": str(exc)})


manager = ExperimentManager()
