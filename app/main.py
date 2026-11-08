"""FastAPI application for local development and authenticated deployment."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.auth import hash_password, verify_password
from app.features.artifacts import load_bundle
from app.features.metadata import fit_metadata, transform_metadata
from app.recommendation.engine import PersonalEngine, featured_catalog
from app.recommendation.feedback import FeedbackStore
from app.recommendation.ranking import rank_candidates
from app.recommendation.retrieval import VectorRetriever

USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


class FeedbackRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    set_id: str = Field(min_length=1, max_length=80)
    action: Literal["like", "dislike", "skip", "undo"]


class AuthRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(min_length=10, max_length=200)


class PasswordRequest(BaseModel):
    current_password: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


def create_app(catalog_path=None, database_path=None):
    app = FastAPI(title="BrickMatch AI", version="0.1.0")
    source = Path(catalog_path or os.getenv("BRICKMATCH_CATALOG", "data/processed/catalog.json"))
    catalog = json.loads(source.read_text(encoding="utf-8")) if source.exists() else []
    by_id = {item["set_id"]: item for item in catalog}
    image_manifest = source.parent / "image_manifest.json"
    image_rows = json.loads(image_manifest.read_text(encoding="utf-8")) if image_manifest.exists() else []
    images = {row["set_id"]: row for row in image_rows if row["status"] == "downloaded"}
    for item in catalog:
        item["image_available"] = item["set_id"] in images
    if len(by_id) != len(catalog):
        raise ValueError("Duplicate catalog IDs")
    store = FeedbackStore(database_path or os.getenv("BRICKMATCH_DB", "data/brickmatch.db"))
    auth_required = os.getenv("BRICKMATCH_AUTH_REQUIRED", "false").lower() == "true"
    dummy_password = hash_password("unused-login-timing-padding")
    rate_limit = int(os.getenv("BRICKMATCH_RATE_LIMIT_PER_MINUTE", "120"))
    request_times = defaultdict(deque)
    values = None
    ids = []
    if catalog:
        # Serving baseline only. Offline evaluation fits its own train-only transformer.
        ids, values = transform_metadata(fit_metadata(catalog), catalog)
    counters = {"recommendation_requests": 0, "last_recommendation_ms": None}
    visual_ids, visual_vectors, retriever = [], None, None
    visual_path = os.getenv("BRICKMATCH_EMBEDDINGS")
    if visual_path:
        visual_ids, visual_vectors, _ = load_bundle(Path(visual_path), by_id)
        if visual_ids:
            retriever = VectorRetriever(visual_ids, visual_vectors)
    engine = PersonalEngine(catalog, ids, values, visual_ids, visual_vectors)
    featured = featured_catalog(catalog)
    featured_positions = {row["set_id"]: i for i, row in enumerate(featured)}
    ui_dir = Path(os.getenv("BRICKMATCH_UI_DIR",
                            str(Path(__file__).resolve().parents[1] / "frontend" / "web")))
    evaluation_path = Path(os.getenv(
        "BRICKMATCH_EVALUATION",
        str(Path(__file__).resolve().parents[1] / "data" / "evaluation_results.json")))
    evaluation = None
    if evaluation_path.is_file():
        try:
            evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            evaluation = None
    origins = [value.strip() for value in
               os.getenv("BRICKMATCH_CORS_ORIGINS", "*").split(",") if value.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def limit_requests(request: Request, call_next):
        if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/v1/images/") and request.url.path not in {
            "/api/v1/health/live", "/api/v1/health/ready"}:
            now = time.monotonic()
            for stale in [key for key, times in request_times.items()
                          if not times or now - times[-1] > 60]:
                del request_times[stale]
            key = request.client.host if request.client else "unknown"
            bucket = request_times[key]
            while bucket and now - bucket[0] > 60:
                bucket.popleft()
            if len(bucket) >= rate_limit:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429,
                                    headers={"Retry-After": "60"})
            bucket.append(now)
        if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
            origin = request.headers.get("origin")
            expected = str(request.base_url).rstrip("/")
            if origin and origin != expected and origin not in [x for x in origins if x != "*"]:
                from fastapi.responses import JSONResponse
                return JSONResponse({"detail": "Cross-origin write rejected"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/v1/images/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def authenticated_user(request: Request) -> str | None:
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else request.cookies.get("brickmatch_session")
        return store.session_user(token)

    def require_user(request: Request, user_id: str):
        if not auth_required:
            return user_id
        current = authenticated_user(request)
        if current is None or current != user_id:
            raise HTTPException(401, "Authentication required")
        return current

    def theme_payload():
        counts: dict[tuple[int, str], int] = {}
        for entry in catalog:
            key = (entry["theme_id"], entry["theme"])
            counts[key] = counts.get(key, 0) + 1
        items = [{"theme_id": theme_id, "theme": name, "count": count}
                 for (theme_id, name), count in counts.items()]
        items.sort(key=lambda row: (-row["count"], row["theme"].casefold()))
        return items

    def model_info():
        clf_active = False
        return {"mode": "classifier_profile" if clf_active else (
                    "hybrid_profile" if retriever is not None else "metadata_baseline"),
                "model_version": "personal-feedback-v2",
                "classifier_policy": "Per-account holdout gate; demo models never served",
                "feature_version": "metadata-v1", "classifier_active": clf_active,
                "visual_features_active": retriever is not None,
                "catalog_count": len(catalog), "images_available": len(images),
                "dataset_version": source.parent.name, "evaluation": evaluation}

    def with_set(rows):
        return [{**row, "set": by_id.get(row["set_id"])} for row in rows]

    def checked_user(user_id: str) -> str:
        """Reject path-like profile ids before they reach the classifier filesystem."""
        if not USER_ID_PATTERN.fullmatch(user_id):
            raise HTTPException(422, "Invalid profile id")
        return user_id

    @app.get("/api/v1/sets")
    def sets(q: str = Query("", max_length=200), theme: int | None = None,
             min_year: int = Query(1949, ge=1949, le=2200),
             max_year: int = Query(2200, ge=1949, le=2200),
             min_parts: int = Query(0, ge=0, le=100000),
             max_parts: int = Query(100000, ge=0, le=100000),
             has_image: bool | None = None,
             sort: Literal["featured", "set_id", "name", "year_desc", "year_asc",
                           "parts_desc", "parts_asc"] = Query("featured"),
             offset: int = Query(0, ge=0), limit: int = Query(24, ge=1, le=100)):
        filtered = [item for item in catalog if q.casefold() in item["name"].casefold()
                    and (theme is None or item["theme_id"] == theme)
                    and min_year <= item["year"] <= max_year
                    and min_parts <= item["num_parts"] <= max_parts
                    and (has_image is None or item["image_available"] == has_image)]
        sorters = {
            "featured": lambda row: featured_positions[row["set_id"]],
            "set_id": lambda row: row["set_id"],
            "name": lambda row: (row["name"].casefold(), row["set_id"]),
            "year_desc": lambda row: (-row["year"], row["set_id"]),
            "year_asc": lambda row: (row["year"], row["set_id"]),
            "parts_desc": lambda row: (-row["num_parts"], row["set_id"]),
            "parts_asc": lambda row: (row["num_parts"], row["set_id"]),
        }
        filtered.sort(key=sorters[sort])
        return {"items": filtered[offset:offset + limit], "total": len(filtered),
                "offset": offset, "limit": limit, "sort": sort}

    @app.get("/api/v1/sets/{set_id}")
    def get_set(set_id: str):
        if set_id not in by_id:
            raise HTTPException(404, "Unknown set ID")
        return by_id[set_id]

    @app.get("/api/v1/themes")
    def themes():
        return {"items": theme_payload()}

    @app.get("/api/v1/users")
    def users(request: Request):
        if auth_required:
            user_id = authenticated_user(request)
            if user_id is None:
                raise HTTPException(401, "Authentication required")
            return {"items": [{"user_id": user_id, "ratings": len(store.current(user_id))}]}
        return {"items": store.users()}

    @app.get("/api/v1/bootstrap")
    def bootstrap():
        return {"catalog_count": len(catalog), "dataset_version": source.parent.name,
                "images_available": len(images), "themes": theme_payload(),
                "users": [] if auth_required else store.users(), "model": model_info(),
                "evaluation": evaluation, "auth_required": auth_required}

    @app.post("/api/v1/auth/register", status_code=201)
    def register(body: AuthRequest, response: Response, request: Request):
        if not store.allow_auth_attempt(request.client.host if request.client else "unknown"):
            raise HTTPException(429, "Too many sign-in attempts. Try again in a minute.", headers={"Retry-After": "60"})
        try:
            password_hash = hash_password(body.password)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        created = store.create_user(body.user_id, password_hash, datetime.now(UTC).isoformat())
        if not created:
            raise HTTPException(409, "Profile already exists")
        token = store.create_session(body.user_id)
        response.set_cookie("brickmatch_session", token, httponly=True,
                            secure=request.url.scheme == "https", samesite="strict", max_age=604800,
                            path="/api")
        return {"user_id": body.user_id, "token": token}

    @app.post("/api/v1/auth/login")
    def login(body: AuthRequest, response: Response, request: Request):
        if not store.allow_auth_attempt(request.client.host if request.client else "unknown"):
            raise HTTPException(429, "Too many sign-in attempts. Try again in a minute.", headers={"Retry-After": "60"})
        user = store.get_user(body.user_id)
        valid = verify_password(body.password, user["password_hash"] if user else dummy_password)
        if user is None or not valid:
            raise HTTPException(401, "Invalid credentials")
        token = store.create_session(body.user_id)
        response.set_cookie("brickmatch_session", token, httponly=True,
                            secure=request.url.scheme == "https", samesite="strict", max_age=604800,
                            path="/api")
        return {"user_id": body.user_id, "token": token}

    @app.post("/api/v1/auth/logout")
    def logout(request: Request, response: Response):
        header = request.headers.get("authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else request.cookies.get("brickmatch_session", "")
        store.revoke_session(token)
        response.delete_cookie("brickmatch_session", path="/api")
        return {"status": "signed_out"}

    @app.get("/api/v1/auth/me")
    def me(request: Request):
        user_id = authenticated_user(request)
        if user_id is None:
            raise HTTPException(401, "Authentication required")
        return {"user_id": user_id}

    @app.post("/api/v1/auth/password")
    def change_password(body: PasswordRequest, request: Request, response: Response):
        user_id = authenticated_user(request)
        if user_id is None:
            raise HTTPException(401, "Authentication required")
        if not store.allow_auth_attempt(request.client.host if request.client else "unknown"):
            raise HTTPException(429, "Too many attempts. Try again in a minute.")
        user = store.get_user(user_id)
        if not verify_password(body.current_password, user["password_hash"]):
            raise HTTPException(401, "Current password is incorrect")
        with store.connect() as db:
            store.exec(db, "UPDATE app_users SET password_hash=? WHERE user_id=?",
                       (hash_password(body.new_password), user_id))
            store.exec(db, "DELETE FROM app_sessions WHERE user_id=?", (user_id,))
        response.delete_cookie("brickmatch_session", path="/api")
        return {"status": "password_changed", "message": "Sign in again on all devices"}

    @app.get("/api/v1/evaluation")
    def evaluation_summary():
        return {"available": evaluation is not None, "data": evaluation}

    @app.post("/api/v1/feedback", status_code=201)
    def feedback(body: FeedbackRequest, request: Request):
        require_user(request, body.user_id)
        if body.set_id not in by_id:
            raise HTTPException(404, "Unknown set ID")
        return store.record(body.user_id, body.set_id, body.action)

    @app.get("/api/v1/images/{set_id}")
    def image(set_id: str):
        item = images.get(set_id)
        if item is None:
            raise HTTPException(404, "No verified local image")
        root = source.parent.resolve()
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise HTTPException(404, "Local image missing")
        media_type, _ = mimetypes.guess_type(item.get("source_url") or item["path"])
        return FileResponse(path, media_type=media_type or "application/octet-stream",
                            headers={"Cache-Control": "public, max-age=86400"})

    @app.get("/api/v1/users/{user_id}/feedback")
    def user_feedback(user_id: str, request: Request):
        user_id = checked_user(user_id)
        require_user(request, user_id)
        return {"current": with_set(store.current(user_id)),
                "events": with_set(store.history(user_id))}

    @app.get("/api/v1/users/{user_id}/summary")
    def user_summary(user_id: str, request: Request):
        user_id = checked_user(user_id)
        require_user(request, user_id)
        current = store.current(user_id)
        counts = {"like": 0, "dislike": 0, "skip": 0}
        theme_counts: dict[str, int] = {}
        for row in current:
            action = row["action"]
            if action in counts:
                counts[action] += 1
            if action == "like" and row["set_id"] in by_id:
                theme = by_id[row["set_id"]]["theme"]
                theme_counts[theme] = theme_counts.get(theme, 0) + 1
        top = sorted(theme_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
        return {"user_id": user_id, "counts": counts, "total": len(current),
                "top_themes": [{"theme": theme, "count": count} for theme, count in top]}

    @app.get("/api/v1/users/{user_id}/recommendations")
    def recommendations(user_id: str, request: Request, k: int = Query(10, ge=1, le=100),
                        theme_cap: int | None = Query(None, ge=1, le=100)):
        user_id = checked_user(user_id)
        require_user(request, user_id)
        start = time.perf_counter()
        ratings = store.current(user_id)
        excluded = {item["set_id"] for item in ratings}
        signals, mode, learning = engine.scores(user_id, ratings)
        candidates = [{"set_id": sid, "signals": values} for sid, values in signals.items()]
        ranked = rank_candidates(candidates, by_id, excluded, k,
                                 weights={"metadata": .4, "visual": .3, "classifier": .3},
                                 theme_cap=theme_cap or max(2, (k + 3) // 4))
        for row in ranked:
            row["explanations"] = [
                "Based on your likes and dislikes in theme, size and build era",
                *(["Includes visual similarity to your feedback"] if "visual" in row["signals"] else []),
                *(["Personal classifier passed the recent-rating validation gate"]
                  if learning["classifier_active"] else []),
            ]
        for row in ranked:
            row["set"] = by_id[row["set_id"]]
        counters["recommendation_requests"] += 1
        counters["last_recommendation_ms"] = (time.perf_counter() - start) * 1000
        mv = "personal-feedback-v2"
        return {"items": ranked, "mode": mode, "learning": learning,
                "onboarding": mode == "cold_start",
                "model_version": mv, "feature_version": "metadata-v1",
                "dataset_version": source.parent.name, "generated_at": datetime.now(UTC).isoformat()}

    @app.post("/api/v1/users/{user_id}/retraining")
    def retrain(user_id: str, request: Request):
        checked_user(user_id)
        require_user(request, user_id)
        raise HTTPException(403, "Training is offline only; candidate evaluation and promotion are required")

    @app.get("/api/v1/models/current")
    def models(request: Request):
        result = model_info()
        user_id = authenticated_user(request)
        if user_id:
            _, mode, learning = engine.scores(user_id, store.current(user_id))
            result.update(mode=mode, classifier_active=learning["classifier_active"], learning=learning)
        return result

    @app.get("/api/v1/health/live")
    def live():
        return {"status": "live"}

    @app.get("/api/v1/health/ready")
    def ready():
        with store.connect() as db:
            db.execute("SELECT 1")
        if not catalog:
            raise HTTPException(503, "Catalog missing or empty; ingest data and set BRICKMATCH_CATALOG")
        return {"status": "ready", "catalog_count": len(catalog)}

    @app.get("/api/v1/metrics")
    def metrics():
        return counters

    if ui_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="ui")

    return app


app = create_app()
