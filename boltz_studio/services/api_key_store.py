"""API key store for managing programmatic access."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from functools import lru_cache

from ..logger import get_logger
from ..models.api_key import (
    APIKeyCreate,
    APIKeyCreated,
    APIKeyList,
    APIKeyPublic,
)
from .database import get_connection

logger = get_logger("api_key_store")


def hash_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


class APIKeyStore:
    """Store for API key operations."""

    def create(self, user_id: str, data: APIKeyCreate) -> APIKeyCreated:
        """Create a new API key.

        Args:
            user_id: User creating the key
            data: Key configuration

        Returns:
            Created key info (includes full key - only shown once!)
        """
        key_id = str(uuid.uuid4())
        raw_key = f"bsk_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:12]
        key_hash = hash_key(raw_key)

        expires_at = None
        if data.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO api_keys
                (id, user_id, name, key_hash, key_prefix, scopes, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key_id,
                    user_id,
                    data.name,
                    key_hash,
                    key_prefix,
                    data.scopes,
                    expires_at.isoformat() if expires_at else None,
                ),
            )

        logger.info(f"Created API key {key_id} for user {user_id}")

        return APIKeyCreated(
            id=key_id,
            name=data.name,
            key=raw_key,
            key_prefix=key_prefix,
            scopes=data.scopes,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
        )

    def list_user_keys(self, user_id: str) -> APIKeyList:
        """List all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            List of keys (without actual key values)
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, key_prefix, scopes, last_used_at, expires_at, created_at
                FROM api_keys
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()

            keys = [
                APIKeyPublic(
                    id=row["id"],
                    name=row["name"],
                    key_prefix=row["key_prefix"],
                    scopes=row["scopes"],
                    last_used_at=(
                        datetime.fromisoformat(row["last_used_at"].replace("Z", ""))
                        if row["last_used_at"]
                        else None
                    ),
                    expires_at=(
                        datetime.fromisoformat(row["expires_at"].replace("Z", ""))
                        if row["expires_at"]
                        else None
                    ),
                    created_at=datetime.fromisoformat(
                        row["created_at"].replace("Z", "")
                    ),
                )
                for row in rows
            ]

            return APIKeyList(keys=keys, total=len(keys))

    def validate_key(self, raw_key: str) -> tuple[str, str] | None:
        """Validate an API key and return user_id and scopes if valid.

        Args:
            raw_key: The raw API key

        Returns:
            Tuple of (user_id, scopes) if valid, None otherwise
        """
        key_hash = hash_key(raw_key)

        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT user_id, scopes, expires_at
                FROM api_keys
                WHERE key_hash = ?
                """,
                (key_hash,),
            ).fetchone()

            if not row:
                return None

            # Check expiration
            if row["expires_at"]:
                expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", ""))
                if expires_at < datetime.utcnow():
                    return None

            # Update last used
            conn.execute(
                "UPDATE api_keys SET last_used_at = CURRENT_TIMESTAMP WHERE key_hash = ?",
                (key_hash,),
            )

            return (row["user_id"], row["scopes"])

    def delete(self, key_id: str, user_id: str) -> bool:
        """Delete an API key.

        Args:
            key_id: Key ID
            user_id: User ID (must own the key)

        Returns:
            True if deleted
        """
        with get_connection() as conn:
            result = conn.execute(
                "DELETE FROM api_keys WHERE id = ? AND user_id = ?",
                (key_id, user_id),
            )
            return result.rowcount > 0

    def revoke_all(self, user_id: str) -> int:
        """Revoke all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            Number of keys revoked
        """
        with get_connection() as conn:
            result = conn.execute(
                "DELETE FROM api_keys WHERE user_id = ?",
                (user_id,),
            )
            return result.rowcount


@lru_cache()
def get_api_key_store() -> APIKeyStore:
    """Get singleton API key store instance."""
    return APIKeyStore()
