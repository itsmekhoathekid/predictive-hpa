import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from house_price_api.api import router
from house_price_api.config import Settings
from house_price_api.predictor import JsonRidgePredictor
from house_price_api.service import PricePredictionService

LOGGER = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        predictor = JsonRidgePredictor(resolved_settings.model_path)
        app.state.prediction_service = PricePredictionService(predictor)
        LOGGER.info("Loaded model %s", predictor.model_version)
        yield

    application = FastAPI(title=resolved_settings.app_name, version="0.1.0", lifespan=lifespan)
    application.include_router(router)
    return application


app = create_app()
