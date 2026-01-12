"""Social schema: stars, forks, comments, collections, notifications."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    """Create social feature tables."""
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

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_stars_created ON stars(created_at)
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

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_forks_created ON forks(created_at)
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

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_created ON comments(created_at)
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
