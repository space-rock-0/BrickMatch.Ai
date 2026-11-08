import numpy as np
import pytest

from app.recommendation.feedback import FeedbackStore
from app.recommendation.personalization import preference_scores, train_candidate
from app.recommendation.ranking import rank_candidates


def test_feedback_persists_corrects_undoes_and_isolates(tmp_path):
    path = tmp_path / "feedback.db"
    store = FeedbackStore(path)
    store.record("a", "set", "like")
    store.record("b", "set", "dislike")
    store.record("a", "set", "skip")
    assert FeedbackStore(path).current("a")[0]["action"] == "skip"
    store.record("a", "set", "undo")
    assert store.current("a") == []
    assert store.current("b")[0]["action"] == "dislike"
    assert len(store.history("a")) == 3


def test_training_filters_user_cutoff_and_skips():
    ids = [str(i) for i in range(12)]
    features = np.eye(12)
    ratings = [{"user_id": "a", "set_id": item, "action": "like" if i < 6 else "dislike",
                "updated_at": "2026-01-01"} for i, item in enumerate(ids)]
    assert train_candidate("b", ids, features, ratings, "v1", "2027") is None
    assert train_candidate("a", ids, features, ratings, "v1", "2025") is None
    model = train_candidate("a", ids, features, ratings, "v1", "2027")
    assert model["training_count"] == 12
    values, mode = preference_scores("a", ids, features, ratings, model, "v1")
    assert mode == "classifier" and np.isfinite(values).all()
    with pytest.raises(ValueError, match="identity"):
        preference_scores("b", ids, features, ratings, model, "v1")


def test_cold_start_and_ranking_exclusions_diversity():
    values, mode = preference_scores("new", ["a", "b"], np.eye(2), [])
    assert mode == "cold_start" and not values.any()
    catalog = {item: {"theme_id": 1} for item in ["a", "b", "c"]}
    candidates = [{"set_id": item, "signals": {"metadata": .8}} for item in catalog]
    result = rank_candidates(candidates, catalog, rated_ids=["a"], theme_cap=1)
    assert [row["set_id"] for row in result] == ["b"]
    assert "0.800" in result[0]["explanations"][0]
