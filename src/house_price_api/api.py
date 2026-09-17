from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from house_price_api.domain import HouseFeatures, PricePrediction
from house_price_api.service import PricePredictionService


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    transaction_date: float = Field(ge=2012.0, le=2014.0)
    house_age_years: float = Field(ge=0.0, le=100.0)
    distance_to_mrt_m: float = Field(ge=0.0, le=10_000.0)
    nearby_convenience_stores: int = Field(ge=0, le=20)
    latitude: float = Field(ge=24.9, le=25.1)
    longitude: float = Field(ge=121.4, le=121.7)
    area_m2: float = Field(gt=0.0, le=1_000.0)

    def to_domain(self) -> HouseFeatures:
        return HouseFeatures(
            transaction_date=self.transaction_date,
            house_age_years=self.house_age_years,
            distance_to_mrt_m=self.distance_to_mrt_m,
            nearby_convenience_stores=self.nearby_convenience_stores,
            latitude=self.latitude,
            longitude=self.longitude,
        )


class PredictionResponse(BaseModel):
    predicted_unit_price_10k_twd_per_ping: float
    estimated_total_price_twd: float
    model_version: str

    @classmethod
    def from_domain(cls, prediction: PricePrediction) -> "PredictionResponse":
        return cls(
            predicted_unit_price_10k_twd_per_ping=round(
                prediction.predicted_unit_price_10k_twd_per_ping, 2
            ),
            estimated_total_price_twd=round(prediction.estimated_total_price_twd, 2),
            model_version=prediction.model_version,
        )


class HealthResponse(BaseModel):
    status: str
    model_version: str


def get_prediction_service(request: Request) -> PricePredictionService:
    return cast(PricePredictionService, request.app.state.prediction_service)


PredictionServiceDependency = Annotated[
    PricePredictionService,
    Depends(get_prediction_service),
]

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse, tags=["health"])
async def health(service: PredictionServiceDependency) -> HealthResponse:
    return HealthResponse(status="ok", model_version=service.model_version)


@router.post("/predict", response_model=PredictionResponse, tags=["prediction"])
def predict(
    request: PredictionRequest,
    service: PredictionServiceDependency,
) -> PredictionResponse:
    prediction = service.predict(request.to_domain(), request.area_m2)
    return PredictionResponse.from_domain(prediction)
