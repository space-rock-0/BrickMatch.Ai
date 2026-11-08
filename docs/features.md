# Phase 2 feature pipeline

Metadata v1 encodes theme IDs and standardizes year and log1p(piece count).
Call `fit_metadata(training_records)` only with eligible training catalog rows;
reuse the returned transformer with `transform_metadata` for validation/test/inference.
Unknown themes yield zero categorical indicators. No age, price, or popularity is inferred.

Embeddings are normalized float32 CLIP vectors in atomic NPZ bundles containing
ordered string IDs and a JSON manifest. Loading disables pickle and validates
identity uniqueness, dimensions, finite values, unit norms, and optional catalog membership.
Per-image caches use image checksum, pinned model revision and processor version.
An interrupted job retains completed per-image entries. An entirely failed run does
not replace the prior complete artifact. Successful partial output lists failed IDs.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_features.py
.venv\Scripts\python.exe -m app.features.image_embeddings data/processed/VERSION/image_manifest.json --revision MODEL_COMMIT_SHA --output artifacts/embeddings/clip.npz
```

Use the actual 40-character model commit SHA from the successful preflight report.
The model loads only when an uncached image needs encoding, on CPU, two threads,
one image at a time. The output reports elapsed time and cache hits. A real catalog run
completed; no separate CPU throughput benchmark has been published. Source-data and
image permission validation is the operator's responsibility; synthetic unit fixtures
are not product data.

Phase 2 tests pass, and a real CPU catalog run produced 485 normalized 512-dimensional
vectors for 486 downloaded images (one image has not been embedded yet). The feature
bundle is served by the API. Interrupted-job recovery and repeated cached execution
are covered by the automated tests; no separate production recovery drill is recorded.
Source-data and image permission validation remains the operator's responsibility.
