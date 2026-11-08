import json

from fastapi.testclient import TestClient

from app.main import create_app


def test_api_feedback_isolation_persistence_and_exclusions(tmp_path):
    source = tmp_path / "catalog.json"
    source.write_text(json.dumps([{"set_id": str(i), "name": f"Fixture {i}", "year": 2020,
                                   "num_parts": 10 + i, "theme_id": 1, "theme": "Fixture"}
                                  for i in range(3)]))
    database = tmp_path / "feedback.db"
    client = TestClient(create_app(source, database))
    assert client.get("/api/v1/health/ready").status_code == 200
    assert client.post("/api/v1/feedback", json={"user_id": "a", "set_id": "0", "action": "like"}).status_code == 201
    assert client.get("/api/v1/users/b/feedback").json()["current"] == []
    assert "0" not in [x["set_id"] for x in client.get("/api/v1/users/a/recommendations").json()["items"]]
    restarted = TestClient(create_app(source, database))
    assert restarted.get("/api/v1/users/a/feedback").json()["current"][0]["action"] == "like"
    assert client.get("/api/v1/users/a/recommendations?k=101").status_code == 422
    assert client.post("/api/v1/users/a/retraining").status_code == 403
    assert client.get("/api/v1/sets/unknown").status_code == 404


def test_empty_catalog_is_not_ready(tmp_path):
    client = TestClient(create_app(tmp_path / "missing.json", tmp_path / "empty.db"))
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/health/ready").status_code == 503
    assert client.get("/api/v1/users/new/recommendations").json()["items"] == []
