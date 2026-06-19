"""
Application-specific exceptions and global FastAPI exception handlers.

Provides a consistent error response format across all API endpoints.
All exceptions map to standard HTTP status codes with structured JSON bodies.
"""

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

logger = logging.getLogger("media_intel.exceptions")


# ═══════════════════════════════════════════
# Custom Exception Classes
# ═══════════════════════════════════════════

class AppException(Exception):
    """Base application exception. All custom exceptions inherit from this."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: Optional[Any] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)


class NotFoundException(AppException):
    """Resource not found (404)."""
    def __init__(self, resource: str = "Resource", identifier: str = ""):
        super().__init__(
            message=f"{resource} not found" + (f": {identifier}" if identifier else ""),
            status_code=status.HTTP_404_NOT_FOUND,
        )


class DuplicateException(AppException):
    """Duplicate resource (409)."""
    def __init__(self, message: str = "Resource already exists", detail: Any = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class ForbiddenException(AppException):
    """Insufficient permissions (403)."""
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class UnauthorizedException(AppException):
    """Authentication failure (401)."""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ScanExecutionError(AppException):
    """Error during scan execution (500)."""
    def __init__(self, message: str = "Scan execution failed", detail: Any = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


class ValidationException(AppException):
    """Business rule validation failure (422)."""
    def __init__(self, message: str = "Validation failed", detail: Any = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


# ═══════════════════════════════════════════
# Global Exception Handlers
# ═══════════════════════════════════════════

def register_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers on the FastAPI application.

    Ensures all errors return a consistent JSON format:
    {
        "success": false,
        "error": {
            "message": "...",
            "detail": ... (optional)
        }
    }
    """

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.error(f"AppException: {exc.message}", extra={"extra_data": exc.detail})
        body = {"success": False, "error": {"message": exc.message}}
        if exc.detail is not None:
            body["error"]["detail"] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {"message": str(exc.detail)},
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for error in exc.errors():
            errors.append({
                "field": " → ".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            })
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "message": "Request validation failed",
                    "detail": errors,
                },
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled exception: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {"message": "Internal server error"},
            },
        )
