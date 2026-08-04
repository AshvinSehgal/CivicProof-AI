from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from civicproof.api.routes import health, incidents
from civicproof.core.config import get_settings
from civicproof.services.embedding_classifier import EmbeddingClassifier
from civicproof.core.logging import configure_logging
from civicproof.services.weather import NWSWeatherClient
import json
import logging
import time

configure_logging()
logger = logging.getLogger('civicproof')

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    model_loading_start = time.perf_counter()
    try:
        classifier = EmbeddingClassifier()
        classifier.load_model()
    except Exception as error:
        model_loading_time = time.perf_counter() - model_loading_start
        logger.exception(
            json.dumps(
                {
                    'event': 'embedding_classifier_load_failed',
                    'status': 'error',
                    'error_type': type(error).__name__,
                    'model_load_time_ms': round(model_loading_time * 1000, 2)
                }
            )
        )
        raise
    model_loading_time = time.perf_counter() - model_loading_start
    app.state.classifier = classifier
    logger.info(
        json.dumps(
            {
                'event': 'embedding_classifier_loaded',
                'status': 'success',
                'model_version': classifier.model_name,
                'model_load_time_ms': round(model_loading_time * 1000, 2)
            }
        )
    )
    try:
        settings = get_settings()
        weather_client = NWSWeatherClient(settings.nws_base_url, settings.nws_user_agent, settings.nws_timeout_seconds)
    except Exception as error:
        logger.exception(
            json.dumps(
                {
                    'event': 'weather_client_load_failed',
                    'status': 'error',
                    'error_type': type(error).__name__
                }
            )
        )
        raise
    app.state.settings = settings
    app.state.weather_client = weather_client
    try:
        yield
    finally:
        weather_client.close()

app = FastAPI(
    title="CivicProof AI",
    description="Evidence-backed multimodal incident triage",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(incidents.router, prefix="/v1")
