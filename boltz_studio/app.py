"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import PACKAGE_ROOT
from .logger import logger
from .routes import design_router, prediction_router, websocket_router
from .services import start_cleanup_task
from .services.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown tasks:
    - Initializes SQLite database
    - Starts background cleanup task on startup
    - Cancels cleanup task on shutdown
    """
    logger.info("Starting Boltz Studio...")

    # Initialize database
    init_db()

    # Start background cleanup task
    cleanup_task = asyncio.create_task(start_cleanup_task())

    yield

    # Cleanup on shutdown
    logger.info("Shutting down Boltz Studio...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Boltz Studio",
        version="0.1.0",
        description="Web UI for protein structure prediction using Boltz-2",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Include routers
    app.include_router(prediction_router)
    app.include_router(design_router)
    app.include_router(websocket_router)

    # Mount static files
    static_dir = PACKAGE_ROOT / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Serve index.html at root
    @app.get("/", include_in_schema=False)
    async def root() -> FileResponse:
        """Serve the main application page."""
        return FileResponse(static_dir / "index.html")

    logger.info("Application configured successfully")
    return app
