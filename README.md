# BrickMatch AI

Local-first personalized LEGO discovery. BrickMatch reads the catalog's pictures and
metadata, learns from like/dislike/skip feedback, and ranks sets around one local
profile. The app is a FastAPI backend with a vanilla HTML/CSS/JavaScript interface
served from the same process. No Node build step, no cloud account, no checkout.

The implementation follows `BRICKMATCH_AI_BUILD_PLAN.md`; visual tokens come from
`Brand guide lines.html` (see `docs/brand_guidelines.md`). The served interface is
`frontend/web/`. The old `frontend/streamlit_app.py` is retained only as a legacy
reference and is not part of the product path.

## What is in the interface

| Route | Purpose |
| --- | --- |
| `#/discover` | Search, theme/year/piece filters, sorting, paginated catalog, inline feedback |
| `#/swipe` | Keyboard-friendly Like / Dislike / Skip / Undo queue |
| `#/for-you` | Ranked recommendations with actual signal breakdowns and model identity |
| `#/preferences` | Rating counts, top liked themes, full rating history with undo |
| `#/model-lab` | Live runtime status and the measured, caveated offline evaluation table |
| `#/system` | Health, dataset, artifact, and endpoint status |

Local development keeps authentication disabled by default. Production deployment
enables signed bearer-token authentication and PostgreSQL through environment variables.

## Quick start (Windows)

Use Python 3.11 from the repository directory.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev,vision,search,tracking]"
.venv\Scripts\python scripts/preflight.py
```

`scripts/preflight.py` downloads the pinned CLIP checkpoint on first use and runs a
CPU compatibility check. That check is not a recommendation evaluation.

Start the app with the artifacts produced by the data pipeline:

```powershell
$env:BRICKMATCH_CATALOG = "data/processed/78b8926d0b520375/catalog.json"
$env:BRICKMATCH_EMBEDDINGS = "artifacts/embeddings/clip.npz"
$env:BRICKMATCH_CLASSIFIER_DIR = "artifacts/models"

.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000/>. Interactive API docs are at
<http://127.0.0.1:8000/docs>. If the artifact paths are omitted, the app still runs
with the metadata/catalog fallback and reports which signals are active.

### Offline classifier training and MLflow

Classifier training is offline. It records cross-validated metrics in each joblib
artifact and, when the tracking extra is installed, logs parameters, metrics, and the
artifact to a local MLflow experiment:

```powershell
.venv\Scripts\python -m pip install -e ".[tracking]"
.venv\Scripts\python scripts/train_classifier.py
.venv\Scripts\python scripts/verify_classifier.py
mlflow ui --backend-store-uri sqlite:///artifacts/mlflow.db
```

Set `MLFLOW_TRACKING_URI` and `MLFLOW_EXPERIMENT_NAME` to use a remote tracking server.
The saved classifier is a real per-profile logistic-regression model when an artifact
is valid and serving feature dimensions match. Existing artifacts without recorded
holdout metrics are loadable but their predictive quality is unverified. The current
evaluation numbers are simulated-persona offline results, not real-user evidence.

### Data pipeline (only needed on a fresh checkout)

Raw Rebrickable files and downloaded images are intentionally not committed. Review the
source terms before downloading images. The full commands and validation rules are in
`docs/data_pipeline.md` and `docs/features.md`.

```powershell
.venv\Scripts\python -m app.data.ingest --sets data/raw/rebrickable/sets.csv.gz --themes data/raw/rebrickable/themes.csv.gz --limit 500
.venv\Scripts\python -m app.data.images data/processed/VERSION/image_manifest.json --permission-confirmed --limit 10
.venv\Scripts\python -m app.features.image_embeddings data/processed/VERSION/image_manifest.json --revision MODEL_COMMIT_SHA
.venv\Scripts\python scripts\train_classifier.py
```

The embedding step needs the actual 40-character model commit SHA used by the
preflight. Classifier training is offline and per profile; the API never trains on a
feedback write.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `BRICKMATCH_CATALOG` | `data/processed/catalog.json` | Versioned `catalog.json`; missing file yields an empty catalog and readiness 503 |
| `BRICKMATCH_DB` | `data/brickmatch.db` | SQLite path locally or PostgreSQL URL in production |
| `BRICKMATCH_AUTH_REQUIRED` | `false` | Require bearer-token authentication |
| `BRICKMATCH_AUTH_SECRET` | unset locally | Secret used to sign production tokens |
| `BRICKMATCH_RATE_LIMIT_PER_MINUTE` | `120` | Per-instance API request limit |
| `BRICKMATCH_EMBEDDINGS` | unset | Verified CLIP `.npz` bundle; enables visual retrieval |
| `BRICKMATCH_CLASSIFIER_DIR` | `artifacts/models` | Per-profile joblib classifiers |
| `BRICKMATCH_UI_DIR` | `frontend/web` | Static interface directory |
| `BRICKMATCH_EVALUATION` | `data/evaluation_results.json` | Measured evaluation report shown in Model Lab |
| `BRICKMATCH_CORS_ORIGINS` | `*` | Comma-separated allowed origins for a separately hosted dev frontend |

The default catalog path is a placeholder; always pass a versioned path. The API binds
to localhost in the command above. The Render Blueprint enables authentication and
PostgreSQL for non-local deployment.

## API

The stable surface is under `/api/v1`: catalog reads, themes, profiles, feedback,
recommendations, model/evaluation status, and health. See `docs/api.md` for parameters
and response shapes. Training and promotion remain offline operations; the retraining
endpoint returns 403 by design.

## Checks

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\ruff.exe check app frontend tests
node --check frontend/web/assets/app.js
```

The test suite uses synthetic fixtures and temporary SQLite databases. It does not
train CLIP or require the production catalog.

## Docker

The image serves the API and interface on port 8000. Catalog, artifacts, and the
database must be mounted; the build does not include downloaded data.

```powershell
docker build -t brickmatch .
docker run --rm -p 127.0.0.1:8000:8000 `
  -v "${PWD}/data:/app/data" `
  -v "${PWD}/artifacts:/app/artifacts" `
  -e BRICKMATCH_CATALOG=/app/data/processed/78b8926d0b520375/catalog.json `
  -e BRICKMATCH_EMBEDDINGS=/app/artifacts/embeddings/clip.npz `
  brickmatch
```

The GitHub Actions Docker job builds the image and verifies the live endpoint and UI.
The image intentionally excludes the catalog, embeddings, and classifier artifacts;
mount those at runtime as shown above before using the readiness endpoint.

## Measured state and limits

- Catalog: 500 sets from 28,587 source rows; dataset version `78b8926d0b520375`.
- Local images: 486 of 500; 14 sets intentionally show a placeholder.
- CLIP embeddings: 485 vectors, 512 dimensions, CPU.
- Per-profile classifiers: 30 joblib artifacts trained offline.
- Evaluation: 30 **simulated** personas, temporal 60/20/20 splits. Best measured
  classifier P@10 = `0.0633`, HR@10 = `0.4333`. These are small, synthetic results,
  not evidence of real-user accuracy or a production ranking gain.
- No real consented user feedback, age metadata, price, or popularity data is present.
- MLflow tracks offline training runs; it is not a request-time serving dependency.

See `docs/experiments.md` for the measured table and `docs/model_card.md` for serving
behavior and limitations. The interface exposes unavailable states rather than
inventing missing metadata.
