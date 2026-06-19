"""
Target management endpoints.

Create, list, retrieve, update, and delete monitoring targets.
No authentication required.
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.target import (
    TargetCreateRequest, TargetResponse, TargetCreateResponse,
    TargetUpdateRequest, TargetListResponse,
)
from app.schemas.auth import MessageResponse
from app.services.target_service import TargetService

logger = logging.getLogger("media_intel.api.targets")

router = APIRouter(prefix="/api/v1/targets", tags=["Targets"])


@router.post(
    "/",
    response_model=TargetCreateResponse,
    status_code=201,
    summary="Create a target",
    description="Create a new monitoring target. "
                "Uses a two-stage matching pipeline:\n\n"
                "1. **Normalization match**: Fast exact match on normalized name.\n"
                "2. **LLM match**: If no normalization match, uses AI to find semantically "
                "similar targets (e.g., 'Apple' → 'Apple Inc').\n\n"
                "If a match is found, the existing target is returned instead of creating a duplicate.",
    responses={
        201: {"description": "Target created or matched successfully"},
        422: {"description": "Validation error"},
    },
)
async def create_target(
    request: TargetCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new target or return an existing matched one.

    Two-stage matching:
    1. Normalization: 'John Doe', 'john doe', 'JOHN DOE' → same target.
    2. LLM matching: 'Apple' matches 'Apple Inc', 'MSFT' matches 'Microsoft'.
    """
    service = TargetService(db)
    target, is_new, match_info = await service.create_or_get_target(
        name=request.name,
        target_type=request.target_type,
        description=request.description,
    )

    if is_new:
        message = f"New target '{target.display_name}' created successfully"
    else:
        matched_by = match_info.get("matched_by", "unknown")
        if matched_by == "llm":
            confidence = match_info.get("confidence", 0)
            message = (
                f"Target '{request.name}' matched to existing target "
                f"'{target.display_name}' via AI matching "
                f"(confidence: {confidence:.0%})."
            )
        else:
            message = (
                f"Target '{target.display_name}' already exists. "
                f"Returning existing target."
            )

    logger.info(
        f"Target {'created' if is_new else 'matched'}: {target.display_name} "
        f"(matched_by={match_info.get('matched_by', 'new')})"
    )

    return TargetCreateResponse(
        success=True,
        message=message,
        target=TargetResponse.model_validate(target),
        is_new=is_new,
        matched_by=match_info.get("matched_by"),
        match_confidence=match_info.get("confidence"),
        match_reasoning=match_info.get("reasoning"),
    )


@router.get(
    "/",
    response_model=TargetListResponse,
    summary="List all targets",
    description="Retrieve a paginated list of all active targets.",
)
async def list_targets(
    limit: int = Query(50, ge=1, le=200, description="Max targets to return"),
    offset: int = Query(0, ge=0, description="Number of targets to skip"),
    db: AsyncSession = Depends(get_db),
):
    """List all active targets with pagination."""
    service = TargetService(db)
    targets, total = await service.list_targets(limit=limit, offset=offset)
    return TargetListResponse(
        success=True,
        total=total,
        targets=[TargetResponse.model_validate(t) for t in targets],
    )


@router.get(
    "/{target_id}",
    response_model=TargetResponse,
    summary="Get target details",
    description="Retrieve details for a specific target by its UUID.",
    responses={
        404: {"description": "Target not found"},
    },
)
async def get_target(
    target_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get target details by ID."""
    service = TargetService(db)
    target = await service.get_target_by_id(target_id)
    return target


@router.put(
    "/{target_id}",
    response_model=TargetResponse,
    summary="Update a target",
    description="Update target details. If the display name changes, "
                "the normalized name is recomputed automatically.",
    responses={
        404: {"description": "Target not found"},
        409: {"description": "Normalized name already exists"},
    },
)
async def update_target(
    target_id: UUID,
    request: TargetUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update a target's details."""
    service = TargetService(db)
    target = await service.update_target(
        target_id=target_id,
        display_name=request.display_name,
        target_type=request.target_type,
        description=request.description,
        is_active=request.is_active,
    )
    return target


@router.delete(
    "/{target_id}",
    response_model=MessageResponse,
    summary="Delete a target",
    description="Soft-delete a target by setting is_active to False.",
    responses={
        404: {"description": "Target not found"},
    },
)
async def delete_target(
    target_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a target."""
    service = TargetService(db)
    target = await service.delete_target(target_id)
    return MessageResponse(
        success=True,
        message=f"Target '{target.display_name}' has been deactivated",
    )
