"""FastAPI application factory."""

import asyncio
import secrets
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .config import PACKAGE_ROOT, settings
from .logger import logger

from .routes import (
    activity_router,
    alignment_router,
    api_keys_router,
    auth_router,
    binder_design_router,
    community_router,
    design_router,
    discovery_router,
    export_router,
    notification_router,
    organization_router,
    pdb_router,
    prediction_router,
    reputation_router,
    social_router,
    validation_router,
    websocket_router,
)
from .services import start_cleanup_task
from .services.database import init_db
from .services.discovery_store import get_discovery_store
from .services.session_store import get_session_store

# Static files directory
STATIC_DIR = PACKAGE_ROOT / "static"


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

    # Start session cleanup task
    async def session_cleanup_loop() -> None:
        """Periodically clean up expired sessions."""
        while True:
            await asyncio.sleep(3600)  # Every hour
            session_store = get_session_store()
            session_store.cleanup_expired()

    session_cleanup_task = asyncio.create_task(session_cleanup_loop())

    # Start discovery stats update task
    async def discovery_stats_loop() -> None:
        """Periodically update trending scores and user stats."""
        discovery_store = get_discovery_store()
        # Initial computation
        discovery_store.compute_trending_scores()
        discovery_store.compute_user_stats()
        while True:
            await asyncio.sleep(1800)  # Every 30 minutes
            discovery_store.compute_trending_scores()
            discovery_store.compute_user_stats()

    discovery_stats_task = asyncio.create_task(discovery_stats_loop())

    yield

    # Cleanup on shutdown
    logger.info("Shutting down Boltz Studio...")
    cleanup_task.cancel()
    session_cleanup_task.cancel()
    discovery_stats_task.cancel()
    try:
        await cleanup_task
        await session_cleanup_task
        await discovery_stats_task
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

    # Session middleware for OAuth state
    session_secret = settings.session_secret or secrets.token_urlsafe(32)
    app.add_middleware(SessionMiddleware, secret_key=session_secret)

    # Include routers
    app.include_router(activity_router)
    app.include_router(alignment_router)
    app.include_router(api_keys_router)
    app.include_router(auth_router)
    app.include_router(binder_design_router)
    app.include_router(community_router)
    app.include_router(discovery_router)
    app.include_router(export_router)
    app.include_router(notification_router)
    app.include_router(organization_router)
    app.include_router(reputation_router)
    app.include_router(social_router)
    app.include_router(validation_router)
    app.include_router(prediction_router)
    app.include_router(design_router)
    app.include_router(websocket_router)
    app.include_router(pdb_router)

    # Mount static files (CSS, JS)
    app.mount("/css", StaticFiles(directory=STATIC_DIR / "css"), name="css")
    app.mount("/js", StaticFiles(directory=STATIC_DIR / "js"), name="js")

    @app.get("/", include_in_schema=False)
    async def root() -> FileResponse:
        """Serve the main application page."""
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{path:path}", include_in_schema=False)
    async def catch_all(request: Request, path: str) -> FileResponse:
        """Serve static files or index.html for SPA routing."""
        file_path = STATIC_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")

    logger.info("Application configured successfully")
    return app
