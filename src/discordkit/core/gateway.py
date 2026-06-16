"""
discordkit.core.gateway
=======================

Discord Gateway (websocket) connection manager.

This module is responsible for:
- Connecting to wss://gateway.discord.gg
- Identifying the bot (with shard info when sharding is enabled)
- Heartbeating, with HEARTBEAT_ACK tracking to detect zombie connections
- Receiving events and dispatching them
- Reconnection with exponential backoff
- Session resume (op 6 RESUME) to replay missed events after a drop

A single ``Gateway`` instance manages exactly one shard. The :class:`Client`
owns one ``Gateway`` per shard.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Protocol

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.protocol import State

from ..types import Intents

logger = logging.getLogger(__name__)

DEFAULT_GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json"

# Close codes after which reconnecting is pointless — the problem is in the
# bot's configuration, so retrying would just loop forever.
# https://discord.com/developers/docs/topics/opcodes-and-status-codes#gateway-gateway-close-event-codes
FATAL_CLOSE_CODES = frozenset(
    {
        4004,  # Authentication failed (bad token)
        4010,  # Invalid shard
        4011,  # Sharding required
        4012,  # Invalid API version
        4013,  # Invalid intent(s)
        4014,  # Disallowed intent(s)
    }
)

# Close codes where we may reconnect but the session is gone — we must start a
# fresh IDENTIFY rather than attempting to RESUME.
NON_RESUMABLE_CLOSE_CODES = frozenset(
    {
        4007,  # Invalid seq
        4009,  # Session timed out
    }
)


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
    d: Any  # the actual data payload
    s: int | None  # sequence number


class EventHandler(Protocol):
    async def __call__(self, event: GatewayEvent) -> None: ...


class Gateway:
    """Manages a single shard's Discord Gateway websocket connection.

    You usually do not instantiate this directly. The `Client` owns it (one
    instance per shard).
    """

    def __init__(
        self,
        token: str,
        intents: Intents,
        *,
        url: str = DEFAULT_GATEWAY_URL,
        on_event: EventHandler | None = None,
        on_ready: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
        shard_id: int = 0,
        shard_count: int = 1,
        reconnect_base_delay: float = 1.0,
        max_retries: int = 5,
    ) -> None:
        self.token = token
        self.intents = intents
        self.shard_id = shard_id
        self.shard_count = shard_count
        self._url = url
        self._on_event = on_event
        self._on_ready = on_ready
        self._reconnect_base_delay = reconnect_base_delay
        self._max_retries = max_retries

        self._ws: ClientConnection | None = None
        self._heartbeat_interval: float = 0.0
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._receive_task: asyncio.Task[None] | None = None
        self._last_heartbeat_acked: bool = True
        self._last_sequence: int | None = None
        self._session_id: str | None = None
        self._resume_gateway_url: str | None = None
        self._reconnect_attempts: int = 0
        self._running = False
        self._ready = asyncio.Event()

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._ws.state is State.OPEN

    @property
    def can_resume(self) -> bool:
        """Whether we hold enough session state to attempt an op 6 RESUME."""
        return self._session_id is not None and self._last_sequence is not None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self, *, resume: bool = False) -> None:
        """Open the websocket and start the receive loop.

        When ``resume`` is true and we have a ``resume_gateway_url`` from a
        previous READY, we reconnect there so Discord can replay missed events.
        """
        target = self._resume_gateway_url if (resume and self._resume_gateway_url) else self._url
        logger.info(
            "Connecting to Discord Gateway (shard=%s/%s, resume=%s)...",
            self.shard_id,
            self.shard_count,
            resume,
        )
        self._ws = await websockets.connect(self._with_query(target))
        self._running = True

        # Start the main receive loop in background (store ref to satisfy linters and allow cancel on close if needed)
        self._receive_task = asyncio.create_task(self._run())

    @staticmethod
    def _with_query(url: str) -> str:
        """Ensure the gateway URL carries the API version/encoding query.

        ``resume_gateway_url`` arrives without a query string, so we add it.
        """
        if "?" in url:
            return url
        return f"{url}?v=10&encoding=json"

    async def _run(self) -> None:
        assert self._ws is not None

        try:
            async for raw in self._ws:
                event = self._parse_event(raw)
                await self._handle_event(event)
        except websockets.ConnectionClosed as exc:
            if not self._running:
                return
            code = exc.code
            logger.warning("Gateway closed (code=%s, reason=%r)", code, exc.reason)
            if code in FATAL_CLOSE_CODES:
                logger.error("Fatal gateway close code %s — not reconnecting.", code)
                self._running = False
                return
            await self._reconnect(resume=code not in NON_RESUMABLE_CLOSE_CODES)
        except Exception as exc:
            if not self._running:
                return
            logger.exception("Unexpected gateway error: %s", exc)
            await self._reconnect(resume=True)
        else:
            # Iterator ended without an exception (a clean 1000/1001 close).
            if self._running:
                logger.info("Gateway stream ended; reconnecting (resume).")
                await self._reconnect(resume=True)

    def _parse_event(self, raw: str | bytes) -> GatewayEvent:
        data = json.loads(raw)
        return GatewayEvent(
            op=data.get("op", -1),
            t=data.get("t"),
            d=data.get("d"),
            s=data.get("s"),
        )

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    async def _handle_event(self, event: GatewayEvent) -> None:
        if event.s is not None:
            self._last_sequence = event.s

        if event.op == GatewayOpcode.HELLO:
            await self._handle_hello(event)
        elif event.op == GatewayOpcode.HEARTBEAT:
            # Server asked us to heartbeat immediately.
            await self._send_heartbeat()
        elif event.op == GatewayOpcode.HEARTBEAT_ACK:
            self._last_heartbeat_acked = True
            logger.debug("Heartbeat ACK received")
        elif event.op == GatewayOpcode.DISPATCH:
            await self._handle_dispatch(event)
        elif event.op == GatewayOpcode.INVALID_SESSION:
            await self._handle_invalid_session(event)
        elif event.op == GatewayOpcode.RECONNECT:
            logger.info("Gateway requested reconnect")
            await self._reconnect(resume=True)

    async def _handle_dispatch(self, event: GatewayEvent) -> None:
        if event.t == "READY":
            self._session_id = event.d.get("session_id")
            self._resume_gateway_url = event.d.get("resume_gateway_url")
            self._reconnect_attempts = 0
            logger.info("Gateway READY - session %s", self._session_id)
            if self._on_ready:
                await self._on_ready(event.d)
            # Unblock anything waiting on wait_until_ready().
            self._ready.set()
        elif event.t == "RESUMED":
            self._reconnect_attempts = 0
            logger.info("Gateway RESUMED - session %s replayed", self._session_id)
            self._ready.set()

        if self._on_event:
            await self._on_event(event)

    async def _handle_invalid_session(self, event: GatewayEvent) -> None:
        # `d` is a boolean: whether the session can still be resumed.
        resumable = bool(event.d)
        logger.warning("Invalid session (resumable=%s).", resumable)
        # Discord recommends waiting 1-5s before reconnecting after this op.
        await asyncio.sleep(1.0 + random.random() * 4.0)
        if not resumable:
            self._reset_session()
        await self._reconnect(resume=resumable)

    async def _handle_hello(self, event: GatewayEvent) -> None:
        self._heartbeat_interval = event.d["heartbeat_interval"] / 1000.0
        logger.debug("Hello received. Heartbeat interval: %.1fs", self._heartbeat_interval)

        # A fresh HELLO means we have not missed an ACK yet.
        self._last_heartbeat_acked = True
        self._start_heartbeat()

        # Resume if we still hold a live session, otherwise identify fresh.
        if self.can_resume:
            await self._resume()
        else:
            await self._identify()

    # ------------------------------------------------------------------
    # Handshake
    # ------------------------------------------------------------------

    async def _identify(self) -> None:
        data: dict[str, Any] = {
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
        }
        # Only advertise sharding when the bot actually runs multiple shards.
        if self.shard_count > 1:
            data["shard"] = [self.shard_id, self.shard_count]

        await self._send({"op": GatewayOpcode.IDENTIFY, "d": data})
        logger.info(
            "IDENTIFY sent (shard=%s/%s, intents=%s)",
            self.shard_id,
            self.shard_count,
            self.intents,
        )

    async def _resume(self) -> None:
        payload = {
            "op": GatewayOpcode.RESUME,
            "d": {
                "token": self.token,
                "session_id": self._session_id,
                "seq": self._last_sequence,
            },
        }
        await self._send(payload)
        logger.info("RESUME sent (session=%s, seq=%s)", self._session_id, self._last_sequence)

    # ------------------------------------------------------------------
    # Heartbeating + zombie detection
    # ------------------------------------------------------------------

    def _start_heartbeat(self) -> None:
        if self._heartbeat_task is not None and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self) -> None:
        # Discord asks for an initial jittered delay before the first beat.
        try:
            await asyncio.sleep(self._heartbeat_interval * random.random())
            while self._running and self.is_connected:
                if not self._last_heartbeat_acked:
                    # The previous heartbeat was never ACKed: the connection is
                    # a zombie. Drop it so the receive loop reconnects + resumes.
                    logger.warning("Heartbeat not ACKed in time — zombie connection. Reconnecting.")
                    await self._close_socket(code=4000)
                    return
                await self._send_heartbeat()
                await asyncio.sleep(self._heartbeat_interval)
        except asyncio.CancelledError:
            pass

    async def _send_heartbeat(self) -> None:
        # Mark unacked *before* sending so a missing ACK is detectable next tick.
        self._last_heartbeat_acked = False
        await self._send({"op": GatewayOpcode.HEARTBEAT, "d": self._last_sequence})

    # ------------------------------------------------------------------
    # Low-level send / reconnect
    # ------------------------------------------------------------------

    async def _send(self, data: dict[str, Any]) -> None:
        if not self._ws or self._ws.state is not State.OPEN:
            logger.warning("Attempted to send on closed gateway")
            return
        await self._ws.send(json.dumps(data))

    async def _close_socket(self, *, code: int = 1000) -> None:
        if self._ws is not None:
            try:
                await self._ws.close(code=code)
            except Exception:  # pragma: no cover - best-effort close
                pass

    def _reset_session(self) -> None:
        self._session_id = None
        self._last_sequence = None
        self._resume_gateway_url = None

    def _backoff_delay(self) -> float:
        """Exponential backoff with jitter, capped at 60s."""
        exp = self._reconnect_base_delay * (2 ** (self._reconnect_attempts - 1))
        return min(exp, 60.0) + random.random()  # type: ignore[no-any-return]

    async def _reconnect(self, *, resume: bool) -> None:
        self._ready.clear()
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        await self._close_socket()
        self._ws = None

        if not resume:
            self._reset_session()

        self._reconnect_attempts += 1
        if self._reconnect_attempts > self._max_retries:
            logger.error(
                "Exceeded max reconnect attempts (%s) for shard %s. Giving up.",
                self._max_retries,
                self.shard_id,
            )
            self._running = False
            return

        delay = self._backoff_delay()
        logger.info(
            "Reconnecting shard %s in %.1fs (attempt %s/%s, resume=%s)",
            self.shard_id,
            delay,
            self._reconnect_attempts,
            self._max_retries,
            resume and self.can_resume,
        )
        await asyncio.sleep(delay)
        await self.connect(resume=resume)

    async def close(self) -> None:
        """Gracefully close the gateway connection."""
        self._running = False
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
        if self._receive_task is not None:
            self._receive_task.cancel()
            self._receive_task = None
        await self._close_socket()
        logger.info("Gateway closed (shard=%s)", self.shard_id)

    async def wait_until_ready(self) -> None:
        """Block until we receive the READY (or RESUMED) event."""
        await self._ready.wait()


__all__ = ["Gateway", "GatewayEvent", "GatewayOpcode"]
