"""Shared utility functions for services."""

from datetime import datetime
from typing import Any

from ..models.design import DesignSummary, TagInput
from ..models.user import UserPublic


def parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse a datetime value from various formats.

    Args:
        value: String, datetime, or None

    Returns:
        Parsed datetime or None
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", ""))


def parse_tags_from_group_concat(tags_str: str | None) -> list[TagInput]:
    """Parse tags from GROUP_CONCAT format.

    Format: "tag1|type1,tag2|type2,..."

    Args:
        tags_str: Concatenated tags string or None

    Returns:
        List of TagInput objects
    """
    if not tags_str:
        return []

    tags = []
    for item in tags_str.split(","):
        if "|" in item:
            parts = item.split("|", 1)
            if len(parts) == 2:
                tags.append(TagInput(tag=parts[0], tag_type=parts[1]))
    return tags


def build_design_summary(row: dict[str, Any], tags: list[TagInput] | None = None) -> DesignSummary:
    """Build a DesignSummary from a database row.

    Expected row keys:
        - id, name, description, sequence, smiles
        - confidence_score, complex_plddt, affinity_probability
        - star_count, fork_count, comment_count
        - preview_image, parent_design_id
        - created_at
        - user_id, display_name, avatar_url, user_created_at

    Optional:
        - tags_concat: GROUP_CONCAT formatted tags string
        - is_starred

    Args:
        row: Database row (dict-like)
        tags: Pre-parsed tags list (if not using tags_concat)

    Returns:
        DesignSummary instance
    """
    # Parse tags from GROUP_CONCAT if not provided
    if tags is None:
        tags = parse_tags_from_group_concat(row.get("tags_concat"))

    # Calculate plddt (0-1 scale) from complex_plddt (0-100 scale)
    plddt = None
    complex_plddt = row.get("complex_plddt")
    if complex_plddt is not None:
        plddt = complex_plddt / 100.0

    # Build author
    author = UserPublic(
        id=row["user_id"],
        display_name=row["display_name"],
        avatar_url=row.get("avatar_url"),
        created_at=parse_datetime(row.get("user_created_at")),
    )

    # Determine sequence length and has_ligand
    sequence = row.get("sequence", "")
    sequence_length = len(sequence) if sequence else 0
    has_ligand = bool(row.get("smiles"))

    return DesignSummary(
        id=row["id"],
        name=row["name"],
        description=row.get("description"),
        sequence_length=sequence_length,
        has_ligand=has_ligand,
        confidence_score=row.get("confidence_score"),
        plddt=plddt,
        affinity_probability=row.get("affinity_probability"),
        preview_image=row.get("preview_image"),
        tags=tags,
        created_at=parse_datetime(row["created_at"]),
        author=author,
        star_count=row.get("star_count") or 0,
        fork_count=row.get("fork_count") or 0,
        comment_count=row.get("comment_count") or 0,
        is_starred=row.get("is_starred"),
        parent_design_id=row.get("parent_design_id"),
    )


# SQL fragment for joining tags with GROUP_CONCAT
TAGS_GROUP_CONCAT_SQL = """
    GROUP_CONCAT(dt.tag || '|' || dt.tag_type) as tags_concat
"""

# SQL fragment for selecting design fields with author
DESIGN_SUMMARY_SELECT_SQL = """
    d.id, d.name, d.description, d.sequence, d.smiles,
    d.confidence_score, d.complex_plddt, d.affinity_probability,
    d.preview_image, d.parent_design_id,
    d.star_count, d.fork_count, d.comment_count,
    d.created_at,
    u.id as user_id, u.display_name, u.avatar_url, u.created_at as user_created_at
"""
