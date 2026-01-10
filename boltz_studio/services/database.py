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

    Creates all tables if they don't exist.
    """
    with get_connection() as conn:
        # Jobs table (existing)
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

        # Users table (OAuth users)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                provider_user_id TEXT NOT NULL,
                email TEXT,
                display_name TEXT NOT NULL,
                avatar_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(provider, provider_user_id)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_provider
            ON users(provider, provider_user_id)
        """)

        # Sessions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)
        """)

        # Published designs table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS designs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                sequence TEXT NOT NULL,
                smiles TEXT,
                structure_pdb TEXT NOT NULL,
                preview_image TEXT,
                confidence_score REAL,
                complex_plddt REAL,
                ptm REAL,
                affinity_probability REAL,
                affinity_raw REAL,
                plddt_json TEXT,
                is_public INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_designs_user ON designs(user_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_designs_public ON designs(is_public)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_designs_confidence
            ON designs(confidence_score)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_designs_affinity
            ON designs(affinity_probability)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_designs_created
            ON designs(created_at)
        """)

        # Design tags table (many-to-many)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS design_tags (
                design_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                tag_type TEXT NOT NULL,
                PRIMARY KEY (design_id, tag, tag_type),
                FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_design_tags_tag
            ON design_tags(tag, tag_type)
        """)

        # Add social columns to designs table if not exists
        # Check existing columns
        columns = {row[1] for row in conn.execute("PRAGMA table_info(designs)")}

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

        # Add profile columns to users table if not exists
        user_columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}

        if "bio" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN bio TEXT")

        if "affiliation" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN affiliation TEXT")

        if "website" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN website TEXT")

        if "orcid" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN orcid TEXT")

        if "location" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN location TEXT")

        if "is_verified" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")

        if "follower_count" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN follower_count INTEGER DEFAULT 0")

        if "following_count" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN following_count INTEGER DEFAULT 0")

        if "design_count" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN design_count INTEGER DEFAULT 0")

        # Follows table (user social graph)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS follows (
                id TEXT PRIMARY KEY,
                follower_id TEXT NOT NULL,
                following_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(follower_id, following_id),
                FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_follows_follower ON follows(follower_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_follows_following ON follows(following_id)
        """)

        # Stars table (bookmarks)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stars (
                id TEXT PRIMARY KEY,
                design_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(design_id, user_id),
                FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_stars_design ON stars(design_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_stars_user ON stars(user_id)
        """)

        # Forks table (design lineage)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS forks (
                id TEXT PRIMARY KEY,
                parent_design_id TEXT NOT NULL,
                fork_design_id TEXT NOT NULL UNIQUE,
                user_id TEXT NOT NULL,
                attribution_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_design_id) REFERENCES designs(id) ON DELETE CASCADE,
                FOREIGN KEY (fork_design_id) REFERENCES designs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_forks_parent ON forks(parent_design_id)
        """)

        # Comments table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id TEXT PRIMARY KEY,
                design_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                lab_validated INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_comments_design ON comments(design_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(user_id)
        """)

        # Collections table (curated lists)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collections (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                is_public INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_collections_user ON collections(user_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_collections_public ON collections(is_public)
        """)

        # Collection items (many-to-many)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS collection_items (
                collection_id TEXT NOT NULL,
                design_id TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (collection_id, design_id),
                FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
                FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_collection_items_collection
            ON collection_items(collection_id)
        """)

        # Full-text search virtual table for designs
        # Check if FTS table exists before creating
        fts_exists = conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='designs_fts'
        """).fetchone()

        if not fts_exists:
            conn.execute("""
                CREATE VIRTUAL TABLE designs_fts USING fts5(
                    design_id,
                    name,
                    description,
                    tags,
                    content='designs',
                    content_rowid='rowid'
                )
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
