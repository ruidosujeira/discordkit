"""
Tests for SQLite-backed PersistentCache.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from discordkit.core.cache import CacheBackend
from discordkit.core.cache_persistent import PersistentCache
from discordkit.models import Guild, Member, User


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_cache.db"


@pytest.fixture
def sample_user() -> User:
    return User(id=123, username="testuser", discriminator="0")


@pytest.fixture
def sample_guild() -> Guild:
    return Guild(id=456, name="Test Guild")


@pytest.fixture
def sample_member(sample_user: User) -> Member:
    return Member(user=sample_user, nick="Tester")


class TestPersistentCacheBasics:
    def test_persists_and_reloads_user(self, db_path: Path, sample_user: User):
        cache = PersistentCache(path=db_path, default_ttl=300)
        cache.set_user(sample_user)

        reloaded = PersistentCache(path=db_path, default_ttl=300)
        assert reloaded.get_user(123) == sample_user

    def test_persists_member_with_guild_scope(self, db_path: Path, sample_member: Member):
        cache = PersistentCache(path=db_path)
        cache.set_member(sample_member, guild_id=456)

        reloaded = PersistentCache(path=db_path)
        assert reloaded.get_member(456, 123) == sample_member

    def test_invalidation_removes_from_disk(self, db_path: Path, sample_user: User):
        cache = PersistentCache(path=db_path)
        cache.set_user(sample_user)
        cache.invalidate_user(123)

        reloaded = PersistentCache(path=db_path)
        assert reloaded.get_user(123) is None

    def test_clear_wipes_disk(self, db_path: Path, sample_user: User, sample_guild: Guild):
        cache = PersistentCache(path=db_path)
        cache.set_user(sample_user)
        cache.set_guild(sample_guild)
        cache.clear()

        reloaded = PersistentCache(path=db_path)
        assert reloaded.get_user(123) is None
        assert reloaded.get_guild(456) is None

    def test_skips_expired_on_load(self, db_path: Path, sample_user: User):
        cache = PersistentCache(path=db_path, default_ttl=0.1, ttl_by_type={"user": 0.1})
        cache.set_user(sample_user)
        time.sleep(0.2)

        reloaded = PersistentCache(path=db_path, default_ttl=0.1, ttl_by_type={"user": 0.1})
        assert reloaded.get_user(123) is None

    def test_implements_cache_backend(self, db_path: Path):
        cache = PersistentCache(path=db_path)
        assert isinstance(cache, CacheBackend)

    def test_db_path_property(self, db_path: Path):
        cache = PersistentCache(path=db_path)
        assert cache.db_path == db_path.resolve()

    def test_creates_parent_directories(self, tmp_path: Path, sample_user: User):
        nested = tmp_path / "data" / "nested" / "cache.db"
        cache = PersistentCache(path=nested)
        cache.set_user(sample_user)

        assert nested.exists()
        reloaded = PersistentCache(path=nested)
        assert reloaded.get_user(123) == sample_user
