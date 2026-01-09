"""In-memory job storage."""

from typing import Any


class JobStore:
    """Thread-safe job storage. Interface ready for Redis/DB later."""

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}

    def create(self, job_id: str) -> dict:
        """Create a new job."""
        job = {
            "status": "queued",
            "progress": 0.0,
            "result": None,
            "error": None,
        }
        self._jobs[job_id] = job
        return job

    def get(self, job_id: str) -> dict | None:
        """Get job by ID."""
        return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs) -> None:
        """Update job fields."""
        if job_id in self._jobs:
            self._jobs[job_id].update(kwargs)

    def exists(self, job_id: str) -> bool:
        """Check if job exists."""
        return job_id in self._jobs


# Singleton instance
_store = JobStore()


def get_job_store() -> JobStore:
    """Dependency injection for FastAPI."""
    return _store
