import json

import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from app.training.promotion import promote, rollback


def test_failed_promotion_preserves_active_and_rollback(tmp_path):
    classifier = LogisticRegression().fit([[0], [1], [2], [3]], [0, 0, 1, 1])
    candidate = {"classifier": classifier, "dimension": 1, "feature_version": "v1",
                 "user_id": "a", "model_version": "one"}
    first, second, registry = tmp_path / "one.joblib", tmp_path / "two.joblib", tmp_path / "registry.json"
    joblib.dump(candidate, first)
    validation = {"split": "validation", "users": 1, "ndcg_at_k": .7, "protocol_id": "fixture"}
    promote(registry, first, "v1", validation)
    initial = registry.read_bytes()
    with pytest.raises(ValueError):
        promote(registry, first, "v1", {**validation, "ndcg_at_k": np.nan})
    assert registry.read_bytes() == initial
    candidate["model_version"] = "two"
    joblib.dump(candidate, second)
    promote(registry, second, "v1", {**validation, "ndcg_at_k": .8})
    rollback(registry)
    assert json.loads(registry.read_text())["active"]["model_version"] == "one"
