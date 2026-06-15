# DiscordKit API Reference

Complete reference for the public DiscordKit API. For tutorials and guides, see the [README](../README.md).

---

## Table of Contents

- [Core](#core)
  - [Client](#client)
  - [Config](#config)
  - [Cache](#cache)
  - [Context](#context)
  - [Rate Limiting](#rate-limiting)
- [Commands](#commands)
  - [command / group](#command--group)
  - [Option](#option)
  - [CommandRegistry](#commandregistry)
- [Components & Interactions](#components--interactions)
- [Models](#models)
- [Types](#types)
- [CLI](#cli)

---

## Core

### Client

```python
from discordkit import Client, Config

bot = Client(config)
```

#### Constructor

| Parameter | Type | Description |
|-----------|------|-------------|
| `config` | `Config` | Validated bot configuration |

#### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `config` | `Config` | Immutable configuration |
| `http` | `DiscordHTTPClient` | REST API client |
| `gateway` | `Gateway` | WebSocket connection |
| `commands` | `CommandRegistry` | Slash command registry |
| `components` | `ComponentRouter` | Button/select/modal router |
| `cache` | `CacheBackend` | Entity cache (default: `MemoryCache`) |
| `user` | `User \| None` | Bot user after READY |
| `application_id` | `int \| None` | Application ID after READY |
| `is_ready` | `bool` | Whether READY has been received |
| `auto_cache` | `bool` | Auto-store resolved command options |

#### Lifecycle

```python
bot.run()              # Blocking; runs until KeyboardInterrupt
await bot.start()      # Async; connect and keep alive
await bot.close()      # Graceful shutdown
await bot.fetch_me()   # Fetch bot user via REST
```

#### Event registration

```python
@bot.event("ready")
async def on_ready(ctx: Context): ...

bot.on("message_create", handler)   # Programmatic registration
```

Supported gateway events are dispatched by name (lowercase), plus a generic `"event"` catch-all.

#### Command registration

```python
bot.add_command(cmd)                    # Register a Command object
@bot.command(name="ping", description="...")
async def ping(ctx): ...

@bot.group(name="admin", description="...")
async def admin(ctx): ...
```

#### Component & modal registration

```python
@bot.component("confirm")               # Exact match
@bot.component("color:")                # Prefix match
async def on_color(ctx: SelectContext): ...

@bot.modal("feedback")
async def on_feedback(ctx: ModalContext): ...
```

#### Autocomplete

```python
@bot.autocomplete("search", "query")
async def search_ac(ctx: AutocompleteContext):
    await ctx.respond([{"name": "Result", "value": "result"}])
```

#### Error handling

```python
@bot.error_handler
async def on_error(error: Exception, context: dict): ...

bot.error_handler(my_handler)   # Programmatic
```

`context` keys: `type`, `command`, `user_id`, `guild_id`, `channel_id`.

#### Cache helpers

```python
bot.configure_cache(
    default_ttl=600,
    max_size=20_000,
    touch_on_read=True,
    ttl_by_type={"member": 120},
    persistent=True,                          # Use PersistentCache
    cache_path=".data/discordkit_cache.db",
)

bot.get_cached_user(user_id)                # User | None
bot.get_cached_member(guild_id, user_id)    # Member | None
bot.get_cached_guild(guild_id)              # Guild | None
bot.get_cached_channel(channel_id)          # Channel | None

await bot.fetch_user_cached(user_id, fetcher)
await bot.fetch_member_cached(guild_id, user_id, fetcher)

bot.invalidate_guild_cache(guild_id)        # int — members removed
bot.cache_stats()                           # CacheStats
```

---

### Config

```python
from discordkit import Config
from discordkit.types import Intents

config = Config(
    token="...",                    # SecretStr — required
    intents=Intents.DEFAULT,        # Gateway intents
    debug=False,                    # Verbose logging
    log_level="INFO",               # DEBUG | INFO | WARNING | ERROR | CRITICAL
    prefix=None,                    # Legacy text command prefix
    shard_count=None,               # Auto shard count
    max_retries=5,                  # Gateway reconnect attempts
    reconnect_base_delay=1.0,       # Backoff base (seconds)
    http_timeout=15.0,              # REST timeout
    user_agent="DiscordKit (...)",  # HTTP User-Agent
    enable_hot_reload=False,        # CLI hot reload flag
)
```

`Config` is **immutable** (`frozen=True`). Typos in field names raise at construction time.

---

### Cache

#### CacheBackend (abstract interface)

Stable contract for all cache implementations. Implement every method to create a custom backend (Redis, etc.).

**Entity accessors** — each type has `get_*`, `set_*`, `invalidate_*`, `touch_*`:

| Entity | Get | Set | Invalidate |
|--------|-----|-----|------------|
| User | `get_user(user_id)` | `set_user(user, ttl=None)` | `invalidate_user(user_id)` |
| Member | `get_member(guild_id, user_id)` | `set_member(member, guild_id, ttl=None)` | `invalidate_member(guild_id, user_id)` |
| Guild | `get_guild(guild_id)` | `set_guild(guild, ttl=None)` | `invalidate_guild(guild_id)` |
| Channel | `get_channel(channel_id)` | `set_channel(channel, ttl=None)` | `invalidate_channel(channel_id)` |

**Cache-aside patterns:**

```python
# Sync — arbitrary string keys
value = cache.get_or_set(getter, "my-key", ttl=60)

# Async — typed entities (fetcher can be sync or async)
user   = await cache.get_or_fetch_user(user_id, fetcher)
member = await cache.get_or_fetch_member(guild_id, user_id, fetcher)
guild  = await cache.get_or_fetch_guild(guild_id, fetcher)
channel = await cache.get_or_fetch_channel(channel_id, fetcher)
```

**Bulk & invalidation:**

```python
cache.bulk_get_users([1, 2, 3])       # dict[int, User]
cache.bulk_set_users(users, ttl=None)
cache.invalidate_by_guild(guild_id)   # members only; returns count
cache.invalidate_by_type("user")      # "user" | "member" | "guild" | "channel" | "generic"
cache.clear()
cache.stats()                       # CacheStats snapshot
```

#### MemoryCache

```python
from discordkit import MemoryCache, EvictionPolicy

cache = MemoryCache(
    default_ttl=300.0,              # Seconds; 0 or None = no expiry
    max_size=10_000,                # None = unlimited
    eviction_policy=EvictionPolicy.LRU,
    touch_on_read=True,             # Sliding TTL on read
    ttl_by_type={
        "user": 600,
        "member": 300,
        "guild": 900,
        "channel": 300,
    },
)
```

Thread-safe via `threading.RLock`.

#### PersistentCache

```python
from discordkit import PersistentCache

cache = PersistentCache(
    path=".data/discordkit_cache.db",   # SQLite file; dirs created automatically
    default_ttl=300.0,
    max_size=20_000,
    touch_on_read=True,
)
```

Extends `MemoryCache` with SQLite durability:

- Non-expired entries are loaded on startup
- Every write/invalidation is mirrored to disk
- `cache.db_path` — resolved absolute path to the database
- `cache.vacuum()` — purge expired rows and reclaim disk space

```python
# Via Client
bot.configure_cache(persistent=True, cache_path=".data/bot.db")
```

#### CacheStats

| Field | Type | Description |
|-------|------|-------------|
| `hits` | `int` | Successful cache lookups |
| `misses` | `int` | Cache misses |
| `evictions` | `int` | TTL + LRU evictions |
| `size_users` | `int` | User entries |
| `size_members` | `int` | Member entries |
| `size_guilds` | `int` | Guild entries |
| `size_channels` | `int` | Channel entries |
| `size_generic` | `int` | Generic key entries |
| `total_size` | `int` | Sum of all sizes (property) |
| `hit_rate` | `float` | hits / (hits + misses) (property) |

#### EvictionPolicy

```python
EvictionPolicy.NONE   # No size-based eviction
EvictionPolicy.LRU    # Least Recently Used (default when max_size is set)
```

---

### Context

#### Context (gateway events)

```python
@bot.event("message_create")
async def on_message(ctx: Context):
    ctx.client          # Client
    ctx.event_name      # e.g. "MESSAGE_CREATE"
    ctx.raw_data        # Raw gateway payload dict
```

#### CommandContext (slash commands)

Inherits all `InteractionContext` response helpers.

| Attribute | Type | Description |
|-----------|------|-------------|
| `command_name` | `str` | Full command path (e.g. `admin ban`) |
| `options` | `dict[str, Any]` | Resolved option values (typed models) |
| `user` | `User \| None` | Invoking user |
| `member` | `Member \| None` | Guild member (in guilds) |
| `guild` | `Guild \| None` | Guild (may be enriched on demand) |
| `channel_id` | `int \| None` | Channel ID |

**Response methods** (shared with all interaction contexts):

```python
await ctx.respond("Hello!", ephemeral=True)
await ctx.respond("Pick one", components=[...])
await ctx.defer(ephemeral=True)
await ctx.defer(thinking=True)
await ctx.followup("Done!", ephemeral=True)
await ctx.edit_message(content="Updated", components=[])
```

#### AutocompleteContext

| Attribute | Type | Description |
|-----------|------|-------------|
| `command_name` | `str` | Command being autocompleted |
| `option_name` | `str` | Focused option name |
| `value` | `str` | Current partial input |

```python
await ctx.respond([{"name": "Display", "value": "value"}, ...])  # max 25
```

#### Component contexts

| Class | Used for | Extra attributes |
|-------|----------|-----------------|
| `ComponentContext` | Base | `custom_id`, `component_type` |
| `ButtonContext` | Buttons | — |
| `SelectContext` | Select menus | `values: list[str]` |
| `ModalContext` | Modal submits | `get_value(field_id)` |

---

### Rate Limiting

Handled automatically by `DiscordHTTPClient`. No user action required.

#### RateLimiter

```python
from discordkit.core.rate_limit import RateLimiter, RateLimitInfo

limiter = RateLimiter()
await limiter.acquire(bucket="abc123")          # Sleep if bucket exhausted
info = limiter.update(headers, status_code, body)
limiter.get_bucket_info("abc123")               # RateLimitInfo | None
```

#### RateLimitInfo

| Field | Type | Description |
|-------|------|-------------|
| `limit` | `int \| None` | Max requests per window |
| `remaining` | `int \| None` | Requests left |
| `reset` | `float \| None` | Absolute monotonic reset time |
| `reset_after` | `float \| None` | Seconds until reset |
| `bucket` | `str \| None` | Discord bucket hash |
| `is_global` | `bool` | Global rate limit flag |

On `429`, the client reads `retry_after` from the body, sleeps, and retries.

---

## Commands

### command / group

```python
from discordkit.commands import command, group

@command(name="ping", description="Ping", guild_ids=None, nsfw=False)
async def ping(ctx): ...

@group(name="mod", description="Moderation")
async def mod(ctx): ...

@mod.command(name="ban", description="Ban a user")
async def ban(ctx, user: User, reason: str = "No reason"): ...
```

#### Command object

| Method / attribute | Description |
|--------------------|-------------|
| `cmd.name` | Command name |
| `cmd.description` | Description |
| `cmd.options` | Discord option dicts |
| `cmd.children` | Subcommands / sub-groups |
| `cmd.to_discord_payload()` | Discord API registration payload |
| `cmd.invoke(ctx)` | Invoke the handler |
| `cmd.command(...)` | Decorator for subcommands |
| `cmd.group(...)` | Decorator for nested groups |

### Option

```python
from typing import Annotated
from discordkit.commands import Option

param: Annotated[str, Option(
    "Description",          # Required first argument
    required=None,          # Auto-inferred from default
    autocomplete=False,
    min_length=None,
    max_length=None,
    min_value=None,
    max_value=None,
    choices=["a", "b"],     # or [("Label", "value"), ...]
    channel_types=[0, 5],   # For Channel options
)]
```

**Validation rules:**
- `description` cannot be empty
- Cannot combine `choices` and `autocomplete`
- `min_length`/`max_length` only on STRING options
- `min_value`/`max_value` only on INTEGER/NUMBER options
- `channel_types` only on CHANNEL options

Unset constraint fields are **omitted** from the Discord payload (not sent as `null`).

### CommandRegistry

Accessed via `bot.commands`.

```python
bot.commands.register(command)
bot.commands.sync_global_commands(application_id)
bot.commands.resolve_command_from_interaction(data)
```

---

## Components & Interactions

### Static builders

```python
from discordkit.interactions import Button, Modal, SelectMenu
from discordkit.types import ButtonStyle

btn = Button(label="OK", style=ButtonStyle.PRIMARY, custom_id="ok", disabled=False)
modal = Modal(title="Feedback", custom_id="feedback", components=[...])
select = SelectMenu(custom_id="color", placeholder="Pick", options=[...], min_values=1, max_values=1)
```

All builders expose `.to_dict()` for Discord API payloads.

### ComponentRouter

Accessed via `bot.components`. Routes `MESSAGE_COMPONENT` and `MODAL_SUBMIT` interactions by `custom_id` (exact or prefix match ending with `:`).

---

## Models

All models extend `DiscordModel` (Pydantic v2). Common fields and helpers:

| Model | Key fields | Helpers |
|-------|-----------|---------|
| `User` | `id`, `username`, `global_name`, `avatar`, `bot` | `.display_name`, `.mention` |
| `Member` | `user`, `nick`, `roles`, `joined_at` | `.display_name`, `.mention` |
| `Guild` | `id`, `name`, `owner_id`, `roles`, `features` | — |
| `Channel` | `id`, `name`, `type`, `guild_id` | — |
| `Role` | `id`, `name`, `permissions`, `color` | — |
| `Message` | `id`, `content`, `author`, `channel_id` | — |
| `Attachment` | `id`, `filename`, `url`, `size` | — |

```python
user = User.model_validate(discord_payload)
data = user.model_dump(mode="json")
```

---

## Types

```python
from discordkit.types import (
    Intents,
    Permissions,
    ApplicationCommandType,
    ApplicationCommandOptionType,
    InteractionType,
    InteractionResponseType,
    ButtonStyle,
)
```

### Intents (flags)

```python
Intents.DEFAULT
Intents.GUILD_MEMBERS
Intents.MESSAGE_CONTENT
Intents.GUILDS
# Combine with |
config = Config(token="...", intents=Intents.DEFAULT | Intents.GUILD_MEMBERS)
```

---

## CLI

```bash
discordkit new <name>     # Scaffold a new bot project
discordkit run [file]     # Run with hot reload
```

Entry point: `discordkit.cli:main` (Typer-based).

---

## Package exports

```python
from discordkit import (
    # Core
    Client, Config, Context, InteractionContext, AutocompleteContext,
    MemoryCache, PersistentCache, CacheBackend, CacheStats, EvictionPolicy,
    GatewayEvent,
    # Commands
    Command, CommandContext, Option, command, group, resolve_options,
    # Interactions
    Button, Modal, SelectMenu,
    # Components
    ComponentContext, ButtonContext, SelectContext, ModalContext,
    # Models
    User, Member, Guild, Channel, Message, Attachment, Role,
    # Types
    Intents, Permissions, ApplicationCommandType,
)
```

---

*DiscordKit v0.2.0 — MIT License*