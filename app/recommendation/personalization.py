"""Explicit per-user classifier fitting with low-data fallback."""
import hashlib
import json

import numpy as np
from sklearn.linear_model import LogisticRegression


def train_candidate(user_id, ids, features, ratings, feature_version, cutoff,
                    min_labels=12, min_per_class=3):
    if features.ndim != 2 or len(ids) != len(features) or len(ids) != len(set(ids)):
        raise ValueError("Invalid feature mapping")
    if not np.isfinite(features).all():
        raise ValueError("Nonfinite features")
    if min_labels < 2 or min_per_class < 1:
        raise ValueError("Invalid eligibility thresholds")
    mapping = {item: position for position, item in enumerate(ids)}
    eligible = [row for row in ratings if row["user_id"] == user_id
                and row["action"] in {"like", "dislike"}
                and row["updated_at"] <= cutoff and row["set_id"] in mapping]
    if len({row["set_id"] for row in eligible}) != len(eligible):
        raise ValueError("Training needs one current eligible rating per set")
    eligible.sort(key=lambda row: row["set_id"])
    labels = np.array([int(row["action"] == "like") for row in eligible])
    if len(labels) < min_labels or min(sum(labels == 0), sum(labels == 1)) < min_per_class:
        return None
    classifier = LogisticRegression(C=1, random_state=42, max_iter=1000)
    classifier.fit(features[[mapping[row["set_id"]] for row in eligible]], labels)
    snapshot = hashlib.sha256(json.dumps(eligible, sort_keys=True).encode()).hexdigest()
    return {"classifier": classifier, "user_id": user_id, "feature_version": feature_version,
            "feedback_cutoff": cutoff, "feedback_snapshot_sha256": snapshot,
            "training_count": len(eligible), "dimension": features.shape[1],
            "model_version": f"lr-{snapshot[:12]}-{feature_version}", "status": "candidate"}


def preference_scores(user_id, ids, features, ratings, candidate=None, feature_version=None):
    if features.ndim != 2 or len(ids) != len(features) or len(ids) != len(set(ids)):
        raise ValueError("Invalid feature mapping")
    if not np.isfinite(features).all():
        raise ValueError("Nonfinite features")
    if candidate is not None:
        if candidate["user_id"] != user_id or candidate["feature_version"] != feature_version:
            raise ValueError("Model identity or feature version mismatch")
        if candidate["dimension"] != features.shape[1]:
            raise ValueError("Model dimension mismatch")
        return candidate["classifier"].predict_proba(features)[:, 1], "classifier"
    liked = {row["set_id"] for row in ratings if row["user_id"] == user_id and row["action"] == "like"}
    positions = [position for position, item in enumerate(ids) if item in liked]
    if not positions:
        return np.zeros(len(ids)), "cold_start"
    profile = features[positions].mean(axis=0)
    return 1 / (1 + np.linalg.norm(features - profile, axis=1)), "profile"


def save_classifier(candidate, path):
    """Persist a trained classifier candidate to disk (joblib)."""
    from pathlib import Path

    import joblib
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(candidate, path)


def load_classifier(path):
    """Load a classifier candidate from disk; return None if missing/invalid."""
    from pathlib import Path

    import joblib
    p = Path(path)
    if not p.exists():
        return None
    try:
        cand = joblib.load(p)
        if not isinstance(cand, dict) or "classifier" not in cand:
            return None
        return cand
    except (OSError, ValueError, KeyError):
        return None
