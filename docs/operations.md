# Operations and release status

## Run locally

```powershell
$env:BRICKMATCH_CATALOG = "data/processed/78b8926d0b520375/catalog.json"
$env:BRICKMATCH_EMBEDDINGS = "artifacts/embeddings/clip.npz"
$env:BRICKMATCH_CLASSIFIER_DIR = "artifacts/models"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>. FastAPI serves both the API and the static interface
from `frontend/web/`. There is no second UI process. Legacy Streamlit is not part of the
product path.

Local development profiles use aliases. Production enables signed bearer authentication
with `BRICKMATCH_AUTH_REQUIRED=true` and stores feedback in PostgreSQL. A readiness
failure with 503 means the catalog path is missing or empty.

## Checks

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\ruff.exe check app frontend tests
node --check frontend/web/assets/app.js
```

CI runs the Python checks on Windows. The UI checks in `tests/test_ui_api.py` use a
temporary catalog and SQLite file; they do not need CLIP or the production database.

## Current measured state

- Catalog: 500 sets; dataset version `78b8926d0b520375`.
- Images: 486 downloaded, 14 missing, served through `/api/v1/images/{set_id}`.
- CLIP: 485 normalized float32 vectors, 512 dimensions, CPU only.
- Classifiers: 30 per-profile joblib artifacts under `artifacts/models/`.
- Feedback at the time of writing: 1,204 events and 1,197 current ratings across 30
  local profiles. `builder` has 83 current ratings: 56 likes, 20 dislikes, 7 skips.
- Evaluation: 30 simulated personas. Best classifier P@10 = 0.0633, HR@10 = 0.4333.
  These are not real-user results; the table uses its original evaluation snapshot.
- Interface: exercised in a browser at 390, 768, 800, and 1440px with no horizontal
  overflow. Discover, Swipe, For You, My Taste, Model Lab, System, filters, pagination,
  profile switching, feedback, and undo were checked against the real API.

## Training and promotion

Training is offline:

```powershell
.venv\Scripts\python scripts\train_classifier.py
```

The API never trains on a feedback write, and the retraining endpoint returns 403.
`app.training.promotion` provides local artifact validation, checksums, atomic
active/previous pointers, metric thresholds, and rollback. The serving API currently
loads per-profile classifiers directly from `BRICKMATCH_CLASSIFIER_DIR`; the promotion
registry does not yet drive serving. Offline classifier runs are tracked in the local
MLflow SQLite store at `artifacts/mlflow.db` when the tracking extra is installed.

## Known gaps

- No real consented feedback; all evaluation uses simulated personas.
- No statistical significance, confidence intervals, or production latency benchmark.
- Age, price, and popularity are absent from the verified source and are not invented.
- Docker packaging is verified by the GitHub Actions build-and-smoke-test job; local
  Docker execution still requires Docker Desktop to be running.
- Source image rights and current Rebrickable terms remain the operator's responsibility.
- Production auth and per-instance rate limiting are implemented; use a shared gateway
  or Redis-backed limiter if horizontally scaling beyond one instance.

## Release recommendation

Before a broader release: collect consented feedback, re-run evaluation with real
splits, benchmark latency, and configure HTTPS, custom domain, backups, and a shared
rate limiter if scaling beyond one instance.
