"""Release regressions for account isolation and actual feedback-driven serving."""
import json
import os
import time
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.auth import issue_token
from app.main import create_app
from app.recommendation.engine import PersonalEngine, featured_catalog
from app.recommendation.feedback import FeedbackStore


def catalog_file(tmp_path):
    rows = [{"set_id": str(i), "name": f"Build {i}", "theme_id": i % 3,
             "theme": f"Theme {i % 3}", "year": 2020 + i % 5, "num_parts": 100 + i * 20}
            for i in range(30)]
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(rows))
    return path, rows


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_account_lifecycle_isolation_and_learning(tmp_path, monkeypatch, backend):
    database = tmp_path / "accounts.db"
    if backend == "postgres":
        database = os.getenv("TEST_DATABASE_URL")
        if not database:
            pytest.skip("TEST_DATABASE_URL not set; PostgreSQL checked in CI")
    monkeypatch.setenv("BRICKMATCH_AUTH_REQUIRED", "true")
    monkeypatch.delenv("BRICKMATCH_EMBEDDINGS", raising=False)
    path, _ = catalog_file(tmp_path)
    app = create_app(path, database)
    alice, bob = TestClient(app, base_url="https://testserver"), TestClient(app, base_url="https://testserver")
    username = "account_" + uuid.uuid4().hex[:12]
    body = {"user_id": username, "password": "account-password-123"}
    response = alice.post("/api/v1/auth/register", json=body)
    assert response.status_code == 201
    token = response.json()["token"]
    assert all(flag in response.headers["set-cookie"].lower() for flag in ("httponly", "secure", "samesite=strict"))
    assert alice.get(f"/api/v1/users/{username}/summary").json()["total"] == 0
    cold = alice.get(f"/api/v1/users/{username}/recommendations").json()
    assert cold["items"] == [] and cold["onboarding"]
    assert bob.get(f"/api/v1/users/{username}/feedback").status_code == 401
    assert bob.post("/api/v1/feedback", json={"user_id": username, "set_id": "0", "action": "like"}).status_code == 401
    assert alice.post("/api/v1/feedback", headers={"Origin": "https://evil.example"},
                      json={"user_id": username, "set_id": "0", "action": "like"}).status_code == 403
    assert alice.post("/api/v1/feedback", json={"user_id": username, "set_id": "0", "action": "like"}).status_code == 201
    recs = alice.get(f"/api/v1/users/{username}/recommendations").json()
    assert recs["mode"] == "metadata_profile"
    assert recs["learning"]["likes"] == 1
    assert "0" not in [row["set_id"] for row in recs["items"]]
    restarted = TestClient(create_app(path, database), base_url="https://testserver")
    headers = {"Authorization": f"Bearer {token}"}
    assert restarted.get(f"/api/v1/users/{username}/summary", headers=headers).json()["total"] == 1
    assert alice.post("/api/v1/auth/logout").status_code == 200
    assert restarted.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert alice.get("/api/v1/auth/me").status_code == 401
    assert alice.post("/api/v1/auth/login", json=body).status_code == 200
    assert alice.post("/api/v1/feedback", json={"user_id": username, "set_id": "0", "action": "undo"}).status_code == 201
    assert alice.get(f"/api/v1/users/{username}/recommendations").json()["items"] == []
    assert alice.post("/api/v1/auth/password", json={
        "current_password": body["password"], "new_password": "changed-password-456"}).status_code == 200
    assert alice.get("/api/v1/auth/me").status_code == 401
    assert alice.post("/api/v1/auth/login", json=body).status_code == 401
    body["password"] = "changed-password-456"
    assert alice.post("/api/v1/auth/login", json=body).status_code == 200


def test_legacy_profile_cannot_be_claimed_and_session_expiry(tmp_path, monkeypatch):
    monkeypatch.setenv("BRICKMATCH_AUTH_REQUIRED", "true")
    monkeypatch.setenv("BRICKMATCH_AUTH_SECRET", "legacy-test-secret")
    path, _ = catalog_file(tmp_path)
    db = tmp_path / "db.sqlite"
    store = FeedbackStore(db)
    store.record("demo", "0", "like")
    client = TestClient(create_app(path, db))
    assert client.post("/api/v1/auth/register", json={"user_id": "demo", "password": "example-password"}).status_code == 409
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {issue_token('demo')}"}).status_code == 401
    store.create_user("new", "unused", "now")
    token = store.create_session("new")
    assert store.session_user(token) == "new"
    with store.connect() as conn:
        store.exec(conn, "UPDATE app_sessions SET expires_at=?", (int(time.time()) - 1,))
    assert store.session_user(token) is None
    for _ in range(15):
        assert store.allow_auth_attempt("ip")
    assert not FeedbackStore(db).allow_auth_attempt("ip")


def test_likes_dislikes_corrections_and_other_users(tmp_path):
    _, rows = catalog_file(tmp_path)
    ids = [row["set_id"] for row in rows]
    features = np.eye(3)[[row["theme_id"] for row in rows]]
    engine = PersonalEngine(rows, ids, features, [], None)
    def rating(sid, action):
        return {"user_id": "a", "set_id": sid, "action": action, "updated_at": sid.zfill(3)}
    scores, mode, _ = engine.scores("a", [rating("0", "like")])
    assert mode == "metadata_profile" and scores["3"]["metadata"] > scores["4"]["metadata"]
    scores, _, _ = engine.scores("a", [rating("0", "like"), rating("1", "dislike")])
    assert scores["4"]["metadata"] < scores["5"]["metadata"]
    scores, _, _ = engine.scores("a", [rating("0", "dislike")])
    assert scores["3"]["metadata"] < scores["4"]["metadata"]
    assert engine.scores("b", [rating("0", "like")])[1] == "cold_start"
    assert engine.scores("a", [rating("0", "skip")])[0] == {}
    labels = [rating(str(i), "like" if i % 3 == 0 else "dislike") for i in range(30)]
    _, mode, status = engine.scores("a", labels)
    assert "roc_auc" in status
    assert mode != "classifier_profile"  # No improvement over a perfect profile baseline.
    assert status["profile_auc"] == 1
    assert engine.scores("a", [])[0] == {}


def test_featured_builds_interleave_themes(tmp_path):
    _, rows = catalog_file(tmp_path)
    featured = featured_catalog(rows)
    assert len(featured) == len(rows)
    assert len({r["theme_id"] for r in featured[:3]}) == 3


def test_classifier_can_pass_gate_and_invalidates_after_undo():
    rng = np.random.default_rng(0)
    features = rng.normal(size=(100, 8))
    labels = (features[:, 0] + .2 * features[:, 1] > 0).astype(int)
    rows = [{"set_id": str(i), "theme_id": 1} for i in range(100)]
    engine = PersonalEngine(rows, [r["set_id"] for r in rows], features, [], None)
    ratings = [{"user_id": "a", "set_id": str(i), "action": "like" if labels[i] else "dislike",
                "updated_at": str(i).zfill(3)} for i in range(80)]
    scores, mode, evidence = engine.scores("a", ratings)
    assert mode == "classifier_profile"
    assert evidence["roc_auc"] > evidence["profile_auc"] + .02
    assert all(0 <= row["classifier"] <= 1 for row in scores.values())
    # Cached fit is deterministic and never survives removed/insufficient labels.
    assert engine.scores("a", ratings) == (scores, mode, evidence)
    assert not engine.scores("a", ratings[:10])[2]["classifier_active"]
    assert engine.scores("other", ratings)[1] == "cold_start"
