"""Transaction utilities for multi-operation database consistency.

This module provides a context manager for executing multiple database
operations atomically. Use it when you need to ensure multiple operations
succeed or fail together.

Example usage:
    from .transactions import atomic

    def fork_design(self, parent_id: str, user_id: str, data: ForkRequest) -> str:
        with atomic() as conn:
            # All operations use same connection/transaction
            design_id = self._create_design(conn, ...)
            self._record_fork(conn, parent_id, design_id)
            self._increment_fork_count(conn, parent_id)
            return design_id
        # Commits on success, rolls back on exception
"""

import sqlite3
from contextlib import contextmanager
from typing import Generator

from .database import DB_PATH

from ..logger import get_logger

logger = get_logger("transactions")


@contextmanager
def atomic() -> Generator[sqlite3.Connection, None, None]:
    """Execute multiple operations in a single atomic transaction.

    All database operations within the with block share the same connection
    and are committed together. If any operation fails, all changes are
    rolled back.

    Yields:
        SQLite connection with Row factory enabled

    Example:
        with atomic() as conn:
            conn.execute("INSERT INTO table1 ...")
            conn.execute("INSERT INTO table2 ...")
            # Both inserts commit together or neither does
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
        logger.debug("Transaction committed successfully")
    except Exception as e:
        conn.rollback()
        logger.warning(f"Transaction rolled back due to: {e}")
        raise
    finally:
        conn.close()


@contextmanager
def savepoint(conn: sqlite3.Connection, name: str = "sp") -> Generator[None, None, None]:
    """Create a savepoint within an existing transaction.

    Use this for partial rollbacks - if operations within the savepoint
    fail, only those operations are rolled back, not the entire transaction.

    Args:
        conn: Active database connection
        name: Savepoint name (must be unique within transaction)

    Example:
        with atomic() as conn:
            conn.execute("INSERT INTO table1 ...")  # This will commit

            try:
                with savepoint(conn, "optional_step"):
                    conn.execute("INSERT INTO table2 ...")  # May be rolled back
            except SomeError:
                pass  # table2 insert rolled back, table1 still pending

            # Transaction continues
    """
    conn.execute(f"SAVEPOINT {name}")
    try:
        yield
        conn.execute(f"RELEASE SAVEPOINT {name}")
    except Exception:
        conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
        raise
