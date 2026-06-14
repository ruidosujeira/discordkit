"""
discordkit.core
===============

Core building blocks: Client, Config, Context, low-level HTTP and Gateway.
"""

from .cache import CacheBackend, CacheStats, MemoryCache  # re-export for convenience
from .client import Client
from .config import Config
from .context import AutocompleteContext, CommandContext, Context, InteractionContext
from .gateway import Gateway, GatewayEvent
from .http import DiscordHTTPClient, DiscordHTTPError

__all__ = [
    "Client",
    "Config",
    "Context",
    "InteractionContext",
    "CommandContext",
    "AutocompleteContext",
    "MemoryCache",
    "CacheBackend",
    "CacheStats",
    "Gateway",
    "GatewayEvent",
    "DiscordHTTPClient",
    "DiscordHTTPError",
]
