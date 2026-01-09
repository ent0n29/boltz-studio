"""Prediction request/response models with validation."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..config import settings

# Valid amino acid characters
VALID_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


class SequenceInput(BaseModel):
    """Input sequence for structure prediction."""

    id: str = Field(
        default="A",
        max_length=10,
        description="Chain identifier"
    )
    sequence: str = Field(
        ...,
        min_length=1,
        description="Amino acid sequence"
    )
    type: Literal["protein", "dna", "rna", "ligand"] = Field(
        default="protein",
        description="Molecule type"
    )

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: str) -> str:
        """Validate and normalize amino acid sequence."""
        v = v.upper().strip()

        if len(v) < settings.min_sequence_length:
            raise ValueError(
                f"Sequence too short: minimum {settings.min_sequence_length} residues"
            )

        if len(v) > settings.max_sequence_length:
            raise ValueError(
                f"Sequence too long: maximum {settings.max_sequence_length} residues"
            )

        invalid = set(v) - VALID_AMINO_ACIDS
        if invalid:
            raise ValueError(f"Invalid amino acids: {sorted(invalid)}")

        return v


class PredictionRequest(BaseModel):
    """Request for structure prediction."""

    sequences: list[SequenceInput] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of sequences to predict"
    )
    name: str = Field(
        default="prediction",
        max_length=50,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Job name (alphanumeric, underscores, hyphens only)"
    )
    recycling_steps: int = Field(
        default=1,
        ge=1,
        le=10,
        description="Number of recycling steps"
    )
    sampling_steps: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Number of diffusion sampling steps"
    )
    diffusion_samples: int = Field(
        default=1,
        ge=1,
        le=5,
        description="Number of diffusion samples"
    )


class ConfidenceMetrics(BaseModel):
    """Confidence metrics for a prediction."""

    confidence_score: float | None = None
    complex_plddt: float | None = None
    ptm: float | None = None


class PredictionResult(BaseModel):
    """Result of a structure prediction."""

    structure_pdb: str
    confidence: ConfidenceMetrics
    plddt_per_residue: list[float]


class JobStatus(BaseModel):
    """Job status response."""

    status: Literal["queued", "running", "completed", "failed"]
    progress: float = 0.0
    result: PredictionResult | None = None
    error: str | None = None
