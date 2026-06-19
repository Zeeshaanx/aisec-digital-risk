"""
Central API v1 router — aggregates all endpoint groups.
"""

from fastapi import APIRouter

from app.api.v1.targets import router as targets_router
from app.api.v1.scans import router as scans_router
from app.api.v1.results import router as results_router

api_v1_router = APIRouter()

api_v1_router.include_router(targets_router)
api_v1_router.include_router(scans_router)
api_v1_router.include_router(results_router)
