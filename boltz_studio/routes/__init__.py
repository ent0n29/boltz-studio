"""API route handlers."""

from .design import router as design_router
from .prediction import router as prediction_router
from .websocket import router as websocket_router

__all__ = ["design_router", "prediction_router", "websocket_router"]
