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
import json
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
    closed_with: int | None = None

    async def send(self, data: str) -> None:
        self.sent.append(data)

    async def close(self, code: int = 1000) -> None:
        self.closed_with = code


def _sent_payloads(ws: _FakeWS) -> list[dict]:
    """Decode the JSON payloads written to a fake websocket."""
    return [json.loads(raw) for raw in ws.sent]


def _hello_event(interval_ms: int = 45000) -> GatewayEvent:
    return GatewayEvent(op=GatewayOpcode.HELLO, t=None, d={"heartbeat_interval": interval_ms}, s=None)


async def _drive_hello(gw: Gateway) -> None:
    """Drive a HELLO through the gateway and stop the spawned heartbeat task."""
    await gw._handle_hello(_hello_event())
    if gw._heartbeat_task is not None:
        gw._heartbeat_task.cancel()


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


class TestSessionResume:
    async def test_ready_captures_resume_url_and_session(self) -> None:
        gw = _make_gateway()
        event = GatewayEvent(
            op=GatewayOpcode.DISPATCH,
            t="READY",
            d={
                "session_id": "sess-abc",
                "resume_gateway_url": "wss://resume.example.discord.gg",
                "user": {"id": "1"},
                "application": {"id": "2"},
            },
            s=10,
        )
        await gw._handle_event(event)
        assert gw._session_id == "sess-abc"
        assert gw._resume_gateway_url == "wss://resume.example.discord.gg"
        assert gw._last_sequence == 10
        assert gw.can_resume is True
        assert gw._reconnect_attempts == 0

    async def test_hello_resumes_when_session_present(self) -> None:
        gw = _make_gateway()
        gw._session_id = "sess-xyz"
        gw._last_sequence = 7
        ws = _FakeWS(state=State.OPEN, sent=[])
        gw._ws = ws  # type: ignore[assignment]

        await _drive_hello(gw)

        payloads = _sent_payloads(ws)
        assert len(payloads) == 1
        assert payloads[0]["op"] == GatewayOpcode.RESUME
        assert payloads[0]["d"] == {
            "token": "fake-token",
            "session_id": "sess-xyz",
            "seq": 7,
        }

    async def test_hello_identifies_when_no_session(self) -> None:
        gw = _make_gateway()
        ws = _FakeWS(state=State.OPEN, sent=[])
        gw._ws = ws  # type: ignore[assignment]

        await _drive_hello(gw)

        payloads = _sent_payloads(ws)
        assert len(payloads) == 1
        assert payloads[0]["op"] == GatewayOpcode.IDENTIFY

    async def test_resumed_dispatch_marks_ready(self) -> None:
        seen: list[str] = []

        async def on_event(event: GatewayEvent) -> None:
            seen.append(event.t or "")

        gw = _make_gateway(on_event=on_event)
        gw._reconnect_attempts = 3
        await gw._handle_event(
            GatewayEvent(op=GatewayOpcode.DISPATCH, t="RESUMED", d={}, s=11)
        )
        assert gw._ready.is_set()
        assert gw._reconnect_attempts == 0
        assert "RESUMED" in seen

    async def test_invalid_session_resumable_keeps_session(self, monkeypatch) -> None:
        gw = _make_gateway()
        gw._session_id = "keep-me"
        gw._last_sequence = 5
        resume_calls: list[bool] = []

        async def fake_reconnect(*, resume: bool) -> None:
            resume_calls.append(resume)

        async def fast_sleep(*_a, **_k) -> None:
            return None

        monkeypatch.setattr(gw, "_reconnect", fake_reconnect)
        monkeypatch.setattr("discordkit.core.gateway.asyncio.sleep", fast_sleep)

        await gw._handle_event(
            GatewayEvent(op=GatewayOpcode.INVALID_SESSION, t=None, d=True, s=None)
        )
        assert resume_calls == [True]
        assert gw._session_id == "keep-me"  # session preserved for resume

    async def test_invalid_session_non_resumable_resets(self, monkeypatch) -> None:
        gw = _make_gateway()
        gw._session_id = "drop-me"
        gw._last_sequence = 5
        resume_calls: list[bool] = []

        async def fake_reconnect(*, resume: bool) -> None:
            resume_calls.append(resume)

        async def fast_sleep(*_a, **_k) -> None:
            return None

        monkeypatch.setattr(gw, "_reconnect", fake_reconnect)
        monkeypatch.setattr("discordkit.core.gateway.asyncio.sleep", fast_sleep)

        await gw._handle_event(
            GatewayEvent(op=GatewayOpcode.INVALID_SESSION, t=None, d=False, s=None)
        )
        assert resume_calls == [False]
        assert gw._session_id is None  # session wiped -> fresh identify next time

    def test_with_query_adds_version(self) -> None:
        assert Gateway._with_query("wss://x.discord.gg") == "wss://x.discord.gg?v=10&encoding=json"
        # An URL that already has a query is left untouched.
        assert Gateway._with_query("wss://x.discord.gg/?v=10") == "wss://x.discord.gg/?v=10"


class TestSharding:
    async def test_identify_includes_shard_when_multiple(self) -> None:
        gw = _make_gateway(shard_id=1, shard_count=3)
        ws = _FakeWS(state=State.OPEN, sent=[])
        gw._ws = ws  # type: ignore[assignment]
        await gw._identify()
        d = _sent_payloads(ws)[0]["d"]
        assert d["shard"] == [1, 3]

    async def test_identify_omits_shard_when_single(self) -> None:
        gw = _make_gateway(shard_id=0, shard_count=1)
        ws = _FakeWS(state=State.OPEN, sent=[])
        gw._ws = ws  # type: ignore[assignment]
        await gw._identify()
        d = _sent_payloads(ws)[0]["d"]
        assert "shard" not in d

    def test_client_builds_one_gateway_per_shard(self, fake_token) -> None:
        from discordkit import Client, Config
        from discordkit.types import Intents

        client = Client(Config(token=fake_token, intents=Intents.DEFAULT, shard_count=3))
        client._build_shards()

        assert client.shard_count == 3
        assert len(client._gateways) == 3
        assert [gw.shard_id for gw in client._gateways] == [0, 1, 2]
        assert all(gw.shard_count == 3 for gw in client._gateways)

    def test_client_single_shard_by_default(self, test_client) -> None:
        test_client._build_shards()
        assert test_client.shard_count == 1
        assert len(test_client._gateways) == 1
        assert test_client._gateways[0].shard_id == 0


class TestHeartbeat:
    async def test_hello_marks_acked(self) -> None:
        gw = _make_gateway()
        gw._last_heartbeat_acked = False
        await _drive_hello(gw)
        assert gw._last_heartbeat_acked is True
        assert gw._heartbeat_interval == 45.0

    async def test_send_heartbeat_marks_unacked(self) -> None:
        gw = _make_gateway()
        gw._last_sequence = 99
        ws = _FakeWS(state=State.OPEN, sent=[])
        gw._ws = ws  # type: ignore[assignment]
        await gw._send_heartbeat()
        payload = _sent_payloads(ws)[0]
        assert payload["op"] == GatewayOpcode.HEARTBEAT
        assert payload["d"] == 99
        assert gw._last_heartbeat_acked is False

    async def test_ack_event_marks_acked(self) -> None:
        gw = _make_gateway()
        gw._last_heartbeat_acked = False
        await gw._handle_event(
            GatewayEvent(op=GatewayOpcode.HEARTBEAT_ACK, t=None, d=None, s=None)
        )
        assert gw._last_heartbeat_acked is True

    async def test_server_heartbeat_request_sends_immediately(self) -> None:
        gw = _make_gateway()
        ws = _FakeWS(state=State.OPEN, sent=[])
        gw._ws = ws  # type: ignore[assignment]
        await gw._handle_event(
            GatewayEvent(op=GatewayOpcode.HEARTBEAT, t=None, d=None, s=None)
        )
        assert _sent_payloads(ws)[0]["op"] == GatewayOpcode.HEARTBEAT
        assert gw._last_heartbeat_acked is False

    async def test_zombie_connection_closes_socket(self) -> None:
        gw = _make_gateway()
        gw._heartbeat_interval = 0.0
        gw._last_heartbeat_acked = False  # previous beat never ACKed
        gw._running = True
        ws = _FakeWS(state=State.OPEN, sent=[])
        gw._ws = ws  # type: ignore[assignment]

        # The loop should detect the missing ACK and tear the socket down.
        await asyncio.wait_for(gw._heartbeat_loop(), timeout=1.0)
        assert ws.closed_with == 4000
        assert ws.sent == []  # no new heartbeat was sent on a zombie link


class TestReconnectPolicy:
    def test_close_code_classification(self) -> None:
        from discordkit.core.gateway import FATAL_CLOSE_CODES, NON_RESUMABLE_CLOSE_CODES

        # Bad token / bad intents must never loop-reconnect.
        assert 4004 in FATAL_CLOSE_CODES
        assert 4014 in FATAL_CLOSE_CODES
        # Stale seq / timed-out session: reconnect, but identify fresh.
        assert 4007 in NON_RESUMABLE_CLOSE_CODES
        assert 4009 in NON_RESUMABLE_CLOSE_CODES
        # Generic errors are both reconnectable and resumable.
        assert 4000 not in FATAL_CLOSE_CODES
        assert 4000 not in NON_RESUMABLE_CLOSE_CODES

    def test_backoff_is_exponential_and_capped(self, monkeypatch) -> None:
        # Pin jitter to 0 for a deterministic curve.
        monkeypatch.setattr("discordkit.core.gateway.random.random", lambda: 0.0)
        gw = _make_gateway(reconnect_base_delay=1.0)

        gw._reconnect_attempts = 1
        assert gw._backoff_delay() == 1.0
        gw._reconnect_attempts = 2
        assert gw._backoff_delay() == 2.0
        gw._reconnect_attempts = 4
        assert gw._backoff_delay() == 8.0
        gw._reconnect_attempts = 20
        assert gw._backoff_delay() == 60.0  # capped
