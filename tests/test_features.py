import numpy as np
import pytest

from app.features.artifacts import cache_key, load_bundle, save_bundle, validate_vectors
from app.features.metadata import fit_metadata, transform_metadata


def test_bundle_roundtrip_and_catalog_mapping(tmp_path):
    path = tmp_path / "vectors.npz"
    save_bundle(path, ["a", "b"], np.eye(2, dtype=np.float32), {"model": "fixture"})
    ids, values, metadata = load_bundle(path, ["a", "b", "c"])
    assert ids == ["a", "b"]
    np.testing.assert_array_equal(values, np.eye(2))
    assert metadata["count"] == 2
    with pytest.raises(ValueError, match="absent"):
        load_bundle(path, ["a"])


@pytest.mark.parametrize("ids,values", [(["a", "a"], np.eye(2)),
                                          (["a"], np.array([[float("nan"), 0]])),
                                          (["a"], np.array([[2., 0]])),
                                          (["a"], np.eye(2))])
def test_invalid_embeddings_rejected(ids, values):
    with pytest.raises(ValueError):
        validate_vectors(ids, values)


def test_cache_invalidated_by_source_or_model_revision():
    assert cache_key("x", "m", "r") == cache_key("x", "m", "r")
    assert cache_key("x", "m", "r") != cache_key("y", "m", "r")
    assert cache_key("x", "m", "r") != cache_key("x", "m", "s")


def test_unseen_theme_does_not_refit_training_preprocessor():
    training = [{"set_id": "a", "theme_id": 1, "year": 2000, "num_parts": 10},
                {"set_id": "b", "theme_id": 2, "year": 2020, "num_parts": 100}]
    transformer = fit_metadata(training)
    before = transformer.named_transformers_["numeric"].mean_.copy()
    ids, values = transform_metadata(transformer, [
        {"set_id": "new", "theme_id": 999, "year": 2025, "num_parts": 900}])
    assert ids == ["new"] and np.isfinite(values).all()
    np.testing.assert_array_equal(transformer.named_transformers_["numeric"].mean_, before)
    np.testing.assert_array_equal(values[0, :2], [0, 0])
