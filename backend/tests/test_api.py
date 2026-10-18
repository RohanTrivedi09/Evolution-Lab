"""API contract tests, including the fairness guarantee comparisons depend on."""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def wait_for(url: str, tries: int = 200, pause: float = 0.02) -> dict:
    for _ in range(tries):
        payload = client.get(url).json()
        status = payload.get("status")
        if status in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(pause)
    raise AssertionError(f"{url} never finished (last status {status})")


def test_health_and_dataset_listing():
    assert client.get("/api/health").json()["status"] == "ok"
    listed = client.get("/api/datasets").json()["datasets"]
    assert {item["id"] for item in listed} >= {"small-college", "medium-college"}


def test_unknown_ids_are_404():
    assert client.get("/api/datasets/nope").status_code == 404
    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/comparisons/nope").status_code == 404
    assert client.post("/api/runs", json={"dataset_id": "nope"}).status_code == 404


def test_run_completes_and_reports_its_budget():
    created = client.post("/api/runs", json={
        "algorithm": "hill_climbing", "max_evaluations": 150}).json()
    assert created["max_evaluations"] == 150
    finished = wait_for(f"/api/runs/{created['run_id']}")
    assert finished["status"] == "completed"
    result = finished["result"]
    assert result["evaluations"] <= 150
    assert result["score"]["hard_violations"] >= 0
    assert result["history"] and result["schedule"] and result["trajectory"]


def test_history_and_trajectory_endpoints_follow_the_run():
    run_id = client.post("/api/runs", json={"max_evaluations": 120}).json()["run_id"]
    wait_for(f"/api/runs/{run_id}")
    assert client.get(f"/api/runs/{run_id}/history").json()["history"]
    assert client.get(f"/api/runs/{run_id}/trajectory").json()["trajectory"]
    assert client.get(f"/api/runs/{run_id}/export").json()["run_id"] == run_id


def test_comparison_gives_every_algorithm_the_same_budget():
    """The headline fairness property: a race must compare algorithms, not budgets."""
    created = client.post("/api/comparisons", json={"max_evaluations": 200}).json()
    assert created["max_evaluations"] == 200
    finished = wait_for(f"/api/comparisons/{created['comparison_id']}")

    runs = finished["runs"]
    assert len(runs) == 4
    assert {run["algorithm"] for run in runs} == {
        "hill_climbing", "simulated_annealing", "genetic_algorithm", "particle_swarm"}
    assert {run["max_evaluations"] for run in runs} == {200}
    for run in runs:
        assert run["status"] == "completed", run.get("error")
        assert run["result"]["evaluations"] <= 200


def test_comparison_honours_a_budget_sent_in_parameters():
    """The Lab sends its budget inside `parameters`, as single runs accept it. A race
    that ignored it ran every strategy at the 2,000 default whatever the user typed."""
    created = client.post("/api/comparisons", json={
        "parameters": {"max_evaluations": 150, "iterations": 80, "generations": 80},
    }).json()
    assert created["max_evaluations"] == 150
    finished = wait_for(f"/api/comparisons/{created['comparison_id']}")
    # Iteration counts translate to different budgets per strategy; they must not leak in.
    assert {run["max_evaluations"] for run in finished["runs"]} == {150}


def test_cancelling_a_finished_run_is_not_an_error():
    run_id = client.post("/api/runs", json={"max_evaluations": 20}).json()["run_id"]
    wait_for(f"/api/runs/{run_id}")
    first = client.post(f"/api/runs/{run_id}/cancel")
    second = client.post(f"/api/runs/{run_id}/cancel")
    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == "completed"


def test_edited_schedule_scores_identically_to_the_optimizer():
    """The editor and the search must agree, or the live cost readout would lie."""
    run_id = client.post("/api/runs", json={"max_evaluations": 200}).json()["run_id"]
    finished = wait_for(f"/api/runs/{run_id}")
    result = finished["result"]

    scored = client.post("/api/schedule/evaluate", json={
        "dataset_id": "small-college", "schedule": result["schedule"]}).json()
    assert scored["score"]["total_cost"] == result["score"]["total_cost"]
    assert scored["score"]["hard_violations"] == result["score"]["hard_violations"]


def test_evaluate_rejects_unknown_sessions():
    response = client.post("/api/schedule/evaluate", json={
        "schedule": {"NOPE-1": {"day": "Mon", "period": "09:00", "room_id": "R101"}}})
    assert response.status_code == 422
    assert "NOPE-1" in response.json()["detail"]


def test_validation_reports_readable_field_errors():
    broken = {
        "days": ["Mon"], "periods": ["09:00"],
        "rooms": [{"id": "R1", "capacity": 10, "type": "lecture"}],
        "faculty": [{"id": "F1", "name": "Dr One"}],
        "groups": [{"id": "G1", "size": 10}],
        "courses": [{"id": "C1", "name": "One", "faculty_id": "MISSING",
                     "group_ids": ["G1"], "sessions_per_week": 1, "room_type": "lecture"}],
    }
    payload = client.post("/api/datasets/validate", json={"dataset": broken}).json()
    assert payload["valid"] is False
    assert any("MISSING" in message for message in payload["errors"])


def test_validation_summarises_a_good_dataset():
    dataset = client.get("/api/datasets/small-college").json()
    payload = client.post("/api/datasets/validate", json={"dataset": dataset}).json()
    assert payload["valid"] is True
    assert payload["sessions"] == 9
    assert payload["summary"]["slots_per_session"] == 5 * 5 * 3
