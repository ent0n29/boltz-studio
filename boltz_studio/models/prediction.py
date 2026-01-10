"""Prediction request/response models with validation."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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
    sequence: str | None = Field(
        default=None,
        description="Amino acid sequence (for protein/dna/rna)"
    )
    smiles: str | None = Field(
        default=None,
        description="SMILES string (for ligand)"
    )
    type: Literal["protein", "dna", "rna", "ligand"] = Field(
        default="protein",
        description="Molecule type"
    )

    @model_validator(mode="after")
    def validate_sequence_or_smiles(self) -> "SequenceInput":
        """Validate that sequence or smiles is provided based on type."""
        if self.type == "ligand":
            if not self.smiles:
                raise ValueError("Ligand requires 'smiles' field")
            # Basic SMILES validation - check for valid characters
            if len(self.smiles.strip()) < 1:
                raise ValueError("SMILES string cannot be empty")
        else:
            if not self.sequence:
                raise ValueError(f"{self.type} requires 'sequence' field")
            # Validate protein sequences
            if self.type == "protein":
                seq = self.sequence.upper().strip()
                if len(seq) < settings.min_sequence_length:
                    raise ValueError(
                        f"Sequence too short: minimum {settings.min_sequence_length} residues"
                    )
                if len(seq) > settings.max_sequence_length:
                    raise ValueError(
                        f"Sequence too long: maximum {settings.max_sequence_length} residues"
                    )
                invalid = set(seq) - VALID_AMINO_ACIDS
                if invalid:
                    raise ValueError(f"Invalid amino acids: {sorted(invalid)}")
                self.sequence = seq
        return self


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


class BatchPredictionRequest(BaseModel):
    """Request for batch structure prediction of multiple independent sequences."""

    sequences: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="List of protein sequences to predict"
    )
    name_prefix: str = Field(
        default="batch",
        max_length=30,
        pattern=r"^[a-zA-Z0-9_-]+$",
        description="Prefix for job names"
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

    @field_validator("sequences")
    @classmethod
    def validate_sequences(cls, v: list[str]) -> list[str]:
        """Validate all sequences in the batch."""
        validated = []
        for i, seq in enumerate(v):
            seq = seq.upper().strip()
            if len(seq) < settings.min_sequence_length:
                raise ValueError(f"Sequence {i+1} too short: minimum {settings.min_sequence_length} residues")
            if len(seq) > settings.max_sequence_length:
                raise ValueError(f"Sequence {i+1} too long: maximum {settings.max_sequence_length} residues")
            invalid = set(seq) - VALID_AMINO_ACIDS
            if invalid:
                raise ValueError(f"Sequence {i+1} has invalid amino acids: {sorted(invalid)}")
            validated.append(seq)
        return validated


class ConfidenceMetrics(BaseModel):
    """Confidence metrics for a prediction."""

    confidence_score: float | None = None
    complex_plddt: float | None = None
    ptm: float | None = None


class AffinityMetrics(BaseModel):
    """Binding affinity metrics for protein-ligand predictions."""

    affinity_pred_value: float | None = None
    affinity_probability_binary: float | None = None


class PredictionResult(BaseModel):
    """Result of a structure prediction."""

    structure_pdb: str
    confidence: ConfidenceMetrics
    plddt_per_residue: list[float]
    affinity: AffinityMetrics | None = None


class JobStatus(BaseModel):
    """Job status response."""

    status: Literal["queued", "running", "completed", "failed"]
    progress: float = 0.0
    result: PredictionResult | None = None
    error: str | None = None
