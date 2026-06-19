"""
Article ORM model — the central data store for scraped content.

Articles are deduplicated per target using (target_id, normalized_url).
They are shared across all users who monitor the same target.
"""

import uuid
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    String, Text, DateTime, Date, Float, ForeignKey,
    func, UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base
from app.models.enums import SentimentType, SecuritySeverity

if TYPE_CHECKING:
    from app.models.target import Target
    from app.models.scan import ScanArticle


class Article(Base):
    """
    A single scraped article or social media post about a target.

    Deduplication is enforced by the composite unique constraint
    on (target_id, normalized_url). The same physical URL can
    exist under different targets — that is intentional.

    Attributes:
        normalized_url: URL after stripping tracking params, trailing slashes,
                        and lowercasing. Used for dedup.
        original_url: The URL as originally discovered.
        published_date: Date the content was published (from the source).
        scraped_at: When our system first captured this article.
        sentiment: Sentiment from the target's perspective.
        security_severity: Whether the article contains security concerns.
    """
    __tablename__ = "articles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("targets.id", ondelete="CASCADE"), nullable=False
    )
    # ── URL fields ──
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Content metadata ──
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    platform: Mapped[str] = mapped_column(String(50), default="web", nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Dates ──
    published_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Analysis results ──
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    what_others_say: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_perspective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_quotes: Mapped[Optional[dict]] = mapped_column(JSONB, default=list, nullable=True)
    snippet_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Sentiment ──
    sentiment: Mapped[SentimentType] = mapped_column(
        default=SentimentType.neutral, nullable=False
    )
    sentiment_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    headline_vs_body: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # ── Risk / Security ──
    risk_flags: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=lambda: ["none"], nullable=True
    )
    risk_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    security_severity: Mapped[SecuritySeverity] = mapped_column(
        default=SecuritySeverity.none, nullable=False
    )
    security_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    security_keywords: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=list, nullable=True
    )

    # ── Content quality ──
    content_completeness: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Relationships ──
    target: Mapped["Target"] = relationship("Target", back_populates="articles")
    scan_articles: Mapped[List["ScanArticle"]] = relationship(
        "ScanArticle", back_populates="article", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("target_id", "normalized_url", name="uq_target_normalized_url"),
        Index("idx_articles_target_id", "target_id"),
        Index("idx_articles_target_date", "target_id", "published_date"),
        Index("idx_articles_sentiment", "sentiment"),
        Index("idx_articles_platform", "platform"),
        Index("idx_articles_scraped_at", "scraped_at"),
        Index("idx_articles_security", "security_severity"),
    )

    def __repr__(self) -> str:
        return f"<Article '{(self.title or 'Untitled')[:40]}' target={self.target_id}>"
