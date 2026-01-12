"""API route handlers."""

from .activity import router as activity_router
from .alignment import router as alignment_router
from .api_keys import router as api_keys_router
from .auth import router as auth_router
from .community import router as community_router
from .design import router as design_router
from .discovery import router as discovery_router
from .export import router as export_router
from .notification import router as notification_router
from .organization import router as organization_router
from .pdb import router as pdb_router
from .prediction import router as prediction_router
from .reputation import router as reputation_router
from .social import router as social_router
from .validation import router as validation_router
from .websocket import router as websocket_router

__all__ = [
    "activity_router",
    "alignment_router",
    "api_keys_router",
    "auth_router",
    "community_router",
    "design_router",
    "discovery_router",
    "export_router",
    "notification_router",
    "organization_router",
    "pdb_router",
    "prediction_router",
    "reputation_router",
    "social_router",
    "validation_router",
    "websocket_router",
]
