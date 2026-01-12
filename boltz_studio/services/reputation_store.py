"""Reputation store for managing badges and reputation points."""

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache

from ..logger import get_logger
from ..models.reputation import (
    BadgeDefinition,
    BadgeList,
    BadgeProgress,
    BadgeProgressList,
    ReputationBreakdown,
    ReputationLeaderboard,
    ReputationLeaderboardEntry,
    UserBadge,
    UserBadgeList,
    UserReputation,
)
from .database import get_connection


@dataclass
class UserStatsData:
    """User statistics for badge evaluation."""

    designs: int = 0
    stars_received: int = 0
    forks_received: int = 0
    comments_made: int = 0
    followers: int = 0
    orcid: bool = False
    org_member: bool = False
    downloads: int = 0
    comments_received: int = 0

logger = get_logger("reputation_store")

# Reputation point values
POINTS_PER_DESIGN = 10
POINTS_PER_STAR_RECEIVED = 5
POINTS_PER_FORK_RECEIVED = 10
POINTS_PER_COMMENT_RECEIVED = 2
POINTS_PER_DOWNLOAD = 1


class ReputationStore:
    """Store for reputation and badge operations."""

    def get_all_badges(self) -> BadgeList:
        """Get all badge definitions.

        Returns:
            List of all badges
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM badge_definitions
                ORDER BY category, tier, criteria_value
                """
            ).fetchall()

            badges = [
                BadgeDefinition(
                    id=row["id"],
                    slug=row["slug"],
                    name=row["name"],
                    description=row["description"],
                    icon=row["icon"],
                    category=row["category"],
                    tier=row["tier"],
                    criteria_type=row["criteria_type"],
                    criteria_field=row["criteria_field"],
                    criteria_value=row["criteria_value"],
                    points=row["points"] or 0,
                )
                for row in rows
            ]

            return BadgeList(badges=badges, total=len(badges))

    def get_user_badges(self, user_id: str) -> UserBadgeList:
        """Get badges earned by a user.

        Args:
            user_id: User ID

        Returns:
            List of earned badges
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT bd.*, ub.earned_at
                FROM user_badges ub
                JOIN badge_definitions bd ON ub.badge_id = bd.id
                WHERE ub.user_id = ?
                ORDER BY ub.earned_at DESC
                """,
                (user_id,),
            ).fetchall()

            badges = [
                UserBadge(
                    badge=BadgeDefinition(
                        id=row["id"],
                        slug=row["slug"],
                        name=row["name"],
                        description=row["description"],
                        icon=row["icon"],
                        category=row["category"],
                        tier=row["tier"],
                        criteria_type=row["criteria_type"],
                        criteria_field=row["criteria_field"],
                        criteria_value=row["criteria_value"],
                        points=row["points"] or 0,
                    ),
                    earned_at=datetime.fromisoformat(
                        row["earned_at"].replace("Z", "")
                    ),
                )
                for row in rows
            ]

            return UserBadgeList(badges=badges, total=len(badges))

    def get_user_stats(self, user_id: str) -> dict:
        """Get user's stats for badge evaluation.

        Optimized to use a single query instead of 9 separate queries.

        Args:
            user_id: User ID

        Returns:
            Dictionary of stat values
        """
        with get_connection() as conn:
            # Single aggregated query for all user stats
            row = conn.execute(
                """
                SELECT
                    u.orcid,
                    -- Design stats (aggregated from designs table)
                    COALESCE(d_stats.design_count, 0) as designs,
                    COALESCE(d_stats.total_downloads, 0) as downloads,
                    -- Stars received (count of stars on user's designs)
                    COALESCE(star_stats.stars_received, 0) as stars_received,
                    -- Forks received (count of forks of user's designs)
                    COALESCE(fork_stats.forks_received, 0) as forks_received,
                    -- Comments received (on user's designs, excluding self)
                    COALESCE(comment_stats.comments_received, 0) as comments_received,
                    -- Comments made by user
                    COALESCE(comments_made.count, 0) as comments_made,
                    -- Followers
                    COALESCE(follower_stats.followers, 0) as followers,
                    -- Org membership
                    COALESCE(org_stats.org_count, 0) as org_count
                FROM users u
                -- Design aggregates
                LEFT JOIN (
                    SELECT user_id, COUNT(*) as design_count, COALESCE(SUM(download_count), 0) as total_downloads
                    FROM designs
                    WHERE user_id = ?
                    GROUP BY user_id
                ) d_stats ON u.id = d_stats.user_id
                -- Stars received
                LEFT JOIN (
                    SELECT d.user_id, COUNT(*) as stars_received
                    FROM stars s
                    JOIN designs d ON s.design_id = d.id
                    WHERE d.user_id = ?
                    GROUP BY d.user_id
                ) star_stats ON u.id = star_stats.user_id
                -- Forks received
                LEFT JOIN (
                    SELECT d.user_id, COUNT(*) as forks_received
                    FROM forks f
                    JOIN designs d ON f.parent_design_id = d.id
                    WHERE d.user_id = ?
                    GROUP BY d.user_id
                ) fork_stats ON u.id = fork_stats.user_id
                -- Comments received (excluding self-comments)
                LEFT JOIN (
                    SELECT d.user_id, COUNT(*) as comments_received
                    FROM comments c
                    JOIN designs d ON c.design_id = d.id
                    WHERE d.user_id = ? AND c.user_id != ?
                    GROUP BY d.user_id
                ) comment_stats ON u.id = comment_stats.user_id
                -- Comments made
                LEFT JOIN (
                    SELECT user_id, COUNT(*) as count
                    FROM comments
                    WHERE user_id = ?
                    GROUP BY user_id
                ) comments_made ON u.id = comments_made.user_id
                -- Followers
                LEFT JOIN (
                    SELECT following_id, COUNT(*) as followers
                    FROM follows
                    WHERE following_id = ?
                    GROUP BY following_id
                ) follower_stats ON u.id = follower_stats.following_id
                -- Org membership
                LEFT JOIN (
                    SELECT user_id, COUNT(*) as org_count
                    FROM org_members
                    WHERE user_id = ?
                    GROUP BY user_id
                ) org_stats ON u.id = org_stats.user_id
                WHERE u.id = ?
                """,
                (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id),
            ).fetchone()

            if not row:
                return UserStatsData().__dict__

            return {
                "designs": row["designs"],
                "stars_received": row["stars_received"],
                "forks_received": row["forks_received"],
                "comments_made": row["comments_made"],
                "followers": row["followers"],
                "orcid": bool(row["orcid"]),
                "org_member": row["org_count"] > 0,
                "downloads": row["downloads"],
                "comments_received": row["comments_received"],
            }

    def check_and_award_badges(self, user_id: str) -> list[BadgeDefinition]:
        """Check if user qualifies for any new badges and award them.

        Args:
            user_id: User ID

        Returns:
            List of newly awarded badges
        """
        stats = self.get_user_stats(user_id)
        earned_badges = self.get_user_badges(user_id)
        earned_ids = {b.badge.id for b in earned_badges.badges}

        all_badges = self.get_all_badges()
        newly_awarded = []

        with get_connection() as conn:
            for badge in all_badges.badges:
                if badge.id in earned_ids:
                    continue

                # Check if user qualifies
                qualifies = False

                if badge.criteria_type == "count" and badge.criteria_field:
                    current_value = stats.get(badge.criteria_field, 0)
                    if badge.criteria_value and current_value >= badge.criteria_value:
                        qualifies = True

                elif badge.criteria_type == "orcid":
                    if stats.get("orcid"):
                        qualifies = True

                elif badge.criteria_type == "org_member":
                    if stats.get("org_member"):
                        qualifies = True

                if qualifies:
                    # Award badge
                    conn.execute(
                        """
                        INSERT INTO user_badges (user_id, badge_id)
                        VALUES (?, ?)
                        """,
                        (user_id, badge.id),
                    )
                    newly_awarded.append(badge)
                    logger.info(f"Awarded badge {badge.slug} to user {user_id}")

        # Update reputation score after awarding badges
        if newly_awarded:
            self.compute_user_reputation(user_id)

        return newly_awarded

    def get_badge_progress(self, user_id: str) -> BadgeProgressList:
        """Get user's progress toward all badges.

        Args:
            user_id: User ID

        Returns:
            Progress list showing earned and in-progress badges
        """
        stats = self.get_user_stats(user_id)
        earned_badges = self.get_user_badges(user_id)
        earned_ids = {b.badge.id for b in earned_badges.badges}

        all_badges = self.get_all_badges()
        in_progress = []

        for badge in all_badges.badges:
            if badge.id in earned_ids:
                continue

            # Skip non-count badges that aren't earned
            if badge.criteria_type != "count":
                continue

            if badge.criteria_field and badge.criteria_value:
                current = stats.get(badge.criteria_field, 0)
                progress_pct = min(100.0, (current / badge.criteria_value) * 100)

                in_progress.append(
                    BadgeProgress(
                        badge=badge,
                        current_value=current,
                        target_value=badge.criteria_value,
                        progress_percent=progress_pct,
                        is_earned=False,
                    )
                )

        # Sort by progress (closest to earning first)
        in_progress.sort(key=lambda x: -x.progress_percent)

        return BadgeProgressList(
            in_progress=in_progress,
            earned=earned_badges.badges,
        )

    def compute_user_reputation(self, user_id: str) -> int:
        """Compute and update user's reputation score.

        Args:
            user_id: User ID

        Returns:
            Updated reputation score
        """
        stats = self.get_user_stats(user_id)
        badges = self.get_user_badges(user_id)

        # Calculate points from activity
        design_points = stats["designs"] * POINTS_PER_DESIGN
        star_points = stats["stars_received"] * POINTS_PER_STAR_RECEIVED
        fork_points = stats["forks_received"] * POINTS_PER_FORK_RECEIVED
        comment_points = stats["comments_received"] * POINTS_PER_COMMENT_RECEIVED
        download_points = stats["downloads"] * POINTS_PER_DOWNLOAD

        # Calculate badge points
        badge_points = sum(b.badge.points for b in badges.badges)

        total = (
            design_points
            + star_points
            + fork_points
            + comment_points
            + download_points
            + badge_points
        )

        # Update user's reputation score
        with get_connection() as conn:
            conn.execute(
                "UPDATE users SET reputation_score = ? WHERE id = ?",
                (total, user_id),
            )

        return total

    def get_user_reputation(self, user_id: str) -> UserReputation:
        """Get user's full reputation summary.

        Args:
            user_id: User ID

        Returns:
            Reputation summary
        """
        badges = self.get_user_badges(user_id)

        with get_connection() as conn:
            user = conn.execute(
                "SELECT reputation_score FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

            score = user["reputation_score"] if user else 0

            # Calculate rank
            rank_row = conn.execute(
                """
                SELECT COUNT(*) + 1 as rank
                FROM users
                WHERE reputation_score > ?
                """,
                (score,),
            ).fetchone()
            rank = rank_row["rank"] if rank_row else None

        return UserReputation(
            user_id=user_id,
            reputation_score=score,
            rank=rank,
            total_badges=badges.total,
            badges=badges.badges[:5],  # Top 5 recent badges
        )

    def get_reputation_breakdown(self, user_id: str) -> ReputationBreakdown:
        """Get detailed breakdown of reputation points.

        Args:
            user_id: User ID

        Returns:
            Reputation breakdown
        """
        stats = self.get_user_stats(user_id)
        badges = self.get_user_badges(user_id)

        design_points = stats["designs"] * POINTS_PER_DESIGN
        star_points = stats["stars_received"] * POINTS_PER_STAR_RECEIVED
        fork_points = stats["forks_received"] * POINTS_PER_FORK_RECEIVED
        comment_points = stats["comments_received"] * POINTS_PER_COMMENT_RECEIVED
        download_points = stats["downloads"] * POINTS_PER_DOWNLOAD
        badge_points = sum(b.badge.points for b in badges.badges)

        total = (
            design_points
            + star_points
            + fork_points
            + comment_points
            + download_points
            + badge_points
        )

        return ReputationBreakdown(
            designs_published=stats["designs"],
            designs_points=design_points,
            stars_received=stats["stars_received"],
            stars_points=star_points,
            forks_received=stats["forks_received"],
            forks_points=fork_points,
            comments_received=stats["comments_received"],
            comments_points=comment_points,
            downloads_received=stats["downloads"],
            downloads_points=download_points,
            badge_points=badge_points,
            total_points=total,
        )

    def get_reputation_leaderboard(
        self,
        offset: int = 0,
        limit: int = 20,
    ) -> ReputationLeaderboard:
        """Get reputation leaderboard.

        Args:
            offset: Pagination offset
            limit: Max results

        Returns:
            Leaderboard entries
        """
        with get_connection() as conn:
            # Use LEFT JOIN instead of scalar subquery to avoid N+1
            rows = conn.execute(
                """
                SELECT
                    u.id, u.display_name, u.avatar_url, u.reputation_score,
                    COUNT(ub.badge_id) as badge_count
                FROM users u
                LEFT JOIN user_badges ub ON u.id = ub.user_id
                WHERE u.reputation_score > 0
                GROUP BY u.id, u.display_name, u.avatar_url, u.reputation_score
                ORDER BY u.reputation_score DESC, u.display_name
                LIMIT ? OFFSET ?
                """,
                (limit + 1, offset),
            ).fetchall()

            has_more = len(rows) > limit
            rows = rows[:limit]

            total = conn.execute(
                "SELECT COUNT(*) FROM users WHERE reputation_score > 0"
            ).fetchone()[0]

            entries = []
            for i, row in enumerate(rows):
                entries.append(
                    ReputationLeaderboardEntry(
                        user_id=row["id"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                        reputation_score=row["reputation_score"] or 0,
                        badge_count=row["badge_count"],
                        rank=offset + i + 1,
                    )
                )

            return ReputationLeaderboard(
                entries=entries,
                total=total,
                has_more=has_more,
            )

    def recompute_all_reputations(self) -> None:
        """Recompute reputation scores for all users.

        This is typically run as a background task.
        """
        with get_connection() as conn:
            user_ids = conn.execute("SELECT id FROM users").fetchall()

        for row in user_ids:
            self.compute_user_reputation(row["id"])
            self.check_and_award_badges(row["id"])

        logger.info(f"Recomputed reputation for {len(user_ids)} users")


@lru_cache()
def get_reputation_store() -> ReputationStore:
    """Get singleton reputation store instance."""
    return ReputationStore()
