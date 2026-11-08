"""Fit catalog preprocessing only on caller-supplied training rows."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SCHEMA_VERSION = "metadata-v1"


def frame(records: list[dict]) -> pd.DataFrame:
    if not records:
        raise ValueError("Metadata requires at least one record")
    ids = [row["set_id"] for row in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate set IDs")
    result = pd.DataFrame({"theme": [str(row["theme_id"]) for row in records],
                           "year": [float(row["year"]) for row in records],
                           "num_parts": [float(row["num_parts"]) for row in records]})
    if not np.isfinite(result[["year", "num_parts"]].to_numpy()).all():
        raise ValueError("Nonfinite metadata")
    if (result["num_parts"] < 0).any():
        raise ValueError("Negative piece count")
    result["num_parts"] = np.log1p(result["num_parts"])
    return result


def fit_metadata(training_records: list[dict]) -> ColumnTransformer:
    transformer = ColumnTransformer([
        ("theme", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["theme"]),
        ("numeric", StandardScaler(), ["year", "num_parts"]),
    ])
    transformer.fit(frame(training_records))
    return transformer


def transform_metadata(transformer: ColumnTransformer, records: list[dict]):
    values = np.asarray(transformer.transform(frame(records)), dtype=np.float32)
    if not np.isfinite(values).all():
        raise ValueError("Nonfinite transformed metadata")
    return [row["set_id"] for row in records], values
