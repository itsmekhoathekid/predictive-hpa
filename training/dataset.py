import hashlib
import math
import urllib.request
import zipfile
from pathlib import Path
from typing import cast

import pandas as pd

DATASET_URL = "https://archive.ics.uci.edu/static/public/477/real+estate+valuation+data+set.zip"
DATASET_SHA256 = "aa437bdac3ca23200258a0a58d251c0af90651aeaf7c7a07aaa714f0f9f25e2c"
DATASET_ARCHIVE_MEMBER = "Real estate valuation data set.xlsx"
DATASET_FILENAME = "real-estate-valuation.zip"

DATA_COLUMNS = (
    "transaction_date",
    "house_age_years",
    "distance_to_mrt_m",
    "nearby_convenience_stores",
    "latitude",
    "longitude",
    "target_unit_price",
)


class DatasetIntegrityError(ValueError):
    """Raised when downloaded data does not match the pinned dataset."""


def download_dataset(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive_path = cache_dir / DATASET_FILENAME
    if not archive_path.exists():
        partial_path = archive_path.with_suffix(".part")
        with urllib.request.urlopen(DATASET_URL, timeout=30) as response:
            partial_path.write_bytes(response.read())
        partial_path.replace(archive_path)

    verify_dataset_checksum(archive_path)
    return archive_path


def verify_dataset_checksum(archive_path: Path) -> None:
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != DATASET_SHA256:
        raise DatasetIntegrityError(
            f"dataset checksum mismatch: expected {DATASET_SHA256}, got {digest}"
        )


def load_dataset(archive_path: Path) -> pd.DataFrame:
    verify_dataset_checksum(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        if DATASET_ARCHIVE_MEMBER not in archive.namelist():
            raise DatasetIntegrityError("expected XLSX file is missing from dataset archive")
        with archive.open(DATASET_ARCHIVE_MEMBER) as workbook:
            source = pd.read_excel(workbook)

    if source.shape != (414, 8):
        raise DatasetIntegrityError(f"unexpected dataset shape: {source.shape}")

    dataset = source.iloc[:, 1:].copy()
    dataset.columns = DATA_COLUMNS
    dataset = cast(pd.DataFrame, dataset.apply(pd.to_numeric, errors="raise"))
    if dataset.isna().any().any():
        raise DatasetIntegrityError("dataset contains missing values")
    if not dataset.map(lambda value: math.isfinite(float(value))).all().all():
        raise DatasetIntegrityError("dataset contains non-finite values")
    return dataset
