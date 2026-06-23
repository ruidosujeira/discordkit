"""
discordkit.core.cache_persistent
================================

SQLite-backed persistent cache for DiscordKit.

``PersistentCache`` extends :class:`MemoryCache` with disk durability so cached
entities survive bot restarts. It uses the standard library ``sqlite3`` module
(no extra dependencies) and stores Pydantic models as JSON.

Typical usage::

    from discordkit import PersistentCache

    cache = PersistentCache(path=".data/discordkit_cache.db", max_size=20_000)
    bot.configure_cache(backend=cache)

On startup, non-expired entries are loaded into memory. Every write and
invalidation is mirrored to SQLite under the same ``RLock`` used by
:class:`MemoryCache`, keeping the in-memory view and disk store consistent.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from ..models import Channel, Guild, Member, User
from ..models.base import DiscordModel
from .cache import (
    ENTITY_CHANNEL,
    ENTITY_GENERIC,
    ENTITY_GUILD,
    ENTITY_MEMBER,
    ENTITY_USER,
    CacheKey,
    EvictionPolicy,
    MemoryCache,
    _CacheEntry,
)

# Pydantic model registry for typed entity deserialization.
_ENTITY_MODELS: dict[str, type[DiscordModel]] = {
    ENTITY_USER: User,
    ENTITY_MEMBER: Member,
    ENTITY_GUILD: Guild,
    ENTITY_CHANNEL: Channel,
}


def _encode_key(entity_type: str, key: Any) -> tuple[str, str]:
    """Map an in-memory cache key to SQLite primary/secondary columns."""
    if entity_type == ENTITY_MEMBER:
        guild_id, user_id = key
        return str(guild_id), str(user_id)
    if entity_type == ENTITY_GENERIC:
        return str(key), ""
    return str(key), ""


def _decode_key(entity_type: str, primary: str, secondary: str) -> Any:
    """Restore an in-memory cache key from SQLite columns."""
    if entity_type == ENTITY_MEMBER:
        return int(primary), int(secondary)
    if entity_type == ENTITY_GENERIC:
        return primary
    return int(primary)


class PersistentCache(MemoryCache):
    """In-memory cache with SQLite persistence.

    Parameters
    ----------
    path:
        SQLite database file. Parent directories are created automatically.
    default_ttl, max_size, eviction_policy, touch_on_read, ttl_by_type:
        Forwarded to :class:`MemoryCache`.

    Notes
    -----
    - Generic (string-keyed) entries are JSON-serialized; store only JSON-safe values.
    - Expired entries are skipped on load and deleted from disk on access.
    - Implements the full :class:`~discordkit.core.cache.CacheBackend` contract.
    """

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS cache_entries (
        entity_type   TEXT NOT NULL,
        key_primary   TEXT NOT NULL,
        key_secondary TEXT NOT NULL DEFAULT '',
        value_json    TEXT NOT NULL,
        expires_at    REAL,
        last_accessed REAL NOT NULL,
        PRIMARY KEY (entity_type, key_primary, key_secondary)
    );
    CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);
    """

    def __init__(
        self,
        path: str | Path = ".discordkit_cache.db",
        default_ttl: float | None = 300.0,
        *,
        max_size: int | None = None,
        eviction_policy: EvictionPolicy = EvictionPolicy.LRU,
        touch_on_read: bool = False,
        ttl_by_type: dict[str, float] | None = None,
    ) -> None:
        self._db_path = Path(path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._loading = False

        super().__init__(
            default_ttl=default_ttl,
            max_size=max_size,
            eviction_policy=eviction_policy,
            touch_on_read=touch_on_read,
            ttl_by_type=ttl_by_type,
        )
        self._init_db()
        self._load_from_disk()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(self._SCHEMA)

    def _serialize(self, entity_type: str, value: Any) -> str:
        if entity_type == ENTITY_GENERIC:
            return json.dumps(value)
        model = _ENTITY_MODELS.get(entity_type)
        if model is not None and isinstance(value, model):
            return value.model_dump_json()
        raise TypeError(f"Cannot serialize {type(value)!r} for entity type {entity_type!r}")

    def _deserialize(self, entity_type: str, raw: str) -> Any:
        if entity_type == ENTITY_GENERIC:
            return json.loads(raw)
        model = _ENTITY_MODELS[entity_type]
        return model.model_validate_json(raw)

    def _persist_entry(
        self,
        entity_type: str,
        key: Any,
        value: Any,
        *,
        expires_at: float | None,
        last_accessed: float,
    ) -> None:
        if self._loading:
            return
        primary, secondary = _encode_key(entity_type, key)
        value_json = self._serialize(entity_type, value)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO cache_entries
                    (entity_type, key_primary, key_secondary, value_json, expires_at, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_type, key_primary, key_secondary) DO UPDATE SET
                    value_json    = excluded.value_json,
                    expires_at    = excluded.expires_at,
                    last_accessed = excluded.last_accessed
                """,
                (entity_type, primary, secondary, value_json, expires_at, last_accessed),
            )

    def _delete_entry(self, cache_key: CacheKey) -> None:
        if self._loading:
            return
        entity_type, key = cache_key
        primary, secondary = _encode_key(entity_type, key)
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM cache_entries WHERE entity_type=? AND key_primary=? AND key_secondary=?",
                (entity_type, primary, secondary),
            )

    def _clear_disk(self) -> None:
        if self._loading:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM cache_entries")

    def _load_from_disk(self) -> None:
        """Hydrate in-memory stores from SQLite, skipping expired rows."""
        now = self._now()
        self._loading = True
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT entity_type, key_primary, key_secondary, value_json, expires_at, last_accessed "
                    "FROM cache_entries"
                ).fetchall()

            expired_keys: list[CacheKey] = []

            with self._lock:
                for entity_type, primary, secondary, value_json, expires_at, last_accessed in rows:
                    if expires_at is not None and now >= expires_at:
                        expired_keys.append(
                            (entity_type, _decode_key(entity_type, primary, secondary))
                        )
                        continue

                    try:
                        value = self._deserialize(entity_type, value_json)
                    except Exception:
                        expired_keys.append(
                            (entity_type, _decode_key(entity_type, primary, secondary))
                        )
                        continue

                    key = _decode_key(entity_type, primary, secondary)
                    store = self._store_for_type(entity_type)
                    store[key] = _CacheEntry(
                        value=value,
                        expires_at=expires_at,
                        last_accessed=last_accessed,
                    )
                    cache_key = (entity_type, key)
                    self._lru[cache_key] = None
                    self._lru.move_to_end(cache_key, last=True)

            for cache_key in expired_keys:
                self._delete_entry(cache_key)
        finally:
            self._loading = False

    def _put_entry(
        self,
        entity_type: str,
        key: Any,
        value: Any,
        *,
        ttl: float | None = None,
    ) -> None:
        store = self._store_for_type(entity_type)
        expires = self._compute_expiry(entity_type, ttl)
        now = self._now()
        store[key] = _CacheEntry(value=value, expires_at=expires, last_accessed=now)
        cache_key = (entity_type, key)
        self._lru[cache_key] = None
        self._lru.move_to_end(cache_key, last=True)
        self._persist_entry(entity_type, key, value, expires_at=expires, last_accessed=now)
        self._enforce_size_limit()

    def _remove_entry(self, cache_key: CacheKey) -> bool:
        entity_type, key = cache_key
        store = self._store_for_type(entity_type)
        removed = store.pop(key, None) is not None
        self._lru.pop(cache_key, None)
        if removed:
            self._stats.evictions += 1
            self._delete_entry(cache_key)
        return removed

    def _touch_entry(self, entity_type: str, key: Any, entry: _CacheEntry[Any]) -> None:
        super()._touch_entry(entity_type, key, entry)
        if not self._loading:
            self._persist_entry(
                entity_type,
                key,
                entry.value,
                expires_at=entry.expires_at,
                last_accessed=entry.last_accessed,
            )

    def _touch(self, entity_type: str, key: Any) -> bool:
        with self._lock:
            self._evict_if_expired(entity_type, key)
            store = self._store_for_type(entity_type)
            entry = store.get(key)
            if entry is None:
                return False
            entry.expires_at = self._compute_expiry(entity_type, None)
            entry.last_accessed = self._now()
            self._record_access(entity_type, key)
            if not self._loading:
                self._persist_entry(
                    entity_type,
                    key,
                    entry.value,
                    expires_at=entry.expires_at,
                    last_accessed=entry.last_accessed,
                )
            return True

    def clear(self) -> None:
        with self._lock:
            super().clear()
            self._clear_disk()

    @property
    def db_path(self) -> Path:
        """Absolute path to the SQLite database file."""
        return self._db_path.resolve()

    def vacuum(self) -> None:
        """Reclaim disk space and remove expired rows from SQLite."""
        now = time.monotonic()
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at < ?", (now,)
            )
            conn.execute("VACUUM")


__all__ = ["PersistentCache"]
