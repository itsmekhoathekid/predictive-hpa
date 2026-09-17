import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from house_price_api.domain import MODEL_FEATURE_ORDER, HouseFeatures, engineer_features
from training.dataset import DATASET_SHA256, DATASET_URL

MODEL_VERSION = "uci-real-estate-ridge-v1"
RIDGE_ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0)
RANDOM_STATE = 42


def build_feature_matrix(dataset: pd.DataFrame) -> np.ndarray:
    source_columns = (
        "transaction_date",
        "house_age_years",
        "distance_to_mrt_m",
        "nearby_convenience_stores",
        "latitude",
        "longitude",
    )
    raw_features: NDArray[np.float64] = dataset.loc[:, source_columns].to_numpy(dtype=np.float64)
    rows = (
        engineer_features(
            HouseFeatures(
                transaction_date=float(row[0]),
                house_age_years=float(row[1]),
                distance_to_mrt_m=float(row[2]),
                nearby_convenience_stores=int(row[3]),
                latitude=float(row[4]),
                longitude=float(row[5]),
            )
        )
        for row in raw_features
    )
    return np.asarray(list(rows), dtype=np.float64)


def train_and_evaluate(dataset: pd.DataFrame) -> dict[str, Any]:
    features = build_feature_matrix(dataset)
    target = dataset["target_unit_price"].to_numpy(dtype=np.float64)
    train_features, test_features, train_target, test_target = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=RANDOM_STATE,
    )

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "ridge",
                RidgeCV(
                    alphas=np.asarray(RIDGE_ALPHAS, dtype=np.float64),
                    cv=5,
                    scoring="neg_mean_absolute_error",
                ),
            ),
        ]
    )
    pipeline.fit(train_features, train_target)
    predictions = pipeline.predict(test_features)

    scaler = pipeline.named_steps["scaler"]
    ridge = pipeline.named_steps["ridge"]
    if not isinstance(scaler, StandardScaler) or not isinstance(ridge, RidgeCV):
        raise TypeError("training pipeline returned unexpected estimator types")
    if scaler.mean_ is None or scaler.scale_ is None:
        raise TypeError("fitted scaler is missing learned parameters")

    metrics = {
        "mae": float(mean_absolute_error(test_target, predictions)),
        "rmse": float(mean_squared_error(test_target, predictions) ** 0.5),
        "r2": float(r2_score(test_target, predictions)),
    }
    return {
        "schema_version": 1,
        "model_version": MODEL_VERSION,
        "model_type": "standard_scaler_ridge",
        "feature_order": list(MODEL_FEATURE_ORDER),
        "scaler": {
            "mean": scaler.mean_.astype(float).tolist(),
            "scale": scaler.scale_.astype(float).tolist(),
        },
        "model": {
            "alpha": float(ridge.alpha_),
            "coefficients": ridge.coef_.astype(float).tolist(),
            "intercept": float(ridge.intercept_),
        },
        "training": {
            "trained_at_utc": datetime.now(UTC).isoformat(),
            "random_state": RANDOM_STATE,
            "train_rows": len(train_target),
            "test_rows": len(test_target),
            "metrics": metrics,
            "dataset": {
                "name": "UCI Real Estate Valuation",
                "url": DATASET_URL,
                "sha256": DATASET_SHA256,
                "license": "CC BY 4.0",
            },
        },
    }


def export_artifact(artifact: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
