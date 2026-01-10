"""SQLite-backed design storage with full-text search."""

import json
import uuid
from typing import Any

from ..logger import get_logger
from ..models import (
    DesignCreate,
    DesignPublic,
    DesignSearchParams,
    DesignSearchResult,
    DesignSummary,
    DesignUpdate,
    TagInput,
    UserPublic,
)
from .database import get_connection

logger = get_logger("design_store")


class DesignStore:
    """SQLite-backed design storage with FTS search."""

    def create(self, user_id: str, design: DesignCreate) -> str:
        """Create a new published design.

        Args:
            user_id: ID of the user publishing the design
            design: Design data

        Returns:
            Design ID
        """
        design_id = str(uuid.uuid4())

        # Serialize plddt as JSON
        plddt_json = (
            json.dumps(design.plddt_per_residue)
            if design.plddt_per_residue
            else None
        )

        with get_connection() as conn:
            # Insert design
            conn.execute(
                """
                INSERT INTO designs (
                    id, user_id, name, description, sequence, smiles,
                    structure_pdb, preview_image, confidence_score, complex_plddt, ptm,
                    affinity_probability, affinity_raw, plddt_json, is_public
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    design_id,
                    user_id,
                    design.name,
                    design.description,
                    design.sequence,
                    design.smiles,
                    design.structure_pdb,
                    design.preview_image,
                    design.confidence_score,
                    design.complex_plddt,
                    design.ptm,
                    design.affinity_probability,
                    design.affinity_raw,
                    plddt_json,
                    1 if design.is_public else 0,
                ),
            )

            # Insert tags
            for tag in design.tags:
                conn.execute(
                    """
                    INSERT INTO design_tags (design_id, tag, tag_type)
                    VALUES (?, ?, ?)
                    """,
                    (design_id, tag.tag, tag.tag_type),
                )

            # Update FTS index
            tags_str = " ".join(t.tag for t in design.tags)
            conn.execute(
                """
                INSERT INTO designs_fts (design_id, name, description, tags)
                VALUES (?, ?, ?, ?)
                """,
                (design_id, design.name, design.description or "", tags_str),
            )

        logger.info(f"Created design: {design_id} by user {user_id}")
        return design_id

    def get(self, design_id: str) -> dict[str, Any] | None:
        """Get a design by ID.

        Args:
            design_id: Design identifier

        Returns:
            Design data or None if not found
        """
        with get_connection() as conn:
            # Get design
            row = conn.execute(
                """
                SELECT d.*, u.id as author_id, u.display_name as author_name,
                       u.avatar_url as author_avatar, u.created_at as author_created
                FROM designs d
                JOIN users u ON d.user_id = u.id
                WHERE d.id = ?
                """,
                (design_id,),
            ).fetchone()

            if not row:
                return None

            design = dict(row)

            # Get tags
            tags = conn.execute(
                """
                SELECT tag, tag_type FROM design_tags WHERE design_id = ?
                """,
                (design_id,),
            ).fetchall()

            design["tags"] = [dict(t) for t in tags]

            return design

    def get_public(self, design_id: str) -> DesignPublic | None:
        """Get a public design with full details.

        Args:
            design_id: Design identifier

        Returns:
            DesignPublic or None if not found/not public
        """
        design = self.get(design_id)
        if not design or not design["is_public"]:
            return None

        return self._to_public(design)

    def _to_public(self, design: dict[str, Any]) -> DesignPublic:
        """Convert design dict to DesignPublic."""
        plddt = None
        if design["plddt_json"]:
            plddt = json.loads(design["plddt_json"])

        return DesignPublic(
            id=design["id"],
            name=design["name"],
            description=design["description"],
            sequence=design["sequence"],
            smiles=design["smiles"],
            structure_pdb=design["structure_pdb"],
            confidence_score=design["confidence_score"],
            complex_plddt=design["complex_plddt"],
            ptm=design["ptm"],
            affinity_probability=design["affinity_probability"],
            affinity_raw=design["affinity_raw"],
            plddt_per_residue=plddt,
            tags=[TagInput(**t) for t in design["tags"]],
            is_public=bool(design["is_public"]),
            created_at=design["created_at"],
            updated_at=design["updated_at"],
            author=UserPublic(
                id=design["author_id"],
                display_name=design["author_name"],
                avatar_url=design["author_avatar"],
                created_at=design["author_created"],
            ),
            star_count=design.get("star_count") or 0,
            fork_count=design.get("fork_count") or 0,
            comment_count=design.get("comment_count") or 0,
            parent_design_id=design.get("parent_design_id"),
        )

    def _to_summary(self, design: dict[str, Any]) -> DesignSummary:
        """Convert design dict to DesignSummary (lightweight, no PDB data)."""
        # Calculate plddt (0-1 scale) from complex_plddt (0-100 scale)
        plddt = None
        if design.get("complex_plddt") is not None:
            plddt = design["complex_plddt"] / 100.0

        return DesignSummary(
            id=design["id"],
            name=design["name"],
            description=design["description"],
            sequence_length=len(design["sequence"]),
            has_ligand=bool(design["smiles"]),
            confidence_score=design["confidence_score"],
            plddt=plddt,
            affinity_probability=design["affinity_probability"],
            preview_image=design.get("preview_image"),
            tags=[TagInput(**t) for t in design["tags"]],
            created_at=design["created_at"],
            author=UserPublic(
                id=design["author_id"],
                display_name=design["author_name"],
                avatar_url=design["author_avatar"],
                created_at=design["author_created"],
            ),
            star_count=design.get("star_count") or 0,
            fork_count=design.get("fork_count") or 0,
            comment_count=design.get("comment_count") or 0,
            parent_design_id=design.get("parent_design_id"),
        )

    def update(
        self, design_id: str, user_id: str, updates: DesignUpdate
    ) -> bool:
        """Update a design (only owner can update).

        Args:
            design_id: Design identifier
            user_id: User attempting the update
            updates: Fields to update

        Returns:
            True if updated, False if not found or not owner
        """
        # Verify ownership
        design = self.get(design_id)
        if not design or design["user_id"] != user_id:
            return False

        with get_connection() as conn:
            # Build update query dynamically
            set_parts = ["updated_at = CURRENT_TIMESTAMP"]
            values: list[Any] = []

            if updates.name is not None:
                set_parts.append("name = ?")
                values.append(updates.name)

            if updates.description is not None:
                set_parts.append("description = ?")
                values.append(updates.description)

            if updates.is_public is not None:
                set_parts.append("is_public = ?")
                values.append(1 if updates.is_public else 0)

            values.append(design_id)

            conn.execute(
                f"UPDATE designs SET {', '.join(set_parts)} WHERE id = ?",
                values,
            )

            # Update tags if provided
            if updates.tags is not None:
                # Delete old tags
                conn.execute(
                    "DELETE FROM design_tags WHERE design_id = ?",
                    (design_id,),
                )

                # Insert new tags
                for tag in updates.tags:
                    conn.execute(
                        """
                        INSERT INTO design_tags (design_id, tag, tag_type)
                        VALUES (?, ?, ?)
                        """,
                        (design_id, tag.tag, tag.tag_type),
                    )

                # Update FTS
                tags_str = " ".join(t.tag for t in updates.tags)
                conn.execute(
                    "DELETE FROM designs_fts WHERE design_id = ?",
                    (design_id,),
                )
                conn.execute(
                    """
                    INSERT INTO designs_fts (design_id, name, description, tags)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        design_id,
                        updates.name or design["name"],
                        updates.description or design["description"] or "",
                        tags_str,
                    ),
                )

        logger.info(f"Updated design: {design_id}")
        return True

    def delete(self, design_id: str, user_id: str) -> bool:
        """Delete a design (only owner can delete).

        Args:
            design_id: Design identifier
            user_id: User attempting the delete

        Returns:
            True if deleted, False if not found or not owner
        """
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM designs WHERE id = ? AND user_id = ?",
                (design_id, user_id),
            )

            if cursor.rowcount > 0:
                # FTS and tags are auto-deleted via triggers/CASCADE
                conn.execute(
                    "DELETE FROM designs_fts WHERE design_id = ?",
                    (design_id,),
                )
                logger.info(f"Deleted design: {design_id}")
                return True

        return False

    def list_user_designs(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[DesignSummary]:
        """List designs by a specific user.

        Args:
            user_id: User identifier
            offset: Pagination offset
            limit: Maximum results

        Returns:
            List of design summaries
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT d.*, u.id as author_id, u.display_name as author_name,
                       u.avatar_url as author_avatar, u.created_at as author_created
                FROM designs d
                JOIN users u ON d.user_id = u.id
                WHERE d.user_id = ?
                ORDER BY d.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset),
            ).fetchall()

            result = []
            for row in rows:
                design = dict(row)
                tags = conn.execute(
                    "SELECT tag, tag_type FROM design_tags WHERE design_id = ?",
                    (design["id"],),
                ).fetchall()
                design["tags"] = [dict(t) for t in tags]
                result.append(self._to_summary(design))

            return result

    def search(self, params: DesignSearchParams) -> DesignSearchResult:
        """Search public designs with filters.

        Args:
            params: Search parameters

        Returns:
            Paginated search results
        """
        with get_connection() as conn:
            # Build WHERE clauses
            where_parts = ["d.is_public = 1"]
            values: list[Any] = []

            # Full-text search
            if params.query:
                where_parts.append(
                    "d.id IN (SELECT design_id FROM designs_fts WHERE designs_fts MATCH ?)"
                )
                values.append(params.query)

            # Tag filter
            if params.tag:
                if params.tag_type:
                    where_parts.append(
                        """d.id IN (
                            SELECT design_id FROM design_tags
                            WHERE tag = ? AND tag_type = ?
                        )"""
                    )
                    values.extend([params.tag, params.tag_type])
                else:
                    where_parts.append(
                        "d.id IN (SELECT design_id FROM design_tags WHERE tag = ?)"
                    )
                    values.append(params.tag)

            # Confidence filters
            if params.min_confidence is not None:
                where_parts.append("d.confidence_score >= ?")
                values.append(params.min_confidence)
            if params.max_confidence is not None:
                where_parts.append("d.confidence_score <= ?")
                values.append(params.max_confidence)

            # Affinity filters
            if params.min_affinity is not None:
                where_parts.append("d.affinity_probability >= ?")
                values.append(params.min_affinity)
            if params.max_affinity is not None:
                where_parts.append("d.affinity_probability <= ?")
                values.append(params.max_affinity)

            # Ligand filter
            if params.has_ligand is not None:
                if params.has_ligand:
                    where_parts.append("d.smiles IS NOT NULL AND d.smiles != ''")
                else:
                    where_parts.append("(d.smiles IS NULL OR d.smiles = '')")

            where_clause = " AND ".join(where_parts)

            # Sort
            order_clause = f"d.{params.sort_by} {params.sort_order.upper()}"

            # Get total count
            count_row = conn.execute(
                f"""
                SELECT COUNT(*) as total
                FROM designs d
                WHERE {where_clause}
                """,
                values,
            ).fetchone()
            total = count_row["total"] if count_row else 0

            # Get results
            rows = conn.execute(
                f"""
                SELECT d.*, u.id as author_id, u.display_name as author_name,
                       u.avatar_url as author_avatar, u.created_at as author_created
                FROM designs d
                JOIN users u ON d.user_id = u.id
                WHERE {where_clause}
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
                """,
                values + [params.limit, params.offset],
            ).fetchall()

            # Build result list with tags
            designs = []
            for row in rows:
                design = dict(row)
                tags = conn.execute(
                    "SELECT tag, tag_type FROM design_tags WHERE design_id = ?",
                    (design["id"],),
                ).fetchall()
                design["tags"] = [dict(t) for t in tags]
                designs.append(self._to_summary(design))

            return DesignSearchResult(
                designs=designs,
                total=total,
                offset=params.offset,
                limit=params.limit,
            )

    def get_popular_tags(
        self,
        tag_type: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get popular tags with usage counts.

        Args:
            tag_type: Filter by tag type (target/organism/purpose)
            limit: Maximum tags to return

        Returns:
            List of tags with counts
        """
        with get_connection() as conn:
            if tag_type:
                rows = conn.execute(
                    """
                    SELECT tag, tag_type, COUNT(*) as count
                    FROM design_tags dt
                    JOIN designs d ON dt.design_id = d.id
                    WHERE d.is_public = 1 AND dt.tag_type = ?
                    GROUP BY tag, tag_type
                    ORDER BY count DESC
                    LIMIT ?
                    """,
                    (tag_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT tag, tag_type, COUNT(*) as count
                    FROM design_tags dt
                    JOIN designs d ON dt.design_id = d.id
                    WHERE d.is_public = 1
                    GROUP BY tag, tag_type
                    ORDER BY count DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

            return [dict(r) for r in rows]


# Singleton instance
_store: DesignStore | None = None


def get_design_store() -> DesignStore:
    """Get the singleton DesignStore instance.

    Returns:
        DesignStore instance
    """
    global _store
    if _store is None:
        _store = DesignStore()
    return _store
