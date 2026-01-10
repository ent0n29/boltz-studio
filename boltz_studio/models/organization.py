"""Organization models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .user import UserPublic


OrgRole = Literal["owner", "admin", "member"]


class OrganizationCreate(BaseModel):
    """Create a new organization."""

    slug: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-z0-9-]+$")
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=200)


class OrganizationUpdate(BaseModel):
    """Update organization fields."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    avatar_url: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=200)


class OrganizationPublic(BaseModel):
    """Public organization data."""

    id: str
    slug: str
    name: str
    description: str | None = None
    avatar_url: str | None = None
    website: str | None = None
    is_verified: bool = False
    member_count: int = 0
    design_count: int = 0
    created_at: datetime


class OrganizationSummary(BaseModel):
    """Lightweight organization summary."""

    id: str
    slug: str
    name: str
    avatar_url: str | None = None
    is_verified: bool = False
    member_count: int = 0


class OrgMember(BaseModel):
    """Organization member info."""

    user: UserPublic
    role: OrgRole
    joined_at: datetime


class OrgMemberList(BaseModel):
    """Paginated list of organization members."""

    members: list[OrgMember]
    total: int
    has_more: bool


class OrgInvite(BaseModel):
    """Invite a user to an organization."""

    user_id: str
    role: OrgRole = "member"


class OrgRoleUpdate(BaseModel):
    """Update a member's role."""

    role: OrgRole
