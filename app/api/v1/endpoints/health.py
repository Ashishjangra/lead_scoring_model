import time
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schemas import HealthCheck
from app.models.predictor import predictor
from app.core.config import settings

router = APIRouter()

# Track service start time
_start_time = time.time()


@router.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    uptime = time.time() - _start_time
    model_loaded = predictor.is_loaded()
    
    status = "healthy" if model_loaded else "degraded"
    
    return HealthCheck(
        status=status,
        version=settings.app_version,
        model_loaded=model_loaded,
        uptime_seconds=uptime
    )


@router.get("/health/ready")
async def readiness_check():
    """Readiness check for ECS Fargate"""
    if not predictor.is_loaded():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "model not loaded"}
        )
    
    return JSONResponse(content={"status": "ready"})


@router.get("/health/live")
async def liveness_check():
    """Liveness check for ECS Fargate"""
    return JSONResponse(content={"status": "alive"})