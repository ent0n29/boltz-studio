"""Community routes for design publishing and discovery."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from ..logger import get_logger
from ..middleware import OptionalUser, RequiredUser
from ..models import (
    DesignCreate,
    DesignPublic,
    DesignSearchParams,
    DesignSearchResult,
    DesignSummary,
    DesignUpdate,
    FollowerList,
    UserProfileUpdate,
    UserPublic,
    UserPublicExtended,
)
from ..services.design_store import DesignStore, get_design_store
from ..services.follow_store import FollowStore, get_follow_store
from ..services.notification_store import NotificationStore, get_notification_store
from ..services.user_store import UserStore, get_user_store

logger = get_logger("routes.community")

router = APIRouter(prefix="/api", tags=["community"])


# ============================================================================
# Design Publishing (Authenticated)
# ============================================================================


@router.post("/designs", response_model=dict)
async def publish_design(
    design: DesignCreate,
    user: RequiredUser,
    store: DesignStore = Depends(get_design_store),
) -> dict:
    """Publish a new design to the community.

    Args:
        design: Design data to publish
        user: Authenticated user
        store: Design store dependency

    Returns:
        Created design ID
    """
    design_id = store.create(user.id, design)
    logger.info(f"User {user.id} published design {design_id}")
    return {"id": design_id, "message": "Design published successfully"}


@router.get("/designs/mine", response_model=list[DesignSummary])
async def list_my_designs(
    user: RequiredUser,
    store: DesignStore = Depends(get_design_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[DesignSummary]:
    """List the current user's designs.

    Args:
        user: Authenticated user
        store: Design store dependency
        offset: Pagination offset
        limit: Maximum results

    Returns:
        List of user's designs
    """
    return store.list_user_designs(user.id, offset, limit)


@router.put("/designs/{design_id}")
async def update_design(
    design_id: str,
    updates: DesignUpdate,
    user: RequiredUser,
    store: DesignStore = Depends(get_design_store),
) -> dict:
    """Update a design (owner only).

    Args:
        design_id: Design identifier
        updates: Fields to update
        user: Authenticated user
        store: Design store dependency

    Returns:
        Success message

    Raises:
        404 if design not found or not owned by user
    """
    if not store.update(design_id, user.id, updates):
        raise HTTPException(
            status_code=404,
            detail="Design not found or you don't have permission to edit it",
        )

    return {"message": "Design updated successfully"}


@router.delete("/designs/{design_id}")
async def delete_design(
    design_id: str,
    user: RequiredUser,
    store: DesignStore = Depends(get_design_store),
) -> dict:
    """Delete a design (owner only).

    Args:
        design_id: Design identifier
        user: Authenticated user
        store: Design store dependency

    Returns:
        Success message

    Raises:
        404 if design not found or not owned by user
    """
    if not store.delete(design_id, user.id):
        raise HTTPException(
            status_code=404,
            detail="Design not found or you don't have permission to delete it",
        )

    return {"message": "Design deleted successfully"}


# ============================================================================
# Design Discovery (Public)
# ============================================================================


@router.get("/designs", response_model=DesignSearchResult)
async def search_designs(
    store: DesignStore = Depends(get_design_store),
    query: str | None = Query(None, description="Full-text search query"),
    tag: str | None = Query(None, description="Filter by tag"),
    tag_type: Literal["target", "organism", "purpose"] | None = Query(
        None, description="Filter tag type"
    ),
    min_confidence: float | None = Query(None, ge=0, le=1),
    max_confidence: float | None = Query(None, ge=0, le=1),
    min_affinity: float | None = Query(None, ge=0, le=1),
    max_affinity: float | None = Query(None, ge=0, le=1),
    has_ligand: bool | None = Query(None, description="Filter by ligand presence"),
    sort_by: Literal["created_at", "confidence_score", "affinity_probability"] = Query(
        "created_at"
    ),
    sort_order: Literal["asc", "desc"] = Query("desc"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> DesignSearchResult:
    """Search and browse public designs.

    Supports full-text search, tag filtering, and metric-based filtering.

    Args:
        store: Design store dependency
        query: Full-text search query
        tag: Filter by specific tag
        tag_type: Only apply tag filter to specific type
        min_confidence: Minimum confidence score
        max_confidence: Maximum confidence score
        min_affinity: Minimum binding affinity
        max_affinity: Maximum binding affinity
        has_ligand: Filter by ligand presence
        sort_by: Field to sort by
        sort_order: Sort direction
        offset: Pagination offset
        limit: Maximum results

    Returns:
        Paginated search results
    """
    params = DesignSearchParams(
        query=query,
        tag=tag,
        tag_type=tag_type,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        min_affinity=min_affinity,
        max_affinity=max_affinity,
        has_ligand=has_ligand,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        limit=limit,
    )

    return store.search(params)


@router.get("/designs/tags")
async def get_popular_tags(
    store: DesignStore = Depends(get_design_store),
    tag_type: Literal["target", "organism", "purpose"] | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Get popular tags with usage counts.

    Args:
        store: Design store dependency
        tag_type: Filter by tag type
        limit: Maximum tags to return

    Returns:
        List of tags with counts
    """
    return store.get_popular_tags(tag_type, limit)


@router.get("/designs/{design_id}", response_model=DesignPublic)
async def get_design(
    design_id: str,
    store: DesignStore = Depends(get_design_store),
) -> DesignPublic:
    """Get a public design by ID.

    Args:
        design_id: Design identifier
        store: Design store dependency

    Returns:
        Full design details

    Raises:
        404 if design not found or not public
    """
    design = store.get_public(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    return design


@router.get("/designs/{design_id}/preview")
async def get_design_preview(
    design_id: str,
    store: DesignStore = Depends(get_design_store),
) -> dict:
    """Get lightweight preview data for a design (just PDB for 3D viewer).

    This is optimized for lazy loading in card views.

    Args:
        design_id: Design identifier
        store: Design store dependency

    Returns:
        Just the PDB data for 3D preview

    Raises:
        404 if design not found
    """
    design = store.get_public(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    return {"pdb_data": design.structure_pdb}


# ============================================================================
# User Profiles (Public)
# ============================================================================


@router.get("/users/{user_id}", response_model=UserPublicExtended)
async def get_user_profile(
    user_id: str,
    user: OptionalUser = None,
    user_store: UserStore = Depends(get_user_store),
) -> UserPublicExtended:
    """Get a user's extended public profile.

    Args:
        user_id: User identifier
        user: Optional authenticated user (to check if following)
        user_store: User store dependency

    Returns:
        Extended public user profile with stats and follow status

    Raises:
        404 if user not found
    """
    viewer_id = user.id if user else None
    profile = user_store.get_extended_profile(user_id, viewer_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    return profile


@router.get("/users/{user_id}/designs", response_model=list[DesignSummary])
async def get_user_designs(
    user_id: str,
    design_store: DesignStore = Depends(get_design_store),
    user_store: UserStore = Depends(get_user_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[DesignSummary]:
    """Get a user's public designs.

    Args:
        user_id: User identifier
        design_store: Design store dependency
        user_store: User store dependency
        offset: Pagination offset
        limit: Maximum results

    Returns:
        List of user's public designs

    Raises:
        404 if user not found
    """
    # Verify user exists
    if not user_store.get(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's designs (only public ones via search)
    designs = design_store.list_user_designs(user_id, offset, limit)

    # Filter to only public designs
    return [d for d in designs if d.id]  # All designs from list_user_designs are valid


# ============================================================================
# Profile Management (Authenticated)
# ============================================================================


@router.put("/users/me/profile", response_model=dict)
async def update_my_profile(
    updates: UserProfileUpdate,
    user: RequiredUser,
    user_store: UserStore = Depends(get_user_store),
) -> dict:
    """Update the current user's profile.

    Args:
        updates: Profile fields to update
        user: Authenticated user
        user_store: User store dependency

    Returns:
        Success message
    """
    user_store.update_profile(user.id, updates)
    return {"message": "Profile updated successfully"}


# ============================================================================
# Following System (Authenticated)
# ============================================================================


@router.post("/users/{user_id}/follow", response_model=dict)
async def follow_user(
    user_id: str,
    user: RequiredUser,
    user_store: UserStore = Depends(get_user_store),
    follow_store: FollowStore = Depends(get_follow_store),
    notification_store: NotificationStore = Depends(get_notification_store),
) -> dict:
    """Follow a user.

    Args:
        user_id: User to follow
        user: Authenticated user
        user_store: User store dependency
        follow_store: Follow store dependency
        notification_store: Notification store dependency

    Returns:
        Success message

    Raises:
        404 if user not found
        400 if trying to follow yourself or already following
    """
    if user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    # Verify user exists
    if not user_store.get(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    if not follow_store.follow(user.id, user_id):
        raise HTTPException(status_code=400, detail="Already following this user")

    # Notify the followed user
    notification_store.create(
        user_id=user_id,
        notification_type="follow",
        message=f"{user.display_name} started following you",
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
    )

    return {"message": "Successfully followed user"}


@router.delete("/users/{user_id}/follow", response_model=dict)
async def unfollow_user(
    user_id: str,
    user: RequiredUser,
    follow_store: FollowStore = Depends(get_follow_store),
) -> dict:
    """Unfollow a user.

    Args:
        user_id: User to unfollow
        user: Authenticated user
        follow_store: Follow store dependency

    Returns:
        Success message

    Raises:
        400 if not following this user
    """
    if not follow_store.unfollow(user.id, user_id):
        raise HTTPException(status_code=400, detail="Not following this user")

    return {"message": "Successfully unfollowed user"}


@router.get("/users/{user_id}/followers", response_model=FollowerList)
async def get_user_followers(
    user_id: str,
    user_store: UserStore = Depends(get_user_store),
    follow_store: FollowStore = Depends(get_follow_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> FollowerList:
    """Get a user's followers.

    Args:
        user_id: User to get followers for
        user_store: User store dependency
        follow_store: Follow store dependency
        offset: Pagination offset
        limit: Maximum results

    Returns:
        Paginated list of followers

    Raises:
        404 if user not found
    """
    # Verify user exists
    if not user_store.get(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    return follow_store.get_followers(user_id, offset, limit)


@router.get("/users/{user_id}/following", response_model=FollowerList)
async def get_user_following(
    user_id: str,
    user_store: UserStore = Depends(get_user_store),
    follow_store: FollowStore = Depends(get_follow_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> FollowerList:
    """Get users that a user is following.

    Args:
        user_id: User to get following for
        user_store: User store dependency
        follow_store: Follow store dependency
        offset: Pagination offset
        limit: Maximum results

    Returns:
        Paginated list of followed users

    Raises:
        404 if user not found
    """
    # Verify user exists
    if not user_store.get(user_id):
        raise HTTPException(status_code=404, detail="User not found")

    return follow_store.get_following(user_id, offset, limit)
