"""
FastAPI application entry point.

Configures the application with:
- CORS middleware
- Global exception handlers
- All API route groups
- Database table creation on startup
- Background scheduler for recurring scans
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import create_all_tables
from app.core.logging_config import setup_logging
from app.core.exceptions import register_exception_handlers
from app.core.scheduler import start_scheduler, stop_scheduler, reload_schedules
from app.api.v1.router import api_v1_router
from app.api.health import router as health_router

logger = logging.getLogger("media_intel.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.

    Startup:
    - Initialize logging.
    - Create database tables.
    - Reload active schedules from DB.
    - Start background scheduler.

    Shutdown:
    - Stop background scheduler.
    """
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} "
        f"({settings.ENVIRONMENT})",
        extra={"action": "app_start"},
    )

    # Create tables
    await create_all_tables()
    logger.info("Database tables ready")

    # Reload schedules and start scheduler
    await reload_schedules()
    start_scheduler()

    yield

    # Shutdown
    stop_scheduler()
    logger.info("Application shutdown complete", extra={"action": "app_shutdown"})


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI instance ready to serve requests.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Media Intelligence & Security Monitoring API.\n\n"
            "Monitor news and social media for specific targets "
            "(people, companies, brands). "
            "Provides sentiment analysis, security threat detection, "
            "and risk assessment.\n\n"
            "## Features\n"
            "- 🔍 Multi-source search (news, social media, security feeds)\n"
            "- 🤖 LLM-powered analysis (sentiment, risk, security)\n"
            "- 📊 Scheduled and one-time scans\n"
            "- 📈 Historical trend tracking\n"
        ),
        root_path="/aisec-digital-risk",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── CORS ──
    # app.add_middleware(
    #     CORSMiddleware,
    #     allow_origins=["*"],
    #     allow_credentials=True,
    #     allow_methods=["*"],
    #     allow_headers=["*"],
    # )

    # ── Exception Handlers ──
    register_exception_handlers(app)

    # ── Routes ──
    app.include_router(health_router)
    app.include_router(api_v1_router)

    return app


# Create the application instance
app = create_app()
