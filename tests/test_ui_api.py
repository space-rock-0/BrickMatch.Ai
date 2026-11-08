import json

from fastapi.testclient import TestClient

from app.main import create_app


def catalog_file(tmp_path):
    source = tmp_path / "catalog.json"
    source.write_text(json.dumps([
        {"set_id": "b-1", "name": "Blue Rocket", "year": 2022, "num_parts": 300,
         "theme_id": 2, "theme": "Space"},
        {"set_id": "a-1", "name": "Apple Farm", "year": 2018, "num_parts": 100,
         "theme_id": 1, "theme": "Farm"},
        {"set_id": "c-1", "name": "Castle", "year": 2020, "num_parts": 900,
         "theme_id": 1, "theme": "Farm"},
    ]), encoding="utf-8")
    return source


def test_bootstrap_themes_and_served_ui_shell(tmp_path):
    client = TestClient(create_app(catalog_file(tmp_path), tmp_path / "db.sqlite"))
    themes = client.get("/api/v1/themes").json()["items"]
    assert themes[0] == {"theme_id": 1, "theme": "Farm", "count": 2}

    boot = client.get("/api/v1/bootstrap").json()
    assert boot["catalog_count"] == 3
    assert boot["themes"] == themes
    assert boot["model"]["catalog_count"] == 3

    page = client.get("/")
    assert page.status_code == 200
    assert "BrickMatch" in page.text
    assert client.get("/assets/styles.css").status_code == 200
    assert client.get("/assets/app.js").status_code == 200


def test_users_summary_and_enriched_feedback(tmp_path):
    client = TestClient(create_app(catalog_file(tmp_path), tmp_path / "db.sqlite"))
    assert client.get("/api/v1/users").json()["items"] == []
    assert client.post("/api/v1/feedback", json={
        "user_id": "a", "set_id": "a-1", "action": "like"}).status_code == 201

    feedback = client.get("/api/v1/users/a/feedback").json()
    assert feedback["current"][0]["set"]["name"] == "Apple Farm"

    summary = client.get("/api/v1/users/a/summary").json()
    assert summary["counts"]["like"] == 1
    assert summary["top_themes"] == [{"theme": "Farm", "count": 1}]

    users = client.get("/api/v1/users").json()["items"]
    assert users == [{"user_id": "a", "ratings": 1}]


def test_set_sorting_filters_and_evaluation_report(tmp_path):
    client = TestClient(create_app(catalog_file(tmp_path), tmp_path / "db.sqlite"))
    data = client.get("/api/v1/sets?sort=parts_desc&limit=2").json()
    assert [row["set_id"] for row in data["items"]] == ["c-1", "b-1"]
    assert client.get("/api/v1/sets?min_parts=500").json()["total"] == 1
    assert client.get("/api/v1/sets?max_year=2019").json()["total"] == 1
    assert client.get("/api/v1/sets?has_image=false").json()["total"] == 3

    evaluation = client.get("/api/v1/evaluation").json()
    assert "available" in evaluation
    assert "data" in evaluation


def test_image_serving_uses_verified_manifest_and_media_type(tmp_path):
    catalog_file(tmp_path)
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "a.img").write_bytes(b"\xff\xd8\xff\xd9")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.jpg"
    outside.write_bytes(b"\xff\xd8\xff\xd9")
    manifest = [
        {"set_id": "a-1", "status": "downloaded", "path": "images/a.img",
         "source_url": "https://example.invalid/a.jpg"},
        {"set_id": "b-1", "status": "downloaded", "path": f"../{outside.name}",
         "source_url": "https://example.invalid/b.jpg"},
    ]
    (tmp_path / "image_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    client = TestClient(create_app(tmp_path / "catalog.json", tmp_path / "db.sqlite"))

    image = client.get("/api/v1/images/a-1")
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/jpeg"
    assert image.headers["cache-control"] == "public, max-age=86400"

    # A manifest path that escapes the catalog directory must never be served.
    assert client.get("/api/v1/images/b-1").status_code == 404
    outside.unlink()


def test_profile_ids_cannot_escape_the_classifier_directory(tmp_path):
    client = TestClient(create_app(catalog_file(tmp_path), tmp_path / "db.sqlite"))
    bad_ids = ["bad!id", "..%5Csecret"]
    for user_id in bad_ids:
        assert client.get(
            f"/api/v1/users/{user_id}/recommendations").status_code == 422
        assert client.get(f"/api/v1/users/{user_id}/feedback").status_code == 422
        assert client.get(f"/api/v1/users/{user_id}/summary").status_code == 422
        assert client.post(f"/api/v1/users/{user_id}/retraining").status_code == 422

    # An encoded slash is normalized before routing; it must not reach a handler.
    assert client.get(
        "/api/v1/users/..%2Fsecret/recommendations").status_code in (404, 422)

    assert client.post("/api/v1/feedback", json={
        "user_id": "../escape", "set_id": "a-1", "action": "like"}).status_code == 422
