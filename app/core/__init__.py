"""
Core package — cross-cutting utilities shared across all layers.

Contains:
- config: Application settings (pydantic-settings).
- database: Async SQLAlchemy engine and session factory.
- security: JWT auth, password hashing, RBAC dependencies.
- normalization: Target name and URL normalization.
- exceptions: Custom exceptions and global error handlers.
- logging_config: Structured JSON logging.
"""
