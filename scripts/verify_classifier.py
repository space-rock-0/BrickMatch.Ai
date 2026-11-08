"""Audit saved per-user classifiers without overstating their quality."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib


def audit(directory: Path) -> dict:
    files = sorted(directory.glob("*.joblib")) if directory.is_dir() else []
    rows = []
    for path in files:
        try:
            candidate = joblib.load(path)
            rows.append({
                "file": path.name,
                "user_id": candidate.get("user_id"),
                "training_count": candidate.get("training_count"),
                "validation_status": candidate.get("validation_status", "not_recorded"),
                "validation_balanced_accuracy": candidate.get("validation_balanced_accuracy"),
                "validation_roc_auc": candidate.get("validation_roc_auc"),
                "feature_version": candidate.get("feature_version"),
            })
        except Exception as exc:  # noqa: BLE001 - audit should report bad artifacts
            rows.append({"file": path.name, "status": "invalid", "error": type(exc).__name__})
    validated = [row for row in rows if row.get("validation_status") == "cross_validated"]
    return {
        "artifact_count": len(files),
        "valid_artifact_count": sum("error" not in row for row in rows),
        "cross_validated_count": len(validated),
        "artifacts": rows,
        "interpretation": (
            "Artifacts exist and include cross-validated metrics. This supports a "
            "measured offline model, not proof of real-user recommendation quality."
            if validated else
            "Artifacts may be loadable, but no cross-validated metrics are recorded. "
            "Predictive quality is unverified; do not call this a proven recommender."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=Path("artifacts/models"))
    args = parser.parse_args()
    print(json.dumps(audit(args.dir), indent=2))


if __name__ == "__main__":
    main()
