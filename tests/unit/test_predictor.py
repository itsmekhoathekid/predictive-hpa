import json
from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from house_price_api.domain import HouseFeatures, engineer_features
from house_price_api.predictor import (
    JsonRidgePredictor,
    ModelArtifactError,
)


def test_predictor_loads_real_artifact_and_returns_finite_value(model_path: Path) -> None:
    predictor = JsonRidgePredictor(model_path)

    result = predictor.predict_unit_price(HouseFeatures(2013.5, 10.0, 500.0, 5, 24.98, 121.54))

    assert predictor.model_version == "uci-real-estate-ridge-v1"
    assert 0.0 < result < 100.0


def test_json_inference_matches_equivalent_scikit_learn_pipeline(model_path: Path) -> None:
    payload = json.loads(model_path.read_text(encoding="utf-8"))
    scaler = StandardScaler()
    scaler.mean_ = np.asarray(payload["scaler"]["mean"], dtype=np.float64)
    scaler.scale_ = np.asarray(payload["scaler"]["scale"], dtype=np.float64)
    scaler.var_ = scaler.scale_**2
    scaler.n_features_in_ = len(scaler.mean_)

    ridge = Ridge(alpha=payload["model"]["alpha"])
    ridge.coef_ = np.asarray(payload["model"]["coefficients"], dtype=np.float64)
    ridge.intercept_ = payload["model"]["intercept"]
    ridge.n_features_in_ = len(ridge.coef_)
    reference = Pipeline([("scaler", scaler), ("ridge", ridge)])

    features = HouseFeatures(2013.5, 10.0, 500.0, 5, 24.98, 121.54)
    expected = reference.predict(np.asarray([engineer_features(features)]))[0]

    assert JsonRidgePredictor(model_path).predict_unit_price(features) == pytest.approx(expected)


def test_predictor_rejects_wrong_feature_order(model_path: Path, tmp_path: Path) -> None:
    payload = json.loads(model_path.read_text(encoding="utf-8"))
    payload["feature_order"] = list(reversed(payload["feature_order"]))
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelArtifactError, match="feature_order"):
        JsonRidgePredictor(invalid_path)


def test_predictor_fails_fast_for_missing_artifact(tmp_path: Path) -> None:
    with pytest.raises(ModelArtifactError, match="not found"):
        JsonRidgePredictor(tmp_path / "missing.json")


def test_predictor_rejects_non_object_json(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ModelArtifactError, match="root"):
        JsonRidgePredictor(invalid_path)


def test_predictor_rejects_zero_scaler_value(model_path: Path, tmp_path: Path) -> None:
    payload = json.loads(model_path.read_text(encoding="utf-8"))
    payload["scaler"]["scale"][0] = 0
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ModelArtifactError, match="greater than zero"):
        JsonRidgePredictor(invalid_path)
