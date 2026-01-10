"""SQLite-backed session storage."""

import secrets
from datetime import datetime, timedelta
from typing import Any

from ..config import settings
from ..logger import get_logger
from .database import get_connection

logger = get_logger("session_store")


class SessionStore:
    """SQLite-backed session storage."""

    def create(
        self,
        user_id: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Create a new session for a user.

        Args:
            user_id: User identifier
            ip_address: Client IP address
            user_agent: Client user agent string

        Returns:
            Session ID (token)
        """
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(
            hours=settings.session_duration_hours
        )

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, user_id, expires_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, user_id, expires_at.isoformat(), ip_address, user_agent),
            )

        logger.info(f"Created session for user: {user_id}")
        return session_id

    def get_valid_session(self, session_id: str) -> dict[str, Any] | None:
        """Get a session if it exists and hasn't expired.

        Args:
            session_id: Session token

        Returns:
            Session data or None if invalid/expired
        """
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, expires_at, ip_address, user_agent, created_at
                FROM sessions
                WHERE id = ? AND expires_at > datetime('now')
                """,
                (session_id,),
            ).fetchone()

            if row:
                return dict(row)
        return None

    def delete(self, session_id: str) -> bool:
        """Delete a session (logout).

        Args:
            session_id: Session token

        Returns:
            True if session was deleted
        """
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            if cursor.rowcount > 0:
                logger.info(f"Deleted session: {session_id[:8]}...")
                return True
        return False

    def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            Number of sessions deleted
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE user_id = ?", (user_id,)
            )
            count = cursor.rowcount

        if count > 0:
            logger.info(f"Deleted {count} sessions for user: {user_id}")
        return count

    def cleanup_expired(self) -> int:
        """Delete all expired sessions.

        Returns:
            Number of sessions cleaned up
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE expires_at <= datetime('now')"
            )
            count = cursor.rowcount

        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")
        return count

    def extend_session(self, session_id: str) -> bool:
        """Extend session expiration time.

        Args:
            session_id: Session token

        Returns:
            True if session was extended
        """
        expires_at = datetime.utcnow() + timedelta(
            hours=settings.session_duration_hours
        )

        with get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE sessions SET expires_at = ?
                WHERE id = ? AND expires_at > datetime('now')
                """,
                (expires_at.isoformat(), session_id),
            )
            return cursor.rowcount > 0


# Singleton instance
_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get the singleton SessionStore instance.

    Returns:
        SessionStore instance
    """
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
