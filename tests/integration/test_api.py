from pathlib import Path
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient

import house_price_api.main as main_module
from house_price_api.api import get_prediction_service
from house_price_api.config import Settings
from house_price_api.domain import HouseFeatures
from house_price_api.main import create_app
from house_price_api.predictor import ModelArtifactError
from house_price_api.service import PricePredictionService

VALID_PAYLOAD = {
    "transaction_date": 2013.5,
    "house_age_years": 10,
    "distance_to_mrt_m": 500,
    "nearby_convenience_stores": 5,
    "latitude": 24.98,
    "longitude": 121.54,
    "area_m2": 80,
}


def test_health_and_prediction(model_path: Path) -> None:
    app = create_app(Settings(model_path=model_path))

    with TestClient(app) as client:
        health = client.get("/healthz")
        prediction = client.post("/predict", json=VALID_PAYLOAD)

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "model_version": "uci-real-estate-ridge-v1"}
    assert prediction.status_code == 200
    assert prediction.json()["model_version"] == "uci-real-estate-ridge-v1"
    assert prediction.json()["estimated_total_price_twd"] > 0


def test_prediction_rejects_out_of_domain_input(model_path: Path) -> None:
    app = create_app(Settings(model_path=model_path))
    payload = {**VALID_PAYLOAD, "latitude": 90}

    with TestClient(app) as client:
        response = client.post("/predict", json=payload)

    assert response.status_code == 422


def test_application_fails_startup_when_artifact_is_missing(tmp_path: Path) -> None:
    app = create_app(Settings(model_path=tmp_path / "missing.json"))

    with pytest.raises(ModelArtifactError), TestClient(app):
        pass


class StubPredictor:
    model_version = "stub-v1"

    def predict_unit_price(self, features: HouseFeatures) -> float:
        return 12.5


def test_prediction_service_dependency_can_be_overridden(model_path: Path) -> None:
    app = create_app(Settings(model_path=model_path))
    stub_service = PricePredictionService(StubPredictor())
    app.dependency_overrides[get_prediction_service] = lambda: stub_service

    with TestClient(app) as client:
        health = client.get("/healthz")
        prediction = client.post("/predict", json=VALID_PAYLOAD)

    assert health.json()["model_version"] == "stub-v1"
    assert prediction.json()["predicted_unit_price_10k_twd_per_ping"] == 12.5


def test_lifespan_loads_model_once(model_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real_predictor = main_module.JsonRidgePredictor

    class CountingPredictor(real_predictor):
        instances: ClassVar[int] = 0

        def __init__(self, artifact_path: Path) -> None:
            type(self).instances += 1
            super().__init__(artifact_path)

    monkeypatch.setattr(main_module, "JsonRidgePredictor", CountingPredictor)
    app = main_module.create_app(Settings(model_path=model_path))

    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/healthz").status_code == 200

    assert CountingPredictor.instances == 1
