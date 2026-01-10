"""Discovery models for trending, leaderboards, and recommendations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .design import DesignSummary
from .user import UserPublic


class TrendingDesign(BaseModel):
    """Design with trending information."""

    design: DesignSummary
    trending_score: float
    trending_rank: int
    recent_stars: int = 0
    recent_downloads: int = 0
    recent_forks: int = 0


class TrendingList(BaseModel):
    """Paginated list of trending designs."""

    designs: list[TrendingDesign]
    total: int
    has_more: bool
    time_window: str


class LeaderboardEntry(BaseModel):
    """User leaderboard entry."""

    rank: int
    user: UserPublic
    total_stars: int = 0
    total_forks: int = 0
    total_downloads: int = 0
    total_designs: int = 0
    reputation_score: float = 0.0


class Leaderboard(BaseModel):
    """Paginated leaderboard."""

    entries: list[LeaderboardEntry]
    total: int
    has_more: bool
    metric: str  # What the leaderboard is sorted by


class DesignStats(BaseModel):
    """Statistics for a single design."""

    design_id: str
    star_count: int = 0
    fork_count: int = 0
    comment_count: int = 0
    download_count: int = 0
    view_count: int = 0
    trending_score: float = 0.0


class UserStats(BaseModel):
    """User statistics for profile and leaderboard."""

    user_id: str
    total_stars_received: int = 0
    total_forks_received: int = 0
    total_downloads: int = 0
    total_designs: int = 0
    reputation_score: float = 0.0
    rank: int | None = None
    updated_at: datetime | None = None


class SimilarDesign(BaseModel):
    """Similar design recommendation."""

    design: DesignSummary
    similarity_score: float
    similarity_reason: Literal["same_tags", "same_author", "same_target", "sequence_similarity"]
