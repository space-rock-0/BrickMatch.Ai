"""Cosine retrieval with FAISS and sklearn backends and stable tie ordering."""
import numpy as np
from sklearn.neighbors import NearestNeighbors

from app.features.artifacts import validate_vectors


class VectorRetriever:
    def __init__(self, ids, vectors, backend="sklearn"):
        validate_vectors(ids, vectors)
        if not len(ids):
            raise ValueError("Cannot index an empty catalog")
        self.ids = list(ids)
        self.vectors = np.asarray(vectors, dtype=np.float32)
        self.backend = backend
        if backend == "faiss":
            import faiss
            self.index = faiss.IndexFlatIP(self.vectors.shape[1])
            self.index.add(self.vectors)
        elif backend == "sklearn":
            self.index = NearestNeighbors(metric="cosine").fit(self.vectors)
        else:
            raise ValueError("Unknown retrieval backend")

    def search(self, query, k=20, excluded=()):
        if not 1 <= k <= 1000:
            raise ValueError("k must be between 1 and 1000")
        query = np.asarray(query, dtype=np.float32)
        if query.shape != (self.vectors.shape[1],) or not np.isfinite(query).all():
            raise ValueError("Invalid query vector")
        norm = np.linalg.norm(query)
        if norm == 0:
            raise ValueError("Zero query vector")
        query = (query / norm)[None, :]
        # Small local catalogs: retrieve all to ensure exclusions and tie-breaks are exact.
        if self.backend == "faiss":
            scores, positions = self.index.search(query, len(self.ids))
        else:
            distances, positions = self.index.kneighbors(query, n_neighbors=len(self.ids))
            scores = 1 - distances
        blocked = set(excluded)
        candidates = [{"set_id": self.ids[position], "score": float(score),
                       "source": "visual"}
                      for position, score in zip(positions[0], scores[0])
                      if self.ids[position] not in blocked]
        candidates.sort(key=lambda row: (-row["score"], row["set_id"]))
        return candidates[:k]


def merge_candidates(*candidate_lists):
    merged = {}
    for candidates in candidate_lists:
        for candidate in candidates:
            set_id = candidate["set_id"]
            row = merged.setdefault(set_id, {"set_id": set_id, "signals": {}})
            source = candidate["source"]
            score = float(candidate["score"])
            if not np.isfinite(score):
                raise ValueError("Nonfinite candidate score")
            row["signals"][source] = max(score, row["signals"].get(source, -np.inf))
    return [merged[key] for key in sorted(merged)]
