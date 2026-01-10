"""Social feature routes: Stars, Forks, Comments, Collections."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..logger import get_logger
from ..middleware import OptionalUser, RequiredUser
from ..models import (
    AddToCollectionRequest,
    CollectionCreate,
    CollectionPublic,
    CollectionSummary,
    CollectionUpdate,
    CommentCreate,
    CommentList,
    CommentUpdate,
    DesignCreate,
    DesignLineage,
    DesignSummary,
    ForkInfo,
    ForkRequest,
)
from ..services.design_store import DesignStore, get_design_store
from ..services.notification_store import NotificationStore, get_notification_store
from ..services.social_store import SocialStore, get_social_store

logger = get_logger("routes.social")

router = APIRouter(prefix="/api", tags=["social"])


# =============================================================================
# Stars
# =============================================================================


@router.post("/designs/{design_id}/star")
async def star_design(
    design_id: str,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
    design_store: DesignStore = Depends(get_design_store),
    notification_store: NotificationStore = Depends(get_notification_store),
) -> dict:
    """Star a design."""
    # Verify design exists and is public
    design = design_store.get_public(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    if social_store.add_star(design_id, user.id):
        # Notify design owner
        notification_store.create(
            user_id=design.author_id,
            notification_type="star",
            message=f"{user.display_name} starred your design \"{design.name}\"",
            actor_id=user.id,
            target_type="design",
            target_id=design_id,
        )
        return {"message": "Design starred"}
    return {"message": "Already starred"}


@router.delete("/designs/{design_id}/star")
async def unstar_design(
    design_id: str,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
) -> dict:
    """Unstar a design."""
    if social_store.remove_star(design_id, user.id):
        return {"message": "Design unstarred"}
    return {"message": "Was not starred"}


@router.get("/users/me/starred", response_model=list[DesignSummary])
async def get_my_starred(
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[DesignSummary]:
    """Get designs I've starred."""
    return social_store.get_user_starred_designs(user.id, offset, limit)


# =============================================================================
# Forks
# =============================================================================


@router.post("/designs/{design_id}/fork")
async def fork_design(
    design_id: str,
    request: ForkRequest,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
    design_store: DesignStore = Depends(get_design_store),
    notification_store: NotificationStore = Depends(get_notification_store),
) -> dict:
    """Fork a design.

    Creates a new design based on the parent, with attribution.
    """
    # Get parent design
    parent = design_store.get_public(design_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Design not found")

    # Create the fork as a new design
    fork_data = DesignCreate(
        name=request.name,
        description=f"Forked from: {parent.name}",
        sequence=parent.sequence,
        smiles=parent.smiles,
        structure_pdb=parent.structure_pdb,
        confidence_score=parent.confidence_score,
        complex_plddt=parent.complex_plddt,
        ptm=parent.ptm,
        affinity_probability=parent.affinity_probability,
        affinity_raw=parent.affinity_raw,
        plddt_per_residue=parent.plddt_per_residue,
        tags=parent.tags,
        is_public=True,
    )

    fork_design_id = design_store.create(user.id, fork_data)

    # Record the fork relationship
    social_store.create_fork(design_id, user.id, fork_design_id, request)

    # Notify design owner
    notification_store.create(
        user_id=parent.author_id,
        notification_type="fork",
        message=f"{user.display_name} forked your design \"{parent.name}\"",
        actor_id=user.id,
        target_type="design",
        target_id=fork_design_id,
    )

    return {
        "message": "Design forked successfully",
        "fork_id": fork_design_id,
    }


@router.get("/designs/{design_id}/forks", response_model=list[ForkInfo])
async def get_design_forks(
    design_id: str,
    social_store: SocialStore = Depends(get_social_store),
    design_store: DesignStore = Depends(get_design_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[ForkInfo]:
    """Get all forks of a design."""
    # Verify design exists
    if not design_store.get_public(design_id):
        raise HTTPException(status_code=404, detail="Design not found")

    return social_store.get_design_forks(design_id, offset, limit)


@router.get("/designs/{design_id}/parent", response_model=DesignLineage | None)
async def get_design_parent(
    design_id: str,
    social_store: SocialStore = Depends(get_social_store),
) -> DesignLineage | None:
    """Get the parent design if this is a fork."""
    return social_store.get_design_parent(design_id)


# =============================================================================
# Comments
# =============================================================================


@router.post("/designs/{design_id}/comments", response_model=dict)
async def create_comment(
    design_id: str,
    comment: CommentCreate,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
    design_store: DesignStore = Depends(get_design_store),
    notification_store: NotificationStore = Depends(get_notification_store),
) -> dict:
    """Add a comment to a design."""
    # Verify design exists
    design = design_store.get_public(design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    comment_id = social_store.create_comment(design_id, user.id, comment)

    # Notify design owner
    preview = comment.content[:50] + "..." if len(comment.content) > 50 else comment.content
    notification_store.create(
        user_id=design.author_id,
        notification_type="comment",
        message=f"{user.display_name} commented on \"{design.name}\": {preview}",
        actor_id=user.id,
        target_type="design",
        target_id=design_id,
    )

    return {"id": comment_id, "message": "Comment created"}


@router.get("/designs/{design_id}/comments", response_model=CommentList)
async def get_comments(
    design_id: str,
    social_store: SocialStore = Depends(get_social_store),
    design_store: DesignStore = Depends(get_design_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> CommentList:
    """Get comments for a design."""
    # Verify design exists
    if not design_store.get_public(design_id):
        raise HTTPException(status_code=404, detail="Design not found")

    return social_store.get_comments(design_id, offset, limit)


@router.put("/comments/{comment_id}")
async def update_comment(
    comment_id: str,
    update: CommentUpdate,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
) -> dict:
    """Update a comment (author only)."""
    if not social_store.update_comment(comment_id, user.id, update):
        raise HTTPException(
            status_code=404,
            detail="Comment not found or you don't have permission to edit it",
        )
    return {"message": "Comment updated"}


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: str,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
) -> dict:
    """Delete a comment (author only)."""
    if not social_store.delete_comment(comment_id, user.id):
        raise HTTPException(
            status_code=404,
            detail="Comment not found or you don't have permission to delete it",
        )
    return {"message": "Comment deleted"}


# =============================================================================
# Collections
# =============================================================================


@router.post("/collections", response_model=dict)
async def create_collection(
    data: CollectionCreate,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
) -> dict:
    """Create a new collection."""
    collection_id = social_store.create_collection(user.id, data)
    return {"id": collection_id, "message": "Collection created"}


@router.get("/collections", response_model=list[CollectionSummary])
async def list_my_collections(
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[CollectionSummary]:
    """List my collections (including private)."""
    return social_store.list_user_collections(user.id, include_private=True, offset=offset, limit=limit)


@router.get("/collections/browse", response_model=list[CollectionSummary])
async def browse_collections(
    social_store: SocialStore = Depends(get_social_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[CollectionSummary]:
    """Browse all public collections."""
    return social_store.list_public_collections(offset=offset, limit=limit)


@router.get("/collections/{collection_id}", response_model=CollectionPublic)
async def get_collection(
    collection_id: str,
    user: OptionalUser,
    social_store: SocialStore = Depends(get_social_store),
) -> CollectionPublic:
    """Get a collection by ID."""
    user_id = user.id if user else None
    collection = social_store.get_collection(collection_id, user_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    return collection


@router.get("/collections/{collection_id}/designs", response_model=list[DesignSummary])
async def get_collection_designs(
    collection_id: str,
    user: OptionalUser,
    social_store: SocialStore = Depends(get_social_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[DesignSummary]:
    """Get designs in a collection."""
    user_id = user.id if user else None

    # Check access
    collection = social_store.get_collection(collection_id, user_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    return social_store.get_collection_designs(collection_id, offset, limit)


@router.put("/collections/{collection_id}")
async def update_collection(
    collection_id: str,
    update: CollectionUpdate,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
) -> dict:
    """Update a collection (owner only)."""
    if not social_store.update_collection(collection_id, user.id, update):
        raise HTTPException(
            status_code=404,
            detail="Collection not found or you don't have permission to edit it",
        )
    return {"message": "Collection updated"}


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
) -> dict:
    """Delete a collection (owner only)."""
    if not social_store.delete_collection(collection_id, user.id):
        raise HTTPException(
            status_code=404,
            detail="Collection not found or you don't have permission to delete it",
        )
    return {"message": "Collection deleted"}


@router.post("/collections/{collection_id}/designs")
async def add_to_collection(
    collection_id: str,
    request: AddToCollectionRequest,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
    design_store: DesignStore = Depends(get_design_store),
) -> dict:
    """Add a design to a collection (owner only)."""
    # Verify design exists
    if not design_store.get_public(request.design_id):
        raise HTTPException(status_code=404, detail="Design not found")

    if not social_store.add_design_to_collection(collection_id, user.id, request.design_id):
        raise HTTPException(
            status_code=404,
            detail="Collection not found or you don't have permission to edit it",
        )
    return {"message": "Design added to collection"}


@router.delete("/collections/{collection_id}/designs/{design_id}")
async def remove_from_collection(
    collection_id: str,
    design_id: str,
    user: RequiredUser,
    social_store: SocialStore = Depends(get_social_store),
) -> dict:
    """Remove a design from a collection (owner only)."""
    if not social_store.remove_design_from_collection(collection_id, user.id, design_id):
        raise HTTPException(
            status_code=404,
            detail="Collection not found or you don't have permission to edit it",
        )
    return {"message": "Design removed from collection"}


@router.get("/users/{user_id}/collections", response_model=list[CollectionSummary])
async def get_user_collections(
    user_id: str,
    social_store: SocialStore = Depends(get_social_store),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[CollectionSummary]:
    """Get a user's public collections."""
    return social_store.list_user_collections(user_id, include_private=False, offset=offset, limit=limit)
