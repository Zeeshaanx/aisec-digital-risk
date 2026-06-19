"""
Generic message response schema shared across endpoints.
"""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message response."""
    success: bool = True
    message: str
