"""Core schema: jobs, users, sessions, designs, design_tags."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    """Create core tables."""
    # Jobs table
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

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)
    """)

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

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_design_tags_design_id
        ON design_tags(design_id)
    """)

    # Full-text search virtual table for designs
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
