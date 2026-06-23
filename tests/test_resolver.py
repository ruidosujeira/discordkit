"""
Tests for the option resolver (complex Discord type resolution + caching).
"""

from __future__ import annotations

from typing import Annotated

from discordkit.commands import Option, command, resolve_options
from discordkit.core.cache import MemoryCache
from discordkit.models import User


def make_fake_interaction(
    command_name: str, options: list[dict], resolved: dict | None = None
) -> dict:
    return {
        "id": "123",
        "type": 2,
        "token": "token123",
        "data": {
            "name": command_name,
            "options": options,
            "resolved": resolved or {},
        },
        "user": {"id": "999", "username": "tester"},
    }


class TestOptionResolver:
    def test_resolves_primitive_and_user(self):
        @command(name="test", description="test")
        async def test_cmd(ctx, name: str, user: Annotated[User, Option("Target")]):
            pass

        interaction = make_fake_interaction(
            "test",
            [
                {"name": "name", "type": 3, "value": "hello"},
                {"name": "user", "type": 6, "value": "123456"},
            ],
            resolved={
                "users": {
                    "123456": {
                        "id": "123456",
                        "username": "targetuser",
                        "discriminator": "0",
                    }
                }
            },
        )

        result = resolve_options(test_cmd, interaction)
        assert result["name"] == "hello"
        assert isinstance(result["user"], User)
        assert result["user"].id == 123456
        assert result["user"].username == "targetuser"

    def test_populates_cache_when_provided(self):
        cache = MemoryCache()

        @command(name="test", description="test")
        async def test_cmd(ctx, user: Annotated[User, Option("Target")]):
            pass

        interaction = make_fake_interaction(
            "test",
            [{"name": "user", "type": 6, "value": "424242"}],
            resolved={"users": {"424242": {"id": "424242", "username": "cacheduser"}}},
        )

        resolve_options(test_cmd, interaction, cache=cache)

        cached = cache.get_user(424242)
        assert cached is not None
        assert cached.username == "cacheduser"

    def test_bulk_and_invalidation_via_cache(self):
        # This test exercises the advanced cache methods through resolution
        from discordkit.core.cache import MemoryCache as AdvCache

        adv_cache = AdvCache()

        @command(name="test", description="test")
        async def test_cmd(ctx, user: Annotated[User, Option("Target")]):
            pass

        interaction = make_fake_interaction(
            "test",
            [{"name": "user", "type": 6, "value": "555"}],
            resolved={"users": {"555": {"id": "555", "username": "bulkuser"}}},
        )

        resolve_options(test_cmd, interaction, cache=adv_cache)

        # Use advanced methods
        bulk = adv_cache.bulk_get_users([555, 999])
        assert 555 in bulk
        assert adv_cache.invalidate_by_type("user") >= 1
