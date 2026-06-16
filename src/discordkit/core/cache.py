"""
discordkit.core.cache
=====================

Production-grade caching for DiscordKit with a stable, extensible backend interface.

Design goals
------------
- **Stable API** — ``CacheBackend`` defines the contract; swap implementations without
  touching application code.
- **Sensible defaults** — TTL, per-entity TTLs, and LRU eviction work out of the box.
- **Bot-friendly patterns** — ``get_or_fetch`` mirrors how real bots resolve entities.
- **Thread-safe** — ``MemoryCache`` uses ``threading.RLock`` for mixed sync/async use.
- **Observable** — rich statistics (hits, misses, evictions, hit rate, sizes).

The default ``MemoryCache`` targets single-process bots on a single asyncio event loop.
For multi-process or distributed deployments, implement ``CacheBackend`` with Redis or
similar and assign it to ``Client.cache``.
"""

from __future__ import annotations

import inspect
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, TypeVar

from ..models import Channel, Guild, Member, User

T = TypeVar("T")

# Canonical entity type names used for TTL maps, invalidation, and LRU bookkeeping.
ENTITY_USER = "user"
ENTITY_MEMBER = "member"
ENTITY_GUILD = "guild"
ENTITY_CHANNEL = "channel"
ENTITY_GENERIC = "generic"

CacheKey = tuple[str, Any]


class EvictionPolicy(StrEnum):
    """Strategy used when the cache reaches ``max_size``."""

    NONE = "none"
    """No size-based eviction; entries expire only via TTL or explicit invalidation."""

    LRU = "lru"
    """Evict the least recently used entry when ``max_size`` is exceeded."""


# Sensible per-entity TTL defaults (seconds). Override via ``ttl_by_type`` on construction.
DEFAULT_TTL_BY_TYPE: dict[str, float] = {
    ENTITY_USER: 600.0,  # users change infrequently
    ENTITY_MEMBER: 300.0,  # nicknames/roles change more often
    ENTITY_GUILD: 900.0,  # guild metadata is relatively stable
    ENTITY_CHANNEL: 300.0,  # channel names/topics can change
    ENTITY_GENERIC: 300.0,
}


@dataclass(slots=True)
class CacheStats:
    """Snapshot of cache performance and occupancy.

    Returned by :meth:`CacheBackend.stats` as a copy so callers cannot mutate
    internal counters accidentally.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size_users: int = 0
    size_members: int = 0
    size_guilds: int = 0
    size_channels: int = 0
    size_generic: int = 0

    @property
    def total_size(self) -> int:
        """Total number of entries across all entity stores."""
        return (
            self.size_users
            + self.size_members
            + self.size_guilds
            + self.size_channels
            + self.size_generic
        )

    @property
    def hit_rate(self) -> float:
        """Ratio of hits to total lookups (0.0 when no lookups yet)."""
        total = self.hits + self.misses
        return (self.hits / total) if total > 0 else 0.0


@dataclass(slots=True)
class _CacheEntry[T]:
    """Internal wrapper storing a value, expiry, and LRU metadata."""

    value: T
    expires_at: float | None = None
    last_accessed: float = field(default_factory=time.monotonic)


class CacheBackend(ABC):
    """Abstract cache contract for DiscordKit.

    Implement this interface to provide alternative storage (Redis, Memcached, etc.).
    All methods are synchronous; async fetch orchestration lives in
    :meth:`get_or_fetch` helpers on concrete backends.

    Entity accessors
    ----------------
    Each Discord entity type (``User``, ``Member``, ``Guild``, ``Channel``) has a
    consistent trio of methods:

    - ``get_<entity>`` — retrieve a cached object or ``None``
    - ``set_<entity>`` — store an object with optional per-call TTL override
    - ``invalidate_<entity>`` — remove one entry; returns whether it existed

    High-level patterns
    -------------------
    - :meth:`get_or_set` — synchronous cache-aside for arbitrary keys
    - :meth:`get_or_fetch` — async cache-aside (the pattern most bots need)
    - :meth:`touch_*` — renew TTL without changing the stored value

    Management
    ----------
    - :meth:`invalidate_by_guild` — drop all members for a guild
    - :meth:`invalidate_by_type` — bulk clear by entity type name
    - :meth:`clear` — wipe everything
    - :meth:`stats` — performance snapshot
    """

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    @abstractmethod
    def get_user(self, user_id: int) -> User | None:
        """Return a cached :class:`~discordkit.models.User` or ``None``."""

    @abstractmethod
    def set_user(self, user: User, ttl: float | None = None) -> None:
        """Cache a user. No-op when ``user.id`` is missing."""

    @abstractmethod
    def invalidate_user(self, user_id: int) -> bool:
        """Remove a user from the cache. Returns ``True`` if it was present."""

    @abstractmethod
    def touch_user(self, user_id: int) -> bool:
        """Renew TTL for a cached user (when ``touch_on_read`` is disabled)."""

    # ------------------------------------------------------------------
    # Members (guild-scoped)
    # ------------------------------------------------------------------

    @abstractmethod
    def get_member(self, guild_id: int, user_id: int) -> Member | None:
        """Return a cached :class:`~discordkit.models.Member` or ``None``."""

    @abstractmethod
    def set_member(self, member: Member, guild_id: int, ttl: float | None = None) -> None:
        """Cache a member under ``(guild_id, user_id)``."""

    @abstractmethod
    def invalidate_member(self, guild_id: int, user_id: int) -> bool:
        """Remove a guild member from the cache."""

    @abstractmethod
    def touch_member(self, guild_id: int, user_id: int) -> bool:
        """Renew TTL for a cached member."""

    # ------------------------------------------------------------------
    # Guilds
    # ------------------------------------------------------------------

    @abstractmethod
    def get_guild(self, guild_id: int) -> Guild | None:
        """Return a cached :class:`~discordkit.models.Guild` or ``None``."""

    @abstractmethod
    def set_guild(self, guild: Guild, ttl: float | None = None) -> None:
        """Cache a guild."""

    @abstractmethod
    def invalidate_guild(self, guild_id: int) -> bool:
        """Remove a guild and all of its cached members."""

    @abstractmethod
    def touch_guild(self, guild_id: int) -> bool:
        """Renew TTL for a cached guild."""

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    @abstractmethod
    def get_channel(self, channel_id: int) -> Channel | None:
        """Return a cached :class:`~discordkit.models.Channel` or ``None``."""

    @abstractmethod
    def set_channel(self, channel: Channel, ttl: float | None = None) -> None:
        """Cache a channel."""

    @abstractmethod
    def invalidate_channel(self, channel_id: int) -> bool:
        """Remove a channel from the cache."""

    @abstractmethod
    def touch_channel(self, channel_id: int) -> bool:
        """Renew TTL for a cached channel."""

    # ------------------------------------------------------------------
    # High-level patterns
    # ------------------------------------------------------------------

    @abstractmethod
    def get_or_set(
        self,
        getter: Callable[[], T | None],
        key: str,
        ttl: float | None = None,
    ) -> T | None:
        """Synchronous cache-aside for arbitrary string keys."""

    @abstractmethod
    async def get_or_fetch(
        self,
        cache_key: CacheKey,
        fetcher: Callable[[], T | None | Awaitable[T | None]],
        *,
        ttl: float | None = None,
        store: Callable[[T], None] | None = None,
        lookup: Callable[[], T | None] | None = None,
    ) -> T | None:
        """Async cache-aside: return cached value or fetch, store, and return.

        Parameters
        ----------
        cache_key:
            ``(entity_type, primary_key)`` used for LRU bookkeeping.
        fetcher:
            Callable (sync or async) that retrieves the value on a cache miss.
        ttl:
            Optional TTL override for the stored entry.
        store:
            Callable invoked to persist ``T`` after a successful fetch.
        lookup:
            Callable invoked to read ``T`` from the typed store before fetching.
        """

    @abstractmethod
    async def get_or_fetch_user(
        self,
        user_id: int,
        fetcher: Callable[[], User | None | Awaitable[User | None]],
        *,
        ttl: float | None = None,
    ) -> User | None:
        """Return a cached user or invoke ``fetcher`` on miss."""

    @abstractmethod
    async def get_or_fetch_member(
        self,
        guild_id: int,
        user_id: int,
        fetcher: Callable[[], Member | None | Awaitable[Member | None]],
        *,
        ttl: float | None = None,
    ) -> Member | None:
        """Return a cached member or invoke ``fetcher`` on miss."""

    @abstractmethod
    async def get_or_fetch_guild(
        self,
        guild_id: int,
        fetcher: Callable[[], Guild | None | Awaitable[Guild | None]],
        *,
        ttl: float | None = None,
    ) -> Guild | None:
        """Return a cached guild or invoke ``fetcher`` on miss."""

    @abstractmethod
    async def get_or_fetch_channel(
        self,
        channel_id: int,
        fetcher: Callable[[], Channel | None | Awaitable[Channel | None]],
        *,
        ttl: float | None = None,
    ) -> Channel | None:
        """Return a cached channel or invoke ``fetcher`` on miss."""

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------

    @abstractmethod
    def bulk_get_users(self, user_ids: list[int]) -> dict[int, User]:
        """Return all cached users found for the given IDs."""

    @abstractmethod
    def bulk_set_users(self, users: list[User], ttl: float | None = None) -> None:
        """Store multiple users in one pass."""

    # ------------------------------------------------------------------
    # Invalidation & introspection
    # ------------------------------------------------------------------

    @abstractmethod
    def invalidate_by_guild(self, guild_id: int) -> int:
        """Remove all cached members for ``guild_id``. Returns count removed."""

    @abstractmethod
    def invalidate_by_type(self, type_name: str) -> int:
        """Bulk-clear a store. Accepts ``user``, ``member``, ``guild``, ``channel``, ``generic``."""

    @abstractmethod
    def clear(self) -> None:
        """Remove every entry and reset LRU tracking."""

    @abstractmethod
    def stats(self) -> CacheStats:
        """Return a snapshot of cache statistics."""


class MemoryCache(CacheBackend):
    """Thread-safe in-memory cache with TTL, LRU eviction, and per-type TTL.

    Parameters
    ----------
    default_ttl:
        Fallback TTL in seconds for all entities when no per-type TTL is set.
        Pass ``0`` or a negative value to disable expiry by default.
    max_size:
        Maximum total entries across all stores. ``None`` means unlimited.
    eviction_policy:
        Policy applied when ``max_size`` is reached. Defaults to :attr:`EvictionPolicy.LRU`.
    touch_on_read:
        When ``True``, successful reads renew the entry TTL (sliding expiration).
    ttl_by_type:
        Per-entity TTL overrides. Keys: ``user``, ``member``, ``guild``, ``channel``,
        ``generic``. Unspecified types fall back to ``default_ttl``.

    Example
    -------
    ::

        cache = MemoryCache(
            default_ttl=300,
            max_size=10_000,
            touch_on_read=True,
            ttl_by_type={"user": 900, "member": 180},
        )
        cache.set_user(user)
        member = cache.get_member(guild_id, user_id)
    """

    def __init__(
        self,
        default_ttl: float = 300.0,
        *,
        max_size: int | None = None,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
        touch_on_read: bool = False,
        ttl_by_type: dict[str, float] | None = None,
    ) -> None:
        if default_ttl is None:
            self.default_ttl = None
        else:
            self.default_ttl = default_ttl if default_ttl > 0 else None
        self.max_size = max_size
        self.eviction_policy = eviction_policy
        self.touch_on_read = touch_on_read
        self.ttl_by_type: dict[str, float] = {**DEFAULT_TTL_BY_TYPE, **(ttl_by_type or {})}

        self._lock = threading.RLock()
        self._users: dict[int, _CacheEntry[User]] = {}
        self._members: dict[tuple[int, int], _CacheEntry[Member]] = {}
        self._guilds: dict[int, _CacheEntry[Guild]] = {}
        self._channels: dict[int, _CacheEntry[Channel]] = {}
        self._generic: dict[str, _CacheEntry[Any]] = {}

        # Global LRU order: oldest at the front, most recent at the back.
        self._lru: OrderedDict[CacheKey, None] = OrderedDict()
        self._stats = CacheStats()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _now(self) -> float:
        return time.monotonic()

    def _ttl_for_type(self, entity_type: str, ttl: float | None) -> float | None:
        """Resolve the effective TTL for an entity type."""
        if ttl is not None:
            return ttl if ttl > 0 else None
        type_ttl = self.ttl_by_type.get(entity_type)
        if type_ttl is not None and type_ttl > 0:
            return type_ttl
        return self.default_ttl

    def _compute_expiry(self, entity_type: str, ttl: float | None) -> float | None:
        effective = self._ttl_for_type(entity_type, ttl)
        return (self._now() + effective) if effective is not None else None

    def _is_expired(self, entry: _CacheEntry[Any]) -> bool:
        return entry.expires_at is not None and self._now() >= entry.expires_at

    def _store_for_type(self, entity_type: str) -> dict[Any, _CacheEntry[Any]]:
        return {
            ENTITY_USER: self._users,
            ENTITY_MEMBER: self._members,
            ENTITY_GUILD: self._guilds,
            ENTITY_CHANNEL: self._channels,
            ENTITY_GENERIC: self._generic,
        }[entity_type]

    def _remove_entry(self, cache_key: CacheKey) -> bool:
        """Remove an entry by cache key. Returns whether it existed."""
        entity_type, key = cache_key
        store = self._store_for_type(entity_type)
        removed = store.pop(key, None) is not None
        self._lru.pop(cache_key, None)
        if removed:
            self._stats.evictions += 1
        return removed

    def _evict_if_expired(self, entity_type: str, key: Any) -> None:
        store = self._store_for_type(entity_type)
        entry = store.get(key)
        if entry and self._is_expired(entry):
            self._remove_entry((entity_type, key))

    def _touch_entry(self, entity_type: str, key: Any, entry: _CacheEntry[Any]) -> None:
        """Update LRU position and optionally renew TTL on access."""
        now = self._now()
        entry.last_accessed = now
        cache_key = (entity_type, key)
        self._lru.move_to_end(cache_key, last=True)

        if self.touch_on_read:
            entry.expires_at = self._compute_expiry(entity_type, None)

    def _record_access(self, entity_type: str, key: Any) -> None:
        cache_key = (entity_type, key)
        if cache_key in self._lru:
            self._lru.move_to_end(cache_key, last=True)

    def _enforce_size_limit(self) -> None:
        """Evict entries when ``max_size`` is exceeded."""
        if self.max_size is None or self.eviction_policy is EvictionPolicy.NONE:
            return

        while self._total_entries() > self.max_size and self._lru:
            oldest_key, _ = self._lru.popitem(last=False)
            self._remove_entry(oldest_key)

    def _total_entries(self) -> int:
        return (
            len(self._users)
            + len(self._members)
            + len(self._guilds)
            + len(self._channels)
            + len(self._generic)
        )

    def _put_entry(
        self,
        entity_type: str,
        key: Any,
        value: Any,
        *,
        ttl: float | None = None,
    ) -> None:
        """Store a value, update LRU, and enforce size limits."""
        store = self._store_for_type(entity_type)
        expires = self._compute_expiry(entity_type, ttl)
        now = self._now()
        store[key] = _CacheEntry(value=value, expires_at=expires, last_accessed=now)
        cache_key = (entity_type, key)
        self._lru[cache_key] = None
        self._lru.move_to_end(cache_key, last=True)
        self._enforce_size_limit()

    def _get_entry(self, entity_type: str, key: Any) -> Any | None:
        """Core lookup: evict expired, count hit/miss, optionally touch."""
        self._evict_if_expired(entity_type, key)
        store = self._store_for_type(entity_type)
        entry = store.get(key)
        if entry is None:
            self._stats.misses += 1
            return None

        self._stats.hits += 1
        if self.touch_on_read:
            self._touch_entry(entity_type, key, entry)
        else:
            self._record_access(entity_type, key)
        return entry.value

    def _touch(self, entity_type: str, key: Any) -> bool:
        """Explicitly renew TTL for an existing, non-expired entry."""
        self._evict_if_expired(entity_type, key)
        store = self._store_for_type(entity_type)
        entry = store.get(key)
        if entry is None:
            return False
        entry.expires_at = self._compute_expiry(entity_type, None)
        entry.last_accessed = self._now()
        self._record_access(entity_type, key)
        return True

    @staticmethod
    async def _resolve_fetcher(
        fetcher: Callable[[], T | None | Awaitable[T | None]],
    ) -> T | None:
        result = fetcher()
        if inspect.isawaitable(result):
            return await result
        return result

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    def get_user(self, user_id: int) -> User | None:
        with self._lock:
            return self._get_entry(ENTITY_USER, user_id)

    def set_user(self, user: User, ttl: float | None = None) -> None:
        if user.id is None:
            return
        with self._lock:
            self._put_entry(ENTITY_USER, user.id, user, ttl=ttl)

    def invalidate_user(self, user_id: int) -> bool:
        with self._lock:
            return self._remove_entry((ENTITY_USER, user_id))

    def touch_user(self, user_id: int) -> bool:
        with self._lock:
            return self._touch(ENTITY_USER, user_id)

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------

    def get_member(self, guild_id: int, user_id: int) -> Member | None:
        with self._lock:
            return self._get_entry(ENTITY_MEMBER, (guild_id, user_id))

    def set_member(self, member: Member, guild_id: int, ttl: float | None = None) -> None:
        if not (member.user and member.user.id):
            return
        with self._lock:
            self._put_entry(ENTITY_MEMBER, (guild_id, member.user.id), member, ttl=ttl)

    def invalidate_member(self, guild_id: int, user_id: int) -> bool:
        with self._lock:
            return self._remove_entry((ENTITY_MEMBER, (guild_id, user_id)))

    def touch_member(self, guild_id: int, user_id: int) -> bool:
        with self._lock:
            return self._touch(ENTITY_MEMBER, (guild_id, user_id))

    # ------------------------------------------------------------------
    # Guilds
    # ------------------------------------------------------------------

    def get_guild(self, guild_id: int) -> Guild | None:
        with self._lock:
            return self._get_entry(ENTITY_GUILD, guild_id)

    def set_guild(self, guild: Guild, ttl: float | None = None) -> None:
        if guild.id is None:
            return
        with self._lock:
            self._put_entry(ENTITY_GUILD, guild.id, guild, ttl=ttl)

    def invalidate_guild(self, guild_id: int) -> bool:
        with self._lock:
            removed = self._remove_entry((ENTITY_GUILD, guild_id))
            self._invalidate_by_guild_locked(guild_id)
            return removed

    def touch_guild(self, guild_id: int) -> bool:
        with self._lock:
            return self._touch(ENTITY_GUILD, guild_id)

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    def get_channel(self, channel_id: int) -> Channel | None:
        with self._lock:
            return self._get_entry(ENTITY_CHANNEL, channel_id)

    def set_channel(self, channel: Channel, ttl: float | None = None) -> None:
        if channel.id is None:
            return
        with self._lock:
            self._put_entry(ENTITY_CHANNEL, channel.id, channel, ttl=ttl)

    def invalidate_channel(self, channel_id: int) -> bool:
        with self._lock:
            return self._remove_entry((ENTITY_CHANNEL, channel_id))

    def touch_channel(self, channel_id: int) -> bool:
        with self._lock:
            return self._touch(ENTITY_CHANNEL, channel_id)

    # ------------------------------------------------------------------
    # High-level patterns
    # ------------------------------------------------------------------

    def get_or_set(
        self,
        getter: Callable[[], T | None],
        key: str,
        ttl: float | None = None,
    ) -> T | None:
        with self._lock:
            self._evict_if_expired(ENTITY_GENERIC, key)
            entry = self._generic.get(key)
            if entry is not None:
                self._stats.hits += 1
                if self.touch_on_read:
                    self._touch_entry(ENTITY_GENERIC, key, entry)
                else:
                    self._record_access(ENTITY_GENERIC, key)
                return entry.value

            value = getter()
            if value is not None:
                self._put_entry(ENTITY_GENERIC, key, value, ttl=ttl)
            else:
                self._stats.misses += 1
            return value

    async def get_or_fetch(
        self,
        cache_key: CacheKey,
        fetcher: Callable[[], T | None | Awaitable[T | None]],
        *,
        ttl: float | None = None,
        store: Callable[[T], None] | None = None,
        lookup: Callable[[], T | None] | None = None,
    ) -> T | None:
        if lookup is not None:
            cached = lookup()
            if cached is not None:
                return cached

        value = await self._resolve_fetcher(fetcher)
        if value is not None and store is not None:
            store(value)
        elif value is None:
            with self._lock:
                self._stats.misses += 1
        return value

    async def get_or_fetch_user(
        self,
        user_id: int,
        fetcher: Callable[[], User | None | Awaitable[User | None]],
        *,
        ttl: float | None = None,
    ) -> User | None:
        return await self.get_or_fetch(
            (ENTITY_USER, user_id),
            fetcher,
            ttl=ttl,
            lookup=lambda: self.get_user(user_id),
            store=lambda u: self.set_user(u, ttl=ttl),
        )

    async def get_or_fetch_member(
        self,
        guild_id: int,
        user_id: int,
        fetcher: Callable[[], Member | None | Awaitable[Member | None]],
        *,
        ttl: float | None = None,
    ) -> Member | None:
        return await self.get_or_fetch(
            (ENTITY_MEMBER, (guild_id, user_id)),
            fetcher,
            ttl=ttl,
            lookup=lambda: self.get_member(guild_id, user_id),
            store=lambda m: self.set_member(m, guild_id, ttl=ttl),
        )

    async def get_or_fetch_guild(
        self,
        guild_id: int,
        fetcher: Callable[[], Guild | None | Awaitable[Guild | None]],
        *,
        ttl: float | None = None,
    ) -> Guild | None:
        return await self.get_or_fetch(
            (ENTITY_GUILD, guild_id),
            fetcher,
            ttl=ttl,
            lookup=lambda: self.get_guild(guild_id),
            store=lambda g: self.set_guild(g, ttl=ttl),
        )

    async def get_or_fetch_channel(
        self,
        channel_id: int,
        fetcher: Callable[[], Channel | None | Awaitable[Channel | None]],
        *,
        ttl: float | None = None,
    ) -> Channel | None:
        return await self.get_or_fetch(
            (ENTITY_CHANNEL, channel_id),
            fetcher,
            ttl=ttl,
            lookup=lambda: self.get_channel(channel_id),
            store=lambda c: self.set_channel(c, ttl=ttl),
        )

    # ------------------------------------------------------------------
    # Bulk helpers
    # ------------------------------------------------------------------

    def bulk_get_users(self, user_ids: list[int]) -> dict[int, User]:
        result: dict[int, User] = {}
        with self._lock:
            for uid in user_ids:
                user = self._get_entry(ENTITY_USER, uid)
                if user is not None:
                    result[uid] = user
        return result

    def bulk_set_users(self, users: list[User], ttl: float | None = None) -> None:
        with self._lock:
            for user in users:
                if user.id is not None:
                    self._put_entry(ENTITY_USER, user.id, user, ttl=ttl)

    # ------------------------------------------------------------------
    # Invalidation & introspection
    # ------------------------------------------------------------------

    def _invalidate_by_guild_locked(self, guild_id: int) -> int:
        """Remove members for a guild. Caller must hold ``_lock``."""
        count = 0
        to_remove = [k for k in self._members if k[0] == guild_id]
        for key in to_remove:
            if self._remove_entry((ENTITY_MEMBER, key)):
                count += 1
        return count

    def invalidate_by_guild(self, guild_id: int) -> int:
        with self._lock:
            return self._invalidate_by_guild_locked(guild_id)

    def invalidate_by_type(self, type_name: str) -> int:
        type_name = type_name.lower()
        with self._lock:
            if type_name == ENTITY_USER:
                keys = list(self._users.keys())
            elif type_name == ENTITY_MEMBER:
                keys = list(self._members.keys())
            elif type_name == ENTITY_GUILD:
                keys = list(self._guilds.keys())
            elif type_name == ENTITY_CHANNEL:
                keys = list(self._channels.keys())
            elif type_name == ENTITY_GENERIC:
                keys = list(self._generic.keys())
            else:
                return 0

            count = 0
            for key in keys:
                if self._remove_entry((type_name, key)):
                    count += 1
            return count

    def clear(self) -> None:
        with self._lock:
            self._users.clear()
            self._members.clear()
            self._guilds.clear()
            self._channels.clear()
            self._generic.clear()
            self._lru.clear()

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                size_users=len(self._users),
                size_members=len(self._members),
                size_guilds=len(self._guilds),
                size_channels=len(self._channels),
                size_generic=len(self._generic),
            )


__all__ = [
    "DEFAULT_TTL_BY_TYPE",
    "ENTITY_CHANNEL",
    "ENTITY_GENERIC",
    "ENTITY_GUILD",
    "ENTITY_MEMBER",
    "ENTITY_USER",
    "CacheBackend",
    "CacheStats",
    "EvictionPolicy",
    "MemoryCache",
]
