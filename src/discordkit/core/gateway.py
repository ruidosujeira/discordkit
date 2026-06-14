"""
discordkit.core.gateway
=======================

Discord Gateway (websocket) connection manager.

This module is responsible for:
- Connecting to wss://gateway.discord.gg
- Identifying the bot
- Heartbeating
- Receiving events and dispatching them
- Reconnection with backoff

Current version is a functional foundation. It will be expanded with
sharding, resume, proper session handling, etc.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Awaitable, Callable, Protocol

import websockets
from websockets.asyncio.client import ClientConnection

from ..types import Intents

logger = logging.getLogger(__name__)


class GatewayOpcode(IntEnum):
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE_UPDATE = 3
    VOICE_STATE_UPDATE = 4
    RESUME = 6
    RECONNECT = 7
    REQUEST_GUILD_MEMBERS = 8
    INVALID_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11


@dataclass(slots=True)
class GatewayEvent:
    """A parsed event received from the Discord gateway."""

    op: int
    t: str | None  # event name, e.g. "READY", "MESSAGE_CREATE"
    d: Any         # the actual data payload
    s: int | None  # sequence number


class EventHandler(Protocol):
    async def __call__(self, event: GatewayEvent) -> None: ...


class Gateway:
    """Manages the Discord Gateway websocket connection.

    You usually do not instantiate this directly. The `Client` owns it.
    """

    def __init__(
        self,
        token: str,
        intents: Intents,
        *,
        url: str = "wss://gateway.discord.gg/?v=10&encoding=json",
        on_event: EventHandler | None = None,
        on_ready: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.token = token
        self.intents = intents
        self._url = url
        self._on_event = on_event
        self._on_ready = on_ready

        self._ws: ClientConnection | None = None
        self._heartbeat_interval: float = 0.0
        self._last_sequence: int | None = None
        self._session_id: str | None = None
        self._running = False
        self._ready = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    async def connect(self) -> None:
        """Open the websocket and start the receive loop."""
        logger.info("Connecting to Discord Gateway...")
        self._ws = await websockets.connect(self._url)
        self._running = True

        # Start the main receive loop in background
        asyncio.create_task(self._run())

    async def _run(self) -> None:
        assert self._ws is not None

        try:
            async for raw in self._ws:
                event = self._parse_event(raw)
                await self._handle_event(event)
        except websockets.ConnectionClosed as exc:
            logger.warning("Gateway connection closed: %s", exc)
            await self._reconnect()
        except Exception as exc:
            logger.exception("Unexpected gateway error: %s", exc)
            await self._reconnect()

    def _parse_event(self, raw: str | bytes) -> GatewayEvent:
        data = json.loads(raw)
        return GatewayEvent(
            op=data.get("op", -1),
            t=data.get("t"),
            d=data.get("d"),
            s=data.get("s"),
        )

    async def _handle_event(self, event: GatewayEvent) -> None:
        if event.s is not None:
            self._last_sequence = event.s

        if event.op == GatewayOpcode.HELLO:
            await self._handle_hello(event)
        elif event.op == GatewayOpcode.HEARTBEAT_ACK:
            logger.debug("Heartbeat ACK received")
        elif event.op == GatewayOpcode.DISPATCH:
            if event.t == "READY":
                self._session_id = event.d.get("session_id")
                logger.info("Gateway READY - session %s", self._session_id)
                if self._on_ready:
                    await self._on_ready(event.d)
            if self._on_event:
                await self._on_event(event)
        elif event.op == GatewayOpcode.INVALID_SESSION:
            logger.warning("Invalid session. Will reconnect with new identify.")
            await asyncio.sleep(1 + (event.d or 0) * 4)
            await self._reconnect(force_new_session=True)
        elif event.op == GatewayOpcode.RECONNECT:
            logger.info("Gateway requested reconnect")
            await self._reconnect()

    async def _handle_hello(self, event: GatewayEvent) -> None:
        self._heartbeat_interval = event.d["heartbeat_interval"] / 1000.0
        logger.debug("Hello received. Heartbeat interval: %.1fs", self._heartbeat_interval)

        # Start heartbeating
        asyncio.create_task(self._heartbeat_loop())

        # Identify
        await self._identify()

    async def _identify(self) -> None:
        payload = {
            "op": GatewayOpcode.IDENTIFY,
            "d": {
                "token": self.token,
                "intents": int(self.intents),
                "properties": {
                    "os": "linux",
                    "browser": "discordkit",
                    "device": "discordkit",
                },
                "presence": {
                    "activities": [],
                    "status": "online",
                    "afk": False,
                },
            },
        }
        await self._send(payload)
        logger.info("IDENTIFY sent (intents=%s)", self.intents)

    async def _heartbeat_loop(self) -> None:
        while self._running and self.is_connected:
            await self._send({"op": GatewayOpcode.HEARTBEAT, "d": self._last_sequence})
            await asyncio.sleep(self._heartbeat_interval)

    async def _send(self, data: dict[str, Any]) -> None:
        if not self._ws or self._ws.closed:
            logger.warning("Attempted to send on closed gateway")
            return
        await self._ws.send(json.dumps(data))

    async def _reconnect(self, *, force_new_session: bool = False) -> None:
        logger.info("Reconnecting to gateway...")
        if self._ws:
            await self._ws.close()
        self._ws = None
        self._ready.clear()

        if force_new_session:
            self._session_id = None
            self._last_sequence = None

        # Simple backoff (production version will be more sophisticated)
        await asyncio.sleep(1.5)
        await self.connect()

    async def close(self) -> None:
        """Gracefully close the gateway connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
        logger.info("Gateway closed")

    async def wait_until_ready(self) -> None:
        """Block until we receive the READY event."""
        await self._ready.wait()


__all__ = ["Gateway", "GatewayEvent", "GatewayOpcode"]
