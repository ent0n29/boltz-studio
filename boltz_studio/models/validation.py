"""Lab validation models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .user import UserPublic

ValidationType = Literal["binding", "expression", "stability", "activity", "structure", "other"]
ValidationResult = Literal["confirmed", "partial", "failed", "inconclusive"]


class ValidationCreate(BaseModel):
    """Create a lab validation."""

    validation_type: ValidationType
    result: ValidationResult
    method: str | None = Field(None, max_length=200)
    notes: str | None = Field(None, max_length=2000)
    evidence_url: str | None = Field(None, max_length=500)


class ValidationPublic(BaseModel):
    """Public validation data."""

    id: str
    design_id: str
    user: UserPublic
    validation_type: ValidationType
    result: ValidationResult
    method: str | None = None
    notes: str | None = None
    evidence_url: str | None = None
    is_verified: bool = False
    created_at: datetime


class ValidationList(BaseModel):
    """List of validations."""

    validations: list[ValidationPublic]
    total: int
    has_more: bool = False


class ValidationSummary(BaseModel):
    """Summary of validations for a design."""

    total: int = 0
    confirmed: int = 0
    partial: int = 0
    failed: int = 0
    inconclusive: int = 0
    is_validated: bool = False  # Has at least one confirmed validation
