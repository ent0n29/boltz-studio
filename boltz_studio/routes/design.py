"""Design tools API routes."""

import random

from fastapi import APIRouter, Query

from ..models import VALID_AMINO_ACIDS

router = APIRouter(prefix="/api", tags=["design"])

AMINO_ACIDS = "".join(sorted(VALID_AMINO_ACIDS))


@router.post("/random-mutate")
async def random_mutate(
    sequence: str = Query(..., min_length=5, max_length=2000),
    num_mutations: int = Query(default=1, ge=1, le=10),
) -> dict[str, str | list[str]]:
    """Generate random mutations in sequence.

    Args:
        sequence: Input amino acid sequence
        num_mutations: Number of random mutations to introduce

    Returns:
        Mutated sequence and list of mutations
    """
    seq = list(sequence.upper())
    mutations: list[str] = []

    positions = random.sample(range(len(seq)), min(num_mutations, len(seq)))
    for pos in positions:
        orig = seq[pos]
        new = random.choice([a for a in AMINO_ACIDS if a != orig])
        mutations.append(f"{orig}{pos + 1}{new}")
        seq[pos] = new

    return {"mutated_sequence": "".join(seq), "mutations": mutations}
