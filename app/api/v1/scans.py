"""
Scan management endpoints.

Handles scan creation (one-time and scheduled), listing, detail retrieval,
and schedule cancellation. Scan execution runs asynchronously in the background.
No authentication required.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.exceptions import NotFoundException
from app.models.enums import ScanStatus, ScanType
from app.schemas.scan import (
    ScanCreateRequest, ScanResponse, ScanListResponse,
)
from app.schemas.auth import MessageResponse
from app.services.scan_service import ScanService
from app.services.target_service import TargetService

logger = logging.getLogger("media_intel.api.scans")

router = APIRouter(prefix="/api/v1/scans", tags=["Scans"])


async def _execute_scan_background(scan_id: str, target_id: str):
    """
    Background task that executes a scan.

    Creates its own database session since FastAPI background tasks
    run outside the request lifecycle.

    Args:
        scan_id: UUID string of the scan.
        target_id: UUID string of the target.
    """
    from app.agents.orchestrator import ScanOrchestrator

    logger.info(f"Background scan execution starting: {scan_id}")

    async with AsyncSessionLocal() as db:
        try:
            orchestrator = ScanOrchestrator(db)
            await orchestrator.execute_scan(
                scan_id=UUID(scan_id),
                target_id=UUID(target_id),
            )
        except Exception as e:
            logger.exception(f"Background scan failed: {scan_id} — {e}")
            try:
                scan_service = ScanService(db)
                await scan_service.fail_scan(UUID(scan_id), str(e)[:2000])
            except Exception as db_err:
                logger.exception(f"Failed to record scan failure: {db_err}")


@router.post(
    "/",
    response_model=ScanResponse,
    status_code=201,
    summary="Create a new scan",
    description="Create a one-time or scheduled scan for a target. "
                "One-time scans execute immediately in the background. "
                "Scheduled scans run at the specified interval.",
    responses={
        201: {"description": "Scan created and queued for execution"},
        404: {"description": "Target not found"},
        422: {"description": "Validation error"},
    },
)
async def create_scan(
    request: ScanCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Create and queue a new scan.

    - **one_time**: Executes immediately in the background, results stored in DB.
    - **scheduled**: First execution runs immediately, then repeats at schedule_interval.

    The API returns immediately with the scan record. Poll GET /scans/{scan_id}
    for status updates, or query results once status is 'completed'.
    """
    # Verify target exists
    target_service = TargetService(db)
    await target_service.get_target_by_id(request.target_id)

    # Create scan record
    scan_service = ScanService(db)
    scan = await scan_service.create_scan(
        target_id=request.target_id,
        scan_type=request.scan_type,
        scan_depth=request.scan_depth,
        timeframe=request.timeframe,
        schedule_interval=request.schedule_interval,
    )

    # Queue background execution
    background_tasks.add_task(
        _execute_scan_background,
        str(scan.id),
        str(scan.target_id),
    )

    logger.info(
        f"Scan {scan.id} created and queued",
        extra={"action": "scan_queued", "scan_id": str(scan.id)},
    )
    return scan


@router.get(
    "/",
    response_model=ScanListResponse,
    summary="List all scans",
    description="List all scans with optional status and type filters.",
)
async def list_scans(
    status: ScanStatus | None = Query(None, description="Filter by scan status"),
    scan_type: ScanType | None = Query(None, description="Filter by scan type"),
    target_id: UUID | None = Query(None, description="Filter by target ID"),
    limit: int = Query(50, ge=1, le=200, description="Max scans to return"),
    offset: int = Query(0, ge=0, description="Number of scans to skip"),
    db: AsyncSession = Depends(get_db),
):
    """List scans with optional filtering and pagination."""
    service = ScanService(db)
    scans, total = await service.list_scans(
        status_filter=status,
        scan_type_filter=scan_type,
        target_id_filter=target_id,
        limit=limit,
        offset=offset,
    )
    return ScanListResponse(
        success=True,
        total=total,
        scans=[ScanResponse.model_validate(s) for s in scans],
    )


@router.get(
    "/scheduled",
    response_model=ScanListResponse,
    summary="List active scheduled scans",
    description="List all active scheduled scans.",
)
async def list_scheduled_scans(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List active scheduled scans with pagination."""
    service = ScanService(db)
    scans, total = await service.list_scheduled_scans(limit=limit, offset=offset)
    return ScanListResponse(
        success=True,
        total=total,
        scans=[ScanResponse.model_validate(s) for s in scans],
    )


@router.get(
    "/{scan_id}",
    response_model=ScanResponse,
    summary="Get scan details",
    description="Retrieve detailed information about a specific scan, "
                "including status, results summary, and cost.",
    responses={
        404: {"description": "Scan not found"},
    },
)
async def get_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get scan details by ID."""
    service = ScanService(db)
    scan = await service.get_scan_by_id(scan_id)
    return scan


@router.delete(
    "/{scan_id}/schedule",
    response_model=MessageResponse,
    summary="Cancel a scheduled scan",
    description="Stop future executions of a scheduled scan. "
                "Historical results are retained.",
    responses={
        404: {"description": "Scan not found"},
        422: {"description": "Scan is not a scheduled scan"},
    },
)
async def cancel_scheduled_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Cancel a scheduled scan.

    Stops future executions. Past scan results are preserved.
    """
    service = ScanService(db)
    scan = await service.cancel_scheduled_scan(scan_id)

    try:
        from app.core.scheduler import remove_scheduled_job
        await remove_scheduled_job(str(scan_id))
    except Exception as e:
        logger.warning(f"Could not remove scheduler job for {scan_id}: {e}")

    logger.info(f"Scheduled scan {scan_id} cancelled")
    return MessageResponse(
        success=True,
        message=f"Scheduled scan {scan_id} has been cancelled. Historical results are preserved.",
    )
