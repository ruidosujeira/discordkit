"""
Pytest configuration and shared fixtures for DiscordKit tests.
"""

from __future__ import annotations

from typing import Any

import pytest

from discordkit import Client, Config
from discordkit.commands import Command, Option, command
from discordkit.types import Intents


@pytest.fixture
def fake_token() -> str:
    """A clearly fake token used only for unit tests (never a real Discord token)."""
    return "TEST_FAKE_TOKEN_ONLY_FOR_UNIT_TESTS.abcdefghijklmnopqrstuvwxyz123456"


@pytest.fixture
def test_config(fake_token: str) -> Config:
    """Basic test Config (no network)."""
    return Config(token=fake_token, intents=Intents.DEFAULT, debug=False)


@pytest.fixture
def test_client(test_config: Config) -> Client:
    """A Client instance suitable for unit testing (no actual connection)."""
    return Client(test_config)


@pytest.fixture
def sample_command() -> Command:
    """A simple command with rich options for testing."""
    from typing import Annotated

    @command(name="test", description="A test command")
    async def _test_cmd(
        ctx,
        name: Annotated[str, Option("Display name", min_length=2, max_length=32)],
        count: Annotated[int, Option("Count", min_value=1, max_value=100)] = 5,
    ):
        pass

    # The decorator returns the Command
    return _test_cmd  # type: ignore[return-value]


@pytest.fixture
def nested_group_command() -> Command:
    """A command group with subcommand for routing tests."""
    from typing import Annotated

    @command(name="admin", description="Admin group")
    async def admin_group(ctx):
        pass

    @admin_group.command(name="ban", description="Ban a user")
    async def ban(ctx, user_id: Annotated[str, Option("User ID")], reason: Annotated[str, Option("Reason")]):
        pass

    return admin_group  # type: ignore[return-value]
