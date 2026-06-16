# DiscordKit

**A modern, strongly-typed Python framework for Discord bots with excellent Developer Experience.**

DiscordKit is a fresh, from-the-ground-up framework focused on **clarity, type safety, and joy of use** — without the legacy baggage or heavy magic of older libraries.

It is designed to be the framework you actually *want* to use for both small personal bots and large, long-running production bots.

---

## Table of Contents

- [Why DiscordKit?](#why-discordkit)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [Core Concepts](#core-concepts)
  - [Client](#client)
  - [Commands & Options](#commands--options)
  - [Subcommands & Groups](#subcommands--groups)
  - [Components & Interactions](#components--interactions)
  - [Cache](#cache)
- [Using the Cache](#using-the-cache)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Production Considerations](#production-considerations)
- [Extending DiscordKit](#extending-discordkit)
- [API Reference](#api-reference)
- [Hot Reload](#hot-reload-development)
- [Testing](#testing-your-bot)
- [Examples](#examples)
- [Contributing](#contributing)
- [Roadmap & Philosophy](#roadmap--philosophy)
- [License](#license)

---

## Why DiscordKit?

- **Strong typing everywhere** — Powered by Pydantic v2 + `Annotated` + `Option`. Your IDE actually helps you.
- **Beautiful, explicit API** — Minimal magic. You can read the code and understand what happens.
- **First-class modern Discord features** — Subcommands & nested groups, rich options, components, modals, and autocomplete done right.
- **Production ready** — Robust error handling, structured logging, intelligent rate limiting, and a mature cache system.
- **Outstanding DX** — `discordkit new`, `discordkit run` (hot reload), and clean separation of concerns.
- **Grows with you** — Starts simple. Scales cleanly to complex command hierarchies and large codebases.

If you are tired of fighting your framework or writing `if isinstance` everywhere, DiscordKit is for you.

---

## Installation

**Recommended (uv):**

```bash
uv add discordkit
```

**With pip:**

```bash
pip install discordkit
```

Python **3.12+** is required.

---

## Quickstart

```python
import os
from typing import Annotated

from discordkit import Client, Config, User
from discordkit.commands import Option, command
from discordkit.types import Intents

config = Config(token=os.environ["DISCORD_TOKEN"], intents=Intents.DEFAULT)
bot = Client(config)

@command(name="ping", description="Replies with Pong!")
async def ping(ctx):
    await ctx.respond("Pong! 🏓")

@command(name="greet", description="Greet someone")
async def greet(
    ctx,
    user: Annotated[User, Option("Who to greet")],
    message: Annotated[str, Option("Optional message", max_length=100)] = "Hello!",
):
    await ctx.respond(f"{message} {user.mention}")

@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Logged in as {bot.user}")

bot.run()
```

Run with hot reload during development:

```bash
discordkit run
# or
discordkit run your_bot.py
```

---

## Core Concepts

### Client

The `Client` is the heart of every DiscordKit bot. It wires together:

| Subsystem | Responsibility |
|-----------|----------------|
| `bot.http` | REST API calls with automatic rate-limit handling |
| `bot.gateway` | WebSocket connection and event dispatch |
| `bot.commands` | Slash command registry and routing |
| `bot.components` | Button, select, and modal routing |
| `bot.cache` | Typed in-memory cache (swappable via `CacheBackend`) |

```python
from discordkit import Client, Config

bot = Client(Config(token="...", intents=Intents.DEFAULT))

# Lifecycle
await bot.start()   # async entry
bot.run()           # blocking helper (most common)

# Readiness
bot.is_ready        # True after READY event
bot.user            # Bot User model
bot.application_id  # Application ID for command sync
```

The client automatically syncs global slash commands on `READY` and populates the cache from resolved command options when `bot.auto_cache` is enabled (default).

### Commands & Options

DiscordKit uses a powerful `Annotated[T, Option(...)]` system:

```python
from typing import Annotated
from discordkit.commands import Option
from discordkit.models import User, Role, Channel

@command(name="ban", description="Ban a user")
async def ban(
    ctx,
    user: Annotated[User, Option("User to ban")],
    reason: Annotated[str, Option("Reason", min_length=5, max_length=400)],
    days: Annotated[int, Option("Days of messages to delete", min_value=0, max_value=7)] = 0,
):
    ...
```

Full feature set:
- `description`, `required` (auto-inferred from defaults)
- `min_length` / `max_length`, `min_value` / `max_value`
- `choices`, `channel_types`, `autocomplete`
- Rich Discord types: `User`, `Member`, `Role`, `Channel`, `Attachment`

When a slash command runs, `resolve_options` turns raw Discord payloads into real Pydantic models — so `ctx.options["user"]` is a `User`, not a raw ID.

### Subcommands & Groups

```python
@bot.group(name="config", description="Server settings")
async def config(ctx): ...

@config.command(name="set", description="Change a setting")
async def config_set(ctx, key: str, value: str): ...

# Nested groups are supported
@config.group(name="advanced", description="Dangerous options")
async def advanced(ctx): ...

@advanced.command(name="reset", description="Factory reset")
async def advanced_reset(ctx, confirm: bool = False): ...
```

The framework builds the correct Discord payload, routes to the exact leaf handler, and resolves options for deeply nested commands.

### Components & Interactions

```python
from discordkit.interactions import Button
from discordkit.types import ButtonStyle
from discordkit.components import ButtonContext

@bot.component("confirm")
async def on_confirm(ctx: ButtonContext):
    await ctx.edit_message(content="Confirmed!", components=[])

# In a command:
confirm_btn = Button(label="Confirm", style=ButtonStyle.SUCCESS, custom_id="confirm")
await ctx.respond("Are you sure?", components=[confirm_btn.to_dict()])
```

Modals and selects work the same way with `@bot.modal("id")` and `@bot.component("prefix:")` for prefix matching.

### Cache

DiscordKit ships a production-grade cache built on a stable `CacheBackend` interface:

- **Typed stores** for `User`, `Member`, `Guild`, and `Channel`
- **TTL** with global defaults, per-entity overrides, and sliding expiration (`touch_on_read`)
- **LRU eviction** when `max_size` is reached
- **`get_or_fetch`** — the cache-aside pattern bots use every day
- **Statistics** — hits, misses, evictions, hit rate
- **Thread-safe** `MemoryCache` for single-process bots
- **Persistent** — `PersistentCache` stores entries in SQLite across restarts
- **Extensible** — implement `CacheBackend` for Redis or other backends

See [Using the Cache](#using-the-cache) for detailed examples and best practices.

---

## Using the Cache

### Automatic population

When users run slash commands, resolved options are stored automatically:

```python
@command(name="profile", description="Show a user profile")
async def profile(ctx, user: Annotated[User, Option("User")]):
    # `user` came from Discord AND was cached
    cached = bot.get_cached_user(user.id)  # same object, no API call
    await ctx.respond(f"Hello, {cached.display_name}!")
```

Disable auto-caching if you prefer full manual control:

```python
bot.auto_cache = False
```

### Configuration

Configure the cache at startup with sensible production defaults:

```python
bot.configure_cache(
    default_ttl=600,          # 10 minutes fallback
    max_size=20_000,        # LRU eviction kicks in above this
    touch_on_read=True,     # renew TTL on every read (sliding window)
    ttl_by_type={
        "user": 900,        # users change infrequently
        "member": 180,      # nicknames/roles change more often
        "guild": 1800,
        "channel": 300,
    },
)
```

Or construct a `MemoryCache` directly and assign it:

```python
from discordkit import MemoryCache, EvictionPolicy

bot.cache = MemoryCache(
    default_ttl=300,
    max_size=10_000,
    eviction_policy=EvictionPolicy.LRU,
    touch_on_read=True,
)
```

### Manual read/write

```python
# Store
bot.cache.set_user(user)
bot.cache.set_member(member, guild_id=ctx.guild_id)
bot.cache.set_guild(guild)
bot.cache.set_channel(channel)

# Read
user = bot.cache.get_user(user_id)
member = bot.cache.get_member(guild_id, user_id)   # guild-scoped
guild = bot.cache.get_guild(guild_id)

# Invalidate
bot.cache.invalidate_user(user_id)
bot.cache.invalidate_member(guild_id, user_id)
bot.invalidate_guild_cache(guild_id)   # all members in a guild
bot.cache.invalidate_by_type("user")   # bulk clear
bot.cache.clear()                      # wipe everything

# Renew TTL without re-fetching
bot.cache.touch_user(user_id)
bot.cache.touch_member(guild_id, user_id)
```

### Cache-aside with `get_or_fetch`

The most common pattern in real bots — check cache first, fetch on miss:

```python
@command(name="lookup", description="Look up a user by ID")
async def lookup(ctx, user_id: Annotated[int, Option("User ID")]):
    async def fetch_from_api():
        data = await bot.http.get_user(user_id)
        return User.model_validate(data)

    user = await bot.cache.get_or_fetch_user(user_id, fetch_from_api)
    # Or via client convenience:
    # user = await bot.fetch_user_cached(user_id, fetch_from_api)

    if user is None:
        await ctx.respond("User not found.", ephemeral=True)
        return
    await ctx.respond(f"Found: **{user.display_name}**")
```

`get_or_fetch` accepts both sync and async fetchers. The same pattern exists for members, guilds, and channels.

### Statistics and monitoring

```python
stats = bot.cache_stats()
print(f"Hit rate: {stats.hit_rate:.1%}")
print(f"Entries: {stats.total_size} (users={stats.size_users}, members={stats.size_members})")
print(f"Evictions: {stats.evictions}")
```

Use these metrics in production to tune TTLs and `max_size`.

### Persistent cache (SQLite)

For bots that restart frequently, use `PersistentCache` to avoid cold-cache API spikes:

```python
from discordkit import PersistentCache

# Direct usage
cache = PersistentCache(path=".data/discordkit_cache.db", max_size=20_000)
bot.cache = cache

# Or via Client helper
bot.configure_cache(
    persistent=True,
    cache_path=".data/discordkit_cache.db",
    default_ttl=600,
    max_size=20_000,
)
```

On startup, non-expired entries are loaded from disk. Writes and invalidations are mirrored to SQLite automatically (stdlib `sqlite3`, no extra dependencies).

```python
# Maintenance
bot.cache.vacuum()   # purge expired rows, reclaim disk space
print(bot.cache.db_path)
```

### Best practices

1. **Let auto-cache do the easy work** — slash command options are free cache hits.
2. **Use `get_or_fetch` for API calls** — never call the REST API without checking cache first.
3. **Invalidate on mutations** — after banning, kicking, or updating roles, call `invalidate_member`.
4. **Tune TTLs per entity** — members change more often than guild metadata.
5. **Set `max_size`** — prevents unbounded memory growth in large bots.
6. **Plan for Redis** — implement `CacheBackend` when you need multi-process or persistence.

---

## Rate Limiting

DiscordKit handles Discord rate limits transparently inside `DiscordHTTPClient`. You normally never think about it — but understanding the internals helps when debugging slow responses.

### How it works

1. **Pre-request check** — Before each REST call, `RateLimiter.acquire()` checks whether the target bucket (or a global limit) is exhausted. If so, it sleeps until the reset time.
2. **Header parsing** — Every response updates state from Discord headers:
   - `X-RateLimit-Limit`
   - `X-RateLimit-Remaining`
   - `X-RateLimit-Reset` / `X-RateLimit-Reset-After`
   - `X-RateLimit-Bucket`
   - `X-RateLimit-Global`
3. **429 handling** — On `429 Too Many Requests`, the client reads `retry_after` from the body, sleeps, and retries (up to a safe limit).
4. **Logging** — Rate-limit waits are logged at `INFO`/`WARNING` so you can spot hot endpoints in production.

```python
# You don't need to write this — it happens automatically:
# await rate_limiter.acquire(bucket)
# response = await session.request(...)
# rate_limiter.update(response.headers, response.status)
```

### What you should do

- **Use the cache** — fewer API calls means fewer rate-limit hits.
- **Batch when possible** — `bulk_get_users` and cache-aside reduce round-trips.
- **Watch your logs** — repeated `Rate limit for bucket` messages indicate a hot loop.
- **Defer long commands** — for work that takes >3 seconds, call `ctx.defer()` before heavy API usage.

---

## Error Handling

DiscordKit catches errors inside command, component, autocomplete, and event handlers so your bot stays alive. Register a global handler for observability:

```python
import logging

logger = logging.getLogger("mybot")

@bot.error_handler
async def on_error(error: Exception, context: dict):
    """
    context keys:
      - type:     "command" | "component" | "autocomplete"
      - command:  full command path (for commands)
      - user_id:  Discord user ID
      - guild_id: guild ID (if applicable)
      - channel_id: channel ID (if applicable)
    """
    logger.error(
        "Handler failed | type=%s | cmd=%s | user=%s | error=%s",
        context.get("type"),
        context.get("command"),
        context.get("user_id"),
        error,
        exc_info=True,
    )

    # Production: send to Sentry, a logging channel, etc.
    # await notify_sentry(error, context)
```

### What happens on failure

| Handler type | User sees | Bot state |
|-------------|-----------|-----------|
| Slash command | Ephemeral "unexpected error" message | Keeps running |
| Component/modal | Logged, no crash | Keeps running |
| Autocomplete | Empty suggestions (safe fallback) | Keeps running |
| Event handler | Logged exception | Keeps running |

### Local recovery

Handle expected errors inside your command and only escalate what you cannot recover:

```python
@command(name="divide", description="Divide two numbers")
async def divide(ctx, a: int, b: int):
    if b == 0:
        await ctx.respond("Cannot divide by zero.", ephemeral=True)
        return
    await ctx.respond(f"Result: {a / b}")

@command(name="risky", description="May fail internally")
async def risky(ctx):
    try:
        result = await do_something()
    except ValueError as e:
        await ctx.respond(f"Handled: {e}", ephemeral=True)
        return
    await ctx.respond(f"Done: {result}")
```

See `examples/error_handling.py` for a complete production-oriented demo.

---

## Production Considerations

### Always register an error handler

At minimum, log structured context for every unhandled exception. In production, forward to Sentry, Datadog, or a private Discord logging channel.

### Configure the cache deliberately

```python
bot.configure_cache(
    default_ttl=600,
    max_size=20_000,
    touch_on_read=True,
    ttl_by_type={"member": 120},
)
```

Monitor `bot.cache_stats().hit_rate` and adjust TTLs based on your bot's access patterns.

### Logging

```python
config = Config(
    token=os.environ["DISCORD_TOKEN"],
    intents=Intents.DEFAULT,
    log_level="INFO",   # "DEBUG" only in development
    debug=False,
)
```

### Graceful shutdown

`bot.run()` handles `KeyboardInterrupt`. For custom lifecycle:

```python
import asyncio

async def main():
    bot = Client(config)
    try:
        await bot.start()
    finally:
        await bot.close()

asyncio.run(main())
```

### Security

- Store tokens in environment variables, never in source code.
- Use `SecretStr` in `Config` — tokens are not logged or repr'd.
- Validate permissions in commands before performing destructive actions.

### Performance checklist

- [ ] Cache enabled with appropriate TTLs and `max_size`
- [ ] `bot.auto_cache = True` (default)
- [ ] Global error handler registered
- [ ] `debug=False` in production
- [ ] Long-running commands use `ctx.defer()`
- [ ] Rate-limit warnings monitored in logs

---

## Extending DiscordKit

### Custom cache backend (Redis, etc.)

Implement `CacheBackend` and assign it to the client:

```python
from discordkit import CacheBackend
from discordkit.models import User, Member, Guild, Channel

class RedisCache(CacheBackend):
    def get_user(self, user_id: int) -> User | None:
        ...
    def set_user(self, user: User, ttl: float | None = None) -> None:
        ...
    # ... implement remaining abstract methods

bot.configure_cache(backend=RedisCache(...))
```

The interface is stable and documented — your backend only needs to satisfy the contract.

### Custom commands and middleware patterns

Commands are plain async functions registered via decorators:

```python
from discordkit.commands import command

@command(name="hello", description="Say hello")
async def hello(ctx):
    await ctx.respond("Hello!")

bot.add_command(hello)
```

For cross-cutting concerns (auth, logging, cooldowns), wrap handlers:

```python
from functools import wraps

def requires_admin(func):
    @wraps(func)
    async def wrapper(ctx, *args, **kwargs):
        if not ctx.member or not ctx.member_has_permission("administrator"):
            await ctx.respond("Admin only.", ephemeral=True)
            return
        return await func(ctx, *args, **kwargs)
    return wrapper

@bot.command(name="purge", description="Purge messages")
@requires_admin
async def purge(ctx, count: int):
    ...
```

### Custom components

Register handlers with `@bot.component(custom_id)` or prefix patterns:

```python
@bot.component("ticket:")
async def handle_ticket(ctx):
    ticket_id = ctx.custom_id.split(":")[1]
    ...
```

### Contributing new models

Models live in `discordkit.models` and extend `DiscordModel` (Pydantic v2). Follow existing patterns in `user.py`, `guild.py`, etc.

---

## API Reference

Full API documentation for every public class, method, and parameter:

**[docs/API_REFERENCE.md](docs/API_REFERENCE.md)**

Covers:
- `Client` — lifecycle, events, commands, cache, error handling
- `Config` — all configuration fields
- `CacheBackend` / `MemoryCache` / `PersistentCache` — complete method tables
- `Option` — constraints, validation rules, payload generation
- Context types — `CommandContext`, `ButtonContext`, `ModalContext`, etc.
- Models, types, rate limiting, and CLI

---

## Hot Reload (Development)

```bash
# From inside your project
discordkit run
```

Watches your Python files and restarts the bot cleanly on save. Uses `watchfiles` under the hood.

---

## Testing Your Bot

DiscordKit ships with a professional test setup using `pytest` + `pytest-asyncio`.

```bash
# Run tests
pytest

# Or with coverage
pytest --cov=src/discordkit
```

Key test areas covered out of the box:
- Command definition and payload generation (including subcommands)
- Complex option resolution (`User`, `Role`, etc.)
- Full slash command routing
- Component handlers
- Error handling paths
- Cache (TTL, LRU, `get_or_fetch`, statistics)

See the `tests/` directory for examples of unit-testing commands without a real Discord connection.

---

## Examples

High-quality, well-commented examples live in the `examples/` directory:

| File | What it demonstrates |
|------|---------------------|
| `simple_bot.py` | Minimal getting-started bot |
| `slash_commands.py` | Rich options + resolved models + autocomplete |
| `subcommands.py` | Groups and nested groups |
| `component_bot.py` | Buttons, selects, and modals |
| `advanced_commands.py` | Heavy use of the `Option` system |
| `moderation_bot.py` | Practical moderation with subcommands |
| `ticket_system.py` | Buttons + modals + staff subcommands |
| `error_handling.py` | Production error patterns |
| `economy_bot.py` | Stateful bot patterns |
| `suggestions_bot.py` | Community feature bot |

Start with `simple_bot.py`, then explore `slash_commands.py` and `subcommands.py`.

---

## Roadmap & Philosophy

DiscordKit prioritizes:

1. **Developer happiness** and **type safety**
2. **Correctness** over cleverness
3. **Production stability**

We are actively improving:
- Even better subcommand ergonomics and discovery
- More first-class Discord models and helpers
- Optional SQLAlchemy / async ORM integrations (via extensions)
- Sharding helpers
- Redis cache backend (as an official extension)

Contributions and feedback that align with the "clean, typed, delightful" philosophy are very welcome.

---

## Contributing

### Local development setup (recommended)

We use [uv](https://docs.astral.sh/uv/) for fast dependency management.

```bash
git clone https://github.com/discordkit/discordkit.git
cd discordkit

# Create virtual environment + install the project + dev dependencies
uv sync --dev
```

Activate the environment when needed:

```bash
source .venv/bin/activate   # or `uv run <command>` (no activation needed)
```

### Pre-commit hooks (strongly recommended)

Pre-commit runs fast checks (ruff, mypy, etc.) automatically before every commit.

```bash
# Install the git hooks (one-time setup)
uv run pre-commit-install

# Or directly:
uv run pre-commit install
```

Run checks manually on the whole codebase:

```bash
uv run pre-commit run --all-files
```

The configuration lives in [`.pre-commit-config.yaml`](.pre-commit-config.yaml). It includes:

- `ruff` (lint + auto-fix)
- `ruff-format`
- `mypy` (uses your project's strict configuration from `pyproject.toml`)
- Standard hygiene hooks (`check-yaml`, `trailing-whitespace`, `debug-statements`, etc.)

### Running checks manually

```bash
# Lint
uv run ruff check .

# Format check
uv run ruff format --check .

# Type checking (strict)
uv run mypy src/discordkit

# Tests (with coverage)
uv run test-cov

# All of the above in one command
uv run checks
```

### Continuous Integration

Every push and pull request to `main` runs the workflow defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml):

- Matrix: Python 3.12 and 3.13
- Steps: ruff check + format, mypy (strict), pytest + coverage
- Uses `uv` + dependency caching for speed

The CI **must pass** before a PR can be merged.

---

## License

MIT

---

**Made with care for developers who care about their tools.**