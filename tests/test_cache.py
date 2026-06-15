"""
Comprehensive tests for the production-grade MemoryCache and CacheBackend.
"""

from __future__ import annotations

import time

import pytest

from discordkit.core.cache import (
    CacheBackend,
    CacheStats,
    EvictionPolicy,
    MemoryCache,
)
from discordkit.models import Channel, Guild, Member, User


@pytest.fixture
def cache() -> MemoryCache:
    return MemoryCache(default_ttl=1.0)  # short TTL for testing expiration


@pytest.fixture
def sample_user() -> User:
    return User(id=123, username="testuser", discriminator="0")


@pytest.fixture
def sample_guild() -> Guild:
    return Guild(id=456, name="Test Guild")


@pytest.fixture
def sample_member(sample_user: User) -> Member:
    return Member(user=sample_user, nick="Tester")


@pytest.fixture
def sample_channel() -> Channel:
    return Channel(id=789, name="general", type=0)


class TestMemoryCacheBasics:
    def test_set_and_get_user(self, cache: MemoryCache, sample_user: User):
        cache.set_user(sample_user)
        assert cache.get_user(123) is sample_user

    def test_get_nonexistent_returns_none(self, cache: MemoryCache):
        assert cache.get_user(999) is None

    def test_invalidate_user(self, cache: MemoryCache, sample_user: User):
        cache.set_user(sample_user)
        assert cache.invalidate_user(123) is True
        assert cache.get_user(123) is None

    def test_ttl_expiration(self, cache: MemoryCache, sample_user: User):
        cache.set_user(sample_user, ttl=0.1)
        assert cache.get_user(123) is sample_user
        time.sleep(0.2)
        assert cache.get_user(123) is None

    def test_get_member(self, cache: MemoryCache, sample_member: Member):
        cache.set_member(sample_member, guild_id=456)
        assert cache.get_member(456, 123) is sample_member
        assert cache.get_member(456, 999) is None


class TestTTLByType:
    def test_different_ttl_per_entity_type(self, sample_user: User, sample_guild: Guild):
        cache = MemoryCache(
            default_ttl=60.0,
            ttl_by_type={"user": 0.1, "guild": 10.0},
        )
        cache.set_user(sample_user)
        cache.set_guild(sample_guild)

        time.sleep(0.2)
        assert cache.get_user(123) is None
        assert cache.get_guild(456) is sample_guild


class TestTouchOnRead:
    def test_touch_on_read_extends_ttl(self, sample_user: User):
        cache = MemoryCache(default_ttl=0.3, touch_on_read=True)
        cache.set_user(sample_user)

        time.sleep(0.15)
        cache.get_user(123)  # should renew TTL

        time.sleep(0.2)
        assert cache.get_user(123) is sample_user

    def test_explicit_touch(self, cache: MemoryCache, sample_user: User):
        cache.set_user(sample_user, ttl=0.2)
        time.sleep(0.1)
        assert cache.touch_user(123) is True
        time.sleep(0.15)
        assert cache.get_user(123) is sample_user

    def test_touch_member(self, cache: MemoryCache, sample_member: Member):
        cache.set_member(sample_member, guild_id=456, ttl=0.2)
        time.sleep(0.1)
        assert cache.touch_member(456, 123) is True


class TestLRUEviction:
    def test_evicts_least_recently_used_when_max_size_reached(self):
        cache = MemoryCache(max_size=3, eviction_policy=EvictionPolicy.LRU, default_ttl=None)

        u1 = User(id=1, username="a", discriminator="0")
        u2 = User(id=2, username="b", discriminator="0")
        u3 = User(id=3, username="c", discriminator="0")
        u4 = User(id=4, username="d", discriminator="0")

        cache.set_user(u1)
        cache.set_user(u2)
        cache.set_user(u3)

        cache.get_user(1)  # u1 becomes most recently used

        cache.set_user(u4)  # should evict u2 (LRU among 1,2,3)

        assert cache.get_user(1) is u1
        assert cache.get_user(2) is None
        assert cache.get_user(3) is u3
        assert cache.get_user(4) is u4

    def test_no_eviction_when_policy_none(self, sample_user: User):
        cache = MemoryCache(max_size=1, eviction_policy=EvictionPolicy.NONE, default_ttl=None)
        cache.set_user(sample_user)
        other = User(id=999, username="other", discriminator="0")
        cache.set_user(other)
        assert cache.get_user(123) is sample_user
        assert cache.get_user(999) is other


class TestGuildScopedInvalidation:
    def test_invalidate_by_guild_cleans_members(self, cache: MemoryCache, sample_member: Member, sample_guild: Guild):
        cache.set_member(sample_member, guild_id=456)
        cache.set_guild(sample_guild)
        count = cache.invalidate_by_guild(456)
        assert count >= 1
        assert cache.get_member(456, 123) is None
        assert cache.get_guild(456) is not None

    def test_invalidate_guild(self, cache: MemoryCache, sample_guild: Guild, sample_member: Member):
        cache.set_guild(sample_guild)
        cache.set_member(sample_member, guild_id=456)
        assert cache.invalidate_guild(456) is True
        assert cache.get_guild(456) is None
        assert cache.get_member(456, 123) is None


class TestAdvancedMethods:
    def test_get_or_set(self, cache: MemoryCache):
        calls: list[int] = []

        def fetch():
            calls.append(1)
            return "computed-value"

        val1 = cache.get_or_set(fetch, "mykey", ttl=10)
        val2 = cache.get_or_set(fetch, "mykey", ttl=10)

        assert val1 == "computed-value"
        assert val2 == "computed-value"
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_get_or_fetch_user_sync_fetcher(self, cache: MemoryCache, sample_user: User):
        calls: list[int] = []

        def fetch():
            calls.append(1)
            return sample_user

        first = await cache.get_or_fetch_user(123, fetch)
        second = await cache.get_or_fetch_user(123, fetch)

        assert first is sample_user
        assert second is sample_user
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_get_or_fetch_member_async_fetcher(self, cache: MemoryCache, sample_member: Member):
        calls: list[int] = []

        async def fetch():
            calls.append(1)
            return sample_member

        first = await cache.get_or_fetch_member(456, 123, fetch)
        second = await cache.get_or_fetch_member(456, 123, fetch)

        assert first is sample_member
        assert second is sample_member
        assert len(calls) == 1

    def test_bulk_operations(self, cache: MemoryCache, sample_user: User):
        user2 = User(id=124, username="user2", discriminator="0")
        cache.bulk_set_users([sample_user, user2])
        result = cache.bulk_get_users([123, 124, 999])
        assert 123 in result and 124 in result
        assert 999 not in result

    def test_invalidate_by_type(self, cache: MemoryCache, sample_user: User, sample_guild: Guild):
        cache.set_user(sample_user)
        cache.set_guild(sample_guild)
        removed = cache.invalidate_by_type("user")
        assert removed == 1
        assert cache.get_user(123) is None
        assert cache.get_guild(456) is not None


class TestStats:
    def test_stats_tracking(self, cache: MemoryCache, sample_user: User):
        cache.set_user(sample_user)
        cache.get_user(123)  # hit
        cache.get_user(999)  # miss

        stats: CacheStats = cache.stats()
        assert stats.hits >= 1
        assert stats.misses >= 1
        assert stats.total_size >= 1
        assert 0.0 <= stats.hit_rate <= 1.0

    def test_stats_include_evictions(self):
        cache = MemoryCache(max_size=1, eviction_policy=EvictionPolicy.LRU, default_ttl=None)
        cache.set_user(User(id=1, username="a", discriminator="0"))
        cache.set_user(User(id=2, username="b", discriminator="0"))
        stats = cache.stats()
        assert stats.evictions >= 1


class TestInterface:
    def test_memory_cache_is_backend(self, cache: MemoryCache):
        assert isinstance(cache, CacheBackend)