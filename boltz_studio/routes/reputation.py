"""Reputation and badge routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..logger import get_logger
from ..middleware import OptionalUser, RequiredUser
from ..models.reputation import (
    BadgeDefinition,
    BadgeList,
    BadgeProgressList,
    ReputationBreakdown,
    ReputationLeaderboard,
    UserBadgeList,
    UserReputation,
)
from ..services.reputation_store import ReputationStore, get_reputation_store

logger = get_logger("routes.reputation")

router = APIRouter(prefix="/api/reputation", tags=["reputation"])


# ============================================================================
# Badges
# ============================================================================


@router.get("/badges", response_model=BadgeList)
async def list_badges(
    store: ReputationStore = Depends(get_reputation_store),
) -> BadgeList:
    """List all available badges.

    Returns:
        List of badge definitions
    """
    return store.get_all_badges()


@router.get("/badges/me", response_model=UserBadgeList)
async def get_my_badges(
    user: RequiredUser,
    store: ReputationStore = Depends(get_reputation_store),
) -> UserBadgeList:
    """Get current user's earned badges.

    Args:
        user: Authenticated user
        store: Reputation store

    Returns:
        List of earned badges
    """
    return store.get_user_badges(user.id)


@router.get("/badges/user/{user_id}", response_model=UserBadgeList)
async def get_user_badges(
    user_id: str,
    store: ReputationStore = Depends(get_reputation_store),
) -> UserBadgeList:
    """Get a user's earned badges.

    Args:
        user_id: Target user ID
        store: Reputation store

    Returns:
        List of earned badges
    """
    return store.get_user_badges(user_id)


@router.get("/progress", response_model=BadgeProgressList)
async def get_badge_progress(
    user: RequiredUser,
    store: ReputationStore = Depends(get_reputation_store),
) -> BadgeProgressList:
    """Get current user's progress toward badges.

    Args:
        user: Authenticated user
        store: Reputation store

    Returns:
        Progress toward unearned badges and list of earned badges
    """
    return store.get_badge_progress(user.id)


@router.post("/check-badges", response_model=list[BadgeDefinition])
async def check_badges(
    user: RequiredUser,
    store: ReputationStore = Depends(get_reputation_store),
) -> list[BadgeDefinition]:
    """Check and award any newly earned badges.

    Args:
        user: Authenticated user
        store: Reputation store

    Returns:
        List of newly awarded badges (empty if none)
    """
    return store.check_and_award_badges(user.id)


# ============================================================================
# Reputation
# ============================================================================


@router.get("/me", response_model=UserReputation)
async def get_my_reputation(
    user: RequiredUser,
    store: ReputationStore = Depends(get_reputation_store),
) -> UserReputation:
    """Get current user's reputation summary.

    Args:
        user: Authenticated user
        store: Reputation store

    Returns:
        Reputation summary with score, rank, and recent badges
    """
    return store.get_user_reputation(user.id)


@router.get("/user/{user_id}", response_model=UserReputation)
async def get_user_reputation(
    user_id: str,
    store: ReputationStore = Depends(get_reputation_store),
) -> UserReputation:
    """Get a user's reputation summary.

    Args:
        user_id: Target user ID
        store: Reputation store

    Returns:
        Reputation summary
    """
    return store.get_user_reputation(user_id)


@router.get("/breakdown", response_model=ReputationBreakdown)
async def get_reputation_breakdown(
    user: RequiredUser,
    store: ReputationStore = Depends(get_reputation_store),
) -> ReputationBreakdown:
    """Get detailed breakdown of reputation points.

    Args:
        user: Authenticated user
        store: Reputation store

    Returns:
        Breakdown showing points from each category
    """
    return store.get_reputation_breakdown(user.id)


@router.get("/leaderboard", response_model=ReputationLeaderboard)
async def get_leaderboard(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: ReputationStore = Depends(get_reputation_store),
) -> ReputationLeaderboard:
    """Get reputation leaderboard.

    Args:
        offset: Pagination offset
        limit: Max results
        store: Reputation store

    Returns:
        Leaderboard entries sorted by reputation
    """
    return store.get_reputation_leaderboard(offset, limit)
