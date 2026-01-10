"""Pydantic models for social features: Stars, Forks, Comments, Collections."""

from datetime import datetime

from pydantic import BaseModel, Field

from .user import UserPublic


# =============================================================================
# Star Models
# =============================================================================


class StarInfo(BaseModel):
    """Information about a star."""

    id: str
    design_id: str
    user: UserPublic
    created_at: datetime


# =============================================================================
# Fork Models
# =============================================================================


class ForkRequest(BaseModel):
    """Request to fork a design."""

    name: str = Field(..., min_length=1, max_length=100)
    attribution_note: str | None = Field(None, max_length=500)


class ForkInfo(BaseModel):
    """Information about a fork relationship."""

    id: str
    parent_design_id: str
    fork_design_id: str
    user: UserPublic
    attribution_note: str | None
    created_at: datetime


class DesignLineage(BaseModel):
    """Design lineage showing parent and forks."""

    parent_design_id: str | None = None
    parent_name: str | None = None
    fork_count: int = 0


# =============================================================================
# Comment Models
# =============================================================================


class CommentCreate(BaseModel):
    """Create a new comment."""

    content: str = Field(..., min_length=1, max_length=5000)
    lab_validated: bool = False


class CommentUpdate(BaseModel):
    """Update an existing comment."""

    content: str | None = Field(None, min_length=1, max_length=5000)
    lab_validated: bool | None = None


class CommentPublic(BaseModel):
    """Public comment information."""

    id: str
    design_id: str
    author: UserPublic
    content: str
    lab_validated: bool
    created_at: datetime
    updated_at: datetime


class CommentList(BaseModel):
    """Paginated list of comments."""

    comments: list[CommentPublic]
    total: int
    offset: int
    limit: int


# =============================================================================
# Collection Models
# =============================================================================


class CollectionCreate(BaseModel):
    """Create a new collection."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    is_public: bool = True


class CollectionUpdate(BaseModel):
    """Update an existing collection."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    is_public: bool | None = None


class CollectionSummary(BaseModel):
    """Summary of a collection for listings."""

    id: str
    name: str
    description: str | None
    owner: UserPublic
    design_count: int
    is_public: bool
    created_at: datetime
    updated_at: datetime


class CollectionPublic(BaseModel):
    """Full collection with designs."""

    id: str
    name: str
    description: str | None
    owner: UserPublic
    design_count: int
    is_public: bool
    created_at: datetime
    updated_at: datetime
    # Note: designs are fetched separately to allow pagination


class AddToCollectionRequest(BaseModel):
    """Request to add a design to a collection."""

    design_id: str
