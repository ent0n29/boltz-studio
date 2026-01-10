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

        # Add discovery/tracking columns to designs table
        if "download_count" not in columns:
            conn.execute("ALTER TABLE designs ADD COLUMN download_count INTEGER DEFAULT 0")

        if "view_count" not in columns:
            conn.execute("ALTER TABLE designs ADD COLUMN view_count INTEGER DEFAULT 0")

        if "trending_score" not in columns:
            conn.execute("ALTER TABLE designs ADD COLUMN trending_score REAL DEFAULT 0.0")

        # Design events table (view/download tracking)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS design_events (
                id TEXT PRIMARY KEY,
                design_id TEXT NOT NULL,
                user_id TEXT,
                event_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_design_events_design
            ON design_events(design_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_design_events_type
            ON design_events(event_type)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_design_events_created
            ON design_events(created_at)
        """)

        # User stats table (precomputed for leaderboard)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                user_id TEXT PRIMARY KEY,
                total_stars_received INTEGER DEFAULT 0,
                total_forks_received INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                total_designs INTEGER DEFAULT 0,
                reputation_score REAL DEFAULT 0.0,
                rank INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

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

        # Notifications table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                type TEXT NOT NULL,
                actor_id TEXT,
                target_type TEXT,
                target_id TEXT,
                message TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_user
            ON notifications(user_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_unread
            ON notifications(user_id, is_read)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_created
            ON notifications(created_at)
        """)

        # Notification preferences table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id TEXT PRIMARY KEY,
                notify_on_star INTEGER DEFAULT 1,
                notify_on_fork INTEGER DEFAULT 1,
                notify_on_comment INTEGER DEFAULT 1,
                notify_on_follow INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Organizations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT,
                avatar_url TEXT,
                website TEXT,
                is_verified INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_organizations_slug
            ON organizations(slug)
        """)

        # Organization members table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS org_members (
                id TEXT PRIMARY KEY,
                org_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(org_id, user_id),
                FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_org_members_org
            ON org_members(org_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_org_members_user
            ON org_members(user_id)
        """)

        # Add org_id column to designs table if not exists
        if "org_id" not in columns:
            conn.execute("ALTER TABLE designs ADD COLUMN org_id TEXT")

        # Add reputation_score to users table if not exists
        if "reputation_score" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN reputation_score INTEGER DEFAULT 0"
            )

        # Badge definitions table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS badge_definitions (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                icon TEXT,
                category TEXT NOT NULL,
                tier TEXT,
                criteria_type TEXT NOT NULL,
                criteria_field TEXT,
                criteria_value INTEGER,
                points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_badge_definitions_slug
            ON badge_definitions(slug)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_badge_definitions_category
            ON badge_definitions(category)
        """)

        # User badges table (earned badges)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_badges (
                user_id TEXT NOT NULL,
                badge_id TEXT NOT NULL,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(user_id, badge_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (badge_id) REFERENCES badge_definitions(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_badges_user
            ON user_badges(user_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_badges_badge
            ON user_badges(badge_id)
        """)

        # Initialize default badges if table is empty
        badge_count = conn.execute(
            "SELECT COUNT(*) FROM badge_definitions"
        ).fetchone()[0]

        if badge_count == 0:
            # Insert default badge definitions
            default_badges = [
                # Contribution badges
                ("first-design", "First Design", "Published your first design",
                 "🎨", "contribution", "bronze", "count", "designs", 1, 10),
                ("prolific-5", "Rising Designer", "Published 5 designs",
                 "✨", "contribution", "silver", "count", "designs", 5, 25),
                ("prolific-10", "Prolific Designer", "Published 10 designs",
                 "🌟", "contribution", "gold", "count", "designs", 10, 50),
                ("prolific-50", "Master Designer", "Published 50 designs",
                 "💎", "contribution", "platinum", "count", "designs", 50, 100),
                # Social badges - stars received
                ("first-star", "Rising Star", "Received your first star",
                 "⭐", "social", "bronze", "count", "stars_received", 1, 5),
                ("popular-10", "Getting Popular", "Received 10 stars",
                 "🌟", "social", "silver", "count", "stars_received", 10, 20),
                ("popular-100", "Popular", "Received 100 stars",
                 "✨", "social", "gold", "count", "stars_received", 100, 50),
                ("popular-1000", "Superstar", "Received 1000 stars",
                 "💫", "social", "platinum", "count", "stars_received", 1000, 100),
                # Social badges - forks
                ("first-fork", "Influential", "One of your designs was forked",
                 "🔱", "social", "bronze", "count", "forks_received", 1, 10),
                ("forked-10", "Trendsetter", "Your designs were forked 10 times",
                 "🔥", "social", "silver", "count", "forks_received", 10, 30),
                ("forked-50", "Innovator", "Your designs were forked 50 times",
                 "🚀", "social", "gold", "count", "forks_received", 50, 75),
                # Engagement badges
                ("first-comment", "Conversationalist", "Left your first comment",
                 "💬", "engagement", "bronze", "count", "comments_made", 1, 5),
                ("commenter-10", "Active Reviewer", "Left 10 comments",
                 "📝", "engagement", "silver", "count", "comments_made", 10, 15),
                ("commenter-50", "Community Voice", "Left 50 comments",
                 "🗣️", "engagement", "gold", "count", "comments_made", 50, 40),
                # Follower badges
                ("first-follower", "Making Connections", "Got your first follower",
                 "👋", "social", "bronze", "count", "followers", 1, 5),
                ("followers-10", "Rising Influence", "Got 10 followers",
                 "📈", "social", "silver", "count", "followers", 10, 20),
                ("followers-100", "Thought Leader", "Got 100 followers",
                 "🎯", "social", "gold", "count", "followers", 100, 50),
                # Verification badges
                ("orcid-verified", "ORCID Verified", "Linked your ORCID account",
                 "✅", "verification", None, "orcid", None, None, 50),
                ("org-member", "Team Player", "Joined an organization",
                 "🏢", "verification", None, "org_member", None, None, 20),
            ]

            for badge in default_badges:
                conn.execute(
                    """
                    INSERT INTO badge_definitions
                    (id, slug, name, description, icon, category, tier,
                     criteria_type, criteria_field, criteria_value, points)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (badge[0], badge[0], badge[1], badge[2], badge[3], badge[4],
                     badge[5], badge[6], badge[7], badge[8], badge[9]),
                )

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
