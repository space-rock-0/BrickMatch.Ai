# Account and recommendation behavior

This release serves `personal-feedback-v2`. Existing accounts and feedback are retained.
Old signed tokens are intentionally invalidated; users sign in again once after deployment.

## Accounts

- Registration creates an empty account. Existing unclaimed demo/local feedback aliases cannot be claimed.
- Hosted UI uses a seven-day HttpOnly, SameSite=Strict session cookie, Secure on HTTPS.
- Only a SHA-256 digest of the random session token is stored in PostgreSQL. Bearer sessions are also supported for API clients.
- Logout revokes the current session. Password changes require the current password and revoke all sessions.
- Protected routes enforce account identity. API responses containing account information are not cached.
- Cross-origin writes are rejected. Auth attempts are throttled in the database, shared across instances; the general API limiter remains per-process.
- Passwords use salted scrypt. Email verification and forgotten-password recovery are not implemented; do not advertise those features.

## Learning loop

1. New accounts have no ratings and no personal recommendations. The public featured catalog provides discovery.
2. Likes and dislikes update metadata and CLIP similarity profiles immediately. Skips exclude a build but do not train preferences.
3. Rated builds are excluded from recommendations. Undo removes the current label; corrections replace it.
4. With at least 24 labels, including six likes and six dislikes, a logistic regression candidate is evaluated chronologically: earlier 75% for training, latest 25% for validation. The validation partition must contain at least two of each class.
5. The classifier must achieve AUC >= 0.65, balanced accuracy >= 0.60, and improve on the earlier-feedback profile AUC by >= 0.02. Otherwise serving continues with the profile.
6. An accepted classifier is refitted on current feedback. A bounded, process-local cache uses account ID and the exact feedback snapshot. Restarting recomputes from durable feedback; it does not load demo models.
7. Theme caps diversify the results. Scores are ranking signals, not calibrated probabilities of user satisfaction.

The holdout gate is a conservative heuristic on limited data, not proof of generalization or production ranking quality. Repeated model selection on changing holdouts is not an independent experiment. Historical simulated-persona metrics shown in Model Lab do not evaluate this release. Real-user ranking quality requires consented usage and a separate temporal evaluation, followed by an online comparison.

## Deployment verification

CI checks Python tests, lint, JavaScript parsing, a Docker startup smoke test, and account lifecycle against PostgreSQL 18. Local tests skip only the PostgreSQL variant when TEST_DATABASE_URL is absent. Live smoke tests should verify empty accounts, cookie flags, feedback isolation, recommendation updates, correction/undo, and logout revocation.

The catalog currently contains 500 sets and 485 usable image vectors, not the entire LEGO catalog. Broadening it requires a representative catalog selection plus rebuilt images/features and new evaluation.

The current Render service and database are free-tier resources. The inspected database expires on 2026-12-08. A durable paid database with backups and an always-on service are still required before treating this as a dependable public production service. This release does not change billing plans or configure hosted MLflow storage.
