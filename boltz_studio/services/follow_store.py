"""Follow store: User following relationships."""

import uuid
from datetime import datetime
from functools import lru_cache

from ..logger import get_logger
from ..models import FollowInfo, FollowerList, UserPublic
from .database import get_connection

logger = get_logger("follow_store")


class FollowStore:
    """Store for user follow relationships."""

    def follow(self, follower_id: str, following_id: str) -> bool:
        """Follow a user.

        Args:
            follower_id: User who is following
            following_id: User being followed

        Returns:
            True if follow was created, False if already following
        """
        if follower_id == following_id:
            return False  # Can't follow yourself

        with get_connection() as conn:
            # Check if already following
            existing = conn.execute(
                "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
                (follower_id, following_id),
            ).fetchone()

            if existing:
                return False

            follow_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO follows (id, follower_id, following_id) VALUES (?, ?, ?)",
                (follow_id, follower_id, following_id),
            )

            # Update follower count for the followed user
            conn.execute(
                "UPDATE users SET follower_count = follower_count + 1 WHERE id = ?",
                (following_id,),
            )

            # Update following count for the follower
            conn.execute(
                "UPDATE users SET following_count = following_count + 1 WHERE id = ?",
                (follower_id,),
            )

            logger.info(f"User {follower_id} followed user {following_id}")
            return True

    def unfollow(self, follower_id: str, following_id: str) -> bool:
        """Unfollow a user.

        Args:
            follower_id: User who is unfollowing
            following_id: User being unfollowed

        Returns:
            True if unfollow was successful, False if wasn't following
        """
        with get_connection() as conn:
            result = conn.execute(
                "DELETE FROM follows WHERE follower_id = ? AND following_id = ?",
                (follower_id, following_id),
            )

            if result.rowcount == 0:
                return False

            # Update follower count for the unfollowed user
            conn.execute(
                """UPDATE users SET follower_count = MAX(0, follower_count - 1)
                   WHERE id = ?""",
                (following_id,),
            )

            # Update following count for the unfollower
            conn.execute(
                """UPDATE users SET following_count = MAX(0, following_count - 1)
                   WHERE id = ?""",
                (follower_id,),
            )

            logger.info(f"User {follower_id} unfollowed user {following_id}")
            return True

    def is_following(self, follower_id: str, following_id: str) -> bool:
        """Check if a user is following another user.

        Args:
            follower_id: User who might be following
            following_id: User who might be followed

        Returns:
            True if follower_id follows following_id
        """
        with get_connection() as conn:
            result = conn.execute(
                "SELECT id FROM follows WHERE follower_id = ? AND following_id = ?",
                (follower_id, following_id),
            ).fetchone()
            return result is not None

    def get_followers(
        self, user_id: str, offset: int = 0, limit: int = 20
    ) -> FollowerList:
        """Get followers of a user.

        Args:
            user_id: User to get followers for
            offset: Pagination offset
            limit: Max results to return

        Returns:
            Paginated list of followers
        """
        with get_connection() as conn:
            # Get total count
            total = conn.execute(
                "SELECT COUNT(*) FROM follows WHERE following_id = ?",
                (user_id,),
            ).fetchone()[0]

            # Get followers with user info
            rows = conn.execute(
                """
                SELECT f.id, f.created_at,
                       u.id as user_id, u.display_name, u.avatar_url, u.created_at as user_created_at
                FROM follows f
                JOIN users u ON f.follower_id = u.id
                WHERE f.following_id = ?
                ORDER BY f.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()

            users = [
                FollowInfo(
                    id=row["id"],
                    user=UserPublic(
                        id=row["user_id"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                        created_at=datetime.fromisoformat(row["user_created_at"]),
                    ),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

            return FollowerList(
                users=users,
                total=total,
                has_more=offset + len(users) < total,
            )

    def get_following(
        self, user_id: str, offset: int = 0, limit: int = 20
    ) -> FollowerList:
        """Get users that a user is following.

        Args:
            user_id: User to get following for
            offset: Pagination offset
            limit: Max results to return

        Returns:
            Paginated list of followed users
        """
        with get_connection() as conn:
            # Get total count
            total = conn.execute(
                "SELECT COUNT(*) FROM follows WHERE follower_id = ?",
                (user_id,),
            ).fetchone()[0]

            # Get following with user info
            rows = conn.execute(
                """
                SELECT f.id, f.created_at,
                       u.id as user_id, u.display_name, u.avatar_url, u.created_at as user_created_at
                FROM follows f
                JOIN users u ON f.following_id = u.id
                WHERE f.follower_id = ?
                ORDER BY f.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()

            users = [
                FollowInfo(
                    id=row["id"],
                    user=UserPublic(
                        id=row["user_id"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                        created_at=datetime.fromisoformat(row["user_created_at"]),
                    ),
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]

            return FollowerList(
                users=users,
                total=total,
                has_more=offset + len(users) < total,
            )

    def get_follower_count(self, user_id: str) -> int:
        """Get the number of followers for a user."""
        with get_connection() as conn:
            result = conn.execute(
                "SELECT follower_count FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return result["follower_count"] if result else 0

    def get_following_count(self, user_id: str) -> int:
        """Get the number of users a user is following."""
        with get_connection() as conn:
            result = conn.execute(
                "SELECT following_count FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            return result["following_count"] if result else 0


# Singleton instance
_follow_store: FollowStore | None = None


@lru_cache(maxsize=1)
def get_follow_store() -> FollowStore:
    """Get the singleton FollowStore instance."""
    global _follow_store
    if _follow_store is None:
        _follow_store = FollowStore()
    return _follow_store
