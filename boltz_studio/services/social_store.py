"""Social features store: Stars, Forks, Comments, Collections."""

import uuid
from functools import lru_cache

from ..logger import get_logger
from ..models import (
    CollectionCreate,
    CollectionPublic,
    CollectionSummary,
    CollectionUpdate,
    CommentCreate,
    CommentList,
    CommentPublic,
    CommentUpdate,
    DesignLineage,
    DesignSummary,
    ForkInfo,
    ForkRequest,
    UserPublic,
)
from .database import get_connection

logger = get_logger("social_store")


class SocialStore:
    """Store for social features."""

    # =========================================================================
    # Stars
    # =========================================================================

    def add_star(self, design_id: str, user_id: str) -> bool:
        """Add a star to a design.

        Args:
            design_id: Design to star
            user_id: User starring the design

        Returns:
            True if star was added, False if already starred
        """
        with get_connection() as conn:
            # Check if already starred
            existing = conn.execute(
                "SELECT id FROM stars WHERE design_id = ? AND user_id = ?",
                (design_id, user_id),
            ).fetchone()

            if existing:
                return False

            star_id = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO stars (id, design_id, user_id) VALUES (?, ?, ?)",
                (star_id, design_id, user_id),
            )

            # Update star count
            conn.execute(
                "UPDATE designs SET star_count = star_count + 1 WHERE id = ?",
                (design_id,),
            )

            logger.info(f"User {user_id} starred design {design_id}")
            return True

    def remove_star(self, design_id: str, user_id: str) -> bool:
        """Remove a star from a design.

        Args:
            design_id: Design to unstar
            user_id: User unstarring the design

        Returns:
            True if star was removed, False if wasn't starred
        """
        with get_connection() as conn:
            result = conn.execute(
                "DELETE FROM stars WHERE design_id = ? AND user_id = ?",
                (design_id, user_id),
            )

            if result.rowcount == 0:
                return False

            # Update star count
            conn.execute(
                "UPDATE designs SET star_count = MAX(0, star_count - 1) WHERE id = ?",
                (design_id,),
            )

            logger.info(f"User {user_id} unstarred design {design_id}")
            return True

    def is_starred(self, design_id: str, user_id: str) -> bool:
        """Check if a user has starred a design."""
        with get_connection() as conn:
            result = conn.execute(
                "SELECT 1 FROM stars WHERE design_id = ? AND user_id = ?",
                (design_id, user_id),
            ).fetchone()
            return result is not None

    def get_user_starred_designs(
        self, user_id: str, offset: int = 0, limit: int = 20
    ) -> list[DesignSummary]:
        """Get designs starred by a user."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT d.id, d.name, d.description, d.sequence, d.smiles,
                       d.confidence_score, d.affinity_probability,
                       d.star_count, d.fork_count, d.comment_count,
                       d.created_at, u.id as user_id, u.display_name, u.avatar_url,
                       u.created_at as user_created_at
                FROM stars s
                JOIN designs d ON s.design_id = d.id
                JOIN users u ON d.user_id = u.id
                WHERE s.user_id = ? AND d.is_public = 1
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()

            return [self._row_to_design_summary(row) for row in rows]

    # =========================================================================
    # Forks
    # =========================================================================

    def create_fork(
        self, parent_design_id: str, user_id: str, fork_design_id: str, request: ForkRequest
    ) -> str:
        """Record a fork relationship.

        The fork design should already be created. This just records the relationship.

        Args:
            parent_design_id: Original design being forked
            user_id: User creating the fork
            fork_design_id: The new forked design ID
            request: Fork request with attribution

        Returns:
            Fork record ID
        """
        fork_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO forks (id, parent_design_id, fork_design_id, user_id, attribution_note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (fork_id, parent_design_id, fork_design_id, user_id, request.attribution_note),
            )

            # Update parent design's parent_design_id
            conn.execute(
                "UPDATE designs SET parent_design_id = ? WHERE id = ?",
                (parent_design_id, fork_design_id),
            )

            # Update fork count on parent
            conn.execute(
                "UPDATE designs SET fork_count = fork_count + 1 WHERE id = ?",
                (parent_design_id,),
            )

            logger.info(f"User {user_id} forked design {parent_design_id} to {fork_design_id}")
            return fork_id

    def get_design_forks(self, design_id: str, offset: int = 0, limit: int = 20) -> list[ForkInfo]:
        """Get all forks of a design."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT f.id, f.parent_design_id, f.fork_design_id, f.attribution_note,
                       f.created_at, u.id as user_id, u.display_name, u.avatar_url,
                       u.created_at as user_created_at
                FROM forks f
                JOIN users u ON f.user_id = u.id
                WHERE f.parent_design_id = ?
                ORDER BY f.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (design_id, limit, offset),
            ).fetchall()

            return [
                ForkInfo(
                    id=row["id"],
                    parent_design_id=row["parent_design_id"],
                    fork_design_id=row["fork_design_id"],
                    user=UserPublic(
                        id=row["user_id"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                        created_at=row["user_created_at"],
                    ),
                    attribution_note=row["attribution_note"],
                    created_at=row["created_at"],
                )
                for row in rows
            ]

    def get_design_parent(self, design_id: str) -> DesignLineage | None:
        """Get the parent design info if this design is a fork."""
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT f.parent_design_id, d.name as parent_name, d.fork_count
                FROM forks f
                JOIN designs d ON f.parent_design_id = d.id
                WHERE f.fork_design_id = ?
                """,
                (design_id,),
            ).fetchone()

            if not row:
                return None

            return DesignLineage(
                parent_design_id=row["parent_design_id"],
                parent_name=row["parent_name"],
                fork_count=row["fork_count"],
            )

    # =========================================================================
    # Comments
    # =========================================================================

    def create_comment(
        self, design_id: str, user_id: str, comment: CommentCreate
    ) -> str:
        """Create a comment on a design."""
        comment_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO comments (id, design_id, user_id, content, lab_validated)
                VALUES (?, ?, ?, ?, ?)
                """,
                (comment_id, design_id, user_id, comment.content, int(comment.lab_validated)),
            )

            # Update comment count
            conn.execute(
                "UPDATE designs SET comment_count = comment_count + 1 WHERE id = ?",
                (design_id,),
            )

            logger.info(f"User {user_id} commented on design {design_id}")
            return comment_id

    def get_comments(
        self, design_id: str, offset: int = 0, limit: int = 20
    ) -> CommentList:
        """Get comments for a design."""
        with get_connection() as conn:
            # Get total count
            total = conn.execute(
                "SELECT COUNT(*) FROM comments WHERE design_id = ?",
                (design_id,),
            ).fetchone()[0]

            rows = conn.execute(
                """
                SELECT c.id, c.design_id, c.content, c.lab_validated,
                       c.created_at, c.updated_at,
                       u.id as user_id, u.display_name, u.avatar_url,
                       u.created_at as user_created_at
                FROM comments c
                JOIN users u ON c.user_id = u.id
                WHERE c.design_id = ?
                ORDER BY c.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (design_id, limit, offset),
            ).fetchall()

            comments = [
                CommentPublic(
                    id=row["id"],
                    design_id=row["design_id"],
                    author=UserPublic(
                        id=row["user_id"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                        created_at=row["user_created_at"],
                    ),
                    content=row["content"],
                    lab_validated=bool(row["lab_validated"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

            return CommentList(
                comments=comments,
                total=total,
                offset=offset,
                limit=limit,
            )

    def update_comment(
        self, comment_id: str, user_id: str, update: CommentUpdate
    ) -> bool:
        """Update a comment (author only)."""
        with get_connection() as conn:
            # Build update query
            updates = []
            params = []

            if update.content is not None:
                updates.append("content = ?")
                params.append(update.content)

            if update.lab_validated is not None:
                updates.append("lab_validated = ?")
                params.append(int(update.lab_validated))

            if not updates:
                return True

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([comment_id, user_id])

            result = conn.execute(
                f"UPDATE comments SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )

            return result.rowcount > 0

    def delete_comment(self, comment_id: str, user_id: str) -> bool:
        """Delete a comment (author only)."""
        with get_connection() as conn:
            # Get design_id first for updating count
            row = conn.execute(
                "SELECT design_id FROM comments WHERE id = ? AND user_id = ?",
                (comment_id, user_id),
            ).fetchone()

            if not row:
                return False

            design_id = row["design_id"]

            conn.execute(
                "DELETE FROM comments WHERE id = ? AND user_id = ?",
                (comment_id, user_id),
            )

            # Update comment count
            conn.execute(
                "UPDATE designs SET comment_count = MAX(0, comment_count - 1) WHERE id = ?",
                (design_id,),
            )

            logger.info(f"User {user_id} deleted comment {comment_id}")
            return True

    # =========================================================================
    # Collections
    # =========================================================================

    def create_collection(self, user_id: str, data: CollectionCreate) -> str:
        """Create a new collection."""
        collection_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO collections (id, user_id, name, description, is_public)
                VALUES (?, ?, ?, ?, ?)
                """,
                (collection_id, user_id, data.name, data.description, int(data.is_public)),
            )

            logger.info(f"User {user_id} created collection {collection_id}")
            return collection_id

    def get_collection(self, collection_id: str, user_id: str | None = None) -> CollectionPublic | None:
        """Get a collection by ID.

        Args:
            collection_id: Collection ID
            user_id: Current user ID (to check access to private collections)
        """
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT c.id, c.name, c.description, c.is_public, c.created_at, c.updated_at,
                       u.id as user_id, u.display_name, u.avatar_url,
                       u.created_at as user_created_at,
                       (SELECT COUNT(*) FROM collection_items WHERE collection_id = c.id) as design_count
                FROM collections c
                JOIN users u ON c.user_id = u.id
                WHERE c.id = ?
                """,
                (collection_id,),
            ).fetchone()

            if not row:
                return None

            # Check access
            if not row["is_public"] and row["user_id"] != user_id:
                return None

            return CollectionPublic(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                owner=UserPublic(
                    id=row["user_id"],
                    display_name=row["display_name"],
                    avatar_url=row["avatar_url"],
                    created_at=row["user_created_at"],
                ),
                design_count=row["design_count"],
                is_public=bool(row["is_public"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def list_user_collections(
        self, user_id: str, include_private: bool = False, offset: int = 0, limit: int = 20
    ) -> list[CollectionSummary]:
        """List collections owned by a user."""
        with get_connection() as conn:
            if include_private:
                rows = conn.execute(
                    """
                    SELECT c.id, c.name, c.description, c.is_public, c.created_at, c.updated_at,
                           u.id as user_id, u.display_name, u.avatar_url,
                           u.created_at as user_created_at,
                           (SELECT COUNT(*) FROM collection_items WHERE collection_id = c.id) as design_count
                    FROM collections c
                    JOIN users u ON c.user_id = u.id
                    WHERE c.user_id = ?
                    ORDER BY c.updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (user_id, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT c.id, c.name, c.description, c.is_public, c.created_at, c.updated_at,
                           u.id as user_id, u.display_name, u.avatar_url,
                           u.created_at as user_created_at,
                           (SELECT COUNT(*) FROM collection_items WHERE collection_id = c.id) as design_count
                    FROM collections c
                    JOIN users u ON c.user_id = u.id
                    WHERE c.user_id = ? AND c.is_public = 1
                    ORDER BY c.updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (user_id, limit, offset),
                ).fetchall()

            return [
                CollectionSummary(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    owner=UserPublic(
                        id=row["user_id"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                        created_at=row["user_created_at"],
                    ),
                    design_count=row["design_count"],
                    is_public=bool(row["is_public"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def list_public_collections(
        self, offset: int = 0, limit: int = 20
    ) -> list[CollectionSummary]:
        """List all public collections for browsing."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.name, c.description, c.is_public, c.created_at, c.updated_at,
                       u.id as user_id, u.display_name, u.avatar_url,
                       u.created_at as user_created_at,
                       (SELECT COUNT(*) FROM collection_items WHERE collection_id = c.id) as design_count
                FROM collections c
                JOIN users u ON c.user_id = u.id
                WHERE c.is_public = 1
                ORDER BY c.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

            return [
                CollectionSummary(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    owner=UserPublic(
                        id=row["user_id"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                        created_at=row["user_created_at"],
                    ),
                    design_count=row["design_count"],
                    is_public=bool(row["is_public"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def update_collection(
        self, collection_id: str, user_id: str, update: CollectionUpdate
    ) -> bool:
        """Update a collection (owner only)."""
        with get_connection() as conn:
            updates = []
            params = []

            if update.name is not None:
                updates.append("name = ?")
                params.append(update.name)

            if update.description is not None:
                updates.append("description = ?")
                params.append(update.description)

            if update.is_public is not None:
                updates.append("is_public = ?")
                params.append(int(update.is_public))

            if not updates:
                return True

            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.extend([collection_id, user_id])

            result = conn.execute(
                f"UPDATE collections SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
                params,
            )

            return result.rowcount > 0

    def delete_collection(self, collection_id: str, user_id: str) -> bool:
        """Delete a collection (owner only)."""
        with get_connection() as conn:
            result = conn.execute(
                "DELETE FROM collections WHERE id = ? AND user_id = ?",
                (collection_id, user_id),
            )

            if result.rowcount > 0:
                logger.info(f"User {user_id} deleted collection {collection_id}")
                return True
            return False

    def add_design_to_collection(
        self, collection_id: str, user_id: str, design_id: str
    ) -> bool:
        """Add a design to a collection (owner only)."""
        with get_connection() as conn:
            # Verify ownership
            owner = conn.execute(
                "SELECT user_id FROM collections WHERE id = ?",
                (collection_id,),
            ).fetchone()

            if not owner or owner["user_id"] != user_id:
                return False

            # Check if already in collection
            existing = conn.execute(
                "SELECT 1 FROM collection_items WHERE collection_id = ? AND design_id = ?",
                (collection_id, design_id),
            ).fetchone()

            if existing:
                return True  # Already exists, not an error

            conn.execute(
                "INSERT INTO collection_items (collection_id, design_id) VALUES (?, ?)",
                (collection_id, design_id),
            )

            # Update collection timestamp
            conn.execute(
                "UPDATE collections SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (collection_id,),
            )

            return True

    def remove_design_from_collection(
        self, collection_id: str, user_id: str, design_id: str
    ) -> bool:
        """Remove a design from a collection (owner only)."""
        with get_connection() as conn:
            # Verify ownership
            owner = conn.execute(
                "SELECT user_id FROM collections WHERE id = ?",
                (collection_id,),
            ).fetchone()

            if not owner or owner["user_id"] != user_id:
                return False

            result = conn.execute(
                "DELETE FROM collection_items WHERE collection_id = ? AND design_id = ?",
                (collection_id, design_id),
            )

            if result.rowcount > 0:
                # Update collection timestamp
                conn.execute(
                    "UPDATE collections SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (collection_id,),
                )
                return True
            return False

    def get_collection_designs(
        self, collection_id: str, offset: int = 0, limit: int = 20
    ) -> list[DesignSummary]:
        """Get designs in a collection."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT d.id, d.name, d.description, d.sequence, d.smiles,
                       d.confidence_score, d.affinity_probability,
                       d.star_count, d.fork_count, d.comment_count,
                       d.created_at, u.id as user_id, u.display_name, u.avatar_url,
                       u.created_at as user_created_at
                FROM collection_items ci
                JOIN designs d ON ci.design_id = d.id
                JOIN users u ON d.user_id = u.id
                WHERE ci.collection_id = ? AND d.is_public = 1
                ORDER BY ci.added_at DESC
                LIMIT ? OFFSET ?
                """,
                (collection_id, limit, offset),
            ).fetchall()

            return [self._row_to_design_summary(row) for row in rows]

    # =========================================================================
    # Helpers
    # =========================================================================

    def _row_to_design_summary(self, row) -> DesignSummary:
        """Convert a database row to DesignSummary."""
        return DesignSummary(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            sequence_length=len(row["sequence"]) if row["sequence"] else 0,
            has_ligand=bool(row["smiles"]),
            confidence_score=row["confidence_score"],
            affinity_probability=row["affinity_probability"],
            star_count=row["star_count"] or 0,
            fork_count=row["fork_count"] or 0,
            comment_count=row["comment_count"] or 0,
            tags=[],
            author=UserPublic(
                id=row["user_id"],
                display_name=row["display_name"],
                avatar_url=row["avatar_url"],
                created_at=row["user_created_at"],
            ),
            created_at=row["created_at"],
        )


@lru_cache()
def get_social_store() -> SocialStore:
    """Get social store singleton."""
    return SocialStore()
