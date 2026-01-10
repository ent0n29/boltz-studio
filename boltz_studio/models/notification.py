"""Notification models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .user import UserPublic


NotificationType = Literal["star", "fork", "comment", "follow"]


class NotificationPublic(BaseModel):
    """Public notification data."""

    id: str
    type: NotificationType
    actor: UserPublic | None = None
    target_type: str | None = None
    target_id: str | None = None
    target_name: str | None = None  # e.g., design name for context
    message: str
    is_read: bool = False
    created_at: datetime


class NotificationList(BaseModel):
    """Paginated list of notifications."""

    notifications: list[NotificationPublic]
    total: int
    unread_count: int
    has_more: bool


class UnreadCount(BaseModel):
    """Unread notification count."""

    count: int


class NotificationPreferences(BaseModel):
    """User notification preferences."""

    notify_on_star: bool = True
    notify_on_fork: bool = True
    notify_on_comment: bool = True
    notify_on_follow: bool = True


class NotificationPreferencesUpdate(BaseModel):
    """Update notification preferences."""

    notify_on_star: bool | None = None
    notify_on_fork: bool | None = None
    notify_on_comment: bool | None = None
    notify_on_follow: bool | None = None
