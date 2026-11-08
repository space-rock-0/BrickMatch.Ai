# Model card

## Serving behavior

BrickMatch ranks the local catalog with a deterministic, non-calibrated score. Rated
sets are excluded. The active signals are reported per recommendation:

- **Catalog** — deterministic catalog order for cold start.
- **Metadata** — cosine similarity to a centroid of the profile's liked sets, using
  one-hot theme plus standardized year and log piece count (69 dimensions).
- **Visual** — cosine similarity to a centroid of liked CLIP image embeddings (512
  dimensions), when the verified embedding bundle is available.
- **Classifier** — a per-profile logistic regression over 581 combined features
  (512 CLIP + 69 metadata), used only when a matching artifact loads and its dimension
  and user id validate.

The combined weights are provisional (`metadata 0.4`, `visual 0.3`, `classifier 0.3`,
`catalog 1.0`). Missing signals are dropped from the weight denominator. Scores are
ranking values, not probabilities that a user will like a set.

## Training

`scripts/train_classifier.py` trains offline on current like/dislike labels with
balanced class weights, L2 regularization (C=0.5), a scaler, and a fixed random seed.
Skips and other profiles' labels are excluded. A profile needs at least 8 mapped
labels, including at least 2 likes and 2 dislikes. Training never runs on a feedback
write.

## Measured evaluation

30 simulated personas, temporal 60/20/20 split per user, leakage-safe metadata
preprocessing, 127 test likes total:

| Approach | P@10 (macro) | HR@10 (macro) |
| --- | --- | --- |
| Catalog baseline | 0.0000 | 0.0000 |
| Metadata similarity | 0.0333 | 0.2667 |
| Visual CLIP centroid | 0.0500 | 0.4000 |
| Hybrid merge | 0.0367 | 0.2667 |
| Per-profile classifier | 0.0633 | 0.4333 |

The classifier has the best measured macro P@10 and hit rate in this simulated set. The
differences are small, the test partitions have few items, and no confidence intervals
were computed. These numbers must not be presented as real-user accuracy or a
production improvement.

## Limits

- Simulated theme-based personas, not consented users.
- Single-digit test likes per user; no significance testing.
- Test partitions contain few or no dislikes; negative ranking is not evaluated.
- No coverage, diversity, or candidate-recall benchmark against explicit relevant sets.
- No calibrated probabilities and no online learning.
- Source data lacks age, price, and popularity; the product does not infer them.
- Local profile aliases are not authentication.

All empirical claims require a new measurement with real consenting users.
