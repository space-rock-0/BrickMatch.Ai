"""Offline per-user classifier training. Produces a joblib artifact per user."""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.preprocessing import StandardScaler

from app.features.metadata import fit_metadata, transform_metadata
from app.recommendation.personalization import save_classifier
from app.training.tracking import log_artifact, log_metrics, log_params, run


def validation_metrics(X, y):
    """Return honest cross-validated metrics, or an explicit unavailable state."""
    min_class = min(np.bincount(y))
    if min_class < 2:
        return {"validation_status": "unavailable", "validation_reason": "fewer than 2 labels per class"}
    folds = min(5, int(min_class))
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=42)
    model = __import__("sklearn.pipeline", fromlist=["make_pipeline"]).make_pipeline(
        StandardScaler(), LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000,
                                             random_state=42))
    probabilities = cross_val_predict(model, X, y, cv=splitter, method="predict_proba")[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    return {"validation_status": "cross_validated", "validation_folds": folds,
            "validation_balanced_accuracy": balanced_accuracy_score(y, predictions),
            "validation_roc_auc": roc_auc_score(y, probabilities)}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-mlflow", action="store_true", help="Disable MLflow tracking")
    args = parser.parse_args()
    tracking = not args.no_mlflow
    os.environ.setdefault("BRICKMATCH_CATALOG", "data/processed/78b8926d0b520375/catalog.json")
    os.environ.setdefault("BRICKMATCH_EMBEDDINGS", "artifacts/embeddings/clip.npz")
    catalog = json.loads(Path(os.environ["BRICKMATCH_CATALOG"]).read_text())
    emb = np.load(os.environ["BRICKMATCH_EMBEDDINGS"])
    emb_ids = list(emb["set_ids"]); emb_vecs = emb["vectors"]; emb_index = {s:i for i,s in enumerate(emb_ids)}
    db = sqlite3.connect(os.getenv("BRICKMATCH_DB","data/brickmatch.db"))
    db.row_factory = sqlite3.Row
    con = db
    out_dir = Path("artifacts/models"); out_dir.mkdir(parents=True, exist_ok=True)
    users = [r[0] for r in con.execute("SELECT DISTINCT user_id FROM current_feedback").fetchall()]
    for user in users:
        rows = con.execute("SELECT set_id,action,updated_at FROM current_feedback WHERE user_id=?",(user,)).fetchall()
        likes=[r["set_id"] for r in rows if r["action"]=="like"]
        dislikes=[r["set_id"] for r in rows if r["action"]=="dislike"]
        if len(likes)+len(dislikes) < 8 or len(likes)<2 or len(dislikes)<2:
            print(f"{user}: skipped (insufficient labels)"); continue
        transformer = fit_metadata(catalog)
        meta_ids, meta_vals = transform_metadata(transformer, catalog)
        meta_map = {sid:meta_vals[i] for i,sid in enumerate(meta_ids)}
        def feat(sid):
            v = emb_vecs[emb_index[sid]] if sid in emb_index else np.zeros(512,dtype=np.float32)
            return np.concatenate([v, meta_map[sid]])  # noqa: B023
        cids = [r["set_id"] for r in catalog if r["set_id"] in meta_map]
        X = np.array([feat(s) for s in cids], dtype=np.float32)
        mapping = {sid:i for i,sid in enumerate(cids)}
        tr_ids = likes + dislikes
        y = np.array([1]*len(likes)+[0]*len(dislikes))
        tr_idx = [mapping[s] for s in tr_ids if s in mapping]
        y = np.array([1 if s in set(likes) else 0 for s in tr_ids if s in mapping])
        if len(tr_idx) < 8: 
            print(f"{user}: skipped (insufficient mapped)"); continue
        X_train, y_train = X[tr_idx], y
        metrics = validation_metrics(X_train, y_train)
        with run(f"classifier-{user}", enabled=tracking):
            log_params({"user_id": user, "feature_version": "metadata-v1",
                        "training_count": len(tr_idx), "feature_dimension": X.shape[1],
                        "classifier": "logistic_regression", "dataset_version":
                        Path(os.environ["BRICKMATCH_CATALOG"]).parent.name}, enabled=tracking)
            numeric_metrics = {key: value for key, value in metrics.items()
                               if key.startswith("validation_") and isinstance(value, (int, float))}
            log_metrics(numeric_metrics, enabled=tracking)
            sc = StandardScaler(); Xtr = sc.fit_transform(X_train)
            clf = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000, random_state=42)
            clf.fit(Xtr, y_train)
            cand = {"classifier": clf, "scaler": sc, "user_id": user,
                    "feature_version": "metadata-v1", "dimension": X.shape[1],
                    "model_version": f"lr-{user}-metadata-v1", "training_count": len(tr_idx),
                    **metrics}
            output = out_dir / f"{user}.joblib"
            save_classifier(cand, output)
            log_artifact(output, enabled=tracking)
        print(f"{user}: trained on {len(tr_idx)} labels; {metrics} -> {output}")

if __name__ == "__main__":
    main()
