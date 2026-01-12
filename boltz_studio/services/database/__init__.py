"""SQLite database management - modular schema organization.

This package provides database connection management and schema initialization
organized into logical modules:
- connection.py: Connection management
- schema_core.py: jobs, users, sessions, designs
- schema_social.py: stars, forks, comments, collections
- schema_discovery.py: events, user_stats, follows
- schema_orgs.py: organizations, org_members
- schema_reputation.py: badges, validations, api_keys
- migrations.py: ALTER TABLE statements
"""

from ...logger import get_logger
from .connection import DB_PATH, get_connection, get_db_path
from . import schema_core, schema_social, schema_discovery, schema_orgs, schema_reputation
from .migrations import run_migrations

logger = get_logger("database")

# Re-export main functions for backward compatibility
__all__ = ["get_connection", "get_db_path", "init_db", "DB_PATH"]


def init_db() -> None:
    """Initialize database schema.

    Creates all tables if they don't exist.
    """
    with get_connection() as conn:
        # Create tables in order (respecting foreign key dependencies)
        schema_core.create_tables(conn)
        schema_social.create_tables(conn)
        schema_discovery.create_tables(conn)
        schema_orgs.create_tables(conn)
        schema_reputation.create_tables(conn)

        # Run migrations for existing tables
        run_migrations(conn)

        # Seed default data
        schema_reputation.seed_default_badges(conn)

    logger.info(f"Database initialized: {DB_PATH}")
