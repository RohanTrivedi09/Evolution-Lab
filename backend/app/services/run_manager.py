"""Owns run lifecycle: creation, background execution, cancellation and expiry.

Kept out of the HTTP layer so routes stay thin and the store's invariants - bounded
size, cooperative cancellation, one lock - live in exactly one place.
"""
from __future__ import annotations

import threading
import time
import uuid

from ..data import load_dataset
from ..models import RunRequest
from ..optimization import DEFAULT_BUDGET, Problem, optimizer_for, resolve_budget

TERMINAL = {"completed", "failed", "cancelled"}


class RunCancelled(Exception):
    """Raised inside the optimizer thread at an iteration boundary."""


class RunManager:
    def __init__(self, ttl_seconds: float = 3600, max_runs: int = 200):
        self._runs: dict[str, dict] = {}
        self._comparisons: dict[str, dict] = {}
        self._cancels: dict[str, threading.Event] = {}
        self._lock = threading.RLock()
        self._ttl = ttl_seconds
        self._max_runs = max_runs

    # -- store -------------------------------------------------------------------------
    def _evict(self) -> None:
        """Drop finished runs past their TTL, then oldest-first if still over cap."""
        now = time.time()
        with self._lock:
            stale = [rid for rid, rec in self._runs.items()
                     if rec["status"] in TERMINAL and now - rec["created_at"] > self._ttl]
            for rid in stale:
                self._runs.pop(rid, None)
                self._cancels.pop(rid, None)
            if len(self._runs) > self._max_runs:
                finished = sorted((rec["created_at"], rid) for rid, rec in self._runs.items()
                                  if rec["status"] in TERMINAL)
                for _, rid in finished[:len(self._runs) - self._max_runs]:
                    self._runs.pop(rid, None)
                    self._cancels.pop(rid, None)

    def get_run(self, run_id: str) -> dict:
        with self._lock:
            return self._runs[run_id]

    def get_comparison(self, comparison_id: str) -> dict:
        with self._lock:
            record = self._comparisons[comparison_id]
            children = [self._runs[rid] for rid in record["run_ids"] if rid in self._runs]
            if children and all(child["status"] in TERMINAL for child in children):
                record["status"] = "completed"
            record["runs"] = children
            return record

    # -- execution ---------------------------------------------------------------------
    def create_run(self, request: RunRequest, budget: int | None = None) -> dict:
        load_dataset(request.dataset_id)  # raises KeyError for unknown datasets
        resolved = resolve_budget(request.algorithm, request.parameters,
                                  budget or request.max_evaluations)
        run_id = uuid.uuid4().hex
        record = {
            "run_id": run_id, "status": "queued", "progress": 0,
            "algorithm": request.algorithm, "dataset_id": request.dataset_id,
            "seed": request.seed, "parameters": request.parameters,
            "weights": request.weights.model_dump(), "max_evaluations": resolved,
            "created_at": time.time(),
        }
        with self._lock:
            self._evict()
            self._runs[run_id] = record
            self._cancels[run_id] = threading.Event()
        threading.Thread(target=self._execute, args=(run_id, request, resolved),
                         daemon=True).start()
        return record

    def _execute(self, run_id: str, request: RunRequest, budget: int) -> None:
        record = self._runs[run_id]
        record["status"] = "running"
        cancel = self._cancels[run_id]
        try:
            problem = Problem(load_dataset(request.dataset_id))

            def progress(point: dict) -> None:
                if cancel.is_set():
                    raise RunCancelled()
                record["progress"] = min(100, round(100 * point["evaluations"] / budget))
                record["latest"] = point

            initial = ({sid: slot.model_dump() for sid, slot in request.initial_schedule.items()}
                       if request.initial_schedule else None)
            optimizer = optimizer_for(request.algorithm, problem, request.weights, request.seed,
                                      request.parameters, progress, budget, initial)
            result = optimizer.run()
            if cancel.is_set():
                raise RunCancelled()
            record.update({"status": "completed", "result": result.as_dict(problem),
                           "progress": 100})
        except RunCancelled:
            record["status"] = "cancelled"
        except Exception as exc:  # surfaced to the client, never swallowed
            record.update({"status": "failed", "error": str(exc)})
        finally:
            with self._lock:
                self._cancels.pop(run_id, None)

    def cancel_run(self, run_id: str) -> str:
        with self._lock:
            record = self._runs[run_id]
            if record["status"] in TERMINAL:
                return record["status"]
            event = self._cancels.get(run_id)
            if event is None:
                # The run finished between our status read and here; report what it became.
                return record["status"]
            event.set()
            record["status"] = "cancel_requested"
            return record["status"]

    # -- comparisons -------------------------------------------------------------------
    def create_comparison(self, request: RunRequest) -> dict:
        """Fan out one identical budget across every strategy.

        The equal budget is the whole point: comparing algorithms that were allowed
        different numbers of fitness evaluations measures the budget, not the algorithm.
        """
        from ..optimization import STRATEGIES

        budget = request.max_evaluations or DEFAULT_BUDGET
        comparison_id = uuid.uuid4().hex
        run_ids = [self.create_run(request.model_copy(update={"algorithm": name}), budget)["run_id"]
                   for name in STRATEGIES]
        record = {"comparison_id": comparison_id, "status": "running",
                  "run_ids": run_ids, "max_evaluations": budget,
                  "dataset_id": request.dataset_id, "seed": request.seed}
        with self._lock:
            self._comparisons[comparison_id] = record
        return record


manager = RunManager()
