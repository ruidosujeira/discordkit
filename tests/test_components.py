"""
Basic tests for the component system.
"""

from __future__ import annotations

from discordkit.components import ButtonContext, ComponentRouter


class TestComponentRouter:
    def test_exact_match(self):
        router = ComponentRouter(client=None)  # type: ignore

        called = []

        @router.component("confirm")
        async def on_confirm(ctx: ButtonContext):
            called.append(ctx.custom_id)

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
