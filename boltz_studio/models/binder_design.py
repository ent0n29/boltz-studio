"""Models for binder design (BoltzGen integration)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# Protocol types supported by BoltzGen
DesignProtocol = Literal[
    "protein-anything",
    "peptide-anything",
    "protein-small_molecule",
    "nanobody-anything",
    "antibody-anything",
]

# Job status
DesignJobStatus = Literal[
    "queued",
    "downloading_models",
    "generating",
    "folding",
    "analyzing",
    "filtering",
    "completed",
    "failed",
    "cancelled",
]

# Target categories
TargetCategory = Literal[
    "cancer",
    "infectious_disease",
    "autoimmune",
    "neurology",
    "metabolic",
    "custom",
]

# Difficulty levels
DifficultyLevel = Literal["easy", "medium", "hard"]


class BindingSiteInput(BaseModel):
    """Binding site specification."""

    chain_id: str = Field(..., description="Chain ID in the target structure")
    residues: list[int] | None = Field(
        None, description="Specific residue indices (1-indexed). If None, uses whole chain."
    )
    radius: float | None = Field(
        None, description="Radius around residues to include (Angstroms)"
    )


class DesignConstraints(BaseModel):
    """Constraints for binder design."""

    secondary_structure: Literal["helix", "sheet", "loop", "any"] | None = None
    disulfide_bonds: bool = False
    cyclic: bool = False
    hotspot_residues: list[int] | None = None


# === Target Models ===


class DesignTargetBase(BaseModel):
    """Base target model."""

    name: str
    description: str | None = None
    category: TargetCategory
    subcategory: str | None = None
    pdb_id: str | None = None
    uniprot_id: str | None = None
    organism: str | None = None
    therapeutic_area: str | None = None
    difficulty: DifficultyLevel = "medium"


class DesignTargetCreate(DesignTargetBase):
    """Create a custom design target."""

    slug: str
    structure_pdb: str = Field(..., description="PDB file content")
    binding_site_residues: list[int] | None = None
    binding_site_chains: list[str] | None = None


class DesignTargetPublic(DesignTargetBase):
    """Public target information."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    is_curated: bool = False
    design_count: int = 0
    successful_designs: int = 0
    created_at: datetime | None = None


class DesignTargetDetail(DesignTargetPublic):
    """Detailed target with structure."""

    structure_pdb: str | None = None
    binding_site_residues: list[int] | None = None
    binding_site_chains: list[str] | None = None


class DesignTargetList(BaseModel):
    """List of design targets."""

    targets: list[DesignTargetPublic]
    total: int
    categories: dict[str, int] = {}  # Category counts


# === Design Job Models ===


class DesignJobCreate(BaseModel):
    """Create a new design job."""

    name: str = Field(..., min_length=1, max_length=100)
    target_id: str | None = Field(None, description="ID of curated target")
    custom_target_pdb: str | None = Field(None, description="Custom PDB content")
    protocol: DesignProtocol = "nanobody-anything"
    num_designs: int = Field(1000, ge=100, le=10000)
    binder_length_min: int = Field(80, ge=10, le=500)
    binder_length_max: int = Field(140, ge=10, le=500)
    binding_site: BindingSiteInput | None = None
    constraints: DesignConstraints | None = None

    def model_post_init(self, __context) -> None:
        """Validate that either target_id or custom_target_pdb is provided."""
        if not self.target_id and not self.custom_target_pdb:
            raise ValueError("Either target_id or custom_target_pdb must be provided")


class DesignJobPublic(BaseModel):
    """Public design job information."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    target_id: str | None = None
    protocol: DesignProtocol
    status: DesignJobStatus
    progress: float = 0.0
    current_step: str | None = None
    num_designs: int
    total_generated: int | None = None
    total_passed: int | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DesignJobDetail(DesignJobPublic):
    """Detailed job information."""

    binder_length_min: int | None = None
    binder_length_max: int | None = None
    binding_site_residues: str | None = None
    constraints: str | None = None
    spec_yaml: str | None = None


class DesignJobList(BaseModel):
    """List of design jobs."""

    jobs: list[DesignJobPublic]
    total: int


# === Design Result Models ===


class DesignResultPublic(BaseModel):
    """Public design result."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    rank: int
    sequence: str
    plddt_score: float | None = None
    ptm_score: float | None = None
    affinity_score: float | None = None
    confidence_score: float | None = None
    is_published: bool = False
    design_id: str | None = None  # Link to published design


class DesignResultDetail(DesignResultPublic):
    """Detailed result with structure."""

    structure_pdb: str | None = None
    secondary_structure: str | None = None
    metrics: dict | None = None


class DesignResultList(BaseModel):
    """List of design results."""

    results: list[DesignResultPublic]
    total: int
    job_id: str


# === Synthesis Order Models ===


SynthesisProvider = Literal["twist", "idt", "genscript", "other"]
SynthesisOrderType = Literal["dna", "plasmid", "protein"]
SynthesisStatus = Literal[
    "pending", "ordered", "in_production", "shipped", "delivered", "failed"
]


class SynthesisOrderCreate(BaseModel):
    """Create a synthesis order."""

    design_result_id: str
    provider: SynthesisProvider = "twist"
    order_type: SynthesisOrderType = "plasmid"
    codon_optimized_for: str = "E. coli"
    quantity: str = "1 ug"
    notes: str | None = None


class SynthesisOrderPublic(BaseModel):
    """Public synthesis order information."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    design_result_id: str
    provider: SynthesisProvider
    order_type: SynthesisOrderType
    status: SynthesisStatus
    external_order_id: str | None = None
    estimated_cost: float | None = None
    tracking_url: str | None = None
    ordered_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    created_at: datetime


# === Progress Models ===


class DesignProgress(BaseModel):
    """Real-time design job progress update."""

    job_id: str
    status: DesignJobStatus
    progress: float
    current_step: str | None = None
    message: str | None = None
    designs_generated: int | None = None
    designs_passed: int | None = None
