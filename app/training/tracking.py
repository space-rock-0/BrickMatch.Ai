"""Small optional MLflow adapter for offline training jobs.

Training remains fully usable without MLflow. When the ``tracking`` extra is
installed, runs are written to the configured MLflow tracking URI.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def run(name: str, *, enabled: bool = True):
    """Yield an MLflow run, or a no-op object when tracking is unavailable."""
    if not enabled:
        yield None
        return
    try:
        import mlflow
    except ImportError:
        print("MLflow not installed; continuing without tracking (install .[tracking]).")
        yield None
        return

    uri = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///artifacts/mlflow.db")
    if uri.startswith("sqlite:///"):
        Path(uri.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(os.getenv("MLFLOW_EXPERIMENT_NAME", "brickmatch-classifier"))
    with mlflow.start_run(run_name=name) as active:
        yield active


def log_params(values: dict, *, enabled: bool = True) -> None:
    if enabled:
        try:
            import mlflow
            mlflow.log_params({key: str(value) for key, value in values.items()})
        except ImportError:
            pass


def log_metrics(values: dict, *, enabled: bool = True) -> None:
    if enabled:
        try:
            import mlflow
            mlflow.log_metrics({key: float(value) for key, value in values.items()})
        except ImportError:
            pass


def log_artifact(path: Path, *, enabled: bool = True) -> None:
    if enabled:
        try:
            import mlflow
            mlflow.log_artifact(str(path))
        except ImportError:
            pass
