from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_and_dataset_routes():
    assert client.get("/api/health").status_code == 200
    response = client.get("/api/datasets")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()["datasets"]} >= {"small-college", "medium-college"}

def test_run_contract():
    response = client.post("/api/runs", json={"algorithm":"hill_climbing", "parameters":{"iterations":2}})
    assert response.status_code == 200
    run_id = response.json()["run_id"]
    import time
    for _ in range(30):
        result = client.get(f"/api/runs/{run_id}").json()
        if result["status"] == "completed":
            break
        time.sleep(.02)
    assert result["status"] == "completed"
    assert "score" in result["result"] and "history" in result["result"]

