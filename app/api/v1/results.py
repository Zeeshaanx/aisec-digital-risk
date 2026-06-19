"""
Result retrieval endpoints.

All results are served from the database (single source of truth).
Supports filtering by date range, sentiment, and platform.
No authentication required.
"""

import logging
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.scan import ArticleResponse, ScanResultsResponse
from app.services.scan_service import ScanService
from app.services.target_service import TargetService

logger = logging.getLogger("media_intel.api.results")

router = APIRouter(prefix="/api/v1/results", tags=["Results"])


@router.get(
    "/target/{target_id}",
    response_model=ScanResultsResponse,
    summary="Get all results for a target",
    description="Retrieve all articles for a target within an optional date range. "
                "Supports filtering by sentiment and platform.",
    responses={
        200: {"description": "Results retrieved successfully"},
        404: {"description": "Target not found"},
    },
)
async def get_target_results(
    target_id: UUID,
    from_date: datetime | None = Query(
        None, description="Start date filter (ISO format, e.g., 2024-01-01T00:00:00)"
    ),
    to_date: datetime | None = Query(
        None, description="End date filter (ISO format)"
    ),
    sentiment: str | None = Query(
        None, description="Filter by sentiment: positive, negative, neutral"
    ),
    platform: str | None = Query(
        None, description="Filter by platform: web, twitter, reddit, youtube, etc."
    ),
    limit: int = Query(100, ge=1, le=500, description="Max articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all articles for a target from the database.

    Results are deduplicated by (target_id, normalized_url) at the storage level.
    """
    # Verify target exists
    target_service = TargetService(db)
    await target_service.get_target_by_id(target_id)

    scan_service = ScanService(db)
    articles, total = await scan_service.get_articles_for_target(
        target_id=target_id,
        from_date=from_date,
        to_date=to_date,
        sentiment=sentiment,
        platform=platform,
        limit=limit,
        offset=offset,
    )

    # Build sentiment and platform summaries
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    platform_counts = {}
    for a in articles:
        sent = a.sentiment.value if hasattr(a.sentiment, "value") else str(a.sentiment)
        if sent in sentiment_counts:
            sentiment_counts[sent] += 1
        plat = a.platform or "web"
        platform_counts[plat] = platform_counts.get(plat, 0) + 1

    total_articles = sum(sentiment_counts.values())
    sentiment_summary = {
        **sentiment_counts,
        "positive_pct": round(sentiment_counts["positive"] / total_articles * 100, 1) if total_articles else 0,
        "negative_pct": round(sentiment_counts["negative"] / total_articles * 100, 1) if total_articles else 0,
        "neutral_pct": round(sentiment_counts["neutral"] / total_articles * 100, 1) if total_articles else 0,
    }

    return ScanResultsResponse(
        success=True,
        target_id=target_id,
        total_count=total,
        articles=[ArticleResponse.model_validate(a) for a in articles],
        sentiment_summary=sentiment_summary,
        platform_breakdown=platform_counts,
        limit=limit,
        offset=offset,
        has_more=(offset + limit < total),
    )


@router.get(
    "/scan/{scan_id}",
    response_model=ScanResultsResponse,
    summary="Get results for a specific scan",
    description="Retrieve all articles discovered by a specific scan execution. "
                "Includes both newly discovered articles and previously existing ones.",
    responses={
        200: {"description": "Scan results retrieved successfully"},
        404: {"description": "Scan not found"},
    },
)
async def get_scan_results(
    scan_id: UUID,
    limit: int = Query(100, ge=1, le=500, description="Max articles to return"),
    offset: int = Query(0, ge=0, description="Number of articles to skip"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all articles linked to a specific scan.

    The new_articles_found field shows how many were first discovered by this scan.
    """
    scan_service = ScanService(db)
    scan = await scan_service.get_scan_by_id(scan_id)

    articles, total, new_count = await scan_service.get_articles_for_scan(
        scan_id=scan_id,
        limit=limit,
        offset=offset,
    )

    # Build summaries
    sentiment_counts = {"positive": 0, "negative": 0, "neutral": 0}
    platform_counts = {}
    for a in articles:
        sent = a.sentiment.value if hasattr(a.sentiment, "value") else str(a.sentiment)
        if sent in sentiment_counts:
            sentiment_counts[sent] += 1
        plat = a.platform or "web"
        platform_counts[plat] = platform_counts.get(plat, 0) + 1

    total_articles = sum(sentiment_counts.values())
    sentiment_summary = {
        **sentiment_counts,
        "positive_pct": round(sentiment_counts["positive"] / total_articles * 100, 1) if total_articles else 0,
        "negative_pct": round(sentiment_counts["negative"] / total_articles * 100, 1) if total_articles else 0,
        "neutral_pct": round(sentiment_counts["neutral"] / total_articles * 100, 1) if total_articles else 0,
    }

    return ScanResultsResponse(
        success=True,
        scan_id=scan_id,
        target_id=scan.target_id,
        total_count=total,
        new_articles_found=new_count,
        scan_execution_time=scan.processing_time_sec,
        articles=[ArticleResponse.model_validate(a) for a in articles],
        sentiment_summary=sentiment_summary,
        risk_summary=scan.risk_summary,
        security_alerts=scan.security_alerts,
        platform_breakdown=platform_counts,
        limit=limit,
        offset=offset,
        has_more=(offset + limit < total),
    )
