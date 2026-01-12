"""Rate limiting for API endpoints."""

import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request

from ..config import settings
from ..logger import get_logger

logger = get_logger("rate_limit")


class RateLimiter:
    """Token bucket rate limiter for API requests.

    Limits requests per IP address within a sliding time window.
    """

    def __init__(self, requests_per_minute: int | None = None) -> None:
        """Initialize rate limiter.

        Args:
            requests_per_minute: Max requests per minute per IP
        """
        self.rpm = requests_per_minute or settings.requests_per_minute
        self.window_seconds = 60
        # Track request timestamps per IP: {ip: [timestamp1, timestamp2, ...]}
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request.

        Handles X-Forwarded-For header for reverse proxy setups.

        Args:
            request: FastAPI request

        Returns:
            Client IP address
        """
        # Check for forwarded header (reverse proxy)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Take first IP in chain (original client)
            return forwarded.split(",")[0].strip()

        # Fall back to direct connection
        if request.client:
            return request.client.host
        return "unknown"

    def _cleanup_old_requests(self, ip: str, now: float) -> None:
        """Remove request timestamps outside the current window.

        Args:
            ip: Client IP
            now: Current timestamp
        """
        cutoff = now - self.window_seconds
        self._requests[ip] = [
            ts for ts in self._requests[ip] if ts > cutoff
        ]

    async def check(self, request: Request) -> None:
        """Check if request is allowed under rate limit.

        Args:
            request: FastAPI request

        Raises:
            HTTPException: 429 Too Many Requests if limit exceeded
        """
        ip = self._get_client_ip(request)
        now = time.time()

        # Clean old requests
        self._cleanup_old_requests(ip, now)

        # Check limit
        if len(self._requests[ip]) >= self.rpm:
            logger.warning(f"Rate limit exceeded for {ip}")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {self.rpm} requests per minute.",
                headers={"Retry-After": "60"},
            )

        # Record this request
        self._requests[ip].append(now)

    def get_remaining(self, request: Request) -> int:
        """Get remaining requests for this client.

        Args:
            request: FastAPI request

        Returns:
            Number of remaining requests in current window
        """
        ip = self._get_client_ip(request)
        now = time.time()
        self._cleanup_old_requests(ip, now)
        return max(0, self.rpm - len(self._requests[ip]))


# Singleton instance
_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get singleton rate limiter instance.

    Returns:
        RateLimiter instance
    """
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter


def rate_limit_dependency() -> Callable:
    """Create a FastAPI dependency for rate limiting.

    Usage:
        @router.post("/predict")
        async def predict(
            request: Request,
            _: None = Depends(rate_limit_dependency()),
        ):
            ...

    Returns:
        Dependency callable
    """
    async def check_rate_limit(request: Request) -> None:
        limiter = get_rate_limiter()
        await limiter.check(request)

    return check_rate_limit


# Endpoint-specific rate limiters
_endpoint_limiters: dict[str, RateLimiter] = {}


def get_endpoint_limiter(endpoint: str, rpm: int) -> RateLimiter:
    """Get or create an endpoint-specific rate limiter.

    Args:
        endpoint: Endpoint name/identifier
        rpm: Requests per minute for this endpoint

    Returns:
        RateLimiter instance
    """
    global _endpoint_limiters
    if endpoint not in _endpoint_limiters:
        _endpoint_limiters[endpoint] = RateLimiter(rpm)
    return _endpoint_limiters[endpoint]


def rate_limit(rpm: int = 60):
    """Create a rate limit dependency with custom RPM.

    Usage:
        @router.post("/export")
        async def export(
            request: Request,
            _: None = Depends(rate_limit(rpm=10)),
        ):
            ...

    Args:
        rpm: Requests per minute

    Returns:
        Dependency callable
    """
    async def check_rate_limit(request: Request) -> None:
        # Use path as endpoint identifier
        endpoint = request.url.path
        limiter = get_endpoint_limiter(endpoint, rpm)
        await limiter.check(request)

    return check_rate_limit


# Pre-configured rate limits for common operations
auth_rate_limit = rate_limit(rpm=10)  # Auth operations: 10/min
prediction_rate_limit = rate_limit(rpm=5)  # Predictions: 5/min
export_rate_limit = rate_limit(rpm=10)  # Exports: 10/min
search_rate_limit = rate_limit(rpm=30)  # Searches: 30/min
