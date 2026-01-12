"""Lab validation store for managing experimental validations."""

import uuid
from datetime import datetime
from functools import lru_cache

from ..logger import get_logger
from ..models.user import UserPublic
from ..models.validation import (
    ValidationCreate,
    ValidationList,
    ValidationPublic,
    ValidationSummary,
)
from .database import get_connection

logger = get_logger("validation_store")


class ValidationStore:
    """Store for lab validation operations."""

    def create(
        self,
        design_id: str,
        user_id: str,
        data: ValidationCreate,
    ) -> str:
        """Create a lab validation.

        Args:
            design_id: Design being validated
            user_id: User submitting validation
            data: Validation data

        Returns:
            Validation ID
        """
        validation_id = str(uuid.uuid4())

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO lab_validations
                (id, design_id, user_id, validation_type, result, method, notes, evidence_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    validation_id,
                    design_id,
                    user_id,
                    data.validation_type,
                    data.result,
                    data.method,
                    data.notes,
                    data.evidence_url,
                ),
            )

            # Update design validation count
            conn.execute(
                """
                UPDATE designs
                SET validation_count = (
                    SELECT COUNT(*) FROM lab_validations WHERE design_id = ?
                )
                WHERE id = ?
                """,
                (design_id, design_id),
            )

        logger.info(f"Created validation {validation_id} for design {design_id}")
        return validation_id

    def get_by_design(
        self,
        design_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> ValidationList:
        """Get validations for a design.

        Args:
            design_id: Design ID
            offset: Pagination offset
            limit: Max results

        Returns:
            List of validations
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT lv.*, u.id as user_id, u.display_name, u.avatar_url
                FROM lab_validations lv
                JOIN users u ON lv.user_id = u.id
                WHERE lv.design_id = ?
                ORDER BY lv.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (design_id, limit + 1, offset),
            ).fetchall()

            has_more = len(rows) > limit
            rows = rows[:limit]

            total = conn.execute(
                "SELECT COUNT(*) FROM lab_validations WHERE design_id = ?",
                (design_id,),
            ).fetchone()[0]

            validations = [
                ValidationPublic(
                    id=row["id"],
                    design_id=row["design_id"],
                    user=UserPublic(
                        id=row["user_id"],
                        display_name=row["display_name"],
                        avatar_url=row["avatar_url"],
                    ),
                    validation_type=row["validation_type"],
                    result=row["result"],
                    method=row["method"],
                    notes=row["notes"],
                    evidence_url=row["evidence_url"],
                    is_verified=bool(row["is_verified"]),
                    created_at=datetime.fromisoformat(
                        row["created_at"].replace("Z", "")
                    ),
                )
                for row in rows
            ]

            return ValidationList(
                validations=validations,
                total=total,
                has_more=has_more,
            )

    def get_summary(self, design_id: str) -> ValidationSummary:
        """Get validation summary for a design.

        Args:
            design_id: Design ID

        Returns:
            Validation summary
        """
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT result, COUNT(*) as count
                FROM lab_validations
                WHERE design_id = ?
                GROUP BY result
                """,
                (design_id,),
            ).fetchall()

            summary = ValidationSummary()
            for row in rows:
                result = row["result"]
                count = row["count"]
                summary.total += count

                if result == "confirmed":
                    summary.confirmed = count
                elif result == "partial":
                    summary.partial = count
                elif result == "failed":
                    summary.failed = count
                elif result == "inconclusive":
                    summary.inconclusive = count

            summary.is_validated = summary.confirmed > 0

            return summary

    def delete(
        self,
        validation_id: str,
        user_id: str,
    ) -> bool:
        """Delete a validation.

        Args:
            validation_id: Validation ID
            user_id: User deleting (must be owner)

        Returns:
            True if deleted
        """
        with get_connection() as conn:
            # Check ownership
            row = conn.execute(
                "SELECT design_id, user_id FROM lab_validations WHERE id = ?",
                (validation_id,),
            ).fetchone()

            if not row or row["user_id"] != user_id:
                return False

            design_id = row["design_id"]

            conn.execute(
                "DELETE FROM lab_validations WHERE id = ?",
                (validation_id,),
            )

            # Update design validation count
            conn.execute(
                """
                UPDATE designs
                SET validation_count = (
                    SELECT COUNT(*) FROM lab_validations WHERE design_id = ?
                )
                WHERE id = ?
                """,
                (design_id, design_id),
            )

        return True

    def verify(self, validation_id: str) -> bool:
        """Mark a validation as verified (admin only).

        Args:
            validation_id: Validation ID

        Returns:
            True if updated
        """
        with get_connection() as conn:
            result = conn.execute(
                "UPDATE lab_validations SET is_verified = 1 WHERE id = ?",
                (validation_id,),
            )
            return result.rowcount > 0


@lru_cache()
def get_validation_store() -> ValidationStore:
    """Get singleton validation store instance."""
    return ValidationStore()
