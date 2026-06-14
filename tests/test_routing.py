"""
Tests for slash command routing (including subcommands and groups).
"""

from __future__ import annotations

from typing import Annotated

import pytest

from discordkit import Client, Config
from discordkit.commands import Option, command, group
from discordkit.types import Intents


@pytest.fixture
def routed_client(fake_token):
    cfg = Config(token=fake_token, intents=Intents.DEFAULT)
    return Client(cfg)


class TestSlashRouting:
    def test_flat_command_registration(self, routed_client):
        @command(name="ping", description="Ping!")
        async def ping(ctx):
            pass

        routed_client.add_command(ping)
        assert routed_client.commands.get("ping") is not None

    def test_group_and_subcommand_registration(self, routed_client):
        @group(name="admin", description="Admin")
        async def admin(ctx):
            pass

        @admin.command(name="ban", description="Ban")
        async def ban(ctx, user: Annotated[str, Option("User")]):
            pass

        routed_client.add_command(admin)
        root = routed_client.commands.get("admin")
        assert root is not None
        assert len(root.children) == 1
        assert root.children[0].name == "ban"

    def test_resolve_nested_command(self, routed_client):
        @group(name="config", description="Config")
        async def config_group(ctx):
            pass

        @config_group.command(name="set", description="Set value")
        async def set_cmd(ctx, key: str, value: str):
            pass

        routed_client.add_command(config_group)

        # Simulate interaction data for /config set key:foo value:bar
        data = {
            "name": "config",
            "options": [
                {
                    "name": "set",
                    "type": 1,
                    "options": [
                        {"name": "key", "type": 3, "value": "foo"},
                        {"name": "value", "type": 3, "value": "bar"},
                    ],
                }
            ],
        }

        leaf, leaf_opts, path = routed_client.commands.resolve_command_from_interaction(data)
        assert leaf is not None
        assert leaf.name == "set"
        assert path == "config set"
        assert len(leaf_opts) == 2
