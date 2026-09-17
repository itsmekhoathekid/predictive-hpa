import math
from dataclasses import dataclass

PING_IN_SQUARE_METERS = 3.3
TWD_PER_DATASET_PRICE_UNIT = 10_000.0

MODEL_FEATURE_ORDER = (
    "transaction_date",
    "house_age_years",
    "distance_to_mrt_m",
    "nearby_convenience_stores",
    "latitude",
    "longitude",
    "log_distance_to_mrt_m",
    "house_age_squared",
)


@dataclass(frozen=True, slots=True)
class HouseFeatures:
    transaction_date: float
    house_age_years: float
    distance_to_mrt_m: float
    nearby_convenience_stores: int
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class PricePrediction:
    predicted_unit_price_10k_twd_per_ping: float
    estimated_total_price_twd: float
    model_version: str


def engineer_features(features: HouseFeatures) -> tuple[float, ...]:
    """Build the exact numeric vector shared by training and inference."""
    values = (
        features.transaction_date,
        features.house_age_years,
        features.distance_to_mrt_m,
        float(features.nearby_convenience_stores),
        features.latitude,
        features.longitude,
        math.log1p(features.distance_to_mrt_m),
        features.house_age_years**2,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("engineered features must all be finite")
    return values


def estimate_total_price_twd(unit_price: float, area_m2: float) -> float:
    """Convert the UCI target unit into an estimated total price in TWD."""
    if not math.isfinite(unit_price) or not math.isfinite(area_m2):
        raise ValueError("price and area must be finite")
    if area_m2 <= 0:
        raise ValueError("area_m2 must be greater than zero")
    return unit_price * TWD_PER_DATASET_PRICE_UNIT * area_m2 / PING_IN_SQUARE_METERS
