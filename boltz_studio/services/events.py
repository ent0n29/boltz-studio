"""Simple synchronous event dispatcher for loose coupling between stores.

This module provides a simple event system that allows stores to emit events
that other parts of the system can listen to, without creating direct dependencies.

Example usage:
    # In social_store.py
    from .events import events, DESIGN_STARRED

    def add_star(self, design_id: str, user_id: str) -> bool:
        # ... add star logic ...
        events.emit(DESIGN_STARRED, design_id=design_id, user_id=user_id, owner_id=owner_id)
        return True

    # In app.py - register handlers
    from .services.events import events, DESIGN_STARRED

    @events.on(DESIGN_STARRED)
    def on_star(design_id: str, user_id: str, owner_id: str):
        notification_store.notify_star(owner_id, user_id, design_id)
        activity_store.record(user_id, "starred", "design", design_id)
"""

from collections import defaultdict
from typing import Any, Callable

from ..logger import get_logger

logger = get_logger("events")


# Event names - use constants to avoid typos
DESIGN_CREATED = "design.created"
DESIGN_STARRED = "design.starred"
DESIGN_UNSTARRED = "design.unstarred"
DESIGN_FORKED = "design.forked"
DESIGN_DOWNLOADED = "design.downloaded"
DESIGN_VIEWED = "design.viewed"

COMMENT_CREATED = "comment.created"
COMMENT_DELETED = "comment.deleted"

USER_FOLLOWED = "user.followed"
USER_UNFOLLOWED = "user.unfollowed"

COLLECTION_CREATED = "collection.created"
COLLECTION_DESIGN_ADDED = "collection.design_added"

BADGE_EARNED = "badge.earned"
VALIDATION_ADDED = "validation.added"


class EventDispatcher:
    """Simple synchronous event dispatcher.

    Events are dispatched synchronously - all handlers run in the same thread
    before the emit() call returns. This keeps things simple and predictable.

    For async/background processing, handlers can enqueue work to a task queue.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def on(self, event: str) -> Callable[[Callable[..., None]], Callable[..., None]]:
        """Register an event handler.

        Can be used as a decorator:
            @events.on(DESIGN_STARRED)
            def handle_star(design_id: str, user_id: str, owner_id: str):
                ...

        Or called directly:
            events.on(DESIGN_STARRED)(handle_star)
        """
        def decorator(handler: Callable[..., None]) -> Callable[..., None]:
            self._handlers[event].append(handler)
            logger.debug(f"Registered handler for {event}: {handler.__name__}")
            return handler
        return decorator

    def emit(self, event: str, **data: Any) -> None:
        """Emit an event to all registered handlers.

        Args:
            event: Event name (use constants like DESIGN_STARRED)
            **data: Event data passed to handlers as keyword arguments
        """
        handlers = self._handlers.get(event, [])
        if not handlers:
            return

        logger.debug(f"Emitting {event} to {len(handlers)} handlers")

        for handler in handlers:
            try:
                handler(**data)
            except Exception as e:
                # Log but don't propagate - one failed handler shouldn't break others
                logger.error(f"Handler {handler.__name__} failed for {event}: {e}")

    def remove_handler(self, event: str, handler: Callable[..., None]) -> bool:
        """Remove a specific handler for an event.

        Returns:
            True if handler was found and removed
        """
        if event in self._handlers:
            try:
                self._handlers[event].remove(handler)
                return True
            except ValueError:
                pass
        return False

    def clear(self, event: str | None = None) -> None:
        """Clear handlers.

        Args:
            event: If specified, clear only handlers for this event.
                   If None, clear all handlers.
        """
        if event:
            self._handlers[event].clear()
        else:
            self._handlers.clear()


# Global event dispatcher singleton
events = EventDispatcher()
