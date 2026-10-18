"""Dataset listing, pasting, and the safety of the id used to look one up."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data import MAX_UPLOADS, list_datasets, load_dataset, register_dataset
from app.main import app
from app.models import Dataset

from factories import BASE

client = TestClient(app)


@pytest.fixture
def sample() -> dict:
    return client.get("/api/datasets/small-college").json()


def test_bundled_datasets_are_listed_with_their_size(sample):
    listed = {item["id"]: item for item in client.get("/api/datasets").json()["datasets"]}
    assert {"small-college", "medium-college", "adani-sem7-cse"} <= set(listed)
    assert listed["small-college"]["sessions"] == 9
    assert listed["small-college"]["pasted"] is False


def test_a_pasted_dataset_becomes_runnable(sample):
    created = client.post("/api/datasets", json={"dataset": sample}).json()
    assert created["sessions"] == 9

    listed = {item["id"] for item in client.get("/api/datasets").json()["datasets"]}
    assert created["dataset_id"] in listed

    started = client.post("/api/runs", json={
        "dataset_id": created["dataset_id"], "parameters": {"max_evaluations": 100}})
    assert started.status_code == 200


def test_pasting_an_invalid_dataset_explains_why():
    broken = {**BASE, "courses": [{**BASE["courses"][0], "faculty_id": "GHOST"}]}
    response = client.post("/api/datasets", json={"dataset": broken})
    assert response.status_code == 422
    assert any("GHOST" in message for message in response.json()["detail"]["errors"])


def test_pasting_a_non_object_is_reported_not_crashed():
    assert client.post("/api/datasets", json={"dataset": "nonsense"}).status_code == 422


def test_the_paste_store_is_bounded():
    """An unbounded store would let a session grow memory without limit."""
    dataset = Dataset.model_validate(BASE)
    ids = [register_dataset(dataset) for _ in range(MAX_UPLOADS + 5)]
    kept = {item["id"] for item in list_datasets() if item["pasted"]}
    assert len(kept) <= MAX_UPLOADS
    assert ids[-1] in kept, "the most recent paste must survive"


@pytest.mark.parametrize("bad", ["../secrets", "..", "nested/path", "..\\windows"])
def test_dataset_ids_cannot_escape_the_data_directory(bad):
    with pytest.raises(KeyError):
        load_dataset(bad)


def test_unknown_dataset_is_a_404():
    assert client.get("/api/datasets/does-not-exist").status_code == 404
