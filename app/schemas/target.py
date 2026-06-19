"""
Pydantic schemas for target management endpoints.

Handles creation, update, and response serialization for targets.
Includes information about whether the target was newly created or
matched to an existing one, and how the match was made.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field

from app.models.enums import TargetType


class TargetCreateRequest(BaseModel):
    """Schema for creating a target."""
    name: str = Field(
        ..., min_length=1, max_length=255,
        description="Target name (person, company, etc.)",
        examples=["John Doe", "Apple Inc"],
    )
    target_type: TargetType = Field(
        default=TargetType.person,
        description="Type of the target",
    )
    description: Optional[str] = Field(
        None, max_length=2000,
        description="Optional description/context about the target",
    )


class TargetResponse(BaseModel):
    """Target details returned by API."""
    id: UUID
    display_name: str
    normalized_name: str
    target_type: TargetType
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TargetCreateResponse(BaseModel):
    """Response when creating a target."""
    success: bool = True
    message: str
    target: TargetResponse
    is_new: bool = Field(
        ..., description="True if a new target was created; False if matched to existing"
    )
    matched_by: Optional[str] = Field(
        None,
        description="How the match was made: 'normalization', 'llm', or None (new target)",
    )
    match_confidence: Optional[float] = Field(
        None,
        description="LLM match confidence (0.0-1.0) if matched_by='llm'",
    )
    match_reasoning: Optional[str] = Field(
        None,
        description="LLM reasoning for the match if matched_by='llm'",
    )


class TargetUpdateRequest(BaseModel):
    """Schema for updating a target."""
    display_name: Optional[str] = Field(None, max_length=255)
    target_type: Optional[TargetType] = None
    description: Optional[str] = Field(None, max_length=2000)
    is_active: Optional[bool] = None


class TargetListResponse(BaseModel):
    """Paginated list of targets."""
    success: bool = True
    total: int
    targets: list[TargetResponse]
