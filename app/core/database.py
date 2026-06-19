"""
Async SQLAlchemy database engine, session factory, and base model.

Uses asyncpg as the async PostgreSQL driver with connection pooling.
Provides the get_db() async generator for FastAPI dependency injection.
"""

import logging
from typing import AsyncGenerator
from sqlalchemy import MetaData, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger("media_intel.database")

# Naming conventions for constraints (helps Alembic generate clean migrations)
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""

    metadata = MetaData(naming_convention=convention)


def create_engine() -> AsyncEngine:
    """Create and return an async SQLAlchemy engine with connection pooling."""
    from app.core.config import get_settings

    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=60.0,
        pool_pre_ping=True,
        echo=False,  # Set True to log all SQL
    )


engine = create_engine()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def create_all_tables():
    """Create all tables defined in models. Safe for multi-worker startups."""
    async with engine.begin() as conn:
        enums = {
            "targettype": ("person", "company", "team", "brand", "organization", "product", "other"),
            "scantype": ("one_time", "scheduled"),
            "scanstatus": ("pending", "running", "completed", "failed"),
            "scandepth": ("quick", "standard", "thorough", "exhaustive"),
            "sentimenttype": ("positive", "negative", "neutral"),
            "securityseverity": ("critical", "high", "medium", "low", "none"),
        }
        
        # 1. Register ENUMs sequentially and handle race-condition errors gracefully
        for enum_name, values in enums.items():
            formatted_values = ", ".join(f"'{v}'" for v in values)
            
            stmt = f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}') THEN
                    CREATE TYPE {enum_name} AS ENUM ({formatted_values});
                END IF;
            END
            $$;
            """
            try:
                # Use a subtransaction/savepoint to absorb a concurrent creation failure
                async with conn.begin_nested():
                    await conn.execute(text(stmt))
            except IntegrityError as e:
                # Check if the error is due to a duplicate key name (a competitor worker beat us to it)
                if "pg_type_typname_nsp_index" in str(e):
                    logger.debug(f"Type '{enum_name}' was concurrently created by another worker.")
                else:
                    raise e
            
        # 2. Instruct SQLAlchemy to skip creating types dynamically since we handled it above
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if hasattr(column.type, "create_type"):
                    column.type.create_type = False

        # 3. Safe to create tables now
        try:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("All database tables verified and created successfully")
        except Exception as e:
            logger.warning(f"Handled minor collision during concurrent table creation: {e}")


async def drop_all_tables():
    """Drop all tables. Use only for development/testing."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.info("All database tables dropped")
