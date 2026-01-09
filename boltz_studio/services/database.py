"""SQLite database management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from ..config import settings
from ..logger import get_logger

logger = get_logger("database")

# Database path - use config setting
DB_PATH = Path(settings.db_path)


def get_db_path() -> Path:
    """Get the database file path.

    Returns:
        Path to SQLite database file
    """
    return DB_PATH


def init_db() -> None:
    """Initialize database schema.

    Creates the jobs table if it doesn't exist.
    """
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'queued',
                progress REAL DEFAULT 0.0,
                result TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index on status for faster queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
        """)

        # Create index on created_at for cleanup queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at)
        """)

    logger.info(f"Database initialized: {DB_PATH}")


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection with automatic cleanup.

    Yields:
        SQLite connection with Row factory enabled
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
