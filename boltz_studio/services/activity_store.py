"""Activity feed store for tracking user activities."""

import json
import uuid
from datetime import datetime
from functools import lru_cache

from ..logger import get_logger
from ..models.activity import ActivityFeed, ActivityPublic
from ..models.user import UserPublic
from .database import get_connection

logger = get_logger("activity_store")


class ActivityStore:
    """Store for activity feed operations."""

    def record(
        self,
        user_id: str,
        activity_type: str,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """Record a user activity.

        Args:
            user_id: User who performed the activity
            activity_type: Type of activity
            target_type: Type of target (design, user, etc.)
            target_id: Target ID
            metadata: Additional metadata

        Returns:
            Activity ID
        """
        activity_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO activities
                (id, user_id, activity_type, target_type, target_id, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    activity_id,
                    user_id,
                    activity_type,
                    target_type,
                    target_id,
                    json.dumps(metadata) if metadata else None,
                ),
            )

        return activity_id

    def get_user_feed(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> ActivityFeed:
        """Get activity feed for users that a user follows.

        Args:
            user_id: User requesting the feed
            offset: Pagination offset
            limit: Max results

        Returns:
            Activity feed
        """
        with get_connection() as conn:
            # Get activities from followed users
            rows = conn.execute(
                """
                SELECT
                    a.id, a.activity_type, a.target_type, a.target_id, a.metadata, a.created_at,
                    u.id as user_id, u.display_name, u.avatar_url, u.created_at as user_created_at
                FROM activities a
                JOIN users u ON a.user_id = u.id
                WHERE a.user_id IN (
                    SELECT following_id FROM follows WHERE follower_id = ?
                )
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit + 1, offset),
            ).fetchall()

            has_more = len(rows) > limit
            rows = rows[:limit]

            total = conn.execute(
                """
                SELECT COUNT(*) FROM activities
                WHERE user_id IN (
                    SELECT following_id FROM follows WHERE follower_id = ?
                )
                """,
                (user_id,),
            ).fetchone()[0]

            activities = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else None

                # Get target name based on target type
                target_name = None
                target_preview = None

                if row["target_type"] == "design" and row["target_id"]:
                    design = conn.execute(
                        "SELECT name, preview_image FROM designs WHERE id = ?",
                        (row["target_id"],),
                    ).fetchone()
                    if design:
                        target_name = design["name"]
                        target_preview = design["preview_image"]
                elif row["target_type"] == "user" and row["target_id"]:
                    target_user = conn.execute(
                        "SELECT display_name FROM users WHERE id = ?",
                        (row["target_id"],),
                    ).fetchone()
                    if target_user:
                        target_name = target_user["display_name"]

                activities.append(
                    ActivityPublic(
                        id=row["id"],
                        user=UserPublic(
                            id=row["user_id"],
                            display_name=row["display_name"],
                            avatar_url=row["avatar_url"],
                            created_at=datetime.fromisoformat(
                                row["user_created_at"].replace("Z", "")
                            ),
                        ),
                        activity_type=row["activity_type"],
                        target_type=row["target_type"],
                        target_id=row["target_id"],
                        target_name=target_name,
                        target_preview=target_preview,
                        metadata=metadata,
                        created_at=datetime.fromisoformat(
                            row["created_at"].replace("Z", "")
                        ),
                    )
                )

            return ActivityFeed(
                activities=activities,
                total=total,
                has_more=has_more,
            )

    def get_user_activities(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> ActivityFeed:
        """Get a user's own activities.

        Args:
            user_id: User ID
            offset: Pagination offset
            limit: Max results

        Returns:
            Activity feed
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    a.id, a.activity_type, a.target_type, a.target_id, a.metadata, a.created_at,
                    u.id as user_id, u.display_name, u.avatar_url, u.created_at as user_created_at
                FROM activities a
                JOIN users u ON a.user_id = u.id
                WHERE a.user_id = ?
                ORDER BY a.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit + 1, offset),
            ).fetchall()

            has_more = len(rows) > limit
            rows = rows[:limit]

            total = conn.execute(
                "SELECT COUNT(*) FROM activities WHERE user_id = ?",
                (user_id,),
            ).fetchone()[0]

            activities = []
            for row in rows:
                metadata = json.loads(row["metadata"]) if row["metadata"] else None

                target_name = None
                target_preview = None

                if row["target_type"] == "design" and row["target_id"]:
                    design = conn.execute(
                        "SELECT name, preview_image FROM designs WHERE id = ?",
                        (row["target_id"],),
                    ).fetchone()
                    if design:
                        target_name = design["name"]
                        target_preview = design["preview_image"]
                elif row["target_type"] == "user" and row["target_id"]:
                    target_user = conn.execute(
                        "SELECT display_name FROM users WHERE id = ?",
                        (row["target_id"],),
                    ).fetchone()
                    if target_user:
                        target_name = target_user["display_name"]

                activities.append(
                    ActivityPublic(
                        id=row["id"],
                        user=UserPublic(
                            id=row["user_id"],
                            display_name=row["display_name"],
                            avatar_url=row["avatar_url"],
                            created_at=datetime.fromisoformat(
                                row["user_created_at"].replace("Z", "")
                            ),
                        ),
                        activity_type=row["activity_type"],
                        target_type=row["target_type"],
                        target_id=row["target_id"],
                        target_name=target_name,
                        target_preview=target_preview,
                        metadata=metadata,
                        created_at=datetime.fromisoformat(
                            row["created_at"].replace("Z", "")
                        ),
                    )
                )

            return ActivityFeed(
                activities=activities,
                total=total,
                has_more=has_more,
            )


@lru_cache()
def get_activity_store() -> ActivityStore:
    """Get singleton activity store instance."""
    return ActivityStore()
