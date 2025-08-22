import time
import psutil
from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schemas import HealthCheck, MetricsResponse
from app.models.predictor import predictor
from app.core.config import settings
from app.middleware.metrics import get_metrics

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
    """Readiness check for Kubernetes"""
    if not predictor.is_loaded():
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", "reason": "model not loaded"}
        )
    
    return JSONResponse(content={"status": "ready"})


@router.get("/health/live")
async def liveness_check():
    """Liveness check for Kubernetes"""
    return JSONResponse(content={"status": "alive"})


@router.get("/metrics/prometheus")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    return get_metrics()


@router.get("/metrics/system")
async def system_metrics():
    """System metrics endpoint"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return JSONResponse(content={
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available // (1024 * 1024),
            "disk_percent": (disk.used / disk.total) * 100,
            "disk_free_gb": disk.free // (1024 * 1024 * 1024),
            "uptime_seconds": time.time() - _start_time,
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get system metrics: {str(e)}"}
        )