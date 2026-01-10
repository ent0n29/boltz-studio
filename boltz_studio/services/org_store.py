"""Organization store for managing organizations and members."""

import re
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Literal

from ..logger import get_logger
from ..models.organization import (
    OrganizationCreate,
    OrganizationPublic,
    OrganizationSummary,
    OrganizationUpdate,
    OrgMember,
    OrgMemberList,
)
from ..models.user import UserPublic
from .database import get_connection

logger = get_logger("org_store")

OrgRole = Literal["owner", "admin", "member"]


class OrgStore:
    """Store for organization operations."""

    def create(self, user_id: str, data: OrganizationCreate) -> str:
        """Create a new organization.

        Args:
            user_id: User creating the organization (becomes owner)
            data: Organization data

        Returns:
            Organization ID

        Raises:
            ValueError if slug is already taken
        """
        org_id = str(uuid.uuid4())

        with get_connection() as conn:
            # Check slug availability
            existing = conn.execute(
                "SELECT id FROM organizations WHERE slug = ?",
                (data.slug,),
            ).fetchone()

            if existing:
                raise ValueError("Organization slug already taken")

            # Create organization
            conn.execute(
                """
                INSERT INTO organizations (id, slug, name, description, website)
                VALUES (?, ?, ?, ?, ?)
                """,
                (org_id, data.slug, data.name, data.description, data.website),
            )

            # Add creator as owner
            member_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO org_members (id, org_id, user_id, role)
                VALUES (?, ?, ?, 'owner')
                """,
                (member_id, org_id, user_id),
            )

        logger.info(f"Created organization {data.slug} (id={org_id}) by user {user_id}")
        return org_id

    def get_by_slug(self, slug: str) -> OrganizationPublic | None:
        """Get organization by slug.

        Args:
            slug: Organization slug

        Returns:
            Organization or None if not found
        """
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM organizations WHERE slug = ?",
                (slug,),
            ).fetchone()

            if not row:
                return None

            # Get member count
            member_count = conn.execute(
                "SELECT COUNT(*) FROM org_members WHERE org_id = ?",
                (row["id"],),
            ).fetchone()[0]

            # Get design count
            design_count = conn.execute(
                "SELECT COUNT(*) FROM designs WHERE org_id = ?",
                (row["id"],),
            ).fetchone()[0]

            return OrganizationPublic(
                id=row["id"],
                slug=row["slug"],
                name=row["name"],
                description=row["description"],
                avatar_url=row["avatar_url"],
                website=row["website"],
                is_verified=bool(row["is_verified"]),
                member_count=member_count,
                design_count=design_count,
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "")),
            )

    def get_by_id(self, org_id: str) -> OrganizationPublic | None:
        """Get organization by ID.

        Args:
            org_id: Organization ID

        Returns:
            Organization or None if not found
        """
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM organizations WHERE id = ?",
                (org_id,),
            ).fetchone()

            if not row:
                return None

            # Get member count
            member_count = conn.execute(
                "SELECT COUNT(*) FROM org_members WHERE org_id = ?",
                (org_id,),
            ).fetchone()[0]

            # Get design count
            design_count = conn.execute(
                "SELECT COUNT(*) FROM designs WHERE org_id = ?",
                (org_id,),
            ).fetchone()[0]

            return OrganizationPublic(
                id=row["id"],
                slug=row["slug"],
                name=row["name"],
                description=row["description"],
                avatar_url=row["avatar_url"],
                website=row["website"],
                is_verified=bool(row["is_verified"]),
                member_count=member_count,
                design_count=design_count,
                created_at=datetime.fromisoformat(row["created_at"].replace("Z", "")),
            )

    def update(
        self,
        org_id: str,
        user_id: str,
        updates: OrganizationUpdate,
    ) -> bool:
        """Update organization.

        Args:
            org_id: Organization ID
            user_id: User making the update (must be owner/admin)
            updates: Fields to update

        Returns:
            True if updated successfully
        """
        # Check permissions
        role = self.get_user_role(org_id, user_id)
        if role not in ("owner", "admin"):
            return False

        with get_connection() as conn:
            set_parts = []
            params = []

            if updates.name is not None:
                set_parts.append("name = ?")
                params.append(updates.name)

            if updates.description is not None:
                set_parts.append("description = ?")
                params.append(updates.description)

            if updates.avatar_url is not None:
                set_parts.append("avatar_url = ?")
                params.append(updates.avatar_url)

            if updates.website is not None:
                set_parts.append("website = ?")
                params.append(updates.website)

            if not set_parts:
                return True

            set_parts.append("updated_at = CURRENT_TIMESTAMP")
            params.append(org_id)

            conn.execute(
                f"UPDATE organizations SET {', '.join(set_parts)} WHERE id = ?",
                params,
            )

        return True

    def delete(self, org_id: str, user_id: str) -> bool:
        """Delete organization.

        Args:
            org_id: Organization ID
            user_id: User deleting (must be owner)

        Returns:
            True if deleted successfully
        """
        # Only owner can delete
        role = self.get_user_role(org_id, user_id)
        if role != "owner":
            return False

        with get_connection() as conn:
            # Remove org_id from designs
            conn.execute(
                "UPDATE designs SET org_id = NULL WHERE org_id = ?",
                (org_id,),
            )

            # Delete organization (cascades to members)
            conn.execute("DELETE FROM organizations WHERE id = ?", (org_id,))

        logger.info(f"Deleted organization {org_id} by user {user_id}")
        return True

    def get_user_role(self, org_id: str, user_id: str) -> OrgRole | None:
        """Get user's role in an organization.

        Args:
            org_id: Organization ID
            user_id: User ID

        Returns:
            Role or None if not a member
        """
        with get_connection() as conn:
            row = conn.execute(
                "SELECT role FROM org_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            ).fetchone()

            return row["role"] if row else None

    def add_member(
        self,
        org_id: str,
        requester_id: str,
        user_id: str,
        role: OrgRole = "member",
    ) -> bool:
        """Add a member to an organization.

        Args:
            org_id: Organization ID
            requester_id: User making the request (must be owner/admin)
            user_id: User to add
            role: Role to assign

        Returns:
            True if added successfully
        """
        # Check permissions
        requester_role = self.get_user_role(org_id, requester_id)
        if requester_role not in ("owner", "admin"):
            return False

        # Admins can only add members, not other admins/owners
        if requester_role == "admin" and role != "member":
            return False

        member_id = str(uuid.uuid4())

        with get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO org_members (id, org_id, user_id, role)
                    VALUES (?, ?, ?, ?)
                    """,
                    (member_id, org_id, user_id, role),
                )
                return True
            except Exception:
                return False

    def remove_member(
        self,
        org_id: str,
        requester_id: str,
        user_id: str,
    ) -> bool:
        """Remove a member from an organization.

        Args:
            org_id: Organization ID
            requester_id: User making the request
            user_id: User to remove

        Returns:
            True if removed successfully
        """
        # Users can remove themselves
        if requester_id == user_id:
            # But owners cannot leave if they're the only owner
            role = self.get_user_role(org_id, user_id)
            if role == "owner":
                with get_connection() as conn:
                    owner_count = conn.execute(
                        "SELECT COUNT(*) FROM org_members WHERE org_id = ? AND role = 'owner'",
                        (org_id,),
                    ).fetchone()[0]
                    if owner_count <= 1:
                        return False

            with get_connection() as conn:
                conn.execute(
                    "DELETE FROM org_members WHERE org_id = ? AND user_id = ?",
                    (org_id, user_id),
                )
            return True

        # Check permissions for removing others
        requester_role = self.get_user_role(org_id, requester_id)
        target_role = self.get_user_role(org_id, user_id)

        if requester_role not in ("owner", "admin"):
            return False

        # Admins can only remove members
        if requester_role == "admin" and target_role != "member":
            return False

        # Owners can remove anyone except other owners
        if requester_role == "owner" and target_role == "owner":
            return False

        with get_connection() as conn:
            conn.execute(
                "DELETE FROM org_members WHERE org_id = ? AND user_id = ?",
                (org_id, user_id),
            )

        return True

    def update_member_role(
        self,
        org_id: str,
        requester_id: str,
        user_id: str,
        new_role: OrgRole,
    ) -> bool:
        """Update a member's role.

        Args:
            org_id: Organization ID
            requester_id: User making the request (must be owner)
            user_id: User to update
            new_role: New role

        Returns:
            True if updated successfully
        """
        # Only owners can change roles
        requester_role = self.get_user_role(org_id, requester_id)
        if requester_role != "owner":
            return False

        # Cannot change own role or other owners
        if requester_id == user_id:
            return False

        target_role = self.get_user_role(org_id, user_id)
        if target_role == "owner":
            return False

        with get_connection() as conn:
            conn.execute(
                "UPDATE org_members SET role = ? WHERE org_id = ? AND user_id = ?",
                (new_role, org_id, user_id),
            )

        return True

    def get_members(
        self,
        org_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> OrgMemberList:
        """Get organization members.

        Args:
            org_id: Organization ID
            offset: Pagination offset
            limit: Max results

        Returns:
            List of members
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    om.role, om.created_at,
                    u.id, u.display_name, u.avatar_url
                FROM org_members om
                JOIN users u ON om.user_id = u.id
                WHERE om.org_id = ?
                ORDER BY
                    CASE om.role
                        WHEN 'owner' THEN 1
                        WHEN 'admin' THEN 2
                        ELSE 3
                    END,
                    om.created_at
                LIMIT ? OFFSET ?
                """,
                (org_id, limit + 1, offset),
            ).fetchall()

            has_more = len(rows) > limit
            rows = rows[:limit]

            total = conn.execute(
                "SELECT COUNT(*) FROM org_members WHERE org_id = ?",
                (org_id,),
            ).fetchone()[0]

            members = []
            for row in rows:
                user = UserPublic(
                    id=row["id"],
                    display_name=row["display_name"],
                    avatar_url=row["avatar_url"],
                )
                member = OrgMember(
                    user=user,
                    role=row["role"],
                    joined_at=datetime.fromisoformat(row["created_at"].replace("Z", "")),
                )
                members.append(member)

            return OrgMemberList(
                members=members,
                total=total,
                has_more=has_more,
            )

    def get_user_organizations(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[OrganizationSummary]:
        """Get organizations a user belongs to.

        Args:
            user_id: User ID
            offset: Pagination offset
            limit: Max results

        Returns:
            List of organization summaries
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT o.*, COUNT(om2.id) as member_count
                FROM organizations o
                JOIN org_members om ON o.id = om.org_id
                LEFT JOIN org_members om2 ON o.id = om2.org_id
                WHERE om.user_id = ?
                GROUP BY o.id
                ORDER BY o.name
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()

            return [
                OrganizationSummary(
                    id=row["id"],
                    slug=row["slug"],
                    name=row["name"],
                    avatar_url=row["avatar_url"],
                    is_verified=bool(row["is_verified"]),
                    member_count=row["member_count"],
                )
                for row in rows
            ]

    def list_public(
        self,
        offset: int = 0,
        limit: int = 20,
    ) -> list[OrganizationSummary]:
        """List public organizations.

        Args:
            offset: Pagination offset
            limit: Max results

        Returns:
            List of organization summaries
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT o.*, COUNT(om.id) as member_count
                FROM organizations o
                LEFT JOIN org_members om ON o.id = om.org_id
                GROUP BY o.id
                ORDER BY member_count DESC, o.name
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

            return [
                OrganizationSummary(
                    id=row["id"],
                    slug=row["slug"],
                    name=row["name"],
                    avatar_url=row["avatar_url"],
                    is_verified=bool(row["is_verified"]),
                    member_count=row["member_count"],
                )
                for row in rows
            ]


@lru_cache()
def get_org_store() -> OrgStore:
    """Get singleton organization store instance."""
    return OrgStore()
