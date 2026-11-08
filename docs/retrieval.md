# Phase 3 retrieval

Catalog baseline uses sorted canonical IDs; it does not claim popularity.
Visual search uses normalized float32 vectors: FAISS inner product and sklearn
cosine distance converted to similarity. The backend is explicit, allowing the tested
fallback to be selected when FAISS is unavailable. Both retrieve the full small catalog
before exclusions and deterministic ID tie-breaking; this favors correctness over
approximate search at the planned 500–1,000-set scale.

Metadata baseline uses Euclidean distance from the liked-item centroid in the
training-fitted feature space. Its score is 1/(1+distance). Unknown/no liked IDs use
the catalog baseline. Liked and explicitly excluded IDs are removed. Callers must
pass all current rated IDs for full exclusions. Candidate merging deduplicates IDs
while retaining separate visual/metadata score components.

Run `.venv\Scripts\python.exe -m pytest tests/test_features.py tests/test_retrieval.py`.
FAISS tests skip explicitly when unavailable. Real catalog retrieval is wired into the
API and served. Candidate recall has been measured only on simulated personas as part of
the evaluation table; there is no production latency or real-user candidate-recall
benchmark.
