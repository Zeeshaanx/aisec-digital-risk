"""
Target ORM model.

Target stores the monitored entity (person, company, etc.) with a
normalized_name for deduplication. Articles are shared across all scans
for the same target.
"""

import uuid
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    String, Boolean, Text, DateTime,
    func, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.models.enums import TargetType, ScanDepth

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.scan import Scan


class Target(Base):
    """
    A monitored entity (person, company, brand, etc.).

    The normalized_name field is the canonical deduplication key.

    Attributes:
        display_name: The original user-provided name for display.
        normalized_name: Lowercased, accent-stripped, punctuation-removed key.
        target_type: Category of the target (person, company, etc.).
        description: Optional context about the target.
    """
    __tablename__ = "targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    normalized_name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    target_type: Mapped[TargetType] = mapped_column(
        default=TargetType.person, nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    # ── Relationships ──
    articles: Mapped[List["Article"]] = relationship(
        "Article", back_populates="target", cascade="all, delete-orphan"
    )
    scans: Mapped[List["Scan"]] = relationship(
        "Scan", back_populates="target", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Target '{self.display_name}' type={self.target_type.value}>"
