"""
Tests for the command and Option system.
"""

from __future__ import annotations

import json
from typing import Annotated

import pytest

from discordkit.commands import Option, build_options_from_signature, command
from discordkit.models import User
from discordkit.types import ApplicationCommandOptionType


class TestOptionClass:
    def test_basic_option(self):
        opt = Option("A cool description")
        assert opt.description == "A cool description"
        assert opt.required is None

    def test_option_with_constraints(self):
        opt = Option(
            "Username",
            min_length=3,
            max_length=32,
            choices=["alice", "bob"],
        )
        assert opt.min_length == 3
        assert opt.max_length == 32
        assert len(opt.choices) == 2

    def test_option_validation_choices_and_autocomplete(self):
        with pytest.raises(ValueError, match="cannot use both choices and autocomplete"):
            Option("test", choices=["a"], autocomplete=True)

    def test_option_normalizes_choices(self):
        opt = Option("Color", choices=[("Red", "red"), "blue", {"name": "Green", "value": "green"}])
        assert opt.choices == [
            {"name": "Red", "value": "red"},
            {"name": "blue", "value": "blue"},
            {"name": "Green", "value": "green"},
        ]


class TestPayloadGeneration:
    def test_basic_annotated_options(self):
        async def my_cmd(ctx, name: Annotated[str, Option("Name", min_length=2)], age: Annotated[int, Option("Age")] = 18):
            pass

        options = build_options_from_signature(my_cmd)
        assert len(options) == 2

        name_opt = options[0]
        assert name_opt["name"] == "name"
        assert name_opt["description"] == "Name"
        assert name_opt["type"] == ApplicationCommandOptionType.STRING
        assert name_opt["required"] is True
        assert name_opt["min_length"] == 2

        age_opt = options[1]
        assert age_opt["required"] is False
        assert "min_value" not in age_opt  # omitted when unset (Discord API convention)

    def test_discord_type_resolution(self):
        async def cmd(ctx, user: Annotated[User, Option("Target user")]):
            pass

        options = build_options_from_signature(cmd)
        assert options[0]["type"] == ApplicationCommandOptionType.USER

    def test_command_decorator_creates_payload(self):
        @command(name="greet", description="Greet someone")
        async def greet(ctx, name: Annotated[str, Option("Who to greet")]):
            pass

        # The decorator returns the Command object
        payload = greet.to_discord_payload()
        assert payload["name"] == "greet"
        assert len(payload["options"]) == 1
        assert payload["options"][0]["name"] == "name"


class TestSubcommandPayloads:
    def test_group_with_subcommand(self):
        @command(name="admin", description="Admin tools")
        async def admin(ctx):
            pass

        @admin.command(name="ban", description="Ban user")
        async def ban(ctx, user: Annotated[str, Option("User ID")]):
            pass

        payload = admin.to_discord_payload()
        assert len(payload["options"]) == 1
        sub = payload["options"][0]
        assert sub["name"] == "ban"
        assert sub["type"] == 1  # SUB_COMMAND
        assert len(sub["options"]) == 1
