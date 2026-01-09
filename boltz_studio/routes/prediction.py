"""Prediction API routes."""

import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from ..logger import get_logger
from ..middleware.rate_limit import rate_limit_dependency
from ..models import PredictionRequest
from ..services import BoltzRunner, JobStore, get_job_store

logger = get_logger("routes.prediction")
router = APIRouter(prefix="/api", tags=["prediction"])


def get_runner(store: JobStore = Depends(get_job_store)) -> BoltzRunner:
    """Dependency injection for BoltzRunner.

    Args:
        store: JobStore instance

    Returns:
        Configured BoltzRunner
    """
    return BoltzRunner(store)


@router.post("/predict")
async def predict(
    request: PredictionRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    store: JobStore = Depends(get_job_store),
    runner: BoltzRunner = Depends(get_runner),
    _: None = Depends(rate_limit_dependency()),
) -> dict[str, str]:
    """Submit a structure prediction job.

    Rate limited to prevent abuse.

    Args:
        request: Prediction request with sequences
        http_request: HTTP request for rate limiting
        background_tasks: FastAPI background tasks
        store: Job store instance
        runner: Boltz runner instance

    Returns:
        Job ID and status
    """
    job_id = str(uuid.uuid4())[:8]
    store.create(job_id)
    background_tasks.add_task(runner.run, job_id, request)
    logger.info(f"Prediction submitted: job_id={job_id}")
    return {"job_id": job_id, "status": "queued"}


@router.get("/job/{job_id}")
async def get_job(
    job_id: str,
    store: JobStore = Depends(get_job_store),
) -> dict[str, Any]:
    """Get job status and results.

    Args:
        job_id: Job identifier
        store: Job store instance

    Returns:
        Job data including status and results

    Raises:
        HTTPException: If job not found
    """
    job = store.get(job_id)
    if not job:
        logger.warning(f"Job not found: {job_id}")
        raise HTTPException(status_code=404, detail="Job not found")
    return job
