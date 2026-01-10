"""Notification store for managing user notifications."""

import uuid
from datetime import datetime
from functools import lru_cache
from typing import Literal

from ..logger import get_logger
from ..models.notification import (
    NotificationList,
    NotificationPreferences,
    NotificationPreferencesUpdate,
    NotificationPublic,
    UnreadCount,
)
from ..models.user import UserPublic
from .database import get_connection

logger = get_logger("notification_store")

NotificationType = Literal["star", "fork", "comment", "follow"]


class NotificationStore:
    """Store for notification operations."""

    def create(
        self,
        user_id: str,
        notification_type: NotificationType,
        message: str,
        actor_id: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> str | None:
        """Create a new notification.

        Args:
            user_id: User to notify
            notification_type: Type of notification
            message: Notification message
            actor_id: User who triggered the notification
            target_type: Type of target (design, user, etc.)
            target_id: ID of target

        Returns:
            Notification ID if created, None if preferences prevent it
        """
        # Don't notify yourself
        if actor_id and actor_id == user_id:
            return None

        # Check user preferences
        prefs = self.get_preferences(user_id)
        pref_map = {
            "star": prefs.notify_on_star,
            "fork": prefs.notify_on_fork,
            "comment": prefs.notify_on_comment,
            "follow": prefs.notify_on_follow,
        }

        if not pref_map.get(notification_type, True):
            return None

        notification_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notifications
                    (id, user_id, type, actor_id, target_type, target_id, message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    notification_id,
                    user_id,
                    notification_type,
                    actor_id,
                    target_type,
                    target_id,
                    message,
                ),
            )

        logger.debug(f"Created {notification_type} notification for user {user_id}")
        return notification_id

    def get_notifications(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
        unread_only: bool = False,
    ) -> NotificationList:
        """Get notifications for a user.

        Args:
            user_id: User ID
            offset: Pagination offset
            limit: Max results
            unread_only: Only return unread notifications

        Returns:
            List of notifications with metadata
        """
        with get_connection() as conn:
            # Build query
            where_clause = "WHERE n.user_id = ?"
            params = [user_id]

            if unread_only:
                where_clause += " AND n.is_read = 0"

            # Get notifications with actor info
            rows = conn.execute(
                f"""
                SELECT
                    n.*,
                    u.id as actor_user_id,
                    u.display_name as actor_name,
                    u.avatar_url as actor_avatar,
                    d.name as design_name
                FROM notifications n
                LEFT JOIN users u ON n.actor_id = u.id
                LEFT JOIN designs d ON n.target_type = 'design' AND n.target_id = d.id
                {where_clause}
                ORDER BY n.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit + 1, offset),
            ).fetchall()

            has_more = len(rows) > limit
            rows = rows[:limit]

            # Get total and unread counts
            total = conn.execute(
                f"SELECT COUNT(*) FROM notifications n {where_clause}",
                params,
            ).fetchone()[0]

            unread_count = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,),
            ).fetchone()[0]

            # Build notification list
            notifications = []
            for row in rows:
                actor = None
                if row["actor_user_id"]:
                    actor = UserPublic(
                        id=row["actor_user_id"],
                        display_name=row["actor_name"],
                        avatar_url=row["actor_avatar"],
                    )

                notification = NotificationPublic(
                    id=row["id"],
                    type=row["type"],
                    actor=actor,
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    target_name=row["design_name"],
                    message=row["message"],
                    is_read=bool(row["is_read"]),
                    created_at=datetime.fromisoformat(
                        row["created_at"].replace("Z", "")
                    ),
                )
                notifications.append(notification)

            return NotificationList(
                notifications=notifications,
                total=total,
                unread_count=unread_count,
                has_more=has_more,
            )

    def get_unread_count(self, user_id: str) -> UnreadCount:
        """Get unread notification count.

        Args:
            user_id: User ID

        Returns:
            Unread count
        """
        with get_connection() as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
                (user_id,),
            ).fetchone()[0]

            return UnreadCount(count=count)

    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read.

        Args:
            notification_id: Notification to mark
            user_id: Owner of the notification

        Returns:
            True if marked successfully
        """
        with get_connection() as conn:
            result = conn.execute(
                """
                UPDATE notifications
                SET is_read = 1
                WHERE id = ? AND user_id = ?
                """,
                (notification_id, user_id),
            )
            return result.rowcount > 0

    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read.

        Args:
            user_id: User ID

        Returns:
            Number of notifications marked
        """
        with get_connection() as conn:
            result = conn.execute(
                """
                UPDATE notifications
                SET is_read = 1
                WHERE user_id = ? AND is_read = 0
                """,
                (user_id,),
            )
            return result.rowcount

    def get_preferences(self, user_id: str) -> NotificationPreferences:
        """Get notification preferences for a user.

        Args:
            user_id: User ID

        Returns:
            Notification preferences (defaults if not set)
        """
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM notification_preferences WHERE user_id = ?",
                (user_id,),
            ).fetchone()

            if row:
                return NotificationPreferences(
                    notify_on_star=bool(row["notify_on_star"]),
                    notify_on_fork=bool(row["notify_on_fork"]),
                    notify_on_comment=bool(row["notify_on_comment"]),
                    notify_on_follow=bool(row["notify_on_follow"]),
                )

            # Return defaults
            return NotificationPreferences()

    def update_preferences(
        self,
        user_id: str,
        updates: NotificationPreferencesUpdate,
    ) -> NotificationPreferences:
        """Update notification preferences.

        Args:
            user_id: User ID
            updates: Preference updates

        Returns:
            Updated preferences
        """
        with get_connection() as conn:
            # Get current preferences
            current = self.get_preferences(user_id)

            # Apply updates
            new_prefs = NotificationPreferences(
                notify_on_star=updates.notify_on_star
                if updates.notify_on_star is not None
                else current.notify_on_star,
                notify_on_fork=updates.notify_on_fork
                if updates.notify_on_fork is not None
                else current.notify_on_fork,
                notify_on_comment=updates.notify_on_comment
                if updates.notify_on_comment is not None
                else current.notify_on_comment,
                notify_on_follow=updates.notify_on_follow
                if updates.notify_on_follow is not None
                else current.notify_on_follow,
            )

            # Upsert preferences
            conn.execute(
                """
                INSERT INTO notification_preferences
                    (user_id, notify_on_star, notify_on_fork,
                     notify_on_comment, notify_on_follow)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    notify_on_star = excluded.notify_on_star,
                    notify_on_fork = excluded.notify_on_fork,
                    notify_on_comment = excluded.notify_on_comment,
                    notify_on_follow = excluded.notify_on_follow
                """,
                (
                    user_id,
                    int(new_prefs.notify_on_star),
                    int(new_prefs.notify_on_fork),
                    int(new_prefs.notify_on_comment),
                    int(new_prefs.notify_on_follow),
                ),
            )

            return new_prefs

    def delete_old_notifications(self, days: int = 30) -> int:
        """Delete notifications older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of notifications deleted
        """
        with get_connection() as conn:
            result = conn.execute(
                """
                DELETE FROM notifications
                WHERE created_at < datetime('now', ?)
                """,
                (f"-{days} days",),
            )
            count = result.rowcount

        if count > 0:
            logger.info(f"Deleted {count} old notifications")

        return count


@lru_cache()
def get_notification_store() -> NotificationStore:
    """Get singleton notification store instance."""
    return NotificationStore()
