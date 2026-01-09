"""Prediction request/response models."""

from pydantic import BaseModel


class SequenceInput(BaseModel):
    id: str = "A"
    sequence: str
    type: str = "protein"


class PredictionRequest(BaseModel):
    sequences: list[SequenceInput]
    name: str = "prediction"
    recycling_steps: int = 1
    sampling_steps: int = 50
    diffusion_samples: int = 1
