"""Organization routes."""

from fastapi import APIRouter, Depends, HTTPException, Query

from ..logger import get_logger
from ..middleware import RequiredUser
from ..models.organization import (
    OrganizationCreate,
    OrganizationPublic,
    OrganizationSummary,
    OrganizationUpdate,
    OrgInvite,
    OrgMemberList,
    OrgRoleUpdate,
)
from ..services.org_store import OrgStore, get_org_store

logger = get_logger("routes.organization")

router = APIRouter(prefix="/api/organizations", tags=["organizations"])


@router.post("", response_model=dict)
async def create_organization(
    data: OrganizationCreate,
    user: RequiredUser,
    store: OrgStore = Depends(get_org_store),
) -> dict:
    """Create a new organization.

    Args:
        data: Organization data
        user: Authenticated user (becomes owner)
        store: Organization store

    Returns:
        Created organization ID and slug
    """
    try:
        org_id = store.create(user.id, data)
        return {"id": org_id, "slug": data.slug, "message": "Organization created"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=list[OrganizationSummary])
async def list_organizations(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: OrgStore = Depends(get_org_store),
) -> list[OrganizationSummary]:
    """List public organizations.

    Args:
        offset: Pagination offset
        limit: Max results
        store: Organization store

    Returns:
        List of organizations
    """
    return store.list_public(offset, limit)


@router.get("/{slug}", response_model=OrganizationPublic)
async def get_organization(
    slug: str,
    store: OrgStore = Depends(get_org_store),
) -> OrganizationPublic:
    """Get organization by slug.

    Args:
        slug: Organization slug
        store: Organization store

    Returns:
        Organization details

    Raises:
        404 if not found
    """
    org = store.get_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.put("/{slug}")
async def update_organization(
    slug: str,
    updates: OrganizationUpdate,
    user: RequiredUser,
    store: OrgStore = Depends(get_org_store),
) -> dict:
    """Update organization.

    Args:
        slug: Organization slug
        updates: Fields to update
        user: Authenticated user (must be owner/admin)
        store: Organization store

    Returns:
        Success message

    Raises:
        404 if not found or no permission
    """
    org = store.get_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not store.update(org.id, user.id, updates):
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"message": "Organization updated"}


@router.delete("/{slug}")
async def delete_organization(
    slug: str,
    user: RequiredUser,
    store: OrgStore = Depends(get_org_store),
) -> dict:
    """Delete organization.

    Args:
        slug: Organization slug
        user: Authenticated user (must be owner)
        store: Organization store

    Returns:
        Success message

    Raises:
        404 if not found or no permission
    """
    org = store.get_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not store.delete(org.id, user.id):
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"message": "Organization deleted"}


# ============================================================================
# Members
# ============================================================================


@router.get("/{slug}/members", response_model=OrgMemberList)
async def get_members(
    slug: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: OrgStore = Depends(get_org_store),
) -> OrgMemberList:
    """Get organization members.

    Args:
        slug: Organization slug
        offset: Pagination offset
        limit: Max results
        store: Organization store

    Returns:
        List of members

    Raises:
        404 if organization not found
    """
    org = store.get_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return store.get_members(org.id, offset, limit)


@router.post("/{slug}/members")
async def add_member(
    slug: str,
    invite: OrgInvite,
    user: RequiredUser,
    store: OrgStore = Depends(get_org_store),
) -> dict:
    """Add a member to the organization.

    Args:
        slug: Organization slug
        invite: User to invite and role
        user: Authenticated user (must be owner/admin)
        store: Organization store

    Returns:
        Success message

    Raises:
        404 if organization not found
        403 if no permission
    """
    org = store.get_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not store.add_member(org.id, user.id, invite.user_id, invite.role):
        raise HTTPException(status_code=403, detail="Permission denied or user already member")

    return {"message": "Member added"}


@router.delete("/{slug}/members/{user_id}")
async def remove_member(
    slug: str,
    user_id: str,
    user: RequiredUser,
    store: OrgStore = Depends(get_org_store),
) -> dict:
    """Remove a member from the organization.

    Args:
        slug: Organization slug
        user_id: User to remove
        user: Authenticated user
        store: Organization store

    Returns:
        Success message

    Raises:
        404 if organization not found
        403 if no permission
    """
    org = store.get_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not store.remove_member(org.id, user.id, user_id):
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"message": "Member removed"}


@router.put("/{slug}/members/{user_id}")
async def update_member_role(
    slug: str,
    user_id: str,
    role_update: OrgRoleUpdate,
    user: RequiredUser,
    store: OrgStore = Depends(get_org_store),
) -> dict:
    """Update a member's role.

    Args:
        slug: Organization slug
        user_id: User to update
        role_update: New role
        user: Authenticated user (must be owner)
        store: Organization store

    Returns:
        Success message

    Raises:
        404 if organization not found
        403 if no permission
    """
    org = store.get_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if not store.update_member_role(org.id, user.id, user_id, role_update.role):
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"message": "Role updated"}


# ============================================================================
# User's Organizations
# ============================================================================


@router.get("/me/list", response_model=list[OrganizationSummary])
async def get_my_organizations(
    user: RequiredUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    store: OrgStore = Depends(get_org_store),
) -> list[OrganizationSummary]:
    """Get organizations the current user belongs to.

    Args:
        user: Authenticated user
        offset: Pagination offset
        limit: Max results
        store: Organization store

    Returns:
        List of user's organizations
    """
    return store.get_user_organizations(user.id, offset, limit)
