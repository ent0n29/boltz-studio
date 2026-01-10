"""Discovery routes for trending, leaderboards, and recommendations."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..logger import get_logger
from ..middleware import OptionalUser
from ..models.discovery import (
    DesignStats,
    Leaderboard,
    SimilarDesign,
    TrendingList,
    UserStats,
)
from ..services.discovery_store import DiscoveryStore, get_discovery_store

logger = get_logger("routes.discovery")

router = APIRouter(prefix="/api", tags=["discovery"])


# ============================================================================
# Trending Designs
# ============================================================================


@router.get("/trending", response_model=TrendingList)
async def get_trending(
    window: Literal["day", "week", "month"] = Query("week"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: DiscoveryStore = Depends(get_discovery_store),
) -> TrendingList:
    """Get trending designs.

    Args:
        window: Time window for trending calculation
        offset: Pagination offset
        limit: Maximum results
        store: Discovery store dependency

    Returns:
        List of trending designs
    """
    return store.get_trending(time_window=window, offset=offset, limit=limit)


# ============================================================================
# Leaderboard
# ============================================================================


@router.get("/leaderboard", response_model=Leaderboard)
async def get_leaderboard(
    metric: Literal["reputation", "stars", "forks", "downloads"] = Query("reputation"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: DiscoveryStore = Depends(get_discovery_store),
) -> Leaderboard:
    """Get user leaderboard.

    Args:
        metric: Sort metric for leaderboard
        offset: Pagination offset
        limit: Maximum results
        store: Discovery store dependency

    Returns:
        Leaderboard with user entries
    """
    return store.get_leaderboard(metric=metric, offset=offset, limit=limit)


# ============================================================================
# Design Statistics
# ============================================================================


@router.get("/designs/{design_id}/stats", response_model=DesignStats)
async def get_design_stats(
    design_id: str,
    store: DiscoveryStore = Depends(get_discovery_store),
) -> DesignStats:
    """Get statistics for a design.

    Args:
        design_id: Design identifier
        store: Discovery store dependency

    Returns:
        Design statistics

    Raises:
        404 if design not found
    """
    stats = store.get_design_stats(design_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Design not found")
    return stats


@router.post("/designs/{design_id}/view")
async def record_view(
    design_id: str,
    user: OptionalUser = None,
    store: DiscoveryStore = Depends(get_discovery_store),
) -> dict:
    """Record a view event for a design.

    Args:
        design_id: Design identifier
        user: Optional authenticated user
        store: Discovery store dependency

    Returns:
        Success message
    """
    user_id = user.id if user else None
    store.record_event(design_id, "view", user_id)
    return {"message": "View recorded"}


@router.post("/designs/{design_id}/download")
async def record_download(
    design_id: str,
    user: OptionalUser = None,
    store: DiscoveryStore = Depends(get_discovery_store),
) -> dict:
    """Record a download event for a design.

    Args:
        design_id: Design identifier
        user: Optional authenticated user
        store: Discovery store dependency

    Returns:
        Success message
    """
    user_id = user.id if user else None
    store.record_event(design_id, "download", user_id)
    return {"message": "Download recorded"}


# ============================================================================
# Similar Designs
# ============================================================================


@router.get("/designs/{design_id}/similar", response_model=list[SimilarDesign])
async def get_similar_designs(
    design_id: str,
    limit: int = Query(5, ge=1, le=20),
    store: DiscoveryStore = Depends(get_discovery_store),
) -> list[SimilarDesign]:
    """Get similar designs based on tags and author.

    Args:
        design_id: Source design identifier
        limit: Maximum results
        store: Discovery store dependency

    Returns:
        List of similar designs with similarity reasons
    """
    return store.get_similar_designs(design_id, limit)


# ============================================================================
# User Statistics
# ============================================================================


@router.get("/users/{user_id}/stats", response_model=UserStats)
async def get_user_stats(
    user_id: str,
    store: DiscoveryStore = Depends(get_discovery_store),
) -> UserStats:
    """Get statistics for a user.

    Args:
        user_id: User identifier
        store: Discovery store dependency

    Returns:
        User statistics

    Raises:
        404 if user not found
    """
    stats = store.get_user_stats(user_id)
    if not stats:
        raise HTTPException(status_code=404, detail="User stats not found")
    return stats
