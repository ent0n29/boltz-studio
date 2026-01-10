"""User and authentication models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user fields."""

    display_name: str = Field(..., min_length=1, max_length=100)
    avatar_url: str | None = None


class UserCreate(UserBase):
    """Internal model for creating a user from OAuth."""

    provider: Literal["google", "github", "dev"]
    provider_user_id: str
    email: EmailStr | None = None


class UserPublic(UserBase):
    """Public user information (safe to expose)."""

    id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserProfile(UserPublic):
    """Full user profile for authenticated user."""

    email: str | None = None
    provider: str
    bio: str | None = None
    affiliation: str | None = None
    website: str | None = None
    orcid: str | None = None
    location: str | None = None


class UserProfileUpdate(BaseModel):
    """Model for updating user profile fields."""

    display_name: str | None = Field(None, min_length=1, max_length=100)
    bio: str | None = Field(None, max_length=500)
    affiliation: str | None = Field(None, max_length=200)
    website: str | None = Field(None, max_length=200)
    orcid: str | None = Field(None, pattern=r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
    location: str | None = Field(None, max_length=100)


class UserPublicExtended(UserPublic):
    """Extended public user profile with stats and social info."""

    bio: str | None = None
    affiliation: str | None = None
    website: str | None = None
    orcid: str | None = None
    location: str | None = None
    is_verified: bool = False
    follower_count: int = 0
    following_count: int = 0
    design_count: int = 0
    is_following: bool | None = None  # Whether current user follows this user


class FollowInfo(BaseModel):
    """Information about a follow relationship."""

    id: str
    user: UserPublic
    created_at: datetime

    model_config = {"from_attributes": True}


class FollowerList(BaseModel):
    """Paginated list of followers/following."""

    users: list[FollowInfo]
    total: int
    has_more: bool


class SessionInfo(BaseModel):
    """Session information."""

    id: str
    user_id: str
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}
