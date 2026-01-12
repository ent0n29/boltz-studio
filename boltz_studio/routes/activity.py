"""Activity feed routes."""

from fastapi import APIRouter, Depends, Query

from ..logger import get_logger
from ..middleware import RequiredUser
from ..models.activity import ActivityFeed
from ..services.activity_store import ActivityStore, get_activity_store

logger = get_logger("routes.activity")

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("/feed", response_model=ActivityFeed)
async def get_activity_feed(
    user: RequiredUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: ActivityStore = Depends(get_activity_store),
) -> ActivityFeed:
    """Get activity feed from followed users.

    Args:
        user: Authenticated user
        offset: Pagination offset
        limit: Max results
        store: Activity store

    Returns:
        Activity feed
    """
    return store.get_user_feed(user.id, offset, limit)


@router.get("/user/{user_id}", response_model=ActivityFeed)
async def get_user_activities(
    user_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: ActivityStore = Depends(get_activity_store),
) -> ActivityFeed:
    """Get a user's activities.

    Args:
        user_id: User ID
        offset: Pagination offset
        limit: Max results
        store: Activity store

    Returns:
        User's activities
    """
    return store.get_user_activities(user_id, offset, limit)


@router.get("/me", response_model=ActivityFeed)
async def get_my_activities(
    user: RequiredUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: ActivityStore = Depends(get_activity_store),
) -> ActivityFeed:
    """Get current user's activities.

    Args:
        user: Authenticated user
        offset: Pagination offset
        limit: Max results
        store: Activity store

    Returns:
        User's activities
    """
    return store.get_user_activities(user.id, offset, limit)
