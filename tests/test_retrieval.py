import numpy as np
import pytest

from app.recommendation.baselines import catalog_baseline, metadata_baseline
from app.recommendation.retrieval import VectorRetriever, merge_candidates


def test_visual_exclusions_and_stable_ties():
    retriever = VectorRetriever(["b", "a", "c"], np.array([[1., 0], [1., 0], [0., 1]]))
    assert [x["set_id"] for x in retriever.search([1, 0])] == ["a", "b", "c"]
    assert [x["set_id"] for x in retriever.search([1, 0], excluded=["a", "b"])] == ["c"]
    with pytest.raises(ValueError, match="Zero"):
        retriever.search([0, 0])


def test_faiss_matches_fallback():
    pytest.importorskip("faiss")
    values = np.eye(3, dtype=np.float32)
    a = VectorRetriever(["a", "b", "c"], values, "sklearn").search([1, 0, 0])
    b = VectorRetriever(["a", "b", "c"], values, "faiss").search([1, 0, 0])
    assert a == b


def test_catalog_and_metadata_exclude_rated():
    assert catalog_baseline([{"set_id": "b"}, {"set_id": "a"}], excluded=["a"])[0]["set_id"] == "b"
    result = metadata_baseline(["a", "b", "c"], np.array([[0., 0], [1., 0], [9., 0]]), ["a"])
    assert [row["set_id"] for row in result] == ["b", "c"]


def test_candidate_merge_retains_sources():
    result = merge_candidates([{"set_id": "a", "score": .5, "source": "visual"}],
                              [{"set_id": "a", "score": .8, "source": "metadata"}])
    assert result == [{"set_id": "a", "signals": {"visual": .5, "metadata": .8}}]
