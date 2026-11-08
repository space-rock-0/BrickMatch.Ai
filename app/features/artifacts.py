"""Validate and atomically save versioned vector/identity bundles."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import numpy as np


def validate_vectors(ids, vectors, expected_dimension=None):
    ids = list(ids)
    if any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("Set IDs must be nonempty strings")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate set IDs")
    if vectors.ndim != 2 or len(ids) != vectors.shape[0] or vectors.shape[1] == 0:
        raise ValueError("Vector shape does not match IDs")
    if expected_dimension is not None and vectors.shape[1] != expected_dimension:
        raise ValueError("Unexpected embedding dimension")
    if not np.isfinite(vectors).all():
        raise ValueError("Nonfinite vectors")
    if len(ids) and not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5):
        raise ValueError("Vectors must be unit normalized")


def save_bundle(path: Path, ids: list[str], vectors: np.ndarray, manifest: dict):
    validate_vectors(ids, vectors)
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {**manifest, "dimension": vectors.shape[1], "count": len(ids),
                "schema_version": "embedding-v1", "normalization": "l2", "dtype": "float32"}
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".npz")
    try:
        with os.fdopen(fd, "wb") as stream:
            np.savez(stream, set_ids=np.asarray(ids, dtype=str),
                     vectors=vectors.astype(np.float32), manifest=json.dumps(metadata, sort_keys=True))
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def load_bundle(path: Path, catalog_ids=None):
    with np.load(path, allow_pickle=False) as stored:
        ids = stored["set_ids"].tolist()
        vectors = stored["vectors"].copy()
        manifest = json.loads(str(stored["manifest"]))
    validate_vectors(ids, vectors, manifest["dimension"])
    if manifest["count"] != len(ids) or manifest["schema_version"] != "embedding-v1":
        raise ValueError("Incompatible manifest")
    if catalog_ids is not None and not set(ids).issubset(set(catalog_ids)):
        raise ValueError("Embedding IDs absent from catalog")
    return ids, vectors, manifest


def cache_key(image_hash: str, model: str, revision: str) -> str:
    return hashlib.sha256(json.dumps([image_hash, model, revision, "clip-processor-v1"],
                                     separators=(",", ":")).encode()).hexdigest()
