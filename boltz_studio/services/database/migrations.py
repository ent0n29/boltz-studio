"""Database migrations for adding columns to existing tables."""

import sqlite3


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run all ALTER TABLE migrations."""
    _migrate_designs_table(conn)
    _migrate_users_table(conn)


def _migrate_designs_table(conn: sqlite3.Connection) -> None:
    """Add columns to designs table if they don't exist."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(designs)")}

    # Social columns
    if "star_count" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN star_count INTEGER DEFAULT 0")

    if "fork_count" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN fork_count INTEGER DEFAULT 0")

    if "comment_count" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN comment_count INTEGER DEFAULT 0")

    if "parent_design_id" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN parent_design_id TEXT")

    if "preview_image" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN preview_image TEXT")

    # Discovery/tracking columns
    if "download_count" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN download_count INTEGER DEFAULT 0")

    if "view_count" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN view_count INTEGER DEFAULT 0")

    if "trending_score" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN trending_score REAL DEFAULT 0.0")

    # Organization column
    if "org_id" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN org_id TEXT")

    # Validation column
    if "validation_count" not in columns:
        conn.execute("ALTER TABLE designs ADD COLUMN validation_count INTEGER DEFAULT 0")


def _migrate_users_table(conn: sqlite3.Connection) -> None:
    """Add columns to users table if they don't exist."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}

    # Profile columns
    if "bio" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN bio TEXT")

    if "affiliation" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN affiliation TEXT")

    if "website" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN website TEXT")

    if "orcid" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN orcid TEXT")

    if "location" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN location TEXT")

    if "is_verified" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")

    # Social stats columns
    if "follower_count" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN follower_count INTEGER DEFAULT 0")

    if "following_count" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN following_count INTEGER DEFAULT 0")

    if "design_count" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN design_count INTEGER DEFAULT 0")

    # Reputation column
    if "reputation_score" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN reputation_score INTEGER DEFAULT 0"
        )
