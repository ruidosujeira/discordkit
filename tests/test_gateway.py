"""
Tests for the Gateway connection manager.

These exercise the event-handling logic directly (no real websocket) to cover
behaviour that previously had no test coverage:

- the READY dispatch unblocks ``wait_until_ready()``
- ``is_connected`` / ``_send`` use the websockets ``State`` enum, not a
  non-existent ``.closed`` attribute
- the client stores ``application_id`` as a real ``int``
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from websockets.protocol import State

from discordkit.core.gateway import Gateway, GatewayEvent, GatewayOpcode
from discordkit.types import Intents


@dataclass
class _FakeWS:
    """Minimal stand-in for websockets ClientConnection (only what we use)."""

    state: State
    sent: list[str]

    async def send(self, data: str) -> None:
        self.sent.append(data)


def _make_gateway(**kwargs) -> Gateway:
    return Gateway(token="fake-token", intents=Intents.DEFAULT, **kwargs)


def _ready_event() -> GatewayEvent:
    return GatewayEvent(
        op=GatewayOpcode.DISPATCH,
        t="READY",
        d={
            "session_id": "sess-123",
            "user": {"id": "42", "username": "bot"},
            "application": {"id": "999"},
        },
        s=1,
    )


class TestReadiness:
    async def test_ready_dispatch_sets_ready_event(self) -> None:
        received: list[dict] = []

        async def on_ready(data: dict) -> None:
            received.append(data)

        gw = _make_gateway(on_ready=on_ready)

        # Before READY: not set, so wait_until_ready() would block.
        assert not gw._ready.is_set()

        await gw._handle_event(_ready_event())

        # READY must unblock waiters and fire the callback.
        assert gw._ready.is_set()
        assert received and received[0]["session_id"] == "sess-123"
        assert gw._session_id == "sess-123"

        # wait_until_ready() now returns immediately rather than hanging.
        await asyncio.wait_for(gw.wait_until_ready(), timeout=1.0)

    async def test_on_event_called_for_dispatch(self) -> None:
        seen: list[str] = []

        async def on_event(event: GatewayEvent) -> None:
            seen.append(event.t or "")

        gw = _make_gateway(on_event=on_event)
        await gw._handle_event(_ready_event())
        assert "READY" in seen


class TestConnectionState:
    def test_is_connected_true_when_open(self) -> None:
        gw = _make_gateway()
        gw._ws = _FakeWS(state=State.OPEN, sent=[])  # type: ignore[assignment]
        assert gw.is_connected is True

    def test_is_connected_false_when_closed(self) -> None:
        gw = _make_gateway()
        gw._ws = _FakeWS(state=State.CLOSED, sent=[])  # type: ignore[assignment]
        assert gw.is_connected is False

    def test_is_connected_false_when_no_socket(self) -> None:
        gw = _make_gateway()
        assert gw.is_connected is False

    async def test_send_skips_when_not_open(self) -> None:
        gw = _make_gateway()
        ws = _FakeWS(state=State.CLOSED, sent=[])
        gw._ws = ws  # type: ignore[assignment]
        await gw._send({"op": GatewayOpcode.HEARTBEAT, "d": None})
        assert ws.sent == []

    async def test_send_writes_when_open(self) -> None:
        gw = _make_gateway()
        ws = _FakeWS(state=State.OPEN, sent=[])
        gw._ws = ws  # type: ignore[assignment]
        await gw._send({"op": GatewayOpcode.HEARTBEAT, "d": 7})
        assert len(ws.sent) == 1
        assert '"op": 1' in ws.sent[0]


class TestClientReady:
    async def test_application_id_stored_as_int(self, test_client) -> None:
        await test_client._handle_ready(
            {
                "user": {"id": "42", "username": "bot"},
                "application": {"id": "1234567890"},
            }
        )
        assert test_client.application_id == 1234567890
        assert isinstance(test_client.application_id, int)
