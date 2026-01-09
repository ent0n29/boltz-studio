"""WebSocket routes for real-time job updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..logger import get_logger
from ..services.job_store import get_job_store
from ..services.progress_manager import get_progress_manager

logger = get_logger("routes.websocket")
router = APIRouter(tags=["websocket"])


@router.websocket("/ws/job/{job_id}")
async def job_progress_websocket(websocket: WebSocket, job_id: str) -> None:
    """WebSocket endpoint for real-time job progress updates.

    Clients connect to this endpoint to receive live updates about job
    status and progress without polling.

    Args:
        websocket: WebSocket connection
        job_id: Job to subscribe to
    """
    store = get_job_store()
    manager = get_progress_manager()

    # Check if job exists
    if not store.exists(job_id):
        await websocket.close(code=4004, reason="Job not found")
        return

    # Subscribe to updates
    await manager.subscribe(job_id, websocket)
    logger.info(f"WebSocket connected for job {job_id}")

    # Send current state immediately
    job = store.get(job_id)
    if job:
        await websocket.send_json(job)

    try:
        # Keep connection alive, wait for disconnect
        while True:
            # Wait for any message (ping/pong or close)
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for job {job_id}")
    finally:
        await manager.unsubscribe(job_id, websocket)
