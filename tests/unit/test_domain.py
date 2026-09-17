import math

import pytest

from house_price_api.domain import HouseFeatures, engineer_features, estimate_total_price_twd


def sample_features() -> HouseFeatures:
    return HouseFeatures(2013.5, 10.0, 500.0, 5, 24.98, 121.54)


def test_engineer_features_adds_expected_derived_values() -> None:
    vector = engineer_features(sample_features())

    assert vector[:6] == (2013.5, 10.0, 500.0, 5.0, 24.98, 121.54)
    assert vector[6] == pytest.approx(math.log1p(500.0))
    assert vector[7] == 100.0


def test_engineer_features_rejects_non_finite_values() -> None:
    features = HouseFeatures(2013.5, 10.0, math.inf, 5, 24.98, 121.54)

    with pytest.raises(ValueError, match="finite"):
        engineer_features(features)


def test_estimate_total_price_converts_ping_to_square_metres() -> None:
    assert estimate_total_price_twd(44.0, 3.3) == pytest.approx(440_000.0)


@pytest.mark.parametrize("area", [0.0, -1.0, math.inf])
def test_estimate_total_price_rejects_invalid_area(area: float) -> None:
    with pytest.raises(ValueError):
        estimate_total_price_twd(44.0, area)
