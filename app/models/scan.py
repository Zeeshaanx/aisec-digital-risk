"""
Scan and ScanArticle ORM models.
"""

import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    String, Text, Float, Integer, Boolean,
    DateTime, ForeignKey, func, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base
from app.models.enums import ScanType, ScanStatus, ScanDepth

if TYPE_CHECKING:
    from app.models.target import Target
    from app.models.article import Article


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )

    scan_type: Mapped[ScanType] = mapped_column(nullable=False)
    scan_depth: Mapped[ScanDepth] = mapped_column(
        default=ScanDepth.standard, nullable=False
    )
    timeframe: Mapped[str] = mapped_column(
        String(50), default="24 hours", nullable=False
    )

    schedule_interval: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    is_schedule_active: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    parent_scan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="SET NULL"), nullable=True
    )
    next_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    status: Mapped[ScanStatus] = mapped_column(
        default=ScanStatus.pending, nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_time_sec: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    total_results: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_articles_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    negative_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    positive_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    negative_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    neutral_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    overall_sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    risk_summary: Mapped[Optional[dict]] = mapped_column(JSONB, default=list, nullable=True)
    security_alerts: Mapped[Optional[dict]] = mapped_column(JSONB, default=list, nullable=True)
    platform_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict, nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──
    target: Mapped["Target"] = relationship("Target", back_populates="scans")
    scan_articles: Mapped[List["ScanArticle"]] = relationship(
        "ScanArticle", back_populates="scan", cascade="all, delete-orphan",
        foreign_keys="ScanArticle.scan_id",
    )
    child_scans: Mapped[List["Scan"]] = relationship(
        "Scan", back_populates="parent_scan",
        foreign_keys="Scan.parent_scan_id",
    )
    parent_scan: Mapped[Optional["Scan"]] = relationship(
        "Scan", back_populates="child_scans",
        foreign_keys=[parent_scan_id], remote_side="Scan.id",
    )

    __table_args__ = (
        Index("idx_scans_target", "target_id"),
        Index("idx_scans_status", "status"),
        Index("idx_scans_scheduled", "is_schedule_active", "next_run_at"),
        Index("idx_scans_created", "created_at"),
    )

    def __repr__(self) -> str:
        try:
            scan_type = self.scan_type.value if self.scan_type else "unknown"
            status = self.status.value if self.status else "unknown"
            return f"<Scan {self.id} type={scan_type} status={status}>"
        except Exception:
            return "<Scan (detached)>"


class ScanArticle(Base):
    __tablename__ = "scan_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    is_new: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    scan: Mapped["Scan"] = relationship(
        "Scan", back_populates="scan_articles",
        foreign_keys=[scan_id],
    )
    article: Mapped["Article"] = relationship(
        "Article", back_populates="scan_articles"
    )

    __table_args__ = (
        Index("idx_scan_articles_scan", "scan_id"),
        Index("idx_scan_articles_article", "article_id"),
    )

    def __repr__(self) -> str:
        try:
            return f"<ScanArticle scan={self.scan_id} article={self.article_id} new={self.is_new}>"
        except Exception:
            return "<ScanArticle (detached)>"
