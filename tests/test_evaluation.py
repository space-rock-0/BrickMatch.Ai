import numpy as np
import pytest

from app.training.evaluate import (
    candidate_recall,
    catalog_coverage,
    intra_list_diversity,
    ranking_metrics,
    temporal_split,
)


def test_known_ranking_metrics_and_no_relevance():
    metrics = ranking_metrics(["a", "x", "b"], ["a", "b"], 3)
    assert metrics["precision_at_k"] == pytest.approx(2 / 3)
    assert metrics["recall_at_k"] == 1
    assert metrics["ndcg_at_k"] == pytest.approx(1.5 / (1 + 1 / np.log2(3)))
    assert ranking_metrics([], [], 5)["recall_at_k"] is None
    assert candidate_recall(["a"], ["a", "b"]) == .5
    assert catalog_coverage([["a"], ["a", "b"]], ["a", "b", "c"]) == pytest.approx(2 / 3)
    assert intra_list_diversity(np.eye(2)) == 1


def test_temporal_split_has_strict_cutoffs_and_disjoint_sets():
    rows = [{"user_id": "a", "set_id": str(i), "created_at": f"2026-01-{i + 1:02d}",
             "action": "like"} for i in range(10)]
    split = temporal_split(rows)
    assert [len(split[name]) for name in ["train", "validation", "test"]] == [6, 2, 2]
    assert max(row["created_at"] for row in split["train"]) < min(row["created_at"] for row in split["validation"])
    assert not ({row["set_id"] for row in split["train"]} & {row["set_id"] for row in split["test"]})
    with pytest.raises(ValueError, match="Repeated"):
        temporal_split(rows + [rows[0]])


def test_equal_timestamps_are_not_split():
    rows = [{"user_id": "a", "set_id": str(i), "created_at": "2026-01-01", "action": "like"}
            for i in range(10)]
    assert temporal_split(rows)["excluded_users"] == ["a"]
