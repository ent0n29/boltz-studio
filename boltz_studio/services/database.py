"""SQLite database management.

This module has been refactored into the database/ package.
All imports are re-exported from there for backward compatibility.
"""

# Re-export everything from the database package
from .database import get_connection, get_db_path, init_db, DB_PATH

__all__ = ["get_connection", "get_db_path", "init_db", "DB_PATH"]
