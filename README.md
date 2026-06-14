# DiscordKit

**A modern, strongly-typed Python framework for Discord bots with excellent Developer Experience.**

DiscordKit is a fresh, from-the-ground-up framework focused on **clarity, type safety, and joy of use** — without the legacy baggage or heavy magic of older libraries.

It is designed to be the framework you actually *want* to use for both small personal bots and large, long-running production bots.

---

## Why DiscordKit?

- **Strong typing everywhere** — Powered by Pydantic v2 + `Annotated` + `Option`. Your IDE actually helps you.
- **Beautiful, explicit API** — Minimal magic. You can read the code and understand what happens.
- **First-class modern Discord features** — Subcommands & nested groups, rich options, components, modals, and autocomplete done right.
- **Production ready** — Robust error handling, structured logging, and graceful failure modes.
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

from discordkit import Client, Config
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

### Commands & Options

DiscordKit uses a powerful `Annotated[T, Option(...)]` system:

```python
from typing import Annotated
from discordkit.commands import Option

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
- `choices`
- `channel_types`
- `autocomplete`
- Rich Discord types: `User`, `Member`, `Role`, `Channel`, `Attachment`

### Subcommands & Groups (Full Support)

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

The framework correctly builds the Discord payload, routes to the exact leaf handler, and resolves options for deeply nested commands.

### Components & Interactions

```python
from discordkit.interactions import Button
from discordkit.types import ButtonStyle

@bot.component("confirm")
async def on_confirm(ctx: ButtonContext):
    await ctx.edit_message(content="Confirmed!", components=[])

# In a command:
confirm_btn = Button(label="Confirm", style=ButtonStyle.SUCCESS, custom_id="confirm")
await ctx.respond("Are you sure?", components=[confirm_btn.to_dict()])
```

Modals and selects work the same way with `@bot.modal("id")`.

### Autocomplete

```python
@bot.autocomplete("search", "query")
async def search_autocomplete(ctx: AutocompleteContext):
    suggestions = [
        {"name": f"Result for {ctx.value}", "value": ctx.value},
    ]
    await ctx.respond(suggestions)
```

### Error Handling (Production Grade)

```python
@bot.error_handler
async def on_error(error: Exception, context: dict):
    print(f"Error in {context.get('command')}: {error}")
    # Send to Sentry, Discord logging channel, etc.

# Errors inside any handler (commands, components, autocomplete) are caught
# and will never crash your bot.
```

---

## Examples

High-quality, well-commented examples live in the `/examples` directory:

- `basic_bot.py` — Minimal getting-started bot
- `slash_commands.py` — Rich options + resolved models + autocomplete
- `subcommands.py` — Complete demonstration of groups and nested groups
- `component_bot.py` — Buttons, selects, and modals
- `advanced_commands.py` — Heavy use of the `Option` system
- `error_handling.py` (conceptual in README) — Production error patterns

Start with `basic_bot.py`, then explore `subcommands.py` and `slash_commands.py`.

---

## Hot Reload (Development)

```bash
# From inside your project
discordkit run
```

Watches your Python files and restarts the bot cleanly on save. Uses `watchfiles` under the hood.

---

## Project Structure Recommendation

DiscordKit works great with both flat scripts and larger `src/` layouts (the `discordkit new` generator creates a clean structure for you).

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

Contributions and feedback that align with the "clean, typed, delightful" philosophy are very welcome.

---

## License

MIT

---

---

## Advanced Features

### Subcommands & Command Groups

DiscordKit has first-class support for deeply nested command structures.

```python
@bot.group(name="admin", description="Administration")
async def admin(ctx): ...

@admin.command(name="ban", description="Ban a user")
async def ban(ctx, user: Annotated[User, Option("User")], reason: str): ...

# You can even nest groups
@admin.group(name="config", description="Advanced configuration")
async def config_group(ctx): ...

@config_group.command(name="set", description="Set a value")
async def set_value(ctx, key: str, value: str): ...
```

The framework correctly builds the Discord payload and routes interactions to the exact leaf handler.

### Cache

DiscordKit includes a simple but useful in-memory cache:

```python
# Automatically populated when resolving options
user = ctx.options.get("user")   # This is a real User object

# Manual usage
bot.cache.set_user(some_user)
cached = bot.cache.get_user(123456)
bot.cache.invalidate_user(123456)

# Members, Guilds and Channels are also supported
bot.cache.set_member(member, guild_id=...)
```

You can configure default TTL on construction:

```python
bot = Client(config)
bot.cache = MemoryCache(default_ttl=600)  # 10 minutes
```

### Rate Limit Handling

The HTTP client handles Discord rate limits intelligently and transparently:

- Detects `429` responses
- Respects `X-RateLimit-Reset-After`, `X-RateLimit-Remaining`, global limits, etc.
- Automatic backoff + retry (up to a safe limit)
- Logs rate limit events

You normally don't need to do anything — it just works.

### Testing Your Bot

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

See the `tests/` directory for examples of unit-testing commands without a real Discord connection.

---

## Examples

High-quality, real-world examples are available in the `examples/` folder:

- `basic_bot.py` — Minimal getting started
- `slash_commands.py` — Rich options + resolved objects + autocomplete
- `subcommands.py` — Complete group and nested group demonstration
- `moderation_bot.py` — Practical moderation commands with subcommands
- `ticket_system.py` — Buttons + Modals + staff subcommands
- `error_handling.py` — Production-grade error patterns
- `component_bot.py` — Interactive components

We recommend starting with `slash_commands.py` and `subcommands.py`.

---

## Production Tips

- Always register at least one global error handler using `@bot.error_handler`
- Use the built-in cache to reduce API calls
- Run your bot with `discordkit run` during development
- Enable `debug=True` only in development (via Config)
- Monitor rate limit warnings in your logs

---

**Made with care for developers who care about their tools.**
