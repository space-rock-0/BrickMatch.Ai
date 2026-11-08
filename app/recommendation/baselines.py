"""Transparent catalog and metadata-only baselines; no invented popularity."""
import numpy as np


def catalog_baseline(records, k=20, excluded=()):
    if not 1 <= k <= 1000:
        raise ValueError("k must be between 1 and 1000")
    blocked = set(excluded)
    ids = sorted({row["set_id"] for row in records} - blocked)
    return [{"set_id": item, "score": 0.0, "source": "catalog"} for item in ids[:k]]


def metadata_baseline(ids, values, liked_ids, k=20, excluded=()):
    if not 1 <= k <= 1000:
        raise ValueError("k must be between 1 and 1000")
    if len(ids) != len(set(ids)) or values.ndim != 2 or len(ids) != len(values):
        raise ValueError("Metadata mapping mismatch")
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite metadata")
    liked = set(liked_ids)
    indices = [index for index, item in enumerate(ids) if item in liked]
    if not indices:
        return catalog_baseline([{"set_id": item} for item in ids], k, excluded)
    profile = values[indices].mean(axis=0)
    # Euclidean distance on training-standardized metadata; 1/(1+d) is bounded.
    scores = 1 / (1 + np.linalg.norm(values - profile, axis=1))
    blocked = set(excluded) | liked
    candidates = [{"set_id": item, "score": float(score), "source": "metadata"}
                  for item, score in zip(ids, scores) if item not in blocked]
    return sorted(candidates, key=lambda row: (-row["score"], row["set_id"]))[:k]
