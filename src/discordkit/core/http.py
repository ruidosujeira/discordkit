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

import logging
from typing import Any

import httpx
from pydantic import BaseModel

from ..models.base import DiscordModel

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

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | BaseModel | None = None,
        params: dict[str, Any] | None = None,
        expect_model: type[DiscordModel] | None = None,
    ) -> Any:
        """Perform a raw request. Returns dict or validated Pydantic model."""
        if isinstance(json, BaseModel):
            json = json.model_dump(mode="json", by_alias=True, exclude_none=True)

        url = f"{self._base_url}{path}" if path.startswith("/") else f"{self._base_url}/{path}"

        logger.debug("HTTP %s %s", method, path)

        resp = await self._client.request(
            method=method.upper(),
            url=path,
            json=json,
            params=params,
        )

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
        return await self.request("GET", "/users/@me")

    async def get_application_commands(self, application_id: int) -> list[dict[str, Any]]:
        return await self.request("GET", f"/applications/{application_id}/commands")

    async def bulk_overwrite_global_commands(
        self, application_id: int, commands: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        return await self.request(
            "PUT",
            f"/applications/{application_id}/commands",
            json=commands,
        )

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
