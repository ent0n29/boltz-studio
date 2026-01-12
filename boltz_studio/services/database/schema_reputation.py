"""Reputation schema: badges, validations, api_keys."""

import sqlite3


def create_tables(conn: sqlite3.Connection) -> None:
    """Create reputation and API tables."""
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

    # Lab validations table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lab_validations (
            id TEXT PRIMARY KEY,
            design_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            validation_type TEXT NOT NULL,
            result TEXT NOT NULL,
            method TEXT,
            notes TEXT,
            evidence_url TEXT,
            is_verified INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (design_id) REFERENCES designs(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lab_validations_design
        ON lab_validations(design_id)
    """)

    # API keys table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            key_prefix TEXT NOT NULL,
            scopes TEXT DEFAULT 'read',
            last_used_at TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_keys_user
        ON api_keys(user_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash
        ON api_keys(key_hash)
    """)


def seed_default_badges(conn: sqlite3.Connection) -> None:
    """Initialize default badge definitions if table is empty."""
    badge_count = conn.execute(
        "SELECT COUNT(*) FROM badge_definitions"
    ).fetchone()[0]

    if badge_count == 0:
        default_badges = [
            # Contribution badges
            ("first-design", "First Design", "Published your first design",
             "A", "contribution", "bronze", "count", "designs", 1, 10),
            ("prolific-5", "Rising Designer", "Published 5 designs",
             "B", "contribution", "silver", "count", "designs", 5, 25),
            ("prolific-10", "Prolific Designer", "Published 10 designs",
             "C", "contribution", "gold", "count", "designs", 10, 50),
            ("prolific-50", "Master Designer", "Published 50 designs",
             "D", "contribution", "platinum", "count", "designs", 50, 100),
            # Social badges - stars received
            ("first-star", "Rising Star", "Received your first star",
             "E", "social", "bronze", "count", "stars_received", 1, 5),
            ("popular-10", "Getting Popular", "Received 10 stars",
             "F", "social", "silver", "count", "stars_received", 10, 20),
            ("popular-100", "Popular", "Received 100 stars",
             "G", "social", "gold", "count", "stars_received", 100, 50),
            ("popular-1000", "Superstar", "Received 1000 stars",
             "H", "social", "platinum", "count", "stars_received", 1000, 100),
            # Social badges - forks
            ("first-fork", "Influential", "One of your designs was forked",
             "I", "social", "bronze", "count", "forks_received", 1, 10),
            ("forked-10", "Trendsetter", "Your designs were forked 10 times",
             "J", "social", "silver", "count", "forks_received", 10, 30),
            ("forked-50", "Innovator", "Your designs were forked 50 times",
             "K", "social", "gold", "count", "forks_received", 50, 75),
            # Engagement badges
            ("first-comment", "Conversationalist", "Left your first comment",
             "L", "engagement", "bronze", "count", "comments_made", 1, 5),
            ("commenter-10", "Active Reviewer", "Left 10 comments",
             "M", "engagement", "silver", "count", "comments_made", 10, 15),
            ("commenter-50", "Community Voice", "Left 50 comments",
             "N", "engagement", "gold", "count", "comments_made", 50, 40),
            # Follower badges
            ("first-follower", "Making Connections", "Got your first follower",
             "O", "social", "bronze", "count", "followers", 1, 5),
            ("followers-10", "Rising Influence", "Got 10 followers",
             "P", "social", "silver", "count", "followers", 10, 20),
            ("followers-100", "Thought Leader", "Got 100 followers",
             "Q", "social", "gold", "count", "followers", 100, 50),
            # Verification badges
            ("orcid-verified", "ORCID Verified", "Linked your ORCID account",
             "R", "verification", None, "orcid", None, None, 50),
            ("org-member", "Team Player", "Joined an organization",
             "S", "verification", None, "org_member", None, None, 20),
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
