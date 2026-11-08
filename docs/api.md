# Local application API

Run from the repository root on Python 3.11:

```powershell
$env:BRICKMATCH_CATALOG = "data/processed/78b8926d0b520375/catalog.json"
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The same process serves the interface at `/` from `frontend/web/` and interactive
schemas at `/docs`. All data endpoints are under `/api/v1`.

Profile ids must match `^[A-Za-z0-9_-]{1,80}$` in path and body. They are local
aliases, not authentication. Invalid ids return 422 before any filesystem or database
lookup. Bind to localhost unless you add real access control.

## Catalog

### `GET /api/v1/sets`

Query parameters:

| Name | Default | Notes |
| --- | --- | --- |
| `q` | empty | Case-insensitive name search, max 200 chars |
| `theme` | unset | Theme id |
| `min_year`, `max_year` | 1949, 2200 | Inclusive |
| `min_parts`, `max_parts` | 0, 100000 | Inclusive |
| `has_image` | unset | `true`/`false` against the verified image manifest |
| `sort` | `set_id` | `set_id`, `name`, `year_desc`, `year_asc`, `parts_desc`, `parts_asc` |
| `offset`, `limit` | 0, 24 | Limit 1–100 |

Response: `{items, total, offset, limit, sort}`. Each item carries catalog fields,
`image_available`, and a stable `set_id`.

### `GET /api/v1/sets/{set_id}`

Returns one set or 404. `set_id` is a catalog lookup, never a file path.

### `GET /api/v1/images/{set_id}`

Streams the verified local image with its detected media type and a one-day cache
header. Returns 404 when the manifest has no downloaded image, or when the recorded
path is missing or escapes the catalog directory.

### `GET /api/v1/themes`

Returns `{items: [{theme_id, theme, count}]}` sorted by count, then name.

## Profiles and feedback

### `GET /api/v1/users`

Returns `{items: [{user_id, ratings}]}` for profiles with current feedback.

### `GET /api/v1/users/{user_id}/feedback`

Returns `{current, events}`. Both lists include the full catalog `set` object or null
if the set is no longer in the catalog. `current` is one row per set; `events` is the
immutable history.

### `POST /api/v1/feedback`

Body: `{"user_id": "...", "set_id": "...", "action": "like|dislike|skip|undo"}`.
Returns 201 with the stored event. Like/dislike/skip upsert the current rating; undo
clears the current rating and preserves history. Unknown set ids return 404. Training
never runs on a write.

### `GET /api/v1/users/{user_id}/summary`

Returns current counts, total ratings, and up to five liked themes:

```json
{
  "user_id": "builder",
  "counts": {"like": 51, "dislike": 18, "skip": 7},
  "total": 76,
  "top_themes": [{"theme": "Classic Town", "count": 12}]
}
```

### `GET /api/v1/users/{user_id}/recommendations`

Query: `k` (1–100, default 10) and optional `theme_cap` (1–100). Rated sets are
excluded. The response contains `items`, `mode`, `model_version`, `feature_version`,
`dataset_version`, and `generated_at`.

Each item has `set_id`, the catalog `set`, a final `score`, and `signals`. Signal keys
are `catalog`, `metadata`, `visual`, and `classifier` and are present only when that
source contributed. Scores are ranking scores, not calibrated probabilities.

Modes:

- `cold_start` — no likes; deterministic catalog order.
- `metadata_profile` — metadata centroid only.
- `hybrid_profile` — metadata plus visual retrieval.
- `classifier_profile` — a valid per-profile classifier contributed; falls back
  silently if the artifact is absent, mismatched, or incompatible.

The metadata transformer is fit on the serving catalog so the 69-dim metadata block
matches the 512-dim CLIP block used by the classifiers (581 features total). Offline
evaluation fits its transformer on training rows only.

## Status and evaluation

### `GET /api/v1/bootstrap`

One-call UI bootstrap: catalog count, dataset version, image count, themes, users,
model status, and the evaluation payload.

### `GET /api/v1/models/current`

Model mode, classifier/visual flags, catalog and image counts, dataset version, and
evaluation availability.

### `GET /api/v1/evaluation`

`{available, data}`. `data/evaluation_results.json` transcribes the measured table from
`docs/experiments.md`. The data is from simulated personas, is explicitly marked
simulated, and is not a real-user benchmark.

### `GET /api/v1/metrics`

In-process counters only: recommendation request count and last latency in
milliseconds. They reset on restart and are not a monitoring system.

### `GET /api/v1/health/live`

`{"status": "live"}`.

### `GET /api/v1/health/ready`

Checks SQLite and a non-empty catalog. Returns 503 when the catalog is missing or
empty; it never fabricates products.

### `POST /api/v1/users/{user_id}/retraining`

Always returns 403. Training, candidate evaluation, and promotion are offline
operations; the endpoint is intentionally not a remote training trigger.

## Static interface

`GET /` and `GET /assets/*` serve `frontend/web/`. Override the directory with
`BRICKMATCH_UI_DIR`. The interface uses the same origin by default; set
`BRICKMATCH_CORS_ORIGINS` only for a separately hosted development frontend.

## Error behavior

- 404: unknown set, unknown image, missing local image.
- 422: invalid profile id or invalid request body/query.
- 403: retraining request.
- 503: readiness check with an empty catalog.
