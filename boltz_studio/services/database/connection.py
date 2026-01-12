"""SQLite connection management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from ...config import settings
from ...logger import get_logger

logger = get_logger("database")

# Database path - use config setting
DB_PATH = Path(settings.db_path)


def get_db_path() -> Path:
    """Get the database file path.

    Returns:
        Path to SQLite database file
    """
    return DB_PATH


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
