"""Repeated-seed experiments: aggregation, ordering, and the API contract."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import ExperimentRequest
from app.services.experiments import Trial, summarise

client = TestClient(app)


def trial(algorithm: str, seed: int, cost: float, hard: int = 0,
          to_feasible: int | None = 10) -> Trial:
    return Trial(algorithm=algorithm, seed=seed, total_cost=cost, hard_violations=hard,
                 soft_violations=0, group_gaps=0, evaluations=100, runtime_ms=5.0,
                 feasible=hard == 0, evaluations_to_feasible=to_feasible)


def test_seeds_default_to_a_numbered_range():
    assert ExperimentRequest(seed_count=3).resolved_seeds() == [1, 2, 3]
    assert ExperimentRequest(seeds=[7, 9]).resolved_seeds() == [7, 9]


def test_summary_reports_spread_not_just_a_single_number():
    rows = summarise([trial("a", 1, 100), trial("a", 2, 200), trial("a", 3, 300)])
    assert len(rows) == 1
    row = rows[0]
    assert row["runs"] == 3
    assert row["mean_cost"] == 200
    assert row["best_cost"] == 100 and row["worst_cost"] == 300
    assert row["median_cost"] == 200
    assert row["std_cost"] > 0


def test_a_single_run_has_no_spread():
    assert summarise([trial("a", 1, 100)])[0]["std_cost"] == 0.0


def test_wins_are_counted_per_seed():
    rows = {r["algorithm"]: r for r in summarise([
        trial("a", 1, 100), trial("b", 1, 200),
        trial("a", 2, 400), trial("b", 2, 50),
        trial("a", 3, 10), trial("b", 3, 900),
    ])}
    assert rows["a"]["seed_wins"] == 2
    assert rows["b"]["seed_wins"] == 1


def test_ties_credit_every_joint_winner():
    rows = {r["algorithm"]: r for r in summarise([trial("a", 1, 100), trial("b", 1, 100)])}
    assert rows["a"]["seed_wins"] == 1 and rows["b"]["seed_wins"] == 1


def test_feasibility_outranks_a_cheaper_but_invalid_schedule():
    """A schedule with clashes must never be reported above a valid one."""
    rows = summarise([
        trial("valid", 1, 5000, hard=0),
        trial("broken", 1, 10, hard=4, to_feasible=None),
    ])
    assert [r["algorithm"] for r in rows] == ["valid", "broken"]
    assert rows[0]["feasible_rate"] == 1.0 and rows[1]["feasible_rate"] == 0.0


def test_unreached_feasibility_is_reported_as_missing_not_zero():
    row = summarise([trial("a", 1, 10, hard=3, to_feasible=None)])[0]
    assert row["mean_evaluations_to_feasible"] is None


def test_experiment_runs_every_algorithm_on_every_seed():
    created = client.post("/api/experiments", json={
        "dataset_id": "small-college", "seed_count": 3, "max_evaluations": 120,
    }).json()
    assert created["total_trials"] == 12

    for _ in range(400):
        record = client.get(f"/api/experiments/{created['experiment_id']}").json()
        if record["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert record["status"] == "completed", record.get("error")

    assert len(record["trials"]) == 12
    assert {t["algorithm"] for t in record["trials"]} == {
        "hill_climbing", "simulated_annealing", "genetic_algorithm", "particle_swarm"}
    assert {t["seed"] for t in record["trials"]} == {1, 2, 3}
    assert all(t["evaluations"] <= 120 for t in record["trials"])
    assert len(record["summary"]) == 4
    assert sum(row["seed_wins"] for row in record["summary"]) >= 3


def test_experiment_can_target_specific_algorithms_and_seeds():
    created = client.post("/api/experiments", json={
        "dataset_id": "small-college", "algorithms": ["hill_climbing"],
        "seeds": [4, 5], "max_evaluations": 60,
    }).json()
    for _ in range(300):
        record = client.get(f"/api/experiments/{created['experiment_id']}").json()
        if record["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert record["status"] == "completed"
    assert len(record["trials"]) == 2
    assert {t["seed"] for t in record["trials"]} == {4, 5}


def test_unknown_experiment_and_dataset_are_404():
    assert client.get("/api/experiments/nope").status_code == 404
    assert client.post("/api/experiments", json={"dataset_id": "nope"}).status_code == 404
