from pathlib import Path

import pandas as pd
import pytest

from training.dataset import DatasetIntegrityError, download_dataset
from training.pipeline import build_feature_matrix, train_and_evaluate


def test_download_rejects_cached_file_with_wrong_checksum(tmp_path: Path) -> None:
    (tmp_path / "real-estate-valuation.zip").write_bytes(b"not the UCI dataset")

    with pytest.raises(DatasetIntegrityError, match="checksum mismatch"):
        download_dataset(tmp_path)


def test_training_is_numerically_deterministic() -> None:
    rows = []
    for index in range(40):
        rows.append(
            {
                "transaction_date": 2012.5 + (index % 12) / 12,
                "house_age_years": float(index % 30),
                "distance_to_mrt_m": float(100 + index * 25),
                "nearby_convenience_stores": index % 10,
                "latitude": 24.95 + index * 0.001,
                "longitude": 121.50 + index * 0.001,
                "target_unit_price": 30.0 + index * 0.5,
            }
        )
    dataset = pd.DataFrame(rows)

    first = train_and_evaluate(dataset)
    second = train_and_evaluate(dataset)

    assert first["model"] == second["model"]
    assert first["training"]["metrics"] == second["training"]["metrics"]
    assert build_feature_matrix(dataset).shape == (40, 8)
