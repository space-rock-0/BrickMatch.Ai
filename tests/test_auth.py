"""Account registration, repeated login, and private profile access."""
from fastapi.testclient import TestClient

from app.main import create_app


def test_register_login_and_profile_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv("BRICKMATCH_AUTH_REQUIRED", "true")
    monkeypatch.setenv("BRICKMATCH_AUTH_SECRET", "test-account-secret")
    catalog = tmp_path / "catalog.json"
    catalog.write_text("[]")
    client = TestClient(create_app(catalog, tmp_path / "feedback.db"))
    body = {"user_id": "alice", "password": "example-password-123"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code == 409
    login = client.post("/api/v1/auth/login", json=body)
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    assert client.get("/api/v1/users/alice/summary", headers=headers).status_code == 200
    assert client.get("/api/v1/users/bob/summary", headers=headers).status_code == 401
    assert client.get("/api/v1/users/alice/summary").status_code == 401
