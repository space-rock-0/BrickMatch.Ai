"""Leakage-aware split utilities and explicit binary ranking metrics."""
import math

import numpy as np


def ranking_metrics(recommended, relevant, k=5):
    if k < 1:
        raise ValueError("k must be positive")
    if len(recommended) != len(set(recommended)):
        raise ValueError("Recommendations contain duplicate IDs")
    truth = set(relevant)
    top = recommended[:k]
    hits = [int(item in truth) for item in top]
    count = sum(hits)
    dcg = sum(hit / math.log2(index + 2) for index, hit in enumerate(hits))
    ideal = sum(1 / math.log2(index + 2) for index in range(min(k, len(truth))))
    return {"precision_at_k": count / k, "recall_at_k": count / len(truth) if truth else None,
            "ndcg_at_k": dcg / ideal if ideal else None,
            "hit_rate_at_k": float(count > 0) if truth else None,
            "relevant_count": len(truth), "recommendation_count": len(top), "k": k}


def candidate_recall(candidates, relevant):
    truth = set(relevant)
    return len(set(candidates) & truth) / len(truth) if truth else None


def catalog_coverage(recommendation_lists, eligible_ids):
    eligible = set(eligible_ids)
    if not eligible:
        return None
    exposed = set().union(*(set(items) for items in recommendation_lists))
    if not exposed.issubset(eligible):
        raise ValueError("Recommendation outside eligible catalog")
    return len(exposed) / len(eligible)


def intra_list_diversity(vectors):
    values = np.asarray(vectors, dtype=float)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("Invalid diversity vectors")
    if len(values) < 2:
        return None
    norms = np.linalg.norm(values, axis=1)
    if np.any(norms == 0):
        raise ValueError("Zero diversity vector")
    unit = values / norms[:, None]
    distances = 1 - np.clip(unit @ unit.T, -1, 1)
    return float(distances[np.triu_indices(len(values), 1)].mean())


def temporal_split(ratings, train_fraction=.6, validation_fraction=.2):
    """Per-user split of unique first-label observations; reject repeated sets."""
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1 - train_fraction:
        raise ValueError("Invalid split fractions")
    groups = {}
    seen = set()
    for row in ratings:
        if row["action"] not in {"like", "dislike"}:
            continue
        key = (row["user_id"], row["set_id"])
        if key in seen:
            raise ValueError("Repeated user-set observations require an explicit correction policy")
        seen.add(key)
        groups.setdefault(row["user_id"], []).append(row)
    result = {"train": [], "validation": [], "test": [], "excluded_users": []}
    for user, rows in sorted(groups.items()):
        rows.sort(key=lambda row: (row["created_at"], row["set_id"]))
        train_end = int(len(rows) * train_fraction)
        validation_end = int(len(rows) * (train_fraction + validation_fraction))
        # Never split equal timestamps across partitions.
        while train_end < len(rows) and train_end > 0 and rows[train_end]["created_at"] == rows[train_end - 1]["created_at"]:
            train_end += 1
        validation_end = max(validation_end, train_end)
        while validation_end < len(rows) and validation_end > 0 and rows[validation_end]["created_at"] == rows[validation_end - 1]["created_at"]:
            validation_end += 1
        if train_end == 0 or validation_end == train_end or validation_end == len(rows):
            result["excluded_users"].append(user)
            continue
        result["train"].extend(rows[:train_end])
        result["validation"].extend(rows[train_end:validation_end])
        result["test"].extend(rows[validation_end:])
    return result
