"""Sequence alignment API routes."""

from typing import Literal

from Bio import pairwise2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..logger import get_logger

logger = get_logger("routes.alignment")
router = APIRouter(prefix="/api", tags=["alignment"])


class AlignmentRequest(BaseModel):
    """Request for sequence alignment."""

    sequences: list[str] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Two sequences to align"
    )
    algorithm: Literal["global", "local"] = Field(
        default="global",
        description="Alignment algorithm: global (Needleman-Wunsch) or local (Smith-Waterman)"
    )


class AlignmentResult(BaseModel):
    """Result of sequence alignment."""

    aligned_seq1: str
    aligned_seq2: str
    score: float
    identity: float
    identity_count: int
    alignment_length: int
    gaps: int


def calculate_alignment_stats(seq1: str, seq2: str) -> dict:
    """Calculate alignment statistics.

    Args:
        seq1: First aligned sequence (with gaps)
        seq2: Second aligned sequence (with gaps)

    Returns:
        Dictionary with identity count, alignment length, and gaps
    """
    identity_count = 0
    gaps = 0

    for a, b in zip(seq1, seq2):
        if a == "-" or b == "-":
            gaps += 1
        elif a == b:
            identity_count += 1

    alignment_length = len(seq1)
    identity = identity_count / alignment_length if alignment_length > 0 else 0

    return {
        "identity_count": identity_count,
        "alignment_length": alignment_length,
        "gaps": gaps,
        "identity": identity
    }


@router.post("/align")
async def align_sequences(request: AlignmentRequest) -> AlignmentResult:
    """Align two sequences using pairwise alignment.

    Args:
        request: Alignment request with two sequences

    Returns:
        Alignment result with aligned sequences and statistics

    Raises:
        HTTPException: If alignment fails
    """
    seq1 = request.sequences[0].upper().strip()
    seq2 = request.sequences[1].upper().strip()

    if len(seq1) < 5 or len(seq2) < 5:
        raise HTTPException(
            status_code=400,
            detail="Both sequences must be at least 5 residues long"
        )

    if len(seq1) > 1000 or len(seq2) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Sequences must be at most 1000 residues long"
        )

    try:
        if request.algorithm == "global":
            alignments = pairwise2.align.globalxx(seq1, seq2)
        else:
            alignments = pairwise2.align.localxx(seq1, seq2)

        if not alignments:
            raise HTTPException(
                status_code=500,
                detail="No alignment found"
            )

        # Get the best alignment
        best = alignments[0]
        aligned_seq1 = best.seqA
        aligned_seq2 = best.seqB
        score = best.score

        # Calculate statistics
        stats = calculate_alignment_stats(aligned_seq1, aligned_seq2)

        logger.info(f"Alignment completed: identity={stats['identity']:.2%}")

        return AlignmentResult(
            aligned_seq1=aligned_seq1,
            aligned_seq2=aligned_seq2,
            score=score,
            identity=stats["identity"],
            identity_count=stats["identity_count"],
            alignment_length=stats["alignment_length"],
            gaps=stats["gaps"]
        )

    except Exception as e:
        logger.error(f"Alignment failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Alignment failed: {str(e)}"
        )
