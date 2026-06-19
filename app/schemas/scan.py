"""
Pydantic schemas for scan management and result endpoints.
"""

from datetime import datetime, date
from uuid import UUID
from typing import Optional, Any
from pydantic import BaseModel, Field, model_validator

from app.models.enums import ScanType, ScanStatus, ScanDepth, SentimentType, SecuritySeverity


class ScanCreateRequest(BaseModel):
    """Schema for creating a new scan."""
    target_id: UUID = Field(..., description="UUID of the target to scan")
    scan_type: ScanType = Field(
        default=ScanType.one_time,
        description="'one_time' or 'scheduled'",
    )
    scan_depth: ScanDepth = Field(
        default=ScanDepth.standard,
        description="Search breadth: quick | standard | thorough | exhaustive",
    )
    timeframe: str = Field(
        default="24 hours",
        description="How far back to search (e.g., '24 hours', '1 week')",
    )
    schedule_interval: Optional[str] = Field(
        None,
        description="Recurrence interval for scheduled scans (e.g., '24 hours', '1 week')",
    )


class ScanResponse(BaseModel):
    """Scan record returned by API endpoints."""
    id: UUID
    target_id: UUID

    # Scan configuration
    scan_type: ScanType
    scan_depth: ScanDepth
    timeframe: str

    # Scheduling
    schedule_interval: Optional[str] = None
    is_schedule_active: bool
    parent_scan_id: Optional[UUID] = None
    next_run_at: Optional[datetime] = None

    # Execution state
    status: ScanStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_sec: Optional[float] = None

    # Results summary
    total_results: int = 0
    new_articles_found: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    positive_pct: float = 0.0
    negative_pct: float = 0.0
    neutral_pct: float = 0.0
    overall_sentiment: Optional[str] = None

    # Detailed report
    risk_summary: Optional[Any] = None
    security_alerts: Optional[Any] = None
    platform_breakdown: Optional[Any] = None

    # Cost tracking
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0

    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleResponse(BaseModel):
    """Article returned in result endpoints."""
    id: UUID
    target_id: UUID
    url: str = Field(description="Article URL")
    title: Optional[str] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    platform: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[date] = None
    summary: Optional[str] = None
    what_others_say: Optional[str] = None
    target_perspective: Optional[str] = None
    key_quotes: Optional[Any] = None
    snippet_content: Optional[str] = None
    sentiment: Optional[SentimentType] = None
    sentiment_reasoning: Optional[str] = None
    headline_vs_body: Optional[str] = None
    risk_flags: Optional[Any] = None
    risk_details: Optional[str] = None
    security_severity: Optional[SecuritySeverity] = None
    security_details: Optional[str] = None
    security_keywords: Optional[Any] = None
    content_completeness: Optional[str] = None
    scraped_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_url(cls, data: Any) -> Any:
        """Map original_url from the ORM model to the url field."""
        # When coming from ORM object (has __dict__ or attribute access)
        if hasattr(data, "original_url"):
            # Convert ORM object to dict-like for Pydantic
            return {
                "id": data.id,
                "target_id": data.target_id,
                "url": data.original_url,
                "title": data.title,
                "source_name": data.source_name,
                "source_type": data.source_type,
                "platform": data.platform,
                "author": data.author,
                "published_date": data.published_date,
                "summary": data.summary,
                "what_others_say": data.what_others_say,
                "target_perspective": data.target_perspective,
                "key_quotes": data.key_quotes,
                "snippet_content": data.snippet_content,
                "sentiment": data.sentiment,
                "sentiment_reasoning": data.sentiment_reasoning,
                "headline_vs_body": data.headline_vs_body,
                "risk_flags": data.risk_flags,
                "risk_details": data.risk_details,
                "security_severity": data.security_severity,
                "security_details": data.security_details,
                "security_keywords": data.security_keywords,
                "content_completeness": data.content_completeness,
                "scraped_at": data.scraped_at,
            }
        # When coming from a dict (e.g. already serialized)
        if isinstance(data, dict):
            if "url" not in data and "original_url" in data:
                data = dict(data)
                data["url"] = data.pop("original_url")
                data.pop("normalized_url", None)
        return data


class ScanListResponse(BaseModel):
    """Paginated list of scans."""
    success: bool = True
    total: int
    scans: list[ScanResponse]


class ScanResultsResponse(BaseModel):
    """Results returned by result retrieval endpoints."""
    success: bool = True
    scan_id: Optional[UUID] = None
    target_id: Optional[UUID] = None
    total_count: int
    new_articles_found: int = 0
    scan_execution_time: Optional[float] = None
    articles: list[ArticleResponse]
    sentiment_summary: Optional[dict] = None
    risk_summary: Optional[Any] = None
    security_alerts: Optional[Any] = None
    platform_breakdown: Optional[dict] = None
    limit: int
    offset: int
    has_more: bool
