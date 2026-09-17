import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from house_price_api.domain import MODEL_FEATURE_ORDER, HouseFeatures, engineer_features

EXPECTED_SCHEMA_VERSION = 1
EXPECTED_MODEL_TYPE = "standard_scaler_ridge"


class ModelArtifactError(ValueError):
    """Raised when a model artifact is missing or internally inconsistent."""


@dataclass(frozen=True, slots=True)
class RidgeArtifact:
    model_version: str
    feature_order: tuple[str, ...]
    scaler_mean: tuple[float, ...]
    scaler_scale: tuple[float, ...]
    coefficients: tuple[float, ...]
    intercept: float
    alpha: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RidgeArtifact":
        if payload.get("schema_version") != EXPECTED_SCHEMA_VERSION:
            raise ModelArtifactError("unsupported model artifact schema_version")
        if payload.get("model_type") != EXPECTED_MODEL_TYPE:
            raise ModelArtifactError("unsupported model_type")

        model_version = _required_string(payload, "model_version")
        feature_order = _string_tuple(payload.get("feature_order"), "feature_order")
        if feature_order != MODEL_FEATURE_ORDER:
            raise ModelArtifactError("artifact feature_order does not match runtime features")

        scaler = _required_mapping(payload, "scaler")
        model = _required_mapping(payload, "model")
        expected_size = len(MODEL_FEATURE_ORDER)
        scaler_mean = _finite_float_tuple(scaler.get("mean"), "scaler.mean", expected_size)
        scaler_scale = _finite_float_tuple(scaler.get("scale"), "scaler.scale", expected_size)
        if any(value <= 0 for value in scaler_scale):
            raise ModelArtifactError("scaler.scale values must be greater than zero")

        coefficients = _finite_float_tuple(
            model.get("coefficients"), "model.coefficients", expected_size
        )
        intercept = _finite_float(model.get("intercept"), "model.intercept")
        alpha = _finite_float(model.get("alpha"), "model.alpha")
        if alpha <= 0:
            raise ModelArtifactError("model.alpha must be greater than zero")

        return cls(
            model_version=model_version,
            feature_order=feature_order,
            scaler_mean=scaler_mean,
            scaler_scale=scaler_scale,
            coefficients=coefficients,
            intercept=intercept,
            alpha=alpha,
        )


class JsonRidgePredictor:
    """Run Ridge inference from a transparent, validated JSON artifact."""

    def __init__(self, artifact_path: Path) -> None:
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ModelArtifactError(f"model artifact not found: {artifact_path}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise ModelArtifactError(f"cannot read model artifact: {artifact_path}") from error
        if not isinstance(payload, dict):
            raise ModelArtifactError("model artifact root must be a JSON object")
        self._artifact = RidgeArtifact.from_mapping(payload)

    @property
    def model_version(self) -> str:
        return self._artifact.model_version

    def predict_unit_price(self, features: HouseFeatures) -> float:
        vector = engineer_features(features)
        standardized = (
            (value - mean) / scale
            for value, mean, scale in zip(
                vector,
                self._artifact.scaler_mean,
                self._artifact.scaler_scale,
                strict=True,
            )
        )
        return self._artifact.intercept + sum(
            value * coefficient
            for value, coefficient in zip(standardized, self._artifact.coefficients, strict=True)
        )


def _required_mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ModelArtifactError(f"{key} must be an object")
    return value


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ModelArtifactError(f"{key} must be a non-empty string")
    return value


def _string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ModelArtifactError(f"{field_name} must be an array of strings")
    return tuple(value)


def _finite_float_tuple(value: object, field_name: str, size: int) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ModelArtifactError(f"{field_name} must be an array")
    result = tuple(_finite_float(item, field_name) for item in value)
    if len(result) != size:
        raise ModelArtifactError(f"{field_name} must contain exactly {size} values")
    return result


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ModelArtifactError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ModelArtifactError(f"{field_name} must be finite")
    return result
