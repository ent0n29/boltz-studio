"""Activity feed models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from .user import UserPublic

ActivityType = Literal[
    "design_published",
    "design_starred",
    "design_forked",
    "design_commented",
    "design_validated",
    "user_followed",
    "badge_earned",
]


class ActivityPublic(BaseModel):
    """Public activity data."""

    id: str
    user: UserPublic
    activity_type: ActivityType
    target_type: str | None = None
    target_id: str | None = None
    target_name: str | None = None
    target_preview: str | None = None  # Preview image URL
    metadata: dict | None = None
    created_at: datetime


class ActivityFeed(BaseModel):
    """Activity feed response."""

    activities: list[ActivityPublic]
    total: int
    has_more: bool = False
