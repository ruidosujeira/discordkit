"""
DiscordKit
==========

A modern, strongly-typed Python framework for building Discord bots
with excellent Developer Experience.

Key principles:
- Strong typing with Pydantic v2 everywhere possible
- Minimal magic, explicit where it matters
- Outstanding DX for both small bots and large applications
- Built-in support for hot reload during development
- Clean separation between core, commands, interactions and models

Example:
    from discordkit import Client, Config
    from discordkit.commands import command

    config = Config(token="...", intents=...)
    bot = Client(config)

    @command()
    async def ping(ctx):
        await ctx.respond("Pong!")

    bot.add_command(ping)
    bot.run()
"""

from __future__ import annotations

__version__ = "0.2.0"
__author__ = "DiscordKit Contributors"

# Core exports - the main public API surface
# Command system
from .commands import (
    Command,
    CommandContext,
    Option,
    command,
    group,
    resolve_options,
)

# Component + Modal callback routing (new in 0.2)
from .components import (
    ButtonContext,
    ComponentContext,
    ModalContext,
    SelectContext,
)
from .core.cache import CacheBackend, CacheStats, EvictionPolicy, MemoryCache
from .core.cache_persistent import PersistentCache
from .core.client import Client
from .core.config import Config
from .core.context import AutocompleteContext, Context, InteractionContext
from .core.gateway import GatewayEvent

# Interaction components (buttons, modals, etc.)
from .interactions import (
    Button,
    Modal,
    SelectMenu,
)

# Public models (Pydantic)
from .models import (
    Attachment,
    Channel,
    Guild,
    Member,
    Message,
    Role,
    User,
)

# Re-export important types
from .types import (
    ApplicationCommandType,
    Intents,
    Permissions,
)

__all__ = [
    "ApplicationCommandType",
    "Attachment",
    "AutocompleteContext",
    # Static interaction builders
    "Button",
    "ButtonContext",
    "CacheBackend",
    "CacheStats",
    "Channel",
    # Core
    "Client",
    # Commands
    "Command",
    "CommandContext",
    # Component callback routing
    "ComponentContext",
    "Config",
    "Context",
    "EvictionPolicy",
    "GatewayEvent",
    "Guild",
    # Types
    "Intents",
    "InteractionContext",
    "Member",
    "MemoryCache",
    "Message",
    "Modal",
    "ModalContext",
    "Option",
    "Permissions",
    "PersistentCache",
    "Role",
    "SelectContext",
    "SelectMenu",
    # Models
    "User",
    # Metadata
    "__version__",
    "command",
    "group",
    "resolve_options",
]
