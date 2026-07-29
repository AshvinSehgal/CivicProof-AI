from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from civicproof.api.routes import health, incidents
from civicproof.core.config import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = get_settings()
    yield

app = FastAPI(
    title="CivicProof AI",
    description="Evidence-backed multimodal incident triage",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(health.router)
app.include_router(incidents.router, prefix="/v1")
