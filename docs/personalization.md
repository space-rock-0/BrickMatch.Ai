# Phase 4 personalization

SQLite stores immutable events and a current per-user rating view. Like/dislike/skip
upserts correct prior feedback; undo clears that set's current rating and preserves
event history. It does not restore a previous rating. Profile aliases provide local
isolation, not authentication. Catalog membership must be validated by the API layer.

Explicit candidate training requires 12 labels and at least 3 per class by default.
Skips and other users' feedback are excluded, as are rows later than the supplied
cutoff. For temporal evaluation, callers must reconstruct ratings as of the cutoff
from event history; current state alone cannot recover an older corrected label.
Training never occurs on a feedback write. Candidate models require a later evaluation
and promotion gate before serving as active models. Low data uses centroid similarity;
no positive evidence gives explicit cold start. Only a user's own labels affect profiles.

Hybrid defaults (.5 preference/.3 visual/.2 metadata) are provisional, not optimized
or validated. Missing signals are excluded from the weight denominator. Scores are
not calibrated probabilities. Explanations report actual numeric component signals,
without invented claims about themes or liked sets. Theme caps can return fewer than K.
All rated IDs must be supplied to the ranker for exclusions.

Run `.venv\Scripts\python.exe -m pytest tests/test_personalization.py`.
The personalization tests pass. The feedback store currently holds 30 local profiles,
including 30 offline per-profile classifier artifacts; the simulator-created profiles
are not real users. Serving loads classifiers directly from the artifact directory; the
promotion registry is implemented but does not yet drive the API. No measured
improvement over baselines is claimed beyond the simulated evaluation in
`docs/experiments.md`, and no real-user feedback exists.
