"""
Comprehensive tests for the advanced MemoryCache and CacheBackend.
"""

from __future__ import annotations

import time

import pytest

from discordkit.core.cache import CacheBackend, CacheStats, MemoryCache
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
        assert cache.get_user(123) is None  # should have expired


class TestGuildScopedInvalidation:
    def test_invalidate_by_guild_cleans_members(self, cache: MemoryCache, sample_member: Member, sample_guild: Guild):
        cache.set_member(sample_member, guild_id=456)
        cache.set_guild(sample_guild)
        count = cache.invalidate_by_guild(456)
        assert count >= 1
        assert cache.get_member(456, 123) is None
        # Guild itself not auto-removed by invalidate_by_guild (separate call)
        assert cache.get_guild(456) is not None

    def test_invalidate_guild(self, cache: MemoryCache, sample_guild: Guild):
        cache.set_guild(sample_guild)
        assert cache.invalidate_guild(456) is True
        assert cache.get_guild(456) is None


class TestAdvancedMethods:
    def test_get_or_set(self, cache: MemoryCache):
        calls = []

        def fetch():
            calls.append(1)
            return "computed-value"

        val1 = cache.get_or_set(fetch, "mykey", ttl=10)
        val2 = cache.get_or_set(fetch, "mykey", ttl=10)

        assert val1 == "computed-value"
        assert val2 == "computed-value"
        assert len(calls) == 1  # second call was cached

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


class TestInterface:
    def test_memory_cache_is_backend(self, cache: MemoryCache):
        assert isinstance(cache, CacheBackend)
