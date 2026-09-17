import math
from typing import Protocol

from house_price_api.domain import HouseFeatures, PricePrediction, estimate_total_price_twd


class PricePredictor(Protocol):
    @property
    def model_version(self) -> str: ...

    def predict_unit_price(self, features: HouseFeatures) -> float: ...


class PricePredictionService:
    """Run model inference and convert its unit-price result to a total price."""

    def __init__(self, predictor: PricePredictor) -> None:
        self._predictor = predictor

    @property
    def model_version(self) -> str:
        return self._predictor.model_version

    def predict(self, features: HouseFeatures, area_m2: float) -> PricePrediction:
        raw_unit_price = self._predictor.predict_unit_price(features)
        if not math.isfinite(raw_unit_price):
            raise RuntimeError("model returned a non-finite prediction")

        unit_price = max(0.0, raw_unit_price)
        return PricePrediction(
            predicted_unit_price_10k_twd_per_ping=unit_price,
            estimated_total_price_twd=estimate_total_price_twd(unit_price, area_m2),
            model_version=self.model_version,
        )
