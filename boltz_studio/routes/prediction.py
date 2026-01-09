"""Prediction API routes."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from ..models import PredictionRequest
from ..services import JobStore, BoltzRunner, get_job_store

router = APIRouter(prefix="/api", tags=["prediction"])


def get_runner(store: JobStore = Depends(get_job_store)) -> BoltzRunner:
    """Dependency injection for BoltzRunner."""
    return BoltzRunner(store)


@router.post("/predict")
async def predict(
    request: PredictionRequest,
    background_tasks: BackgroundTasks,
    store: JobStore = Depends(get_job_store),
    runner: BoltzRunner = Depends(get_runner),
):
    """Submit a structure prediction job."""
    job_id = str(uuid.uuid4())[:8]
    store.create(job_id)
    background_tasks.add_task(runner.run, job_id, request)
    return {"job_id": job_id, "status": "queued"}


@router.get("/job/{job_id}")
async def get_job(job_id: str, store: JobStore = Depends(get_job_store)):
    """Get job status and results."""
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
