"""Design tools API routes."""

import random

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["design"])

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"


@router.post("/random-mutate")
async def random_mutate(sequence: str, num_mutations: int = 1):
    """Generate random mutations in sequence."""
    seq = list(sequence)
    mutations = []

    positions = random.sample(range(len(seq)), min(num_mutations, len(seq)))
    for pos in positions:
        orig = seq[pos]
        new = random.choice([a for a in AMINO_ACIDS if a != orig])
        mutations.append(f"{orig}{pos + 1}{new}")
        seq[pos] = new

    return {"mutated_sequence": "".join(seq), "mutations": mutations}
