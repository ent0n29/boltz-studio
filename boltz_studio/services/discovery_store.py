"""Discovery store for trending, leaderboards, and recommendations."""

import uuid
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Literal

from ..logger import get_logger
from ..models.discovery import (
    DesignStats,
    Leaderboard,
    LeaderboardEntry,
    SimilarDesign,
    TrendingDesign,
    TrendingList,
    UserStats,
)
from ..models.user import UserPublic
from .cache import leaderboard_cache, trending_cache
from .database import get_connection
from .utils import build_design_summary, parse_tags_from_group_concat

logger = get_logger("discovery_store")

# Time decay factor for trending score
DECAY_HALF_LIFE_DAYS = 3


class DiscoveryStore:
    """Store for discovery features."""

    def record_event(
        self,
        design_id: str,
        event_type: Literal["view", "download"],
        user_id: str | None = None,
    ) -> bool:
        """Record a view or download event.

        Args:
            design_id: Design being viewed/downloaded
            event_type: Type of event
            user_id: Optional user who triggered the event

        Returns:
            True if recorded successfully
        """
        event_id = str(uuid.uuid4())

        with get_connection() as conn:
            # Insert event
            conn.execute(
                """
                INSERT INTO design_events (id, design_id, user_id, event_type)
                VALUES (?, ?, ?, ?)
                """,
                (event_id, design_id, user_id, event_type),
            )

            # Update design counter
            if event_type == "view":
                conn.execute(
                    "UPDATE designs SET view_count = view_count + 1 WHERE id = ?",
                    (design_id,),
                )
            elif event_type == "download":
                conn.execute(
                    "UPDATE designs SET download_count = download_count + 1 WHERE id = ?",
                    (design_id,),
                )

        logger.debug(f"Recorded {event_type} event for design {design_id}")
        return True

    def get_design_stats(self, design_id: str) -> DesignStats | None:
        """Get statistics for a design.

        Args:
            design_id: Design ID

        Returns:
            Design statistics or None if not found
        """
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, star_count, fork_count, comment_count,
                       download_count, view_count, trending_score
                FROM designs
                WHERE id = ?
                """,
                (design_id,),
            ).fetchone()

            if not row:
                return None

            return DesignStats(
                design_id=row["id"],
                star_count=row["star_count"] or 0,
                fork_count=row["fork_count"] or 0,
                comment_count=row["comment_count"] or 0,
                download_count=row["download_count"] or 0,
                view_count=row["view_count"] or 0,
                trending_score=row["trending_score"] or 0.0,
            )

    def compute_trending_scores(self, time_window_days: int = 7) -> int:
        """Compute trending scores for all designs.

        Uses a weighted score with time decay:
        score = (stars*3 + downloads*1 + forks*5 + comments*2) * age_decay

        Args:
            time_window_days: Days to look back for activity

        Returns:
            Number of designs updated
        """
        cutoff = datetime.utcnow() - timedelta(days=time_window_days)

        with get_connection() as conn:
            # Get recent activity counts per design
            activity = conn.execute(
                """
                WITH recent_stars AS (
                    SELECT design_id, COUNT(*) as cnt
                    FROM stars
                    WHERE created_at >= ?
                    GROUP BY design_id
                ),
                recent_forks AS (
                    SELECT parent_design_id as design_id, COUNT(*) as cnt
                    FROM forks
                    WHERE created_at >= ?
                    GROUP BY parent_design_id
                ),
                recent_comments AS (
                    SELECT design_id, COUNT(*) as cnt
                    FROM comments
                    WHERE created_at >= ?
                    GROUP BY design_id
                ),
                recent_downloads AS (
                    SELECT design_id, COUNT(*) as cnt
                    FROM design_events
                    WHERE event_type = 'download' AND created_at >= ?
                    GROUP BY design_id
                )
                SELECT
                    d.id,
                    d.created_at,
                    COALESCE(rs.cnt, 0) as recent_stars,
                    COALESCE(rf.cnt, 0) as recent_forks,
                    COALESCE(rc.cnt, 0) as recent_comments,
                    COALESCE(rd.cnt, 0) as recent_downloads
                FROM designs d
                LEFT JOIN recent_stars rs ON d.id = rs.design_id
                LEFT JOIN recent_forks rf ON d.id = rf.design_id
                LEFT JOIN recent_comments rc ON d.id = rc.design_id
                LEFT JOIN recent_downloads rd ON d.id = rd.design_id
                WHERE d.is_public = 1
                """,
                (cutoff, cutoff, cutoff, cutoff),
            ).fetchall()

            now = datetime.utcnow()
            updated = 0

            for row in activity:
                # Calculate raw score
                raw_score = (
                    row["recent_stars"] * 3.0
                    + row["recent_forks"] * 5.0
                    + row["recent_comments"] * 2.0
                    + row["recent_downloads"] * 1.0
                )

                # Apply time decay based on design age
                created_at = datetime.fromisoformat(row["created_at"].replace("Z", ""))
                age_days = (now - created_at).days
                decay = 0.5 ** (age_days / DECAY_HALF_LIFE_DAYS)
                score = raw_score * decay

                # Update score
                conn.execute(
                    "UPDATE designs SET trending_score = ? WHERE id = ?",
                    (score, row["id"]),
                )
                updated += 1

        logger.info(f"Updated trending scores for {updated} designs")

        # Invalidate trending cache after recomputation
        trending_cache.invalidate_prefix("trending:")

        return updated

    def get_trending(
        self,
        time_window: Literal["day", "week", "month"] = "week",
        offset: int = 0,
        limit: int = 20,
    ) -> TrendingList:
        """Get trending designs.

        Args:
            time_window: Time window for trending
            offset: Pagination offset
            limit: Max results

        Returns:
            List of trending designs
        """
        # Use cache for first page of each time window
        cache_key = f"trending:{time_window}:{offset}:{limit}"
        if offset == 0 and limit == 20:
            cached = trending_cache.get(cache_key)
            if cached is not None:
                return cached

        window_days = {"day": 1, "week": 7, "month": 30}.get(time_window, 7)
        cutoff = datetime.utcnow() - timedelta(days=window_days)

        with get_connection() as conn:
            # Get designs with recent activity and tags in a single query
            rows = conn.execute(
                """
                WITH recent_activity AS (
                    SELECT design_id, COUNT(*) as recent_stars
                    FROM stars
                    WHERE created_at >= ?
                    GROUP BY design_id
                ),
                recent_downloads AS (
                    SELECT design_id, COUNT(*) as cnt
                    FROM design_events
                    WHERE event_type = 'download' AND created_at >= ?
                    GROUP BY design_id
                ),
                recent_forks AS (
                    SELECT parent_design_id as design_id, COUNT(*) as cnt
                    FROM forks
                    WHERE created_at >= ?
                    GROUP BY parent_design_id
                )
                SELECT
                    d.id, d.name, d.description, d.sequence, d.smiles,
                    d.confidence_score, d.complex_plddt, d.affinity_probability,
                    d.preview_image, d.parent_design_id,
                    d.star_count, d.fork_count, d.comment_count,
                    d.trending_score, d.created_at,
                    u.id as user_id, u.display_name, u.avatar_url, u.created_at as user_created_at,
                    COALESCE(ra.recent_stars, 0) as recent_stars,
                    COALESCE(rd.cnt, 0) as recent_downloads,
                    COALESCE(rf.cnt, 0) as recent_forks,
                    GROUP_CONCAT(dt.tag || '|' || dt.tag_type) as tags_concat
                FROM designs d
                JOIN users u ON d.user_id = u.id
                LEFT JOIN recent_activity ra ON d.id = ra.design_id
                LEFT JOIN recent_downloads rd ON d.id = rd.design_id
                LEFT JOIN recent_forks rf ON d.id = rf.design_id
                LEFT JOIN design_tags dt ON d.id = dt.design_id
                WHERE d.is_public = 1
                GROUP BY d.id
                ORDER BY d.trending_score DESC, d.star_count DESC
                LIMIT ? OFFSET ?
                """,
                (cutoff, cutoff, cutoff, limit + 1, offset),
            ).fetchall()

            has_more = len(rows) > limit
            rows = rows[:limit]

            # Get total count
            total = conn.execute(
                "SELECT COUNT(*) FROM designs WHERE is_public = 1"
            ).fetchone()[0]

            # Build trending list using shared utility
            designs = []
            for i, row in enumerate(rows):
                summary = build_design_summary(dict(row))

                trending = TrendingDesign(
                    design=summary,
                    trending_score=row["trending_score"] or 0.0,
                    trending_rank=offset + i + 1,
                    recent_stars=row["recent_stars"],
                    recent_downloads=row["recent_downloads"],
                    recent_forks=row["recent_forks"],
                )
                designs.append(trending)

            result = TrendingList(
                designs=designs,
                total=total,
                has_more=has_more,
                time_window=time_window,
            )

            # Cache first page results
            if offset == 0 and limit == 20:
                trending_cache.set(cache_key, result)

            return result

    def compute_user_stats(self) -> int:
        """Compute and cache user statistics for leaderboard.

        Returns:
            Number of users updated
        """
        with get_connection() as conn:
            # Calculate stats for all users with designs
            stats = conn.execute(
                """
                SELECT
                    u.id as user_id,
                    COALESCE(SUM(d.star_count), 0) as total_stars,
                    COALESCE(SUM(d.fork_count), 0) as total_forks,
                    COALESCE(SUM(d.download_count), 0) as total_downloads,
                    COUNT(d.id) as total_designs
                FROM users u
                LEFT JOIN designs d ON u.id = d.user_id AND d.is_public = 1
                GROUP BY u.id
                """,
            ).fetchall()

            updated = 0
            for row in stats:
                # Calculate reputation score
                reputation = (
                    row["total_stars"] * 5
                    + row["total_forks"] * 10
                    + row["total_downloads"] * 1
                    + row["total_designs"] * 10
                )

                # Upsert user stats
                conn.execute(
                    """
                    INSERT INTO user_stats
                        (user_id, total_stars_received, total_forks_received,
                         total_downloads, total_designs, reputation_score, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        total_stars_received = excluded.total_stars_received,
                        total_forks_received = excluded.total_forks_received,
                        total_downloads = excluded.total_downloads,
                        total_designs = excluded.total_designs,
                        reputation_score = excluded.reputation_score,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        row["user_id"],
                        row["total_stars"],
                        row["total_forks"],
                        row["total_downloads"],
                        row["total_designs"],
                        reputation,
                    ),
                )
                updated += 1

            # Update ranks
            conn.execute(
                """
                UPDATE user_stats
                SET rank = (
                    SELECT COUNT(*) + 1
                    FROM user_stats us2
                    WHERE us2.reputation_score > user_stats.reputation_score
                )
                """
            )

        logger.info(f"Updated stats for {updated} users")

        # Invalidate leaderboard cache after recomputation
        leaderboard_cache.invalidate_prefix("leaderboard:")

        return updated

    def get_leaderboard(
        self,
        metric: Literal["reputation", "stars", "forks", "downloads"] = "reputation",
        offset: int = 0,
        limit: int = 20,
    ) -> Leaderboard:
        """Get user leaderboard.

        Args:
            metric: Sort metric
            offset: Pagination offset
            limit: Max results

        Returns:
            Leaderboard with entries
        """
        # Use cache for first page
        cache_key = f"leaderboard:{metric}:{offset}:{limit}"
        if offset == 0 and limit == 20:
            cached = leaderboard_cache.get(cache_key)
            if cached is not None:
                return cached

        order_col = {
            "reputation": "us.reputation_score",
            "stars": "us.total_stars_received",
            "forks": "us.total_forks_received",
            "downloads": "us.total_downloads",
        }.get(metric, "us.reputation_score")

        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    u.id, u.display_name, u.avatar_url,
                    us.total_stars_received, us.total_forks_received,
                    us.total_downloads, us.total_designs, us.reputation_score
                FROM user_stats us
                JOIN users u ON us.user_id = u.id
                WHERE us.total_designs > 0
                ORDER BY {order_col} DESC
                LIMIT ? OFFSET ?
                """,
                (limit + 1, offset),
            ).fetchall()

            has_more = len(rows) > limit
            rows = rows[:limit]

            # Get total
            total = conn.execute(
                "SELECT COUNT(*) FROM user_stats WHERE total_designs > 0"
            ).fetchone()[0]

            entries = []
            for i, row in enumerate(rows):
                user = UserPublic(
                    id=row["id"],
                    display_name=row["display_name"],
                    avatar_url=row["avatar_url"],
                )

                entry = LeaderboardEntry(
                    rank=offset + i + 1,
                    user=user,
                    total_stars=row["total_stars_received"] or 0,
                    total_forks=row["total_forks_received"] or 0,
                    total_downloads=row["total_downloads"] or 0,
                    total_designs=row["total_designs"] or 0,
                    reputation_score=row["reputation_score"] or 0.0,
                )
                entries.append(entry)

            result = Leaderboard(
                entries=entries,
                total=total,
                has_more=has_more,
                metric=metric,
            )

            # Cache first page results
            if offset == 0 and limit == 20:
                leaderboard_cache.set(cache_key, result)

            return result

    def get_user_stats(self, user_id: str) -> UserStats | None:
        """Get stats for a specific user.

        Args:
            user_id: User ID

        Returns:
            User statistics or None
        """
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM user_stats WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

            if not row:
                return None

            return UserStats(
                user_id=row["user_id"],
                total_stars_received=row["total_stars_received"] or 0,
                total_forks_received=row["total_forks_received"] or 0,
                total_downloads=row["total_downloads"] or 0,
                total_designs=row["total_designs"] or 0,
                reputation_score=row["reputation_score"] or 0.0,
                rank=row["rank"],
                updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "")) if row["updated_at"] else None,
            )

    def get_similar_designs(
        self,
        design_id: str,
        limit: int = 5,
    ) -> list[SimilarDesign]:
        """Get similar designs based on tags and author.

        Args:
            design_id: Source design
            limit: Max results

        Returns:
            List of similar designs with reasons
        """
        with get_connection() as conn:
            # Get source design info
            source = conn.execute(
                "SELECT user_id FROM designs WHERE id = ?",
                (design_id,),
            ).fetchone()

            if not source:
                return []

            # Get source tags
            source_tags = conn.execute(
                "SELECT tag FROM design_tags WHERE design_id = ?",
                (design_id,),
            ).fetchall()
            source_tag_set = {t["tag"] for t in source_tags}

            # Find designs with matching tags (excluding source) - single query with tags
            similar = []

            if source_tag_set:
                tag_matches = conn.execute(
                    """
                    SELECT
                        d.id, d.name, d.description, d.sequence, d.smiles,
                        d.confidence_score, d.complex_plddt, d.affinity_probability,
                        d.preview_image, d.parent_design_id,
                        d.star_count, d.fork_count, d.comment_count, d.created_at,
                        u.id as user_id, u.display_name, u.avatar_url, u.created_at as user_created_at,
                        COUNT(DISTINCT dt_match.tag) as matching_tags,
                        GROUP_CONCAT(DISTINCT dt_all.tag || '|' || dt_all.tag_type) as tags_concat
                    FROM designs d
                    JOIN users u ON d.user_id = u.id
                    JOIN design_tags dt_match ON d.id = dt_match.design_id
                    LEFT JOIN design_tags dt_all ON d.id = dt_all.design_id
                    WHERE d.id != ? AND d.is_public = 1
                      AND dt_match.tag IN ({})
                    GROUP BY d.id
                    ORDER BY matching_tags DESC, d.star_count DESC
                    LIMIT ?
                    """.format(",".join("?" * len(source_tag_set))),
                    (design_id, *source_tag_set, limit),
                ).fetchall()

                for row in tag_matches:
                    summary = build_design_summary(dict(row))

                    # Determine similarity reason
                    if row["user_id"] == source["user_id"]:
                        reason = "same_author"
                    else:
                        reason = "same_tags"

                    score = row["matching_tags"] / len(source_tag_set) if source_tag_set else 0

                    similar.append(SimilarDesign(
                        design=summary,
                        similarity_score=score,
                        similarity_reason=reason,
                    ))

            # If not enough matches, add from same author - single query with tags
            if len(similar) < limit:
                same_author = conn.execute(
                    """
                    SELECT
                        d.id, d.name, d.description, d.sequence, d.smiles,
                        d.confidence_score, d.complex_plddt, d.affinity_probability,
                        d.preview_image, d.parent_design_id,
                        d.star_count, d.fork_count, d.comment_count, d.created_at,
                        u.id as user_id, u.display_name, u.avatar_url, u.created_at as user_created_at,
                        GROUP_CONCAT(dt.tag || '|' || dt.tag_type) as tags_concat
                    FROM designs d
                    JOIN users u ON d.user_id = u.id
                    LEFT JOIN design_tags dt ON d.id = dt.design_id
                    WHERE d.user_id = ? AND d.id != ? AND d.is_public = 1
                    GROUP BY d.id
                    ORDER BY d.star_count DESC
                    LIMIT ?
                    """,
                    (source["user_id"], design_id, limit - len(similar)),
                ).fetchall()

                existing_ids = {s.design.id for s in similar}
                for row in same_author:
                    if row["id"] in existing_ids:
                        continue

                    summary = build_design_summary(dict(row))

                    similar.append(SimilarDesign(
                        design=summary,
                        similarity_score=0.5,
                        similarity_reason="same_author",
                    ))

            return similar[:limit]


@lru_cache()
def get_discovery_store() -> DiscoveryStore:
    """Get singleton discovery store instance."""
    return DiscoveryStore()
