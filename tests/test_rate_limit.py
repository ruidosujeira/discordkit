"""
Tests for intelligent rate limit handling.
"""

from __future__ import annotations

import asyncio

import pytest

from discordkit.core.rate_limit import RateLimiter


class TestRateLimiter:
    def test_update_from_headers(self):
        rl = RateLimiter()
        headers = {
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Reset-After": "1.5",
            "X-RateLimit-Bucket": "test-bucket",
        }
        info = rl.update(headers, 200)
        assert info.remaining == 5
        assert info.bucket == "test-bucket"

    @pytest.mark.asyncio
    async def test_acquire_and_backoff(self):
        rl = RateLimiter()
        # Simulate a 429
        headers = {"X-RateLimit-Reset-After": "0.1", "X-RateLimit-Bucket": "b1"}
        rl.update(headers, 429, {"retry_after": 0.05, "global": False})

        start = asyncio.get_event_loop().time()
        await rl.acquire("b1")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.04  # should have waited


class TestHTTPRateLimitIntegration:
    """Lightweight integration test (no real network)."""

    def test_client_has_rate_limiter(self, test_client):
        # The HTTP client inside should have a rate limiter
        http_client = test_client.http
        assert hasattr(http_client, "_rate_limiter")
        assert http_client._rate_limiter is not None
