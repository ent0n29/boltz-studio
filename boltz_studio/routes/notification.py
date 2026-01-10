"""Notification routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..logger import get_logger
from ..middleware import RequiredUser
from ..models.notification import (
    NotificationList,
    NotificationPreferences,
    NotificationPreferencesUpdate,
    UnreadCount,
)
from ..services.notification_store import NotificationStore, get_notification_store

logger = get_logger("routes.notification")

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def get_notifications(
    user: RequiredUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    store: NotificationStore = Depends(get_notification_store),
) -> NotificationList:
    """Get notifications for the current user.

    Args:
        user: Authenticated user
        offset: Pagination offset
        limit: Max results
        unread_only: Only return unread notifications
        store: Notification store

    Returns:
        List of notifications
    """
    return store.get_notifications(
        user_id=user.id,
        offset=offset,
        limit=limit,
        unread_only=unread_only,
    )


@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(
    user: RequiredUser,
    store: NotificationStore = Depends(get_notification_store),
) -> UnreadCount:
    """Get unread notification count.

    Args:
        user: Authenticated user
        store: Notification store

    Returns:
        Unread count
    """
    return store.get_unread_count(user.id)


@router.post("/{notification_id}/read")
async def mark_as_read(
    notification_id: str,
    user: RequiredUser,
    store: NotificationStore = Depends(get_notification_store),
) -> dict:
    """Mark a notification as read.

    Args:
        notification_id: Notification to mark
        user: Authenticated user
        store: Notification store

    Returns:
        Success message

    Raises:
        404 if notification not found
    """
    if not store.mark_as_read(notification_id, user.id):
        raise HTTPException(status_code=404, detail="Notification not found")

    return {"message": "Notification marked as read"}


@router.post("/read-all")
async def mark_all_as_read(
    user: RequiredUser,
    store: NotificationStore = Depends(get_notification_store),
) -> dict:
    """Mark all notifications as read.

    Args:
        user: Authenticated user
        store: Notification store

    Returns:
        Count of notifications marked
    """
    count = store.mark_all_as_read(user.id)
    return {"message": f"Marked {count} notifications as read", "count": count}


@router.get("/preferences", response_model=NotificationPreferences)
async def get_preferences(
    user: RequiredUser,
    store: NotificationStore = Depends(get_notification_store),
) -> NotificationPreferences:
    """Get notification preferences.

    Args:
        user: Authenticated user
        store: Notification store

    Returns:
        User's notification preferences
    """
    return store.get_preferences(user.id)


@router.put("/preferences", response_model=NotificationPreferences)
async def update_preferences(
    updates: NotificationPreferencesUpdate,
    user: RequiredUser,
    store: NotificationStore = Depends(get_notification_store),
) -> NotificationPreferences:
    """Update notification preferences.

    Args:
        updates: Preference updates
        user: Authenticated user
        store: Notification store

    Returns:
        Updated preferences
    """
    return store.update_preferences(user.id, updates)
