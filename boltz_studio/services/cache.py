"""Simple in-memory cache with TTL support."""

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, TypeVar

from ..logger import get_logger

logger = get_logger("cache")

T = TypeVar("T")


@dataclass
class CacheEntry:
    """A cached value with expiration time."""

    value: Any
    expires_at: float


@dataclass
class TTLCache:
    """Thread-safe in-memory cache with time-to-live expiration.

    Useful for caching expensive computations like trending scores,
    leaderboard data, and popular tags.

    Example:
        cache = TTLCache(default_ttl=300)  # 5 minutes

        # Simple get/set
        cache.set("trending", trending_data)
        data = cache.get("trending")

        # Get or compute
        data = cache.get_or_set("trending", compute_trending, ttl=600)
    """

    default_ttl: float = 300.0  # 5 minutes default
    max_size: int = 1000
    _data: dict[str, CacheEntry] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    def get(self, key: str) -> Any | None:
        """Get a value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if missing/expired
        """
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None

            if time.time() > entry.expires_at:
                # Expired, remove it
                del self._data[key]
                return None

            return entry.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Set a value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if not specified)
        """
        ttl = ttl if ttl is not None else self.default_ttl

        with self._lock:
            # Evict if at capacity
            if len(self._data) >= self.max_size:
                self._evict_expired()
                # If still at capacity, remove oldest
                if len(self._data) >= self.max_size:
                    oldest_key = min(self._data, key=lambda k: self._data[k].expires_at)
                    del self._data[oldest_key]

            self._data[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl,
            )

    def get_or_set(
        self, key: str, factory: Callable[[], T], ttl: float | None = None
    ) -> T:
        """Get value from cache, or compute and cache it.

        This is the most common usage pattern - get cached value or
        compute it if missing/expired.

        Args:
            key: Cache key
            factory: Function to compute value if not cached
            ttl: Time-to-live in seconds

        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is not None:
            logger.debug(f"Cache hit: {key}")
            return value

        logger.debug(f"Cache miss: {key}")
        value = factory()
        self.set(key, value, ttl)
        return value

    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache.

        Args:
            key: Cache key to remove

        Returns:
            True if key was in cache
        """
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove all keys with a given prefix.

        Useful for invalidating related cache entries.

        Args:
            prefix: Key prefix to match

        Returns:
            Number of keys removed
        """
        with self._lock:
            keys_to_remove = [k for k in self._data if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._data[key]
            return len(keys_to_remove)

    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            self._data.clear()

    def _evict_expired(self) -> None:
        """Remove expired entries (called with lock held)."""
        now = time.time()
        expired = [k for k, v in self._data.items() if v.expires_at < now]
        for key in expired:
            del self._data[key]

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with size and entry info
        """
        with self._lock:
            now = time.time()
            return {
                "size": len(self._data),
                "max_size": self.max_size,
                "expired_count": sum(1 for v in self._data.values() if v.expires_at < now),
            }


# Global cache instances for different purposes
_caches: dict[str, TTLCache] = {}


def get_cache(name: str = "default", ttl: float = 300.0) -> TTLCache:
    """Get or create a named cache instance.

    Args:
        name: Cache name (e.g., "trending", "leaderboard")
        ttl: Default TTL for this cache

    Returns:
        TTLCache instance
    """
    if name not in _caches:
        _caches[name] = TTLCache(default_ttl=ttl)
    return _caches[name]


# Pre-configured caches for common use cases
trending_cache = get_cache("trending", ttl=300)  # 5 minutes
leaderboard_cache = get_cache("leaderboard", ttl=600)  # 10 minutes
popular_tags_cache = get_cache("popular_tags", ttl=900)  # 15 minutes
