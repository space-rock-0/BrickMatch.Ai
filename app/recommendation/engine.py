"""Account-scoped online profiles and conservatively gated personal classifiers.

No demo artifacts are loaded. A bounded cache is keyed by the exact current feedback;
undo and corrections therefore invalidate a model, including after a restart.
"""
from collections import OrderedDict
from threading import Lock

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score


def normalized(matrix):
    return matrix / np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-8)


def featured_catalog(catalog):
    """Interleave themes; prefer pictured, substantial, recent builds within each theme."""
    ordered = sorted(catalog, key=lambda x: (
        not x.get("image_available", False), x["num_parts"] < 20,
        -x["year"], -x["num_parts"], x["set_id"]))
    counts = {}
    ranked = []
    for index, item in enumerate(ordered):
        theme = item["theme_id"]
        position = counts.get(theme, 0)
        counts[theme] = position + 1
        ranked.append((position, index, item))
    return [item for _, _, item in sorted(ranked, key=lambda x: x[:2])]


class PersonalEngine:
    def __init__(self, catalog, ids, metadata, visual_ids, visual_vectors):
        self.ids = ids
        self.index = {sid: i for i, sid in enumerate(ids)}
        self.catalog = {x["set_id"]: x for x in catalog}
        self.metadata = normalized(metadata) if metadata is not None else np.empty((0, 0))
        self.visual = np.zeros((len(ids), visual_vectors.shape[1] if visual_vectors is not None else 0))
        if visual_vectors is not None:
            for sid, vector in zip(visual_ids, visual_vectors):
                if sid in self.index:
                    self.visual[self.index[sid]] = vector
            self.visual = normalized(self.visual)
        self.features = np.concatenate([self.metadata, self.visual], axis=1)
        self.cache = OrderedDict()
        self.lock = Lock()

    def scores(self, user_id, ratings):
        labels = sorted([r for r in ratings if r["user_id"] == user_id
                         and r["set_id"] in self.index and r["action"] in {"like", "dislike"}],
                        key=lambda r: (r["updated_at"], r["set_id"]))
        positive = [self.index[r["set_id"]] for r in labels if r["action"] == "like"]
        negative = [self.index[r["set_id"]] for r in labels if r["action"] == "dislike"]
        status = {"labels": len(labels), "likes": len(positive), "dislikes": len(negative),
                  "classifier_active": False, "reason": "Needs 24 ratings, including 6 of each kind"}
        if not labels:
            return {}, "cold_start", status

        def profile(matrix):
            pos = matrix @ matrix[positive].mean(axis=0) if positive else np.zeros(len(self.ids))
            neg = matrix @ matrix[negative].mean(axis=0) if negative else np.zeros(len(self.ids))
            return np.clip((pos - .65 * neg + 1) / 2, 0, 1)

        signals = {"metadata": profile(self.metadata)}
        if self.visual.shape[1]:
            signals["visual"] = profile(self.visual)
        mode = "hybrid_profile" if "visual" in signals else "metadata_profile"
        key = (user_id, tuple((r["set_id"], r["action"], r["updated_at"]) for r in labels))
        if len(labels) >= 24 and min(len(positive), len(negative)) >= 6:
            with self.lock:
                cached = self.cache.get(key)
                if cached is None:
                    cached = self.fit_validated(labels)
                    self.cache[key] = cached
                    while len(self.cache) > 128:
                        self.cache.popitem(last=False)
                else:
                    self.cache.move_to_end(key)
            probabilities, evidence = cached
            status.update(evidence)
            if probabilities is not None:
                signals["classifier"] = probabilities
                mode = "classifier_profile"
                status["classifier_active"] = True
        return {sid: {name: float(values[i]) for name, values in signals.items()}
                for i, sid in enumerate(self.ids)}, mode, status

    def fit_validated(self, labels):
        positions = [self.index[r["set_id"]] for r in labels]
        y = np.array([int(r["action"] == "like") for r in labels])
        split = int(len(labels) * .75)
        train_y, test_y = y[:split], y[split:]
        if min(np.bincount(train_y, minlength=2)) < 3 or min(np.bincount(test_y, minlength=2)) < 2:
            return None, {"reason": "Latest holdout needs both likes and dislikes"}
        model = LogisticRegression(C=.5, class_weight="balanced", max_iter=500, random_state=42)
        x = self.features[positions]
        model.fit(x[:split], train_y)
        probabilities = model.predict_proba(x[split:])[:, 1]
        auc = float(roc_auc_score(test_y, probabilities))
        balanced = float(balanced_accuracy_score(test_y, probabilities >= .5))
        # Compare against the same profile using ONLY earlier ratings.
        baseline_scores = np.zeros(len(test_y))
        for matrix, weight in ((self.metadata, .4), (self.visual, .3)):
            if not matrix.shape[1]:
                continue
            train = matrix[positions[:split]]
            pos, neg = train[train_y == 1].mean(axis=0), train[train_y == 0].mean(axis=0)
            baseline_scores += weight * np.clip((matrix[positions[split:]] @ (pos - .65 * neg) + 1) / 2, 0, 1)
        baseline_auc = float(roc_auc_score(test_y, baseline_scores))
        evidence = {"holdout_count": len(test_y), "roc_auc": auc,
                    "balanced_accuracy": balanced, "profile_auc": baseline_auc,
                    "reason": "Classifier did not beat the profile on recent held-out ratings"}
        if auc < .65 or balanced < .6 or auc < baseline_auc + .02:
            return None, evidence
        model.fit(x, y)
        evidence["reason"] = "Validated on recent ratings; refitted to current feedback"
        return model.predict_proba(self.features)[:, 1], evidence
