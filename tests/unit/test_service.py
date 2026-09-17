import math
from dataclasses import dataclass

import pytest

from house_price_api.domain import HouseFeatures
from house_price_api.service import PricePredictionService


@dataclass
class FakePredictor:
    value: float
    model_version: str = "test-v1"

    def predict_unit_price(self, features: HouseFeatures) -> float:
        return self.value


def test_service_builds_prediction() -> None:
    service = PricePredictionService(FakePredictor(44.0))

    result = service.predict(HouseFeatures(2013.5, 10.0, 500.0, 5, 24.98, 121.54), 80.0)

    assert result.predicted_unit_price_10k_twd_per_ping == 44.0
    assert result.estimated_total_price_twd == pytest.approx(10_666_666.67, rel=1e-8)


def test_service_clamps_negative_predictions() -> None:
    service = PricePredictionService(FakePredictor(-5.0))

    result = service.predict(HouseFeatures(2013.5, 10.0, 500.0, 5, 24.98, 121.54), 80.0)

    assert result.predicted_unit_price_10k_twd_per_ping == 0.0
    assert result.estimated_total_price_twd == 0.0


def test_service_rejects_non_finite_model_output() -> None:
    service = PricePredictionService(FakePredictor(math.nan))

    with pytest.raises(RuntimeError, match="non-finite"):
        service.predict(HouseFeatures(2013.5, 10.0, 500.0, 5, 24.98, 121.54), 80.0)
