"""
Health check endpoint.

Provides a simple liveness probe for load balancers and monitoring.
Checks database connectivity and returns application version info.
"""

import logging
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import get_settings

logger = logging.getLogger("media_intel.api.health")

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    summary="Health check",
    description="Check application health and database connectivity.",
    responses={
        200: {
            "description": "Application is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "version": "1.0.0",
                        "database": "connected",
                    }
                }
            },
        },
        503: {"description": "Application is unhealthy"},
    },
)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Application health check.

    Verifies:
    - The application is running.
    - The database connection is active.
    """
    settings = get_settings()

    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Health check DB failure: {e}")
        db_status = "disconnected"

    healthy = db_status == "connected"

    response = {
        "status": "healthy" if healthy else "unhealthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
    }

    if not healthy:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=response)

    return response
