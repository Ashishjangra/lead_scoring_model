import time

from fastapi import APIRouter

from app.core.config import settings
from app.models.predictor import predictor
from app.models.schemas import HealthCheck

router = APIRouter()

# Track service start time
_start_time = time.time()


@router.get("/health", response_model=HealthCheck)
async def health_check() -> HealthCheck:
    """Health check endpoint"""
    uptime = time.time() - _start_time
    model_loaded = predictor.is_loaded()

    status = "healthy" if model_loaded else "degraded"

    return HealthCheck(
        status=status,
        version=settings.app_version,
        model_loaded=model_loaded,
        uptime_seconds=uptime,
    )
