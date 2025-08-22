from fastapi import APIRouter
from app.api.v1.endpoints import scoring, health

router = APIRouter()

# Include endpoint routers
router.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
router.include_router(health.router, tags=["health"])