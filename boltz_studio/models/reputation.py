"""Reputation and badge models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

BadgeCategory = Literal["contribution", "social", "engagement", "verification"]
BadgeTier = Literal["bronze", "silver", "gold", "platinum"]


class BadgeDefinition(BaseModel):
    """Badge definition model."""

    id: str
    slug: str
    name: str
    description: str
    icon: str | None = None
    category: BadgeCategory
    tier: BadgeTier | None = None
    criteria_type: str
    criteria_field: str | None = None
    criteria_value: int | None = None
    points: int = 0


class UserBadge(BaseModel):
    """A badge earned by a user."""

    badge: BadgeDefinition
    earned_at: datetime


class BadgeProgress(BaseModel):
    """Progress toward earning a badge."""

    badge: BadgeDefinition
    current_value: int = 0
    target_value: int
    progress_percent: float = 0.0
    is_earned: bool = False


class UserReputation(BaseModel):
    """User's reputation summary."""

    user_id: str
    reputation_score: int = 0
    rank: int | None = None
    total_badges: int = 0
    badges: list[UserBadge] = Field(default_factory=list)


class ReputationBreakdown(BaseModel):
    """Breakdown of how reputation is calculated."""

    designs_published: int = 0
    designs_points: int = 0
    stars_received: int = 0
    stars_points: int = 0
    forks_received: int = 0
    forks_points: int = 0
    comments_received: int = 0
    comments_points: int = 0
    downloads_received: int = 0
    downloads_points: int = 0
    badge_points: int = 0
    total_points: int = 0


class BadgeList(BaseModel):
    """List of badges."""

    badges: list[BadgeDefinition]
    total: int


class UserBadgeList(BaseModel):
    """List of user's earned badges."""

    badges: list[UserBadge]
    total: int


class BadgeProgressList(BaseModel):
    """List of badge progress items."""

    in_progress: list[BadgeProgress]
    earned: list[UserBadge]


class ReputationLeaderboardEntry(BaseModel):
    """Entry in reputation leaderboard."""

    user_id: str
    display_name: str
    avatar_url: str | None = None
    reputation_score: int = 0
    badge_count: int = 0
    rank: int


class ReputationLeaderboard(BaseModel):
    """Reputation leaderboard."""

    entries: list[ReputationLeaderboardEntry]
    total: int
    has_more: bool = False
