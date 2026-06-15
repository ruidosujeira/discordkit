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
from .core.cache import CacheBackend, CacheStats, EvictionPolicy, MemoryCache
from .core.cache_persistent import PersistentCache
from .core.client import Client
from .core.config import Config
from .core.context import AutocompleteContext, Context, InteractionContext
from .core.gateway import GatewayEvent

# Command system
from .commands import (
    Command,
    CommandContext,
    Option,
    command,
    group,
    resolve_options,
)

# Interaction components (buttons, modals, etc.)
from .interactions import (
    Button,
    Modal,
    SelectMenu,
)

# Component + Modal callback routing (new in 0.2)
from .components import (
    ButtonContext,
    ComponentContext,
    ModalContext,
    SelectContext,
)

# Public models (Pydantic)
from .models import (
    User,
    Member,
    Guild,
    Channel,
    Message,
    Attachment,
    Role,
)

# Re-export important types
from .types import (
    Intents,
    Permissions,
    ApplicationCommandType,
)

__all__ = [
    # Core
    "Client",
    "Config",
    "Context",
    "InteractionContext",
    "AutocompleteContext",
    "MemoryCache",
    "PersistentCache",
    "CacheBackend",
    "CacheStats",
    "EvictionPolicy",
    "GatewayEvent",
    # Commands
    "Command",
    "CommandContext",
    "Option",
    "command",
    "group",
    "resolve_options",
    # Static interaction builders
    "Button",
    "Modal",
    "SelectMenu",
    # Component callback routing
    "ComponentContext",
    "ButtonContext",
    "SelectContext",
    "ModalContext",
    # Models
    "User",
    "Member",
    "Guild",
    "Channel",
    "Message",
    "Attachment",
    "Role",
    # Types
    "Intents",
    "Permissions",
    "ApplicationCommandType",
    # Metadata
    "__version__",
]
