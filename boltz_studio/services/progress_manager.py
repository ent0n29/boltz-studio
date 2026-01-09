"""WebSocket connection manager for real-time job updates."""

import asyncio
from typing import Any

from fastapi import WebSocket

from ..logger import get_logger

logger = get_logger("progress_manager")


class ProgressManager:
    """Manage WebSocket connections and broadcast job updates."""

    def __init__(self) -> None:
        # Map of job_id -> set of connected WebSockets
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str, websocket: WebSocket) -> None:
        """Subscribe a WebSocket to job updates.

        Args:
            job_id: Job to subscribe to
            websocket: WebSocket connection
        """
        await websocket.accept()
        async with self._lock:
            if job_id not in self._connections:
                self._connections[job_id] = set()
            self._connections[job_id].add(websocket)
        logger.debug(f"Client subscribed to job {job_id}")

    async def unsubscribe(self, job_id: str, websocket: WebSocket) -> None:
        """Unsubscribe a WebSocket from job updates.

        Args:
            job_id: Job to unsubscribe from
            websocket: WebSocket connection
        """
        async with self._lock:
            if job_id in self._connections:
                self._connections[job_id].discard(websocket)
                if not self._connections[job_id]:
                    del self._connections[job_id]
        logger.debug(f"Client unsubscribed from job {job_id}")

    async def broadcast(self, job_id: str, data: dict[str, Any]) -> None:
        """Broadcast update to all subscribers of a job.

        Args:
            job_id: Job that was updated
            data: Data to send to subscribers
        """
        async with self._lock:
            if job_id not in self._connections:
                return
            connections = self._connections[job_id].copy()

        dead_connections: list[WebSocket] = []

        for websocket in connections:
            try:
                await websocket.send_json(data)
            except Exception:
                dead_connections.append(websocket)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for ws in dead_connections:
                    if job_id in self._connections:
                        self._connections[job_id].discard(ws)

    def get_subscriber_count(self, job_id: str) -> int:
        """Get number of subscribers for a job.

        Args:
            job_id: Job identifier

        Returns:
            Number of active subscribers
        """
        return len(self._connections.get(job_id, set()))


# Singleton instance
progress_manager = ProgressManager()


def get_progress_manager() -> ProgressManager:
    """Get the singleton ProgressManager instance.

    Returns:
        ProgressManager instance
    """
    return progress_manager
