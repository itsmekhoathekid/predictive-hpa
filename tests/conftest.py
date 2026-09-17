from pathlib import Path

import pytest


@pytest.fixture
def model_path() -> Path:
    return Path(__file__).parents[1] / "models" / "uci-real-estate-ridge-v1.json"
