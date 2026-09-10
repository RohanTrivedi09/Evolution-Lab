"""Input validation: bounds, size limits, and refusing to score partial data.

These are the cases where a wrong answer is worse than an error - the system would
otherwise hand back a confident number built on values it invented.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.data import load_dataset
from app.main import app
from app.models import MAX_SESSIONS, Dataset, Weights
from app.optimization import Problem
from app.optimization.fuzzy import infer

from factories import BASE, build, course

client = TestClient(app)


# --- weights --------------------------------------------------------------------------

@pytest.mark.parametrize("field", ["hard", "soft", "gaps", "fragmentation"])
def test_weights_cannot_be_negative(field):
    """A negative weight inverts the objective: the search would maximise clashes."""
    with pytest.raises(ValidationError):
        Weights(**{field: -1})


def test_zero_weights_are_allowed():
    assert Weights(hard=0, soft=0, gaps=0, fragmentation=0).hard == 0


def test_api_rejects_a_run_with_a_negative_weight():
    assert client.post("/api/runs", json={"weights": {"hard": -1}}).status_code == 422


# --- dataset size limits (spec section 7) ---------------------------------------------

def test_a_dataset_that_expands_past_the_session_cap_is_refused():
    payload = {**BASE, "courses": [
        {**BASE["courses"][0], "id": f"X{i}", "sessions_per_week": 20} for i in range(200)
    ]}
    with pytest.raises(ValidationError, match="sessions"):
        Dataset.model_validate(payload)


def test_oversized_collections_are_refused():
    with pytest.raises(ValidationError):
        Dataset.model_validate({**BASE, "periods": [f"P{i}" for i in range(50)]})


def test_validate_endpoint_explains_an_oversized_dataset():
    payload = {**BASE, "courses": [
        {**BASE["courses"][0], "id": f"X{i}", "sessions_per_week": 20} for i in range(200)
    ]}
    body = client.post("/api/datasets/validate", json={"dataset": payload}).json()
    assert body["valid"] is False
    assert any("sessions" in message for message in body["errors"])


@pytest.mark.parametrize("dataset_id", ["small-college", "medium-college", "adani-sem7-cse"])
def test_shipped_datasets_stay_inside_the_limits(dataset_id):
    dataset = load_dataset(dataset_id)
    assert sum(c.sessions_per_week for c in dataset.courses) <= MAX_SESSIONS


# --- partial schedules ----------------------------------------------------------------

def test_scoring_refuses_a_schedule_that_omits_sessions():
    """Completing a partial timetable would report invented clashes as the caller's."""
    problem = Problem(load_dataset("small-college"))
    full = problem.to_schedule(problem.random_candidate(__import__("random").Random(1)))
    partial = dict(list(full.items())[:3])

    response = client.post("/api/schedule/evaluate", json={
        "dataset_id": "small-college", "schedule": partial})
    assert response.status_code == 422
    assert "missing" in response.json()["detail"].lower()


def test_scoring_accepts_a_complete_schedule():
    problem = Problem(load_dataset("small-college"))
    full = problem.to_schedule(problem.random_candidate(__import__("random").Random(1)))
    response = client.post("/api/schedule/evaluate", json={
        "dataset_id": "small-college", "schedule": full})
    assert response.status_code == 200
    assert len(response.json()["schedule"]) == len(problem.sessions)


# --- fuzzy inputs ---------------------------------------------------------------------

@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_fuzzy_refuses_non_finite_inputs(bad):
    with pytest.raises(ValueError, match="finite"):
        infer(bad, 0.0, 0.0)
