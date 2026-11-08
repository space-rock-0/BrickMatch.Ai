# Phase 1: catalog and image ingestion

Use the official Rebrickable downloads page to obtain `sets.csv.gz` and
`themes.csv.gz`, retaining originals under `data/raw/rebrickable/`.
The source pages and terms could not be accessed by the build agent (HTTP 402).
No source data or images have been fetched, and no license permission is assumed.
Before downloading images, verify current source terms and your permitted usage.

Expected required set columns: `set_num,name,year,theme_id,num_parts`.
Theme columns: `id,name`. Optional `img_url` is used only when actually present.
No prices, popularity, age ranges, or ratings are invented. Missing images remain
explicitly missing. Only HTTPS Rebrickable/CDN image URLs are accepted; redirects
are rejected to prevent a source URL from reaching arbitrary network destinations.

```powershell
.venv\Scripts\python.exe -m app.data.ingest --sets data/raw/rebrickable/sets.csv.gz --themes data/raw/rebrickable/themes.csv.gz --limit 500
.venv\Scripts\python.exe -m app.data.images data/processed/VERSION/image_manifest.json --permission-confirmed --limit 10
.venv\Scripts\python.exe -m pytest tests/test_ingestion.py
```

Outputs are content-addressed by both source hashes, selection limit and schema.
Catalog IDs are sorted before selection. Rejected rows include source line and reason.
The quality report counts rows and missing images. Re-ingestion preserves existing
image states. Downloads are sequential, timeout after 20 seconds, retry transient
failures at most three times, limit each image to 10 MiB and 25 million pixels,
validate decoding, and write atomically. Successful images are reused only when
their checksum matches; duplicate hashes are reported in the download summary.
Raw files are never modified. JSON is the initial canonical format for readable
inspection; Parquet can be added without changing stable IDs.

## Gate status

Implementation and a real local ingestion run are complete: 28,587 source rows, 500
selected sets, dataset version `78b8926d0b520375`, and 486 downloaded images. The
remaining 14 sets intentionally show placeholders. Current source terms and image
usage permissions are the operator's responsibility and were not independently
verified by the build agent. Synthetic fixtures remain test-only and are never used as
product catalog or evaluation evidence.
