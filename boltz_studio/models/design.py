"""Design models for publishing and discovery."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .user import UserPublic


class TagInput(BaseModel):
    """Tag input model."""

    tag: str = Field(..., min_length=1, max_length=50)
    tag_type: Literal["target", "organism", "purpose"]


class DesignCreate(BaseModel):
    """Model for publishing a design."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    sequence: str = Field(..., min_length=5, max_length=2000)
    smiles: str | None = None
    structure_pdb: str = Field(..., min_length=1)
    preview_image: str | None = None  # Base64 PNG preview
    confidence_score: float | None = Field(None, ge=0, le=1)
    complex_plddt: float | None = Field(None, ge=0, le=100)
    ptm: float | None = Field(None, ge=0, le=1)
    affinity_probability: float | None = Field(None, ge=0, le=1)
    affinity_raw: float | None = None
    plddt_per_residue: list[float] | None = None
    tags: list[TagInput] = Field(default_factory=list, max_length=10)
    is_public: bool = True


class DesignUpdate(BaseModel):
    """Model for updating a design."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=2000)
    tags: list[TagInput] | None = None
    is_public: bool | None = None


class DesignPublic(BaseModel):
    """Public design information."""

    id: str
    name: str
    description: str | None
    sequence: str
    smiles: str | None
    structure_pdb: str
    confidence_score: float | None
    complex_plddt: float | None
    ptm: float | None
    affinity_probability: float | None
    affinity_raw: float | None
    plddt_per_residue: list[float] | None
    tags: list[TagInput]
    is_public: bool
    created_at: datetime
    updated_at: datetime
    author: UserPublic
    # Social counts
    star_count: int = 0
    fork_count: int = 0
    comment_count: int = 0
    parent_design_id: str | None = None
    is_starred: bool | None = None  # Whether current user starred this

    model_config = {"from_attributes": True}


class DesignSummary(BaseModel):
    """Summary for design listings (smaller payload - NO PDB data for performance)."""

    id: str
    name: str
    description: str | None
    sequence_length: int
    has_ligand: bool
    confidence_score: float | None
    plddt: float | None = None  # complex_plddt normalized to 0-1 scale
    affinity_probability: float | None
    preview_image: str | None = None  # Base64 PNG preview for static display
    tags: list[TagInput]
    created_at: datetime
    author: UserPublic
    # Social counts
    star_count: int = 0
    fork_count: int = 0
    comment_count: int = 0
    is_starred: bool | None = None
    # Lineage
    parent_design_id: str | None = None

    model_config = {"from_attributes": True}


class DesignSearchParams(BaseModel):
    """Search parameters for design discovery."""

    query: str | None = None
    tag: str | None = None
    tag_type: Literal["target", "organism", "purpose"] | None = None
    min_confidence: float | None = Field(None, ge=0, le=1)
    max_confidence: float | None = Field(None, ge=0, le=1)
    min_affinity: float | None = Field(None, ge=0, le=1)
    max_affinity: float | None = Field(None, ge=0, le=1)
    has_ligand: bool | None = None
    sort_by: Literal[
        "created_at", "confidence_score", "affinity_probability", "star_count", "fork_count"
    ] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
    offset: int = Field(0, ge=0)
    limit: int = Field(20, ge=1, le=100)


class DesignSearchResult(BaseModel):
    """Paginated search results."""

    designs: list[DesignSummary]
    total: int
    offset: int
    limit: int
