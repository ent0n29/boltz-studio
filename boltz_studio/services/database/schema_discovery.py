"""Discovery schema: events, user_stats, follows, activities."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    """Create discovery and tracking tables."""
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

    # Activity feed table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activities_user
        ON activities(user_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activities_created
        ON activities(created_at)
    """)
