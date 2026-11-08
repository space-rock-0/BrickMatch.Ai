# Environment and phase gate

> **Later verification (2026-11-08):** the runner recovered after the blocked run
> recorded below. Catalog ingestion, image downloads, CPU CLIP embedding, per-profile
> classifier training, the test suite, and live browser checks were subsequently
> completed. Current measured state and remaining gaps are in `docs/operations.md` and
> `docs/experiments.md`. The historical failure details below are retained; the
> `scripts/preflight.py` result file was not recovered, so this report does not claim
> that the preflight gate artifact exists.

Phase 0 was initially blocked by execution infrastructure. No CLIP gate passed at that
time.

Python 3.11.13 and 122 dependencies installed successfully (installer exit 0),
including torch 2.15.0, transformers 4.57.6, faiss-cpu 1.15.1,
scikit-learn 1.9.1, FastAPI 0.162.2 and Streamlit 1.67.0.
The following command could not start because the execution helper reported
`helper_unknown_error: setup refresh had errors`:

```powershell
.venv\Scripts\python.exe scripts/preflight.py
```

This is a runner error before Python execution, not a CLIP test failure.
No lint, encoder, retrieval or unit tests ran. Dependency freezing also remains
pending. After the runner is restored, run:

```powershell
uv pip freeze --python .venv\Scripts\python.exe > requirements.txt
.venv\Scripts\python.exe scripts/preflight.py
.venv\Scripts\ruff.exe check scripts/preflight.py
```

Remove the machine-specific editable project entry from the frozen requirements
before committing. The preflight may require network approval for checkpoint download.

Measured hardware: Intel Core i5-1135G7 @ 2.40GHz; 8,211,918,848 bytes RAM
(7.65 GiB); Windows build 10.0.26300; D: free space 326,166,245,376 bytes
before dependencies finished. Python 3.11.13 was installed successfully.
GPU: Intel Iris Xe integrated graphics; the execution path explicitly uses CPU.

The workspace initially contained only the build plan and HTML brand reference.
`uv` is available; Python was absent from PATH. Python 3.11 installation is underway
inside `.uv-python`, with the project environment in `.venv`.
The sandbox denied CIM machine queries and external downloads. The Python download
was reissued with explicit elevated approval. CPU-only execution is required.

`scripts/preflight.py` writes actual encoder/retrieval results to
`docs/preflight_result.json` on success. A generated red image is only a compatibility
fixture, never catalog data or evaluation feedback.

## Architecture decision

Use a Python modular monolith, FastAPI, a static HTML/CSS/JS interface and SQLite. The
earlier Streamlit scaffold is retained only as legacy reference. Keep CLIP offline;
request-time recommendation paths load precomputed features.
Use normalized float32 vectors. Verify FAISS where installable, and always verify
the scikit-learn cosine nearest-neighbor fallback. Store raw data in `data/`, artifacts
in `artifacts/`, Hugging Face downloads in `.cache/huggingface/`; all are Git-ignored.
