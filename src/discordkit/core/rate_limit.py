"""
discordkit.core.rate_limit
==========================

Intelligent rate limit handling for the Discord REST API.

Features:
- Automatic detection and respect of 429 responses
- Parsing of X-RateLimit-* headers (remaining, reset, bucket, global)
- Automatic backoff with sleep (using asyncio)
- Retry logic for rate limited requests (with reasonable limits)
- Logging of rate limit events

This is integrated transparently into DiscordHTTPClient.request().
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RateLimitInfo:
    """Parsed rate limit information from Discord headers."""
    limit: int | None = None
    remaining: int | None = None
    reset: float | None = None
    reset_after: float | None = None
    bucket: str | None = None
    is_global: bool = False


class RateLimiter:
    """Manages rate limits for Discord API requests.

    This is a per-client rate limiter. It tracks global rate limits and
    per-bucket limits based on headers returned by Discord.
    """

    def __init__(self) -> None:
        self._global_reset: float | None = None
        self._buckets: dict[str, RateLimitInfo] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, bucket: str | None = None) -> None:
        """Wait if necessary before making a request for this bucket."""
        async with self._lock:
            now = time.monotonic()

            # Global rate limit
            if self._global_reset and now < self._global_reset:
                wait = self._global_reset - now
                logger.warning("Global rate limit hit. Waiting %.2fs", wait)
                await asyncio.sleep(wait)
                self._global_reset = None

            # Bucket specific
            if bucket and bucket in self._buckets:
                info = self._buckets[bucket]
                if info.remaining is not None and info.remaining <= 0 and info.reset:
                    if now < info.reset:
                        wait = info.reset - now + 0.1  # small buffer
                        logger.info("Rate limit for bucket %s. Waiting %.2fs", bucket, wait)
                        await asyncio.sleep(wait)

    def update(self, headers: dict[str, str], status_code: int, body: dict[str, Any] | None = None) -> RateLimitInfo:
        """Update rate limit state from response headers."""
        info = RateLimitInfo()

        # Parse common headers (Discord sends them as strings)
        try:
            if "X-RateLimit-Limit" in headers:
                info.limit = int(headers["X-RateLimit-Limit"])
            if "X-RateLimit-Remaining" in headers:
                info.remaining = int(headers["X-RateLimit-Remaining"])
            if "X-RateLimit-Reset" in headers:
                info.reset = float(headers["X-RateLimit-Reset"])
            if "X-RateLimit-Reset-After" in headers:
                info.reset_after = float(headers["X-RateLimit-Reset-After"])
            if "X-RateLimit-Bucket" in headers:
                info.bucket = headers["X-RateLimit-Bucket"]
            if headers.get("X-RateLimit-Global", "").lower() == "true":
                info.is_global = True
        except (ValueError, TypeError):
            pass

        # Handle 429 specially (body may contain retry_after)
        if status_code == 429 and body:
            retry_after = body.get("retry_after")
            if retry_after is not None:
                reset_time = time.monotonic() + float(retry_after) + 0.1
                if info.is_global or body.get("global"):
                    self._global_reset = reset_time
                    logger.warning("Global rate limit triggered. Retry after %.2fs", retry_after)
                elif info.bucket:
                    self._buckets[info.bucket] = RateLimitInfo(
                        reset=reset_time,
                        remaining=0,
                        bucket=info.bucket,
                    )
                    logger.warning("Bucket %s rate limited. Retry after %.2fs", info.bucket, retry_after)

        # Update bucket info from headers if we have a bucket
        if info.bucket:
            if info.reset_after is not None:
                # Convert reset_after to absolute monotonic time
                info.reset = time.monotonic() + info.reset_after
            self._buckets[info.bucket] = info

        return info

    def get_bucket_info(self, bucket: str) -> RateLimitInfo | None:
        return self._buckets.get(bucket)


__all__ = ["RateLimiter", "RateLimitInfo"]
