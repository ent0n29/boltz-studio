"""Organizations schema: organizations, org_members."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    """Create organization tables."""
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
