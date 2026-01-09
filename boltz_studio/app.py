"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import PACKAGE_ROOT
from .routes import prediction_router, design_router


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Boltz Studio",
        version="0.1.0",
        description="Web UI for protein structure prediction",
    )

    # Include routers
    app.include_router(prediction_router)
    app.include_router(design_router)

    # Mount static files
    static_dir = PACKAGE_ROOT / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # Serve index.html at root
    @app.get("/")
    async def root():
        return FileResponse(static_dir / "index.html")

    return app
