"""SQLite-backed user storage."""

import uuid
from typing import Any

from ..logger import get_logger
from ..models import UserCreate, UserProfile, UserProfileUpdate, UserPublic, UserPublicExtended
from .database import get_connection

logger = get_logger("user_store")


class UserStore:
    """SQLite-backed user storage for OAuth users."""

    def create_or_update(self, user_data: UserCreate) -> dict[str, Any]:
        """Create or update a user from OAuth data.

        If user with same provider + provider_user_id exists, updates their info.
        Otherwise creates a new user.

        Args:
            user_data: User data from OAuth provider

        Returns:
            User record as dictionary
        """
        existing = self.get_by_provider(user_data.provider, user_data.provider_user_id)

        if existing:
            # Update existing user
            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE users SET
                        display_name = ?,
                        avatar_url = ?,
                        email = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        user_data.display_name,
                        user_data.avatar_url,
                        user_data.email,
                        existing["id"],
                    ),
                )
            logger.info(f"Updated user: {existing['id']}")
            return self.get(existing["id"])  # type: ignore
        else:
            # Create new user
            user_id = str(uuid.uuid4())
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO users (
                        id, provider, provider_user_id, email, display_name, avatar_url
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        user_data.provider,
                        user_data.provider_user_id,
                        user_data.email,
                        user_data.display_name,
                        user_data.avatar_url,
                    ),
                )
            logger.info(f"Created user: {user_id} ({user_data.provider})")
            return self.get(user_id)  # type: ignore

    def get(self, user_id: str) -> dict[str, Any] | None:
        """Get user by ID.

        Args:
            user_id: User identifier

        Returns:
            User record or None if not found
        """
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, provider, provider_user_id, email, display_name,
                       avatar_url, bio, affiliation, website, orcid, location,
                       is_verified, follower_count, following_count, design_count,
                       created_at, updated_at
                FROM users WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

            if row:
                return dict(row)
        return None

    def get_by_provider(
        self, provider: str, provider_user_id: str
    ) -> dict[str, Any] | None:
        """Get user by OAuth provider and provider user ID.

        Args:
            provider: OAuth provider name (google/github)
            provider_user_id: User ID from the provider

        Returns:
            User record or None if not found
        """
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, provider, provider_user_id, email, display_name,
                       avatar_url, bio, affiliation, website, orcid, location,
                       is_verified, follower_count, following_count, design_count,
                       created_at, updated_at
                FROM users WHERE provider = ? AND provider_user_id = ?
                """,
                (provider, provider_user_id),
            ).fetchone()

            if row:
                return dict(row)
        return None

    def get_public_profile(self, user_id: str) -> UserPublic | None:
        """Get public user profile.

        Args:
            user_id: User identifier

        Returns:
            Public user profile or None if not found
        """
        user = self.get(user_id)
        if user:
            return UserPublic(
                id=user["id"],
                display_name=user["display_name"],
                avatar_url=user["avatar_url"],
                created_at=user["created_at"],
            )
        return None

    def get_full_profile(self, user_id: str) -> UserProfile | None:
        """Get full user profile (for authenticated user).

        Args:
            user_id: User identifier

        Returns:
            Full user profile or None if not found
        """
        user = self.get(user_id)
        if user:
            return UserProfile(
                id=user["id"],
                display_name=user["display_name"],
                avatar_url=user["avatar_url"],
                email=user["email"],
                provider=user["provider"],
                bio=user.get("bio"),
                affiliation=user.get("affiliation"),
                website=user.get("website"),
                orcid=user.get("orcid"),
                location=user.get("location"),
                created_at=user["created_at"],
            )
        return None

    def get_extended_profile(
        self, user_id: str, viewer_id: str | None = None
    ) -> UserPublicExtended | None:
        """Get extended public profile with stats and follow status.

        Args:
            user_id: User to get profile for
            viewer_id: Optional current user viewing the profile

        Returns:
            Extended public profile or None if not found
        """
        user = self.get(user_id)
        if not user:
            return None

        # Check if viewer is following this user
        is_following = None
        if viewer_id and viewer_id != user_id:
            with get_connection() as conn:
                result = conn.execute(
                    "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
                    (viewer_id, user_id),
                ).fetchone()
                is_following = result is not None

        return UserPublicExtended(
            id=user["id"],
            display_name=user["display_name"],
            avatar_url=user["avatar_url"],
            bio=user.get("bio"),
            affiliation=user.get("affiliation"),
            website=user.get("website"),
            orcid=user.get("orcid"),
            location=user.get("location"),
            is_verified=bool(user.get("is_verified", 0)),
            follower_count=user.get("follower_count", 0),
            following_count=user.get("following_count", 0),
            design_count=user.get("design_count", 0),
            is_following=is_following,
            created_at=user["created_at"],
        )

    def update_profile(self, user_id: str, updates: UserProfileUpdate) -> bool:
        """Update user profile fields.

        Args:
            user_id: User to update
            updates: Profile fields to update

        Returns:
            True if update was successful
        """
        # Build dynamic update query
        fields = []
        values = []

        if updates.display_name is not None:
            fields.append("display_name = ?")
            values.append(updates.display_name)

        if updates.bio is not None:
            fields.append("bio = ?")
            values.append(updates.bio)

        if updates.affiliation is not None:
            fields.append("affiliation = ?")
            values.append(updates.affiliation)

        if updates.website is not None:
            fields.append("website = ?")
            values.append(updates.website)

        if updates.orcid is not None:
            fields.append("orcid = ?")
            values.append(updates.orcid)

        if updates.location is not None:
            fields.append("location = ?")
            values.append(updates.location)

        if not fields:
            return True  # Nothing to update

        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(user_id)

        with get_connection() as conn:
            result = conn.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = ?",
                values,
            )
            if result.rowcount > 0:
                logger.info(f"Updated profile for user: {user_id}")
                return True
        return False

    def increment_design_count(self, user_id: str) -> None:
        """Increment the design count for a user."""
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET design_count = design_count + 1 WHERE id = ?",
                (user_id,),
            )

    def decrement_design_count(self, user_id: str) -> None:
        """Decrement the design count for a user."""
        with get_connection() as conn:
            conn.execute(
                """UPDATE users SET design_count = MAX(0, design_count - 1)
                   WHERE id = ?""",
                (user_id,),
            )

    def delete(self, user_id: str) -> bool:
        """Delete a user and all their data.

        Args:
            user_id: User identifier

        Returns:
            True if user was deleted
        """
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            if cursor.rowcount > 0:
                logger.info(f"Deleted user: {user_id}")
                return True
        return False


# Singleton instance
_store: UserStore | None = None


def get_user_store() -> UserStore:
    """Get the singleton UserStore instance.

    Returns:
        UserStore instance
    """
    global _store
    if _store is None:
        _store = UserStore()
    return _store
