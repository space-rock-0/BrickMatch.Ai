"""Offline local artifact validation and atomic promotion/rollback registry."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np

from app.data.ingest import atomic_json


def promote(registry_path, artifact_path, expected_feature_version, validation,
            min_ndcg=0., max_regression=.02, min_users=1):
    registry_path, artifact_path = Path(registry_path), Path(artifact_path)
    # joblib is for locally produced trusted model files only, never user uploads.
    candidate = joblib.load(artifact_path)
    if candidate["feature_version"] != expected_feature_version:
        raise ValueError("Feature version mismatch")
    if validation.get("split") != "validation" or validation.get("users", 0) < min_users:
        raise ValueError("Insufficient validation evidence")
    score = validation.get("ndcg_at_k")
    if score is None or not np.isfinite(score) or not min_ndcg <= score <= 1:
        raise ValueError("Candidate fails metric threshold")
    predictions = candidate["classifier"].predict_proba(np.zeros((1, candidate["dimension"])))
    if predictions.shape != (1, 2) or not np.isfinite(predictions).all() or not ((predictions >= 0) & (predictions <= 1)).all():
        raise ValueError("Invalid model predictions")
    previous = json.loads(registry_path.read_text()) if registry_path.exists() else {}
    current = previous.get("active")
    if current and current["user_id"] != candidate["user_id"]:
        raise ValueError("Registry belongs to a different user")
    if current and current["validation"].get("protocol_id") != validation.get("protocol_id"):
        raise ValueError("Cannot compare different validation protocols")
    if current and score < current["validation"]["ndcg_at_k"] - max_regression:
        raise ValueError("Candidate exceeds permitted regression")
    record = {"artifact_path": str(artifact_path.resolve()),
              "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
              "model_version": candidate["model_version"], "user_id": candidate["user_id"],
              "feature_version": expected_feature_version, "validation": validation}
    atomic_json(registry_path, {"active": record, "previous": current})
    return record


def rollback(registry_path):
    registry_path = Path(registry_path)
    registry = json.loads(registry_path.read_text())
    previous = registry.get("previous")
    if not previous:
        raise ValueError("No previous model")
    path = Path(previous["artifact_path"])
    if hashlib.sha256(path.read_bytes()).hexdigest() != previous["sha256"]:
        raise ValueError("Previous artifact checksum mismatch")
    joblib.load(path)
    atomic_json(registry_path, {"active": previous, "previous": registry["active"]})
    return previous


def log_experiment(parameters, metrics, tracking_uri="file:./mlruns"):
    import mlflow
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("brickmatch-offline")
    with mlflow.start_run() as run:
        mlflow.log_params(parameters)
        mlflow.log_metrics({key: value for key, value in metrics.items()
                            if value is not None and np.isfinite(value)})
        return run.info.run_id
