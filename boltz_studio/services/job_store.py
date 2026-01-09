"""SQLite-backed job storage."""

import json
from typing import Any, Literal

from ..logger import get_logger
from .database import get_connection

logger = get_logger("job_store")

JobStatusType = Literal["queued", "running", "completed", "failed"]


class JobStore:
    """SQLite-backed job storage with persistence across restarts."""

    def create(self, job_id: str) -> dict[str, Any]:
        """Create a new job.

        Args:
            job_id: Unique job identifier

        Returns:
            Initial job data
        """
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO jobs (id, status, progress) VALUES (?, ?, ?)",
                (job_id, "queued", 0.0)
            )

        logger.info(f"Created job: {job_id}")
        return self.get(job_id) or {
            "status": "queued",
            "progress": 0.0,
            "result": None,
            "error": None,
        }

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Get job by ID.

        Args:
            job_id: Job identifier

        Returns:
            Job data or None if not found
        """
        with get_connection() as conn:
            row = conn.execute(
                "SELECT status, progress, result, error FROM jobs WHERE id = ?",
                (job_id,)
            ).fetchone()

            if row:
                return {
                    "status": row["status"],
                    "progress": row["progress"],
                    "result": json.loads(row["result"]) if row["result"] else None,
                    "error": row["error"],
                }
        return None

    def update(self, job_id: str, **kwargs: Any) -> None:
        """Update job fields.

        Args:
            job_id: Job identifier
            **kwargs: Fields to update (status, progress, result, error)
        """
        if not kwargs:
            return

        # Serialize result to JSON if present
        if "result" in kwargs and kwargs["result"] is not None:
            kwargs["result"] = json.dumps(kwargs["result"])

        # Build dynamic UPDATE query
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [job_id]

        with get_connection() as conn:
            conn.execute(
                f"UPDATE jobs SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )

        if "status" in kwargs:
            logger.info(f"Job {job_id} status: {kwargs['status']}")

    def exists(self, job_id: str) -> bool:
        """Check if job exists.

        Args:
            job_id: Job identifier

        Returns:
            True if job exists
        """
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM jobs WHERE id = ?",
                (job_id,)
            ).fetchone()
            return row is not None

    def delete(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: Job identifier

        Returns:
            True if job was deleted
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM jobs WHERE id = ?",
                (job_id,)
            )
            if cursor.rowcount > 0:
                logger.info(f"Deleted job: {job_id}")
                return True
        return False

    def list_jobs(
        self,
        status: JobStatusType | None = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """List jobs, optionally filtered by status.

        Args:
            status: Filter by job status
            limit: Maximum number of jobs to return

        Returns:
            List of job data dictionaries
        """
        with get_connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT id, status, progress, error, created_at FROM jobs "
                    "WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, status, progress, error, created_at FROM jobs "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                ).fetchall()

            return [
                {
                    "id": row["id"],
                    "status": row["status"],
                    "progress": row["progress"],
                    "error": row["error"],
                    "created_at": row["created_at"],
                }
                for row in rows
            ]

    def cleanup_old_jobs(self, hours: int = 24) -> int:
        """Delete jobs older than specified hours.

        Args:
            hours: Age threshold in hours

        Returns:
            Number of jobs deleted
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM jobs WHERE created_at < datetime('now', ?)",
                (f"-{hours} hours",)
            )
            count = cursor.rowcount

        if count > 0:
            logger.info(f"Cleaned up {count} old jobs")
        return count


# Singleton instance
_store: JobStore | None = None


def get_job_store() -> JobStore:
    """Dependency injection for FastAPI.

    Returns:
        Singleton JobStore instance
    """
    global _store
    if _store is None:
        _store = JobStore()
    return _store
