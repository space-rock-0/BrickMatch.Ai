# Evaluation protocol and measured results

Only explicit likes are relevant; dislikes are labeled negatives and skips are ignored.
Metrics: Precision@K divides by K even when fewer results exist. Recall, NDCG and hit
rate return null when no relevant held-out items exist; exclude those users from
their aggregate denominators and report excluded counts. Candidate recall and coverage
use unique identities. Diversity is average pairwise cosine dissimilarity.

Temporal splitting is per user, ordered by UTC ISO timestamps with strict partition
boundaries; equal timestamps stay together. Users without three nonempty partitions
are excluded. Repeated user-set observations are rejected until an explicit correction
policy is selected; do not silently random-split feedback or treat future corrections
as earlier labels. Fit metadata preprocessing only on training rows, choose weights on
validation, then evaluate the test partition once.

## Verified state (2026-11-08, updated)

- Catalog: 28,587 source rows, 500 selected, dataset version `78b8926d0b520375`.
- Images downloaded: 486 of 500; 14 missing.
- CLIP embeddings: 485 vectors, 512-dim float32, artifact `artifacts/embeddings/clip.npz`.
- Feedback DB (`data/brickmatch.db`) as of 2026-11-08 15:45 IST: 1,204 events,
  1,197 current ratings, 30 users. `builder`: 86 events, 83 current ratings —
  56 likes, 20 dislikes, 7 skips.
- Current-profile count exceeds the 76-rating snapshot used for the single-user baseline
  below because local interaction continued after that measurement. The evaluation
  table is reported against its original 76-rating snapshot, not the growing database.
- Deduplication: repeated user-set observations collapse to the latest (explicit
  correction policy); undone ratings are removed from current state but retained in
  event history.
- Temporal split for the single-user baseline: train=41, validation=14, test=14,
  excluded users=0. Likes: train=24, validation=13, test=14. Dislikes: train=15,
  validation=1, test=0.
- Evaluation tests: `tests/test_evaluation.py` -> 3 passed.

## Baseline comparison (measured)

User: `builder`. Split: temporal, 60/20/20, strict timestamp boundaries.
Relevant set for metrics = likes in the test partition (14 items).
Recommendations exclude all sets rated in train. K in {5, 10}.
Metadata preprocessing fit on train likes only (leakage-safe).

| Approach | K=5 P@K | K=5 R@K | K=5 NDCG | K=5 HR | K=10 P@K | K=10 R@K | K=10 NDCG | K=10 HR |
|---|---|---|---|---|---|---|---|---|
| Catalog (non-personalized) | 0.0000 | 0.0000 | 0.0000 | 0.0 | 0.0000 | 0.0000 | 0.0000 | 0.0 |
| Metadata similarity | 0.0000 | 0.0000 | 0.0000 | 0.0 | 0.1000 | 0.0714 | 0.0734 | 1.0 |
| Visual (CLIP centroid) | 0.0000 | 0.0000 | 0.0000 | 0.0 | 0.1000 | 0.0714 | 0.0636 | 1.0 |
| Hybrid (merged) | 0.0000 | 0.0000 | 0.0000 | 0.0 | 0.1000 | 0.0714 | 0.0636 | 1.0 |

Candidate recall @K=10: metadata 0.0714, visual 0.0714, hybrid 0.0714, catalog 0.0.
For this single-user `builder` split, the personalized classifier was not trained
because 24 train likes are below the offline eligibility threshold. The multi-user
section below trains per-profile classifiers on simulated personas; it is a separate
experiment.

## Feedback-size learning curve (visual, K=5)

Train size varied over chronologically ordered likes (excluding the fixed test set).

| Train likes (N) | P@5 | R@5 | Hit Rate |
|---|---|---|---|
| 5 | 0.0000 | 0.0000 | 0.0 |
| 10 | 0.0000 | 0.0000 | 0.0 |
| 20 | 0.0000 | 0.0000 | 0.0 |
| 30 | 0.0000 | 0.0000 | 0.0 |
| 40 | 0.2000 | 0.0714 | 1.0 |
| 24 (full train) | 0.0000 | 0.0000 | 0.0 |

Note: the N=40 row uses 40 train likes which overlaps/leaks into the fixed test set
definition used for that row's exclusion; interpret with caution. Full-train (N=24)
is the leakage-safe evaluation.

## Multi-user evaluation (30 users)

30 users (5 original personas + 25 generated), each rating ~30-45 sets by theme
preference. Temporal split 60/20/20 per user, leakage-safe (metadata fit on train
likes only). Total: 30 users, 127 test likes.

| Approach | P@10 (macro) | HR@10 (macro) | n |
|---|---|---|---|
| Catalog (non-personalized) | 0.0000 | 0.0000 | 30 |
| Metadata similarity | 0.0333 | 0.2667 | 30 |
| Visual (CLIP centroid) | 0.0500 | 0.4000 | 30 |
| Hybrid (merged) | 0.0367 | 0.2667 | 30 |
| Classifier (CLIP+metadata LR) | 0.0633 | 0.4333 | 30 |

The personalized classifier achieves the best macro P@10 (0.0633) and hit rate
(0.4333), outperforming visual centroid (0.0500/0.4000) and metadata (0.0333/0.2667).

## Production-readiness improvements applied

1. Combined feature space: CLIP embedding (512-dim) + metadata (69-dim) = 581-dim.
2. Per-user logistic regression classifier with balanced class weights and L2
   regularization (C=0.5), trained when eligibility thresholds are met.
3. Classifier improves hit rate for man_cars and man_space where visual centroid
   alone failed (0.0 -> 0.100 P@10).
4. Metadata preprocessing fit on train likes only (leakage-safe).
5. Model identity, feature version, and dimension checks enforced before scoring.

## Limitations

- Simulated personas (theme-based), not real user preferences; small samples.
- Single-digit test likes per user; no statistical significance.
- Test partitions contain few/no dislikes; dislike-based negatives not evaluated.
- Personalized classifier results come from simulated personas, not a real-user model.
- No confidence intervals, no API latency benchmarks, no coverage/diversity.
- Synthetic tests verify formula correctness only; product claims remain limited.

## What is required to strengthen Phase 5

1. More users and more feedback per user (cross-user splits).
2. Dislikes in the test partition for negative evaluation.
3. Candidate recall and coverage measured against explicit relevant sets.
4. API latency and CPU embedding throughput benchmarks.
