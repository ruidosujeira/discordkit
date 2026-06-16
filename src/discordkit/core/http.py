"""
discordkit.core.http
====================

Async Discord REST client built on httpx + Pydantic.

Responsibilities:
- Authentication via Bot token
- Rate limit handling (basic version for v1)
- JSON serialization/deserialization with Pydantic
- Clean error types

This is intentionally kept relatively low-level. Higher-level APIs (commands,
interactions) are built on top of this.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from pydantic import BaseModel

from ..models.base import DiscordModel
from .rate_limit import RateLimiter

logger = logging.getLogger(__name__)

DISCORD_API_BASE = "https://discord.com/api/v10"


class DiscordHTTPError(Exception):
    """Base error for all REST-related failures."""

    def __init__(self, status: int, message: str, response: Any | None = None) -> None:
        self.status = status
        self.message = message
        self.response = response
        super().__init__(f"Discord HTTP {status}: {message}")


class DiscordHTTPClient:
    """Async HTTP client for Discord REST API.

    Example:
        async with DiscordHTTPClient(token=...) as client:
            user = await client.get_current_user()
    """

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DISCORD_API_BASE,
        timeout: float = 15.0,
        user_agent: str = "DiscordKit",
    ) -> None:
        self._token = token
        self._base_url = base_url.rstrip("/")
        self._rate_limiter = RateLimiter()

        headers = {
            "Authorization": f"Bot {token}",
            "User-Agent": user_agent,
            "Content-Type": "application/json",
        }

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
            # http2=True requires the optional "h2" package.
            # Users who want HTTP/2 can install "httpx[http2]" and flip this.
            http2=False,
        )

    def _get_bucket_key(self, path: str) -> str:
        """Generate a simple bucket key from the path.

        Discord uses more sophisticated bucketing, but this provides a good
        approximation for most common routes (per major resource).
        """
        # Normalize common routes for better bucketing
        parts = [p for p in path.strip("/").split("/") if p]
        if not parts:
            return "root"
        # Group by first two meaningful segments (e.g. /guilds/{id}/channels -> guilds/id)
        key_parts = parts[:2]
        return "/".join(key_parts)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | BaseModel | None = None,
        params: dict[str, Any] | None = None,
        expect_model: type[DiscordModel] | None = None,
        _retry_count: int = 0,
    ) -> Any:
        """Perform a raw request with intelligent rate limit handling.

        Automatically respects Discord rate limits using headers and 429 responses.
        Will back off and retry on rate limits (up to a reasonable limit).
        """
        if isinstance(json, BaseModel):
            json = json.model_dump(mode="json", by_alias=True, exclude_none=True)

        bucket = self._get_bucket_key(path)

        # Wait for rate limit clearance if we know we're limited
        await self._rate_limiter.acquire(bucket)

        logger.debug("HTTP %s %s (bucket=%s)", method, path, bucket)

        resp = await self._client.request(
            method=method.upper(),
            url=path,
            json=json,
            params=params,
        )

        headers = dict(resp.headers)
        body: dict[str, Any] | None = None

        if resp.status_code == 429:
            try:
                body = resp.json()
            except Exception:
                body = {"message": resp.text}

        # Always update rate limiter state
        self._rate_limiter.update(headers, resp.status_code, body)

        if resp.status_code == 429:
            retry_after = 1.0
            if body and isinstance(body.get("retry_after"), (int, float)):
                retry_after = float(body["retry_after"])
            elif "X-RateLimit-Reset-After" in headers:
                try:
                    retry_after = float(headers["X-RateLimit-Reset-After"])
                except ValueError:
                    pass

            logger.warning(
                "Rate limited on %s %s (global=%s). Backing off for %.2fs",
                method,
                path,
                body.get("global") if body else False,
                retry_after,
            )

            if _retry_count < 2:  # Allow up to 2 retries on rate limits
                await asyncio.sleep(retry_after + 0.05)
                return await self.request(
                    method,
                    path,
                    json=json,
                    params=params,
                    expect_model=expect_model,
                    _retry_count=_retry_count + 1,
                )
            else:
                # Give up after retries
                try:
                    data = body or resp.text
                except Exception:
                    data = resp.text
                raise DiscordHTTPError(429, f"Rate limited after retries: {data}", data)

        if resp.status_code >= 400:
            try:
                data = resp.json()
            except Exception:
                data = resp.text
            raise DiscordHTTPError(resp.status_code, str(data), data)

        if resp.status_code == 204:
            return None

        data = resp.json()
        if expect_model is not None:
            return expect_model.model_validate(data)
        return data

    # ------------------------------------------------------------------
    # Convenience methods (expand as needed)
    # ------------------------------------------------------------------

    async def get_current_user(self) -> dict[str, Any]:
        result: Any = await self.request("GET", "/users/@me")
        return result  # type: ignore[no-any-return]

    async def get_application_commands(self, application_id: int) -> list[dict[str, Any]]:
        result: Any = await self.request("GET", f"/applications/{application_id}/commands")
        return result  # type: ignore[no-any-return]

    async def bulk_overwrite_global_commands(
        self, application_id: int, commands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # request() json accepts dict | BaseModel | None; list is accepted at runtime by httpx/json
        result: Any = await self.request(
            "PUT",
            f"/applications/{application_id}/commands",
            json=commands,  # type: ignore[arg-type]
        )
        return result  # type: ignore[no-any-return]

    async def create_interaction_response(
        self,
        interaction_id: int,
        interaction_token: str,
        *,
        payload: dict[str, Any],
    ) -> None:
        # Responses use a special endpoint without the Bot prefix in some cases,
        # but since we use the main client it works.
        path = f"/interactions/{interaction_id}/{interaction_token}/callback"
        await self.request("POST", path, json=payload)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> DiscordHTTPClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()


__all__ = ["DiscordHTTPClient", "DiscordHTTPError"]
