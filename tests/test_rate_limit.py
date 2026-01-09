"""Tests for rate limiting middleware."""

import pytest
from fastapi import HTTPException


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_allows_within_limit(self, rate_limiter, mock_request):
        """Test that requests within limit are allowed."""
        # Should allow up to 5 requests (configured in fixture)
        for i in range(5):
            await rate_limiter.check(mock_request)

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, rate_limiter, mock_request):
        """Test that requests over limit are blocked."""
        # Use up the limit
        for _ in range(5):
            await rate_limiter.check(mock_request)

        # Next request should fail
        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter.check(mock_request)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail

    def test_get_remaining(self, rate_limiter, mock_request):
        """Test remaining request count."""
        assert rate_limiter.get_remaining(mock_request) == 5

    @pytest.mark.asyncio
    async def test_remaining_decreases(self, rate_limiter, mock_request):
        """Test that remaining count decreases."""
        assert rate_limiter.get_remaining(mock_request) == 5

        await rate_limiter.check(mock_request)
        assert rate_limiter.get_remaining(mock_request) == 4

        await rate_limiter.check(mock_request)
        assert rate_limiter.get_remaining(mock_request) == 3

    @pytest.mark.asyncio
    async def test_different_ips_separate_limits(self, rate_limiter):
        """Test that different IPs have separate limits."""
        from unittest.mock import MagicMock

        request1 = MagicMock()
        request1.client.host = "192.168.1.1"
        request1.headers = {}

        request2 = MagicMock()
        request2.client.host = "192.168.1.2"
        request2.headers = {}

        # Use up limit for IP 1
        for _ in range(5):
            await rate_limiter.check(request1)

        # IP 1 should be blocked
        with pytest.raises(HTTPException):
            await rate_limiter.check(request1)

        # IP 2 should still be allowed
        await rate_limiter.check(request2)
        assert rate_limiter.get_remaining(request2) == 4

    def test_forwarded_header(self, rate_limiter):
        """Test X-Forwarded-For header handling."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"x-forwarded-for": "203.0.113.50, 70.41.3.18"}

        # Should use first IP in chain
        ip = rate_limiter._get_client_ip(request)
        assert ip == "203.0.113.50"

    def test_no_client(self, rate_limiter):
        """Test handling of request with no client."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.client = None
        request.headers = {}

        ip = rate_limiter._get_client_ip(request)
        assert ip == "unknown"

    @pytest.mark.asyncio
    async def test_retry_after_header(self, rate_limiter, mock_request):
        """Test that blocked response includes Retry-After header."""
        # Use up the limit
        for _ in range(5):
            await rate_limiter.check(mock_request)

        with pytest.raises(HTTPException) as exc_info:
            await rate_limiter.check(mock_request)

        assert "Retry-After" in exc_info.value.headers
        assert exc_info.value.headers["Retry-After"] == "60"


class TestRateLimiterConfiguration:
    """Tests for rate limiter configuration."""

    def test_custom_rpm(self):
        """Test custom requests per minute."""
        from boltz_studio.middleware.rate_limit import RateLimiter

        limiter = RateLimiter(requests_per_minute=100)
        assert limiter.rpm == 100

    def test_default_rpm_from_settings(self):
        """Test default RPM from settings."""
        from boltz_studio.middleware.rate_limit import RateLimiter

        limiter = RateLimiter()
        # Default from settings is 10
        assert limiter.rpm == 10

    def test_singleton_getter(self):
        """Test singleton getter returns same instance."""
        from boltz_studio.middleware.rate_limit import get_rate_limiter

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2
