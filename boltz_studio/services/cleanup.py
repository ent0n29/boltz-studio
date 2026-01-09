"""Background cleanup service for temporary job directories."""

import asyncio
import shutil
import tempfile
import time
from pathlib import Path

from ..config import settings
from ..logger import get_logger
from .job_store import get_job_store

logger = get_logger("cleanup")


async def cleanup_old_jobs(max_age_hours: int | None = None) -> tuple[int, int]:
    """Remove old jobs from database and temp directories.

    Args:
        max_age_hours: Maximum age in hours before cleanup (uses settings if None)

    Returns:
        Tuple of (directories cleaned, database jobs cleaned)
    """
    if max_age_hours is None:
        max_age_hours = settings.job_retention_hours

    max_age_seconds = max_age_hours * 3600
    temp_dir = Path(tempfile.gettempdir())
    dirs_cleaned = 0
    now = time.time()

    # Clean up temp directories
    for path in temp_dir.glob("boltz_*"):
        if not path.is_dir():
            continue

        try:
            mtime = path.stat().st_mtime
            age_seconds = now - mtime

            if age_seconds > max_age_seconds:
                shutil.rmtree(path)
                dirs_cleaned += 1
                logger.debug(f"Cleaned up old job directory: {path.name}")
        except OSError as e:
            logger.warning(f"Failed to clean up {path}: {e}")

    # Clean up old jobs from database
    store = get_job_store()
    jobs_cleaned = store.cleanup_old_jobs(max_age_hours)

    if dirs_cleaned > 0 or jobs_cleaned > 0:
        logger.info(
            f"Cleanup complete: {dirs_cleaned} directories, {jobs_cleaned} database jobs"
        )

    return dirs_cleaned, jobs_cleaned


async def start_cleanup_task() -> None:
    """Run cleanup periodically in the background.

    This task runs indefinitely, cleaning up old job directories
    at the configured interval.
    """
    interval_seconds = settings.cleanup_interval_hours * 3600
    logger.info(
        f"Starting cleanup task (interval: {settings.cleanup_interval_hours}h, "
        f"retention: {settings.job_retention_hours}h)"
    )

    while True:
        try:
            await cleanup_old_jobs()
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")

        await asyncio.sleep(interval_seconds)
