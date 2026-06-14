"""
Basic tests for the component system.
"""

from __future__ import annotations

import pytest

from discordkit.components import ButtonContext, ComponentRouter
from discordkit.core.context import CommandContext
from discordkit.models import User


def make_fake_component_interaction(custom_id: str) -> dict:
    return {
        "id": "int123",
        "type": 3,
        "token": "tkn",
        "data": {
            "custom_id": custom_id,
            "component_type": 2,
        },
        "user": {"id": "111", "username": "clicker"},
    }


class TestComponentRouter:
    def test_exact_match(self):
        router = ComponentRouter(client=None)  # type: ignore

        called = []

        @router.component("confirm")
        async def on_confirm(ctx: ButtonContext):
            called.append(ctx.custom_id)

        interaction = make_fake_component_interaction("confirm")
        # We can't easily run full dispatch without a real client, so test matching logic
        match = router._find_handler("confirm", router._component_handlers)
        assert match is not None
        assert match[0] == "confirm"

    def test_prefix_match(self):
        router = ComponentRouter(client=None)  # type: ignore

        @router.component("ticket:")
        async def on_ticket(ctx):
            pass

        match = router._find_handler("ticket:42", router._component_handlers)
        assert match is not None
        assert match[0] == "ticket:"
